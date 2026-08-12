# Reproduction

Three levels, in increasing order of what they need. Every command here has been
executed before being written down.

| Level | Needs | Reproduces |
|---|---|---|
| 1. Verify | Python 3.12 | tests, validators, frozen-artefact checksums |
| 2. Re-score and re-report | Python 3.12 | every metric and report, from stored traces |
| 3. Re-run the pipeline | + torch, + API key | the model calls themselves |

**No API key is needed for levels 1 and 2.**

---

## Setup

```bash
git clone <repo> && cd rag-evaluation-lab
python -m venv .venv

# Windows
.venv/Scripts/activate
pip install -r requirements/lock/windows-py312.txt

# Linux
source .venv/bin/activate
pip install -r requirements/lock/linux-py312.txt

pip install -e . --no-deps
```

The Linux lock is hash-pinned and cross-compiled so CI never resolves dependencies
for itself. `torch` and `transformers` are deliberately **excluded** from
both locks — on PyPI's manylinux wheels `torch` is the CUDA build, which would add
roughly 2.5 GB of `nvidia-*` wheels to every CI run.
`scripts/assert_ci_env.py` fails the build if any leaks back in.

---

## Level 1 — verify

```bash
pytest                                 # 164 passed, 3 skipped
python scripts/verify_frozen.py        # all 10 frozen artefacts match
python scripts/validate_corpus.py      # 14 documents, 69 facts, invariants hold
python scripts/validate_dataset.py     # 50 cases, 79 evidence spans, all quotes resolve
rag-eval ledger                        # 2 held-out accesses, both disclosed
```

`pytest` is fully offline. `tests/conftest.py` enforces that rather than asserting
it: provider keys are deleted from the environment **and** `socket.connect` is
monkeypatched to raise, so an attempted call fails with a traceback pointing at the
offending line instead of succeeding quietly.

The three skipped tests are the MiniLM parity checks, which need the Tier-2 stack
and a model download. Run them deliberately:

```bash
pip install -r constraints/torch-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers
pytest tests/regression/test_minilm_parity.py --run-network
```

### The exact CI commands

```bash
python -m ruff format --check --diff .
python -m ruff check .
python -m mypy src/rag_eval

python scripts/assert_ci_env.py
python -m pytest tests/unit/test_pytest_plugin_guard.py -q
python scripts/validate_corpus.py
python scripts/validate_dataset.py
python -m pytest tests/unit -m unit -q
python -m pytest tests/integration -m integration -q
python -m pytest tests/regression -m regression -q
```

CI sets `RAG_EVAL_OFFLINE=1` and `RAG_EVAL_CACHE_DIR=tests/fixtures/cache`.

---

## Level 2 — re-score and re-report, no model calls

Scoring is a pure function of stored traces, so every metric and every report can
be regenerated without touching a provider.

```bash
# Regenerate the dev comparison. Byte-identical to the committed version.
rag-eval compare \
  runs/baseline-dev-20260806T180859Z-66ee099b \
  runs/improved-dev-20260806T181347Z-1e6a1bf8 \
  --out reports/dev

# The dev-only retrieval ablation (needs torch for MiniLM; see below)
python scripts/ablate_retrieval.py --out reports/ablation
```

> **Do not regenerate `reports/held-out/`.** Those artefacts are closed evidence.
> `scripts/verify_frozen.py` and `tests/unit/test_frozen_artefacts.py` will fail if
> they change. A re-issued result must be written to a **new** path as a new report
> version. See [`frozen-held-out-result.md`](frozen-held-out-result.md).

The ablation defaults to MiniLM to match the frozen arms. To run it without torch:

```bash
python scripts/ablate_retrieval.py --embedder tfidf_svd
```

That changes the numbers — `tfidf_svd` is a genuinely weaker retriever — so results
from it are not comparable with the tables in [`results.md`](results.md).

---

## Level 3 — re-run the pipeline

Needs a provider key **and** the Tier-2 stack, because both frozen arms used
MiniLM embeddings.

```bash
pip install -r constraints/torch-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu
cp .env.example .env      # add GEMINI_API_KEY
```

```bash
rag-eval ingest --config configs/baseline.yaml     # 164 chunks, pipeline_hash 66ee099bcb76
rag-eval ingest --config configs/improved.yaml     # 136 chunks, pipeline_hash 1e6a1bf838ee

rag-eval run --config configs/baseline.yaml --split dev
rag-eval run --config configs/improved.yaml --split dev
```

Every completed call is cached by content, so a re-run makes no calls for cases
already done and resumes where an interrupted run stopped. The free tier permits 5
requests/minute; the generator paces itself and honours the server's retry hint,
with a circuit breaker for daily-quota exhaustion. See
[`model-budget.md`](model-budget.md).

### The held-out split

```bash
rag-eval run --config configs/baseline.yaml --split test --final --reason "..."
```

This **requires** `--final` and a reason, and appends an entry to
`runs/.test_ledger.jsonl` that is visible to every reader and asserted by a unit
test. Do not run it. The held-out evaluation is complete and frozen; a third
access would need to be justified and disclosed.

---

## What will not reproduce byte-for-byte

- **Model text, if regenerated.** The cache replays exactly what the frozen runs
  received. Regenerating against a provider whose weights have changed — even under
  the same pinned model name — can produce different text and therefore different
  answer-side metrics.
- **Latency and timestamps.** Recorded, not reproducible. Cached calls replay the
  original latency, which is why `cache_hit_rate` is reported beside it.
- **`tfidf_svd` retrieval rankings across very different BLAS builds**, in
  principle. The offline tests are written to assert structural properties rather
  than exact rankings for this reason.

Deterministic and reproducible: chunking, corpus and dataset hashes, config and
pipeline hashes, every metric, the bootstrap intervals (seeded), and the failure
classification.
