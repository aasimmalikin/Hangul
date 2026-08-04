"""CI gate: decide whether an eval report is good enough to merge."""
from dataclasses import dataclass

@dataclass
class GateResult:
    passed: bool
    blocking_failures: list[str]
    advisory_notes: list[str]

BLOCKING = {"avg_faithfulness": 0.80, "avg_correctness": 0.80, "pass_rate": 0.80}
NOISE_MARGIN = 0.05

def evaluate_gate(report: dict, baseline: dict | None = None)->GateResult:
    blocking_failures: list[str] = []
    advisory_notes: list[str] = []
    for metric, floor in BLOCKING.items():
        value = report.get(metric, 0.0)
        if value<floor:
            blocking_failures.append(f"{metric} = {value:.2f} below floor {floor:.2f}")
        
        if baseline is not None:
            for metric in BLOCKING:
                new = report.get(metric, 0.0)
                old = baseline.get(metric, 0.0)
                drop = old - new
                if drop > NOISE_MARGIN:
                    blocking_failures.append(f"{metric} regressed {old:.2f} -> {new:.2f} (drop {drop:.2f} > noise {NOISE_MARGIN})")
                elif drop>0:
                    advisory_notes.append(f"{metric} dipped {old:.2f} -> {new:.2f} (within noise, not blocking)")
    
    return GateResult(
        passed = len(blocking_failures)==0,
        blocking_failures = blocking_failures, 
        advisory_notes = advisory_notes,
    )
