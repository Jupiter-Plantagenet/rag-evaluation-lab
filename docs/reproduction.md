# Reproduction

No API key is needed to verify frozen evidence or derive corrected-v2 reports.

## Setup

```bash
git clone https://github.com/Jupiter-Plantagenet/rag-evaluation-lab.git
cd rag-evaluation-lab
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux:   source .venv/bin/activate
pip install -r requirements/lock/windows-py312.txt  # use linux-py312.txt on Linux
pip install -e . --no-deps
```

## Verify and re-score

```bash
python scripts/verify_frozen.py
python scripts/validate_corpus.py
python scripts/validate_dataset.py
python scripts/derive_corrected_v2.py
python -m pytest -q                 # 174 passed, 3 skipped
python -m ruff format --check --diff .
python -m ruff check .
python -m mypy src/rag_eval
```

The frozen experimental outputs can be re-scored from committed traces without
provider access. CI integration tests use deterministic scripted responses and do
not replay the original provider calls.

The original `reports/held-out/` artefacts are closed evidence. Do not regenerate
or overwrite them; `scripts/verify_frozen.py` checks all ten frozen artefacts.

## Optional provider execution

Provider execution requires the optional embedding dependencies and a provider
key. It can produce new outputs because no committed response cache reproduces
the historical provider calls. The documented held-out run path requires explicit
`--final` authorization and records access in `runs/.test_ledger.jsonl`; do not
use it for this frozen experiment.
