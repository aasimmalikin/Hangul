# agentic-qa

A production-grade harness for a document-grounded QA agent: a retrieve, draft, self-score, re-draft, escalate loop with an LLM-as-judge eval suite, permission-tiered tools, human-in-the-loop approval for destructive actions, and a one-command container deploy. Built for engineers who want to see how an agent is wired end to end, not just called through a framework.

![build](https://img.shields.io/badge/build-passing-brightgreen)
![evals](https://img.shields.io/badge/evals-95%25%20correctness%20%7C%2096%25%20faithfulness-blue)
![python](https://img.shields.io/badge/python-3.12-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## What it is

`agentic-qa` answers questions from documents you give it. Under the hood it runs a real agentic loop: the model picks a tool, calls it, reads the result, and loops until it can answer, with a self-scoring pass that re-drafts weak answers and escalates when it still cannot ground a claim. It is deliberately built from first principles (pure Python, the provider SDK, and MCP) rather than an agent framework, so every part of the control flow is visible and modifiable.

It exists to be read and forked. If you are learning how to build an agent that is safe, measurable, and deployable, this is a complete worked example: retrieval, tool dispatch, a policy layer, budget enforcement, checkpointing, observability, an eval gate, and a container that runs the whole thing.

## Features

- **Agentic loop with self-scoring.** Retrieve, draft, score for faithfulness, re-draft, and escalate when a claim cannot be grounded, rather than answering in a single shot.
- **Per-session RAG.** Upload documents per session; answers are grounded in the caller's own uploads, isolated from other sessions.
- **Documents-only mode.** A toggle that restricts the agent to uploaded documents and provably refuses to answer from outside them.
- **Permission-tiered tools.** Every tool is classified SAFE, SENSITIVE, DESTRUCTIVE, or DENIED, with a policy layer that decides what runs automatically.
- **Human-in-the-loop approval.** Destructive filesystem actions pause and wait for an explicit approve or reject before executing, using a durable propose-then-commit checkpoint.
- **Structural session isolation.** Filesystem tools are wrapped so every path is forced into the session's own sandbox; a session cannot read or write another's files.
- **Budget enforcement.** Hard caps on steps and tokens so a run cannot loop away.
- **Real eval suite.** A 25-case golden set (factual, multi-step reasoning, and hallucination traps) scored by an LLM-as-judge for correctness and faithfulness, with a CI gate that blocks regressions.
- **Observability.** Every run is traced with per-step timing, tokens, and cost, exposed over `/metrics` and `/traces`.
- **One-command deploy.** A multi-stage Docker image plus Terraform to stand up the whole thing on AWS.

## Architecture

```
                 Streamlit UI  (chat, approval gate, docs-only toggle)
                        |
                     FastAPI  (/ask, /approve, /upload, /quality, /metrics, /traces)
                        |
        +---------------+----------------+
        |               |                |
   Agent loop      Policy layer     Observability
  (retrieve →     (tier + budget     (traces, cost,
   draft →         + approval)        metrics)
   self-score →         |
   re-draft →      Tool registry
   escalate)       ├── calculator
        |          ├── search_docs (per-session RAG)
   Checkpoint      ├── web_search (Tavily)
   store           └── filesystem (MCP, sandboxed)
```

The loop, the policy layer, and the tool registry are the three pieces worth reading first. Everything else supports them.

## Quick start

### Prerequisites

- Python 3.12
- Node.js (the filesystem tools run via the MCP filesystem server, a Node package)
- An OpenAI API key, and a Tavily API key for web search

### Install

```bash
git clone https://github.com/aasimmalikin/agentic-qa.git
cd agentic-qa
python -m venv .venv && source .venv/bin/activate
pip install .
```

### Configure

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

### Build the document index

```bash
python src/harness/retrieval/ingest.py docs
```

### Run it

The API and the UI run as two processes.

```bash
# terminal 1 — the API
uvicorn harness.api.app:app --reload

# terminal 2 — the UI
streamlit run streamlit_app.py
```

Open the Streamlit URL it prints, upload a document, and ask a question.

## Usage

Ask the API directly:

```bash
curl -s -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -H 'X-Session-ID: demo' \
  -d '{"question":"What was the total revenue?"}' | python3 -m json.tool
```

Restrict the agent to uploaded documents only:

```bash
curl -s -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -H 'X-Session-ID: demo' \
  -d '{"question":"What was the total revenue?","docs_only":true}' | python3 -m json.tool
```

A destructive action (writing a file) returns `stopped_reason: "pending_approval"` and a `pending_tool`. Approve it in a second request:

```bash
curl -s -X POST http://localhost:8000/approve \
  -H 'Content-Type: application/json' \
  -H 'X-Session-ID: demo' \
  -d '{"approval_id":"<run_id>","decision":"approve"}' | python3 -m json.tool
```

Every response carries the showcase fields that make the agent's work legible: `tools_used`, `steps`, `cost_usd`, `budget_used`, and `pending_tool`.

## Evaluation

The agent is measured, not assumed. `run_evals.py` runs a 25-case golden set through the agent and scores each answer with an LLM-as-judge for correctness (does it match the reference) and faithfulness (is every claim grounded in the retrieved context).

```bash
python run_evals.py
```

Current results on the golden set: **95% correctness, 96% faithfulness, 96% pass rate**, with **100% faithfulness on the hallucination-trap cases** (questions whose answers are not in the documents, where the correct behavior is to refuse).

The eval earned its place. An earlier run scored 65% and surfaced a real tool-choice bug: the agent preferred web search over the user's uploaded documents for factual questions. Restricting the eval to a document-grounded tool set both fixed the score and documented the failure. The two remaining sub-100 cases are judge artifacts, not agent errors (a computed answer flagged as unfaithful because the number is not verbatim in the source, and one strict reference match), which is itself a useful reminder that an LLM judge has failure modes.

A CI gate (`ci_gate.py`) enforces 0.80 floors on correctness, faithfulness, and pass rate, and blocks regressions against a saved baseline.

## Deployment

The whole system ships as a single container and deploys to AWS with Terraform.

```bash
# build and run locally
docker build -t agentic-qa .
docker run --rm -p 8000:8000 -p 8501:8501 \
  -e OPENAI_API_KEY="..." -e TAVILY_API_KEY="..." agentic-qa

# deploy to AWS (EC2 + security group + IAM role, pulling from ECR)
cd infra/terraform
terraform init
terraform plan
terraform apply
```

The container is a multi-stage build on `python:3.12-slim`, runs as a non-root user, includes a health check, and installs Node for the MCP filesystem server. The Terraform stands up a single EC2 instance that pulls the image from ECR via an IAM role and runs it, with SSH locked to your IP and the UI exposed publicly.

This is deliberately a single-instance demo. The production path is documented rather than built: split the API and UI into separate containers, move the vector store to pgvector and the cache to Redis, put an Application Load Balancer with a TLS certificate in front for HTTPS, and pull secrets from a secrets manager instead of environment variables. See [docs/PRODUCTION.md](docs/PRODUCTION.md) for the full scaling ladder.

## Project layout

```
src/harness/
  agent/        the loop, checkpointing
  api/          FastAPI routes (ask, approve, upload, quality, ...)
  tools/        tool registry and builtin tools
  retrieval/    chunking, embeddings, vector stores, ingest
  eval/         dataset, graders, judge, runner, CI gate
  policy/       permission tiers and budget
  obs/          tracing and metrics
  prompts/      versioned prompt templates
streamlit_app.py  the demo UI
run_evals.py      the eval entry point
infra/terraform/  the AWS deployment
Dockerfile        the container
```

## What this is not

Honest scope so you know what you are forking. This is a reference harness and a portfolio-grade demo, not a hardened multi-tenant service. The session store is in-memory (it resets on restart), the cache is in-memory, secrets are passed as environment variables, and the demo runs one instance over HTTP. Every one of these has a documented production upgrade in `docs/PRODUCTION.md`. The value here is a complete, readable, correct implementation of the hard parts (the loop, the policy layer, the eval methodology, the deploy), not a drop-in production system.

## Contributing

Contributions are welcome. Good first areas: additional builtin tools, alternative vector-store backends, more eval cases, or the production upgrades listed above. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up a dev environment, run the tests and evals, and open a pull request. In short: fork, branch, make sure `python run_evals.py` still clears the CI gate, and open a PR describing the change.

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgements

Built on the [Model Context Protocol](https://modelcontextprotocol.io) for tool integration, the OpenAI API for generation and judging, and [Tavily](https://tavily.com) for web search. The human-in-the-loop design draws on the propose-then-commit pattern common to durable-execution and agent frameworks.
