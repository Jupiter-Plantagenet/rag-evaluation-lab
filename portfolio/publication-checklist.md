# Publication checklist

Run before anything leaves this machine. Every row below was actually executed on
the current tree, not asserted.

**Nothing has been published.** No remote, no push, no deployment, no Upwork
change, no social post, no landing page, no outreach.

| # | Check | Result |
|---|---|---|
| 1 | README status current | **PASS** — reads "verification and portfolio packaging complete; publication pending GitHub CI" |
| 2 | Claims match `docs/results.md` | **PASS** — see [claim trace](#claim-trace) |
| 3 | No frozen artefact changed | **PASS** — 10/10 checksums match; `git diff f4ac2b1 HEAD` over frozen paths is empty |
| 4 | No secret committed | **PASS with one note** — see [secret scan](#secret-scan) |
| 5 | No absolute local paths | **PASS after fix** — one found and redacted |
| 6 | No private information | **PASS** — only the author's own public GitHub handle |
| 7 | Synthetic corpus labelled | **PASS** — front matter, README, case study, and visual 1 |
| 8 | LICENSE correct | **PASS** — MIT (code) + CC BY 4.0 (corpus) |
| 9 | CITATION.cff correct | **PASS after fix** — abstract rewritten; `date-released` removed |
| 10 | Links relative and valid | **PASS** — every internal link in README, `docs/` and `portfolio/` resolves |
| 11 | Images readable | **PASS** — 4 × 1600×1200 (4:3), 163–280 KB PNG, layout guard clean |
| 12 | Upwork copy truthful | **PASS** — every claim traceable; character counts verified |
| 13 | No production claim | **PASS** — "not production-ready" stated in README, case study and limitations |
| 14 | No client-work claim | **PASS** — "self-directed research-engineering case study" throughout |
| 15 | No significance / SOTA terminology | **PASS** — appears only inside prohibition lists |
| 16 | No misleading bare percentage | **PASS** — no "improved X by N%" anywhere |
| 17 | CITATION.cff describes only implemented functionality | **PASS after fix** — see [correction pass](#correction-pass) |
| 18 | No unused declared dependency | **PASS after fix** — `faiss-cpu` removed |
| 19 | Environment comments match the published setup | **PASS after fix** — 6 files corrected |

---

## Correction pass

An independent review of `d540134` found claim/documentation inconsistencies.
All were fixed in one bounded pass; no frozen artefact, corpus byte, dataset byte,
experiment output or pipeline configuration was touched.

| Finding | Fix |
|---|---|
| `CITATION.cff` claimed the harness "keeps deterministic metrics apart from model-assisted ones and publishes grader-agreement figures for the latter" | Abstract rewritten to describe only implemented functionality, and now states explicitly that model-assisted grading is **not** implemented and that citation metrics establish resolution rather than entailment |
| `CITATION.cff` carried `date-released: "2026-08-06"` — the experiment date, for a release that has not happened | Field removed. CFF 1.2.0 makes it optional; it should be set when a release actually occurs |
| `faiss-cpu` was declared in `[project.optional-dependencies].local`, `constraints/torch-cpu.txt` and a mypy override, but no source, test or reproduction command imports it — the dense retriever is exact cosine search over a NumPy matrix | Removed from all three, plus the vestigial `*.faiss` patterns in `.gitignore`/`.gitattributes` and the stale mentions in `README.md`, `docs/reproduction.md` and the CI workflow comment. Kept in `assert_ci_env.py`'s forbidden list as a regression guard, with a comment saying why |
| Six files described a `--system-site-packages` / inherited-Anaconda environment that the published setup (`python -m venv .venv`) does not use | Comments corrected in `pyproject.toml` (×2), `constraints/torch-cpu.txt`, `requirements/core.in`, `scripts/assert_ci_env.py`, `tests/unit/test_pytest_plugin_guard.py`. The pytest `-p no:` blocks were **kept** as defensive compatibility guards and are now documented as inert in a clean environment |
| The Upwork description said a measured difference "is attributable to the change rather than to two different programs" — stronger than the experiment supports | Replaced with "measured differences can be traced to explicit configuration changes without code-path drift". The same construction in `docs/evaluation-methodology.md` was softened for consistency |
| The recommended Upwork title led with "Grounding", which implies claim-to-evidence entailment | Changed to **RAG Evaluation Lab: Retrieval, Citations & Regression Testing**. The repository keeps its scientific title, where the surrounding documentation defines the term |

The FAISS mention that remains in `portfolio/upwork-portfolio-copy.md` is in the
explicit *"not used, and therefore not listed"* line, which is accurate and
worth keeping. The mentions in `docs/source-project-audit.md` describe the
**predecessor** project, which genuinely used LangChain and FAISS.

### Re-checked after the corrections

Nine claim categories were re-scanned across every tracked Markdown, TOML, YAML,
Python and requirements file: model-assisted grading, grader agreement, FAISS,
system-site-packages, Anaconda inheritance, production readiness, client-work
wording, CI status, and semantic entailment.

Twenty-one raw hits, **zero contradictions** — every one is a negation ("not
production-ready", "Not client work"), a prohibition-list entry, or an accurate
statement about the audited predecessor project.

---

## Secret scan

Scanned **all 281 objects across every ref** in git history, not just the working
tree:

```bash
git grep -InE "AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{20,}|sk_live_[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-|-----BEGIN" $(git rev-list --all)
git log --all -S "<each live value from .env>"
```

**The live `GEMINI_API_KEY` does not appear in any commit, on any ref.** `.env` has
been gitignored since the first commit and was never tracked.

One match, and it is not a secret:

| Match | Location | Assessment |
|---|---|---|
| `sk_live_4f8a2c9e1b7d3506` | `data/corpus/novapay/api-authentication.md:40` | **Synthetic.** An invented example token inside the fictional NovaPay API documentation, in a file whose front matter declares `synthetic: true` with a disclaimer. NovaPay does not exist and there is no service for it to authenticate against. |

**Action before publishing to GitHub:** this string is *key-shaped*, so GitHub
secret scanning and tools like trufflehog will flag it. It is harmless, but expect
an alert and be ready to dismiss it as a documented false positive. Defanging it
(e.g. `sk_live_EXAMPLE_NOT_A_REAL_KEY`) would change the corpus bytes, which are
hashed into `corpus_manifest_sha` and therefore into every frozen artefact — so it
**must not** be changed while the held-out result stands.

One further match was a false positive of the scanner itself:
`BRAINTRUST_PROJECT=rag-evaluation-lab` is the repository name, not a credential.

## Absolute local paths

One found and fixed:

| File | Was | Now |
|---|---|---|
| `docs/source-project-audit.md:18` | `C:\Users\akorg\CascadeProjects\resume\projects\llm-support-agent` | `local working copy (absolute path redacted for publication)` |

It leaked both a filesystem layout and the local username. Re-scanned after the
fix: no absolute Windows or POSIX home paths remain in any tracked text file.

## Private information

The only personal identifiers are the author's own, and are intentional:

- `George Akor` in `LICENSE` and `CITATION.cff` — a copyright and citation record.
- `Jupiter-Plantagenet` in `CITATION.cff` and the JSON-Schema `$id` — the author's
  public GitHub handle.

No email addresses, no machine hostnames, no third-party names. The `host` field in
`runs/.test_ledger.jsonl` records `Jupiter`, which is a machine name, not a person
— it is part of a frozen artefact and cannot be edited.

## Claim trace

Each public number, and the file that must agree with it:

| Claim | Source of truth |
|---|---|
| MRR 0.667 → 0.835, CI [+0.008, +0.339] | `reports/held-out/comparison.json` |
| recall@10 0.692 → 0.883, CI [+0.025, +0.375] | `reports/held-out/comparison.json` |
| matched-budget MRR +0.150 [−0.017, +0.321] | `docs/statistical-audit.md` A-13 |
| matched-budget recall@4 +0.058 [−0.067, +0.200] | `docs/statistical-audit.md` A-13 |
| 10 of 12 metrics no measurable difference | `docs/results.md` |
| non-authoritative citations 4 → 7 | `reports/held-out/comparison.json` |
| forbidden claims 6 → 6, fabricated 0 → 0 | `reports/held-out/comparison.json` |
| ablation MRR 0.435 / 0.574 / 0.399 / 0.565 | `reports/ablation/dev-retrieval-ablation.json` |
| 22 held-out cases, 20 retrieval-evaluable | `docs/frozen-held-out-result.md` |
| 164 tests passed, 3 skipped | `pytest` on the current tree |

`scripts/make_portfolio_visuals.py` re-reads the two JSON reports on every run and
**fails** if any plotted value has drifted, so the figures cannot silently
disagree with the evidence.

## Wording rules applied

Present in the copy:

- "the improved retrieval configuration" (a bundle), never a single named component
- "the paired-bootstrap 95% CI excluded zero"
- "development split — explanatory, not held-out evidence" on every ablation number
- "context/retrieval-budget comparison" for recall@10
- "not false — confounded by the retrieval budget"

Absent from every claim (they appear only in prohibition lists):

- "statistically significant", "state-of-the-art", "production-ready",
  "enterprise-grade", "battle-tested"
- "the improved system ranks better"
- "BM25 / hybrid retrieval / structure-aware chunking caused the held-out improvement"
- any bare "improved by N%"

## Remaining blockers to publication

| Blocker | Owner decision |
|---|---|
| No GitHub remote exists | Create one when ready |
| No GitHub Actions run has been observed | No CI badge or "CI green" claim until one has |
| The synthetic `sk_live_…` string will trip secret scanners | Expect the alert; dismiss as documented above. Do **not** edit the corpus. |
| Nothing has been reviewed by a second person | Optional, but the strongest remaining check |

None of these is a defect in the work. They are the difference between *ready to
publish* and *published*.

## Re-run this checklist

```bash
python scripts/verify_frozen.py
python scripts/validate_corpus.py
python scripts/validate_dataset.py
python -m pytest -q
python scripts/make_portfolio_visuals.py     # fails if a figure drifts from the reports
git grep -InE "AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}" $(git rev-list --all)
```
