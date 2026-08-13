#!/usr/bin/env python3
"""Calibrate the faithfulness AND correctness LLM-as-judges against human-labeled
golden sets, computing TPR, TNR, precision, accuracy, and Cohen's kappa.

Golden-set design follows 2026 LLM-eval guidance:
  - covers NORMAL, EDGE, and KNOWN-HARD cases (not just blatant ones), because a
    judge can score high on easy cases while missing the subtle failures that
    matter; hard cases are where judges actually break.
  - stratified by difficulty (clear / subtle / borderline) so the resulting
    kappa is realistic and defensible, not inflated by trivial examples.
  - correctness matches on KEY FACTS, not verbatim wording (paraphrase should
    still score correct; the hard cases test whether the judge handles this).
  - both classes represented ~50/50 so TNR (catching the failure) is meaningful.
  - Cohen's kappa reported (chance-adjusted; harder to game than raw accuracy).

Your judges (grade_faithfulness / grade_correctness) return a CONTINUOUS score
0.0-1.0; this converts to binary via a threshold and SWEEPS thresholds to find
the best-agreement cutoff.

Usage:
    python3 judge_calibration.py
"""
import asyncio


# ---- wiring to your project ----------------------------------------------
def build_judge():
    from harness.eval.openai_judge import OpenAIJudge
    return OpenAIJudge(model="gpt-4o")

async def score_faithfulness(judge, answer, context):
    from harness.eval.graders import grade_faithfulness
    return await grade_faithfulness(judge, answer=answer, context=context)

async def score_correctness(judge, question, answer, reference):
    from harness.eval.graders import grade_correctness
    return await grade_correctness(judge, question=question, answer=answer, reference=reference)
# ---------------------------------------------------------------------------


# ==========================================================================
# FAITHFULNESS GOLDEN SET (answer vs context). label: faithful / unfaithful
# Stratified: clear, subtle, borderline. The subtle/borderline UNFAITHFUL ones
# are the real test -- plausible answers with one unsupported claim, over-
# generalisations, or added specifics not in the context.
# ==========================================================================
FAITH = [
    # ---- CLEAR FAITHFUL ----
    {"id":"f01","difficulty":"clear","context":"Nimbus Analytics reported total revenue of $82M in fiscal 2025.",
     "answer":"Nimbus Analytics had $82M in total revenue in fiscal 2025.","label":"faithful"},
    {"id":"f02","difficulty":"clear","context":"The API rate limit is 100 requests per minute per API key.",
     "answer":"Each API key is limited to 100 requests per minute.","label":"faithful"},
    {"id":"f03","difficulty":"clear","context":"Data is encrypted at rest using AES-256.",
     "answer":"They use AES-256 encryption for data at rest.","label":"faithful"},
    {"id":"f04","difficulty":"clear","context":"Support is available Monday through Friday, 9am to 6pm EST.",
     "answer":"Support hours are weekdays 9am-6pm EST.","label":"faithful"},
    {"id":"f05","difficulty":"clear","context":"The platform supports SSO via SAML 2.0 and OIDC.",
     "answer":"SSO is supported through SAML 2.0 and OIDC.","label":"faithful"},
    # ---- SUBTLE FAITHFUL (correct but reworded / inferred within support) ----
    {"id":"f06","difficulty":"subtle","context":"The free tier includes up to 5 users and 10GB of storage. Paid tiers start at $20/user/month.",
     "answer":"You can use the product with as many as 5 people for free before paying.","label":"faithful"},
    {"id":"f07","difficulty":"subtle","context":"Backups run nightly and are retained for 30 days. Restores can be requested via support.",
     "answer":"If you lose data, you could recover it from a backup taken within the last month.","label":"faithful"},
    {"id":"f08","difficulty":"subtle","context":"The SLA guarantees 99.9% uptime, measured monthly, excluding scheduled maintenance.",
     "answer":"They promise 99.9% uptime per month, though planned maintenance windows don't count against it.","label":"faithful"},
    {"id":"f09","difficulty":"subtle","context":"Enterprise customers get a dedicated account manager and a 4-hour support SLA.",
     "answer":"Enterprise plans come with a named account manager and faster support response.","label":"faithful"},
    {"id":"f10","difficulty":"subtle","context":"Q3 net income rose 12% year over year to $14.2M, driven mainly by enterprise renewals.",
     "answer":"Enterprise renewals were the main driver behind the 12% YoY rise in Q3 net income.","label":"faithful"},
    # ---- BORDERLINE FAITHFUL (mostly supported, phrasing tests the judge) ----
    {"id":"f11","difficulty":"borderline","context":"The trial period lasts 14 days. No credit card is required to start.",
     "answer":"There's a two-week free trial you can begin without entering payment details.","label":"faithful"},
    {"id":"f12","difficulty":"borderline","context":"Integrations include Slack, Salesforce, and Jira via native connectors.",
     "answer":"It connects natively to Slack, Salesforce, and Jira.","label":"faithful"},
    {"id":"f13","difficulty":"borderline","context":"The audit log retains events for 90 days on the Pro plan; Enterprise retains for 1 year.",
     "answer":"Pro keeps audit events for 90 days, and Enterprise keeps them considerably longer.","label":"faithful"},

    # ---- CLEAR UNFAITHFUL (blatant contradiction) ----
    {"id":"u01","difficulty":"clear","context":"Nimbus Analytics reported total revenue of $82M in fiscal 2025.",
     "answer":"Nimbus Analytics had $120M in total revenue in fiscal 2025.","label":"unfaithful"},
    {"id":"u02","difficulty":"clear","context":"The company's headquarters is located in Austin, Texas.",
     "answer":"Nimbus is headquartered in Boston, Massachusetts.","label":"unfaithful"},
    {"id":"u03","difficulty":"clear","context":"The API rate limit is 100 requests per minute per API key.",
     "answer":"The API allows 1,000 requests per minute per key.","label":"unfaithful"},
    {"id":"u04","difficulty":"clear","context":"The SLA guarantees 99.9% uptime.",
     "answer":"The SLA guarantees 100% uptime with zero downtime.","label":"unfaithful"},
    {"id":"u05","difficulty":"clear","context":"Support is available Monday through Friday, 9am to 6pm EST.",
     "answer":"Support is available 24/7 including weekends and holidays.","label":"unfaithful"},
    # ---- SUBTLE UNFAITHFUL (plausible, ONE unsupported claim / added specific) ----
    {"id":"u06","difficulty":"subtle","context":"Data is encrypted at rest using AES-256.",
     "answer":"Data is encrypted at rest using AES-256, and all traffic uses TLS 1.3.","label":"unfaithful"},
    {"id":"u07","difficulty":"subtle","context":"The free tier includes up to 5 users and 10GB of storage.",
     "answer":"The free tier includes up to 5 users, 10GB of storage, and unlimited API calls.","label":"unfaithful"},
    {"id":"u08","difficulty":"subtle","context":"Backups run nightly and are retained for 30 days.",
     "answer":"Backups run nightly, are retained for 30 days, and are stored in three geographic regions.","label":"unfaithful"},
    {"id":"u09","difficulty":"subtle","context":"The platform supports SSO via SAML 2.0 and OIDC.",
     "answer":"The platform supports SSO via SAML 2.0 and OIDC, with SCIM provisioning included.","label":"unfaithful"},
    {"id":"u10","difficulty":"subtle","context":"Enterprise customers get a dedicated account manager.",
     "answer":"Enterprise customers get a dedicated account manager available around the clock.","label":"unfaithful"},
    # ---- BORDERLINE UNFAITHFUL (over-generalisation / unsupported inference) ----
    {"id":"u11","difficulty":"borderline","context":"Q3 net income rose 12% year over year to $14.2M.",
     "answer":"Net income has been rising 12% every quarter this year, reaching $14.2M in Q3.","label":"unfaithful"},
    {"id":"u12","difficulty":"borderline","context":"The trial period lasts 14 days with no credit card required.",
     "answer":"The 14-day trial requires no credit card, and it auto-converts to the paid plan afterward.","label":"unfaithful"},
    {"id":"u13","difficulty":"borderline","context":"Integrations include Slack, Salesforce, and Jira.",
     "answer":"It integrates with all major tools, including Slack, Salesforce, Jira, and Microsoft Teams.","label":"unfaithful"},
]

# ==========================================================================
# CORRECTNESS GOLDEN SET (answer vs reference, given question).
# label: correct / incorrect.  Matches on KEY FACTS, not verbatim wording.
# Stratified: clear, subtle (paraphrase / partial), borderline.
# ==========================================================================
CORR = [
    # ---- CLEAR CORRECT ----
    {"id":"c01","difficulty":"clear","question":"What is the capital of France?",
     "reference":"Paris","answer":"The capital of France is Paris.","label":"correct"},
    {"id":"c02","difficulty":"clear","question":"How many days are in a leap year?",
     "reference":"366 days","answer":"A leap year has 366 days.","label":"correct"},
    {"id":"c03","difficulty":"clear","question":"What is Nimbus's fiscal 2025 revenue?",
     "reference":"$82 million","answer":"Nimbus reported $82M in revenue for fiscal 2025.","label":"correct"},
    {"id":"c04","difficulty":"clear","question":"What encryption is used at rest?",
     "reference":"AES-256","answer":"Data at rest is encrypted with AES-256.","label":"correct"},
    # ---- SUBTLE CORRECT (paraphrased / different wording, same key fact) ----
    {"id":"c05","difficulty":"subtle","question":"What is the API rate limit?",
     "reference":"100 requests per minute per API key",
     "answer":"Each key can make up to 6,000 requests an hour.","label":"correct"},  # 100/min = 6000/hr
    {"id":"c06","difficulty":"subtle","question":"When was the company founded?",
     "reference":"2019","answer":"The company has been operating since 2019.","label":"correct"},
    {"id":"c07","difficulty":"subtle","question":"What is the free tier user limit?",
     "reference":"5 users","answer":"Up to five people can use the free plan.","label":"correct"},
    {"id":"c08","difficulty":"subtle","question":"What is the uptime guarantee?",
     "reference":"99.9% uptime","answer":"They guarantee three-nines availability.","label":"correct"},
    # ---- BORDERLINE CORRECT (correct core, extra harmless detail) ----
    {"id":"c09","difficulty":"borderline","question":"What is the backup retention period?",
     "reference":"30 days","answer":"Backups are kept for 30 days, taken nightly.","label":"correct"},
    {"id":"c10","difficulty":"borderline","question":"Which integrations are supported?",
     "reference":"Slack, Salesforce, and Jira","answer":"Slack, Salesforce, and Jira are supported.","label":"correct"},

    # ---- CLEAR INCORRECT ----
    {"id":"x01","difficulty":"clear","question":"What is the capital of France?",
     "reference":"Paris","answer":"The capital of France is Lyon.","label":"incorrect"},
    {"id":"x02","difficulty":"clear","question":"What is Nimbus's fiscal 2025 revenue?",
     "reference":"$82 million","answer":"Nimbus reported $120M in revenue.","label":"incorrect"},
    {"id":"x03","difficulty":"clear","question":"What encryption is used at rest?",
     "reference":"AES-256","answer":"Data at rest is encrypted with RSA-2048.","label":"incorrect"},
    {"id":"x04","difficulty":"clear","question":"What is the uptime guarantee?",
     "reference":"99.9% uptime","answer":"They guarantee 95% uptime.","label":"incorrect"},
    # ---- SUBTLE INCORRECT (close but wrong on the key fact) ----
    {"id":"x05","difficulty":"subtle","question":"What is the API rate limit?",
     "reference":"100 requests per minute per API key",
     "answer":"Each key can make up to 100 requests per hour.","label":"incorrect"},  # per hour, not minute
    {"id":"x06","difficulty":"subtle","question":"What is the free tier user limit?",
     "reference":"5 users","answer":"The free plan supports up to 15 users.","label":"incorrect"},
    {"id":"x07","difficulty":"subtle","question":"What is the backup retention period?",
     "reference":"30 days","answer":"Backups are retained for 13 days.","label":"incorrect"},
    {"id":"x08","difficulty":"subtle","question":"When was the company founded?",
     "reference":"2019","answer":"The company was founded in 2009.","label":"incorrect"},
    # ---- BORDERLINE INCORRECT (partially right, misses/contradicts key part) ----
    {"id":"x09","difficulty":"borderline","question":"Which integrations are supported?",
     "reference":"Slack, Salesforce, and Jira","answer":"It supports Slack and Microsoft Teams.","label":"incorrect"},
    {"id":"x10","difficulty":"borderline","question":"What is the trial period and its terms?",
     "reference":"14 days, no credit card required","answer":"There's a 30-day trial requiring a credit card.","label":"incorrect"},
]


def cohens_kappa(tp, tn, fp, fn):
    n = tp + tn + fp + fn
    if n == 0: return 0.0
    po = (tp + tn) / n
    p_yes_h = (tp + fn) / n
    p_yes_j = (tp + fp) / n
    pe = p_yes_h * p_yes_j + (1 - p_yes_h) * (1 - p_yes_j)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def metrics_at(scored, threshold, pos_label):
    # scored: list of (human_label, float_score); pos_label = "faithful"/"correct"
    tp = tn = fp = fn = 0
    for human, score in scored:
        judge_pos = score >= threshold
        human_pos = (human == pos_label)
        if human_pos and judge_pos: tp += 1
        elif (not human_pos) and (not judge_pos): tn += 1
        elif (not human_pos) and judge_pos: fp += 1
        else: fn += 1
    tpr = tp/(tp+fn) if (tp+fn) else 0
    tnr = tn/(tn+fp) if (tn+fp) else 0
    prec = tp/(tp+fp) if (tp+fp) else 0
    acc = (tp+tn)/len(scored) if scored else 0
    return dict(tp=tp,tn=tn,fp=fp,fn=fn,tpr=tpr,tnr=tnr,precision=prec,
               accuracy=acc,kappa=cohens_kappa(tp,tn,fp,fn))


def report(name, scored, pos_label, neg_label):
    print("\n" + "=" * 62)
    print(f"{name.upper()} JUDGE CALIBRATION")
    print("=" * 62)
    n_pos = sum(1 for h,_ in scored if h == pos_label)
    print(f"  Golden set: {len(scored)} items "
          f"({n_pos} {pos_label} / {len(scored)-n_pos} {neg_label})")
    print(f"{'t':>5} | {'TPR':>5} | {'TNR':>5} | {'prec':>5} | {'acc':>5} | {'kappa':>6}")
    print("-" * 62)
    best = None
    for t in [0.3,0.4,0.5,0.6,0.7,0.8]:
        m = metrics_at(scored, t, pos_label)
        print(f"{t:>5.1f} | {m['tpr']:>5.2f} | {m['tnr']:>5.2f} | "
              f"{m['precision']:>5.2f} | {m['accuracy']:>5.2f} | {m['kappa']:>6.3f}")
        if best is None or m['kappa'] > best[1]['kappa']:
            best = (t, m)
    bt, bm = best
    print("-" * 62)
    print(f"  BEST THRESHOLD {bt}:  TPR {bm['tpr']:.2f}  "
          f"TNR {bm['tnr']:.2f} (catches {neg_label})  "
          f"kappa {bm['kappa']:.3f}")
    verdict = "PASS" if bm['kappa'] >= 0.60 and bm['tnr'] >= 0.80 else "NEEDS WORK"
    print(f"  Verdict: {verdict}")
    return bt, bm


async def run():
    judge = build_judge()

    # ---- faithfulness ----
    print("Scoring FAITHFULNESS golden set...")
    faith_scored = []
    for it in FAITH:
        s, _ = await score_faithfulness(judge, it["answer"], it["context"])
        faith_scored.append((it["label"], float(s)))
        print(f"  {it['id']} [{it['difficulty']:>10}] score={float(s):.2f} (human={it['label']})")

    # ---- correctness ----
    print("\nScoring CORRECTNESS golden set...")
    corr_scored = []
    for it in CORR:
        s, _ = await score_correctness(judge, it["question"], it["answer"], it["reference"])
        corr_scored.append((it["label"], float(s)))
        print(f"  {it['id']} [{it['difficulty']:>10}] score={float(s):.2f} (human={it['label']})")

    fb = report("faithfulness", faith_scored, "faithful", "unfaithful")
    cb = report("correctness", corr_scored, "correct", "incorrect")

    print("\n" + "=" * 62)
    print("RESUME LINE")
    print("=" * 62)
    print(f'  "Calibrated faithfulness and correctness LLM-as-judges against '
          f'stratified golden sets (clear/subtle/borderline cases): '
          f'faithfulness TNR {fb[1]["tnr"]:.2f} / kappa {fb[1]["kappa"]:.2f}, '
          f'correctness TNR {cb[1]["tnr"]:.2f} / kappa {cb[1]["kappa"]:.2f}."')


if __name__ == "__main__":
    asyncio.run(run())