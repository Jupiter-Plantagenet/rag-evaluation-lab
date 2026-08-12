# Source-project audit: `llm-support-agent`

**Audited:** 2026-08-06 · **Auditor:** George Akor · **Method:** full read of every tracked file, plus
`git log`/`git ls-files` inspection, binary inspection of the FAISS index header, and static reading
of the test and CI configuration. No file in the audited repository was modified.

**Purpose.** This audit determined what to reuse when building `rag-evaluation-lab`. It is a
record of a starting point, not a criticism of a finished product. The audited repository is a
self-directed demo built in two days; it was never presented as production software and is not
assessed as such here.

---

## 1. Identity and provenance

| Item | Value |
|---|---|
| Path | local working copy (absolute path redacted for publication) |
| Remote | `https://github.com/Jupiter-Plantagenet/llm-support-agent.git` |
| Branch | `main` (only local branch), working tree clean |
| Commits | 4, all 2026-04-01 → 2026-04-02 |
| Tracked files | 21 |

```
d648244 Clean up source display: extract section titles, show as pills
b5f05d8 Add chat UI at root, enable Gemini RAG on Render
b78bf61 Add root redirect to /docs Swagger UI
fa94c3e Initial commit: LangChain RAG agent with Gemini, FAISS, FastAPI
```

The initial commit added all 21 files (911 insertions); the three follow-ups touched only
`app/main.py` and `app/agent.py`.

**Broken submodule wiring.** The parent repo (`resume`) records `projects/llm-support-agent` as a
gitlink (mode `160000`, SHA `d648244`) but **has no `.gitmodules` file**, so
`git submodule status` fails with `no submodule mapping found`. A recursive clone of `resume`
yields an empty directory. The recorded SHA does match the nested repo's HEAD, so the pointer is at
least current.

---

## 2. Architecture

Five modules under `app/`, plus one orphan.

| Module | Responsibility |
|---|---|
| `config.py` | `Settings(BaseSettings)`, env-file backed; module-level `settings` singleton |
| `models.py` | Five Pydantic request/response models |
| `vectorstore.py` | `VectorStoreManager`: build/load/persist the FAISS store |
| `agent.py` | `DemoAgent` (canned) and `SupportAgent` (LCEL chain), plus a module-level rate limiter |
| `main.py` | FastAPI app, 4 routes, and a 178-line inline HTML/JS chat UI |
| `mlflow_config.py` | **Orphan** — imported by nothing |

**Request flow (live mode):**

```
POST /chat {query}
  → chat_endpoint (main.py:251) → agent.answer(query)      (agent.py:106)
      → _rate_limit()                  # blocking sleep, up to 4.1 s
      → _get_chain()                   # builds the LCEL chain lazily
      → self._retriever.invoke(query)  # RETRIEVAL PASS 1 -- for source labels
      → label extraction loop          (agent.py:112-136)
      → chain.invoke(query)            # RETRIEVAL PASS 2 -- inside the chain
  → ChatResponse(answer, sources, session_id)
```

### 2.1 Structural findings

- **Double retrieval per request.** `agent.py:110` invokes the retriever; `agent.py:138` invokes the
  chain, whose first step (`agent.py:98`) is `{"context": retriever | _format_docs, ...}` — the same
  retriever runs a second time. Every `/chat` call costs two query-embedding API calls and two FAISS
  searches. Critically, **the sources shown come from pass 1 and the context fed to the model comes
  from pass 2**; they are separate invocations that agree only by coincidence.
- **`/ingest` is a no-op stub.** `main.py:264-271` returns `chunks_added=0` in both branches. The
  live branch imports `VectorStoreManager` (line 270) and never uses it — an unused import that also
  breaks the lint job. `VectorStoreManager.add_texts()` is dead code.
- **`/health` reports the wrong thing.** `main.py:246` returns `vector_store_ready=not is_demo`,
  which is the demo flag, not the store state. `VectorStoreManager.is_ready` is never consulted. If
  the knowledge-base file is missing, `_build_from_knowledge_base` returns early leaving
  `self.store = None`, and `/health` still reports ready.
- **`session_id` is accepted and echoed but never used.** There is no conversation state.

---

## 3. Dependencies

`requirements.txt` — **13 entries, all floating `>=`, none pinned, no lock file, no hashes.**

```
fastapi>=0.110.0   uvicorn[standard]>=0.27.0   langchain>=0.2.0
langchain-google-genai>=2.0.0   langchain-community>=0.2.0   faiss-cpu>=1.8.0
pydantic>=2.6.0    pydantic-settings>=2.2.0    python-dotenv>=1.0.0
mlflow>=2.12.0     httpx>=0.27.0               pytest>=8.1.0   pytest-asyncio>=0.23.0
```

- No `pyproject.toml`, no lock file of any kind, no Python-version constraint in the repo.
- **Undeclared but imported:** `langchain_text_splitters` (`vectorstore.py:8`), `langchain_core`
  (`agent.py:75-77`) — resolved transitively only.
- **Undeclared but required by CI:** `ruff`, installed ad-hoc at `ci.yml:39`.
- `langchain>=0.2.0` alone spans breaking API changes; two installs a month apart differ.
- `mlflow>=2.12.0` is a heavy dependency for code that is never imported.

The only pinned version anywhere is the MLflow *server image* in `docker-compose.yml`
(`ghcr.io/mlflow/mlflow:v2.12.2`).

---

## 4. Ingestion, chunking, embedding, storage, retrieval

**Ingestion** — one hard-coded relative path, one format. `vectorstore.py:48` reads
`./data/sample_kb.txt` whole into a single string. No loader abstraction, no glob, no recursion, no
Markdown/PDF/HTML support. A missing file degrades silently: a warning is logged, `self.store` stays
`None`, the app starts anyway, and the first `/chat` raises an uncaught 500.

**Chunking** — `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)`, character-based
(`length_function` left at default `len`), default separators. **Not structure-aware**, despite the
corpus being a Markdown Q&A document. Evidence from the built index: chunk `$ffdaec08` *begins* with
`## Payments & Transactions` while chunk `$94f35e39` *ends* with the same header — the heading is
duplicated across the overlap and separated from part of its content. `add_start_index` is not set,
so **no character offsets are retained**. This is the root cause of the citation problem in §5.

**Embedding** — `GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")`, 3072-dim. No
`task_type` set, so document and query embeddings are not differentiated
(`RETRIEVAL_DOCUMENT` vs `RETRIEVAL_QUERY`).

**Vector store** — `FAISS.from_texts(chunks, self.embeddings)` at `vectorstore.py:56`, **with no
`metadatas` argument**. Verified from the index binary header:

```
0000000   I   x   F   2  \0  \f  \0  \0  \v  \0  \0  \0  \0  \0  \0  \0
```

fourcc `IxF2` = `IndexFlatL2` (exact brute-force); `d = 0x0c00` = 3072; `ntotal = 0x0b` = **11
vectors**. Size check: `135213 − 45 = 135168 = 11 × 3072 × 4` — exact.

Consequences: every `Document` carries `metadata={}` — no source filename, no section, no offsets, no
checksum. Docstore keys are **random UUID4s** that change on every rebuild, so no two runs are
comparable at chunk level, and `add_texts` always appends (no upsert, so re-ingestion duplicates).

**Retrieval** — `as_retriever(search_kwargs={"k": 4})`, default `similarity` search. `k=4` is a
hard-coded default argument at `agent.py:94`, not a setting. No metadata filters (there is no
metadata), no reranking, no hybrid search, no score threshold, no MMR, no query rewriting. **With
11 vectors, `k=4` returns 36% of the entire corpus for any query**, including off-topic ones — which
still render four "sources" in the UI.

---

## 5. Generation and citations

**Model** — `ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)`. Temperature is
hard-coded at `agent.py:83`. No `max_tokens`, no seed, no timeout, no retry policy.

**The only prompt in the codebase** (`agent.py:66-72`):

```python
SYSTEM_PROMPT = (
    "You are a helpful customer support agent. Answer questions accurately "
    "using only the provided context. If the context does not contain the "
    "answer, say so honestly. Be concise and professional.\n\n"
    "Context:\n{context}\n\n"
    "Question: {question}"
)
```

Applied via `ChatPromptTemplate.from_template`, so despite the name it becomes a **human** message,
not a system message. There is no output-format instruction and **no instruction to cite anything**.

Context assembly is `"\n\n".join(doc.page_content for doc in docs)` — chunks are concatenated with no
separators, numbering, or source tags, so the model cannot distinguish one chunk from another.

**The citation mechanism is a post-hoc string-scraping heuristic** (`agent.py:112-136`): for each
retrieved chunk, take the first line starting with `## ` or `Q: `; failing that, take the first
non-heading line truncated to 60 characters. Deduplicate. Return as `list[str]`.

Six findings:

1. **Per-answer, not per-claim.** A flat list attached to the whole response.
2. **Decoupled from generation.** The labels come from retrieval pass 1; the answer from pass 2. The
   model never sees the labels and is never asked to cite.
3. **Nothing resolves.** A label is a *line of text*, not an ID or offset. There is no path from a
   displayed pill back to a character range in the source.
4. **Labels are frequently wrong.** Because chunking is structure-blind, the `## ` branch fires
   whenever a chunk *happens* to start with a heading; a chunk starting mid-answer gets a truncated
   fragment of an unrelated sentence as its "source".
5. **Deduplication hides evidence.** Distinct chunks sharing a first line collapse to one label, so
   source count ≠ chunk count.
6. **Nothing verifies anything.** No groundedness check, no entailment check, not even a substring
   check. Abstention is a soft request in the prompt.

**Rate limiting** — `_rate_limit()` (`agent.py:15-22`) does a synchronous `time.sleep()` of up to
4.1 s, called from `answer()`, called from an `async def` route. It **blocks the event loop**: N
concurrent requests serialise into 4.1 s × N. The global `_last_request_time` is not thread-safe and
is per-process, so it breaks under multiple workers.

---

## 6. Tracing and logging

**MLflow is declared but entirely non-functional.** `mlflow_config.py` defines `init_mlflow()` and
`log_query()`; **neither is called anywhere**. The file is also broken code — line 18 reads
`settings.openai_model`, and `Settings` has no such attribute (it has `llm_model`), so `log_query()`
would raise `AttributeError` if it were ever called. The `mlflow` dependency is installed for
nothing, and `docker-compose.yml` runs a tracking server that receives zero data.

Otherwise: `logging.basicConfig`, a handful of info lines, and one per query
(`agent.py:139`) that writes user input to the log with no redaction. No structured logging, no
request IDs, no latency capture, no token accounting, no retrieved-chunk logging.

---

## 7. Tests — 1 of 7 pass

| File | Test | Status |
|---|---|---|
| `test_agent.py` | `test_format_docs` | **passes** |
| `test_agent.py` | `test_agent_answer` | errors |
| `test_agent.py` | `test_agent_returns_empty_sources_when_none` | errors |
| `test_api.py` | 4 tests | **never collected** |

- Both `test_agent.py` failures are `@patch("app.agent.ChatOpenAI")` (lines 29, 52). **`app.agent`
  has no `ChatOpenAI`** — it imports `ChatGoogleGenerativeAI`. These are leftovers from a pre-Gemini
  version that were never updated when the provider changed.
- `test_api.py:8` is `from app.main import app, vsm`. **`app.main` defines no module-level `vsm`** —
  the only `vsm` is a local inside `lifespan`. `ImportError` at collection, so all four tests error.
- Latent failures behind those: `test_ingest_endpoint` asserts `chunks_added == 3` while the code
  hard-codes `0`; `TestClient(app)` is not used as a context manager, so `lifespan` never runs and
  `agent` stays `None`.

No `conftest.py`, no fixtures, no coverage config, no pytest configuration. `pytest-asyncio` is
installed but no async test exists.

---

## 8. CI — red since the first commit

`.github/workflows/ci.yml`, three jobs:

| Job | Outcome | Cause |
|---|---|---|
| `test` | **fails** | sets `OPENAI_API_KEY` (`ci.yml:25`) — the wrong provider; and the suite does not run (§7) |
| `lint` | **fails** | `ruff` default rules include pyflakes `F`; `main.py:270` has an unused import → `F401` |
| `docker` | **skipped** | `needs: [test, lint]`, both of which fail |

No caching, no matrix, no coverage upload, and no `GEMINI_API_KEY` referenced anywhere in the
workflow. There are no badges in the README, which is fortunate.

---

## 9. Demo mode, and what is actually deployed

```python
is_demo = settings.demo_mode or not settings.gemini_api_key    # main.py:24
```

Evaluated at **import time**, so it is fixed for the process lifetime. Because `gemini_api_key`
defaults to `""`, **a fresh clone with no `.env` silently runs in demo mode** — no error, no warning
beyond one log line.

`DemoAgent.RESPONSES` (`agent.py:33-48`) is a **14-entry dict** matched by naive substring
containment against the lowercased query, returning the first key found anywhere in it. Keys:
`fee, country, currency, refund, payout, api, webhook, plan, pci, fraud, support, account,
rate limit, test`. Matching is order-dependent and fragile — `"Are there fees for refunds?"` returns
the *fees* answer because `fee` is checked first; `test` matches "latest" and "greatest"; `api`
matches "rapid".

Demo answers return **fake citations** in the same field as real ones:
`sources=[f"[DEMO MODE] Matched keyword: '{keyword}'"]`. They render as identical source pills.

**The deployed configuration is demo mode.** `render.yaml:9-12` sets `DEMO_MODE: "true"` and
`OPENAI_API_KEY: ""`. Commit `b5f05d8` is titled *"enable Gemini RAG on Render"* but
`git log -- render.yaml` shows the file was **only ever touched in the initial commit**. Any hosted
demo serves the 14 canned strings.

The shell launchers compound this: `demo.sh:48` greps `.env` for `^OPENAI_API_KEY=sk-`, which can
never match the `GEMINI_API_KEY=` template, so they **always** export `DEMO_MODE=true` — overriding a
perfectly valid Gemini key.

---

## 10. Reproducibility weaknesses

1. No pinned dependencies, no lock file, no hashes (§3).
2. No `pyproject.toml`; no Python-version constraint in-repo (CI says 3.11, `render.yaml` says
   3.11.0, the code needs ≥3.10 for `X | None`).
3. **No seeds anywhere** — grep for `seed|random_state` returns zero matches. `temperature=0.1` is
   non-zero and no seed is passed, so generations are not reproducible.
4. **Non-deterministic chunk IDs** (random UUID4), so runs cannot be compared at chunk level.
5. The FAISS index is gitignored and requires a live API key plus network to rebuild. No index
   checksum, no manifest, no build timestamp.
6. **No corpus checksum** — an index cannot be validated against the KB it was built from, and goes
   stale silently after any edit.
7. Relative paths resolved against CWD (`./data/...`); running from elsewhere silently yields no store.
8. **No evaluation set, no metrics, no baseline** (§12) — nothing to reproduce *to*.
9. Global mutable rate-limiter state makes timing order- and process-dependent.

---

## 11. Security

**Secret hygiene is sound.** `.env` is not committed and never was —
`git log --all --full-history -- .env` is empty, and the full set of paths ever added is the 21
tracked files. `.gitignore` covers it, and the parent repo documents an AES-256-CBC encrypted-secrets
workflow. Nothing below concerns leaked credentials.

| # | Issue | Location |
|---|---|---|
| 1 | `FAISS.load_local(..., allow_dangerous_deserialization=True)` — unconditional pickle load, no checksum or signature. `docker-compose.yml:9` mounts `./data` writable, so host write access → RCE in the container on next start | `vectorstore.py:34-36` |
| 2 | **XSS**: bot text and source labels are concatenated into HTML and assigned via `innerHTML`. The only "sanitisation" is `text.replace(/\\n/g,'<br>')`, which is not escaping — and the doubled backslash means the JS regex matches a literal `\n`, not a newline, so even that is wrong. Model output is attacker-influenceable via the query | `main.py:171-178` |
| 3 | No authentication, no rate limiting, no quota on `/chat`. The 4.1 s blocking sleep doubles as a DoS amplifier | `main.py:250` |
| 4 | Prompt injection unmitigated — `{context}` interpolated raw with no delimiters or instruction hierarchy. Inert only because `/ingest` is a stub | `agent.py:66-72` |
| 5 | Docker runs as **root** (no `USER`), no `HEALTHCHECK`, shell-form `CMD` (so uvicorn never receives `SIGTERM`), base image unpinned by digest | `Dockerfile` |
| 6 | `docker-compose.yml` injects the whole `.env` into the container env, visible to `docker inspect` | `docker-compose.yml:6-7` |
| 7 | User queries written to logs unredacted | `agent.py:139` |
| 8 | No CORS config at all (fail-safe, but the API is unusable cross-origin and this appears unintentional) | — |

---

## 12. README accuracy

The README is the **pre-Gemini draft** and was never updated; `git log -- README.md` shows it was
written once, in the commit whose own title says "with Gemini".

| README claim | Line | Reality |
|---|---|---|
| "**OpenAI** — LLM and embeddings (configurable)" | 18 | Gemini throughout (`agent.py:81`, `vectorstore.py:19`). No OpenAI package, no OpenAI code path, and no provider switch — so "(configurable)" is false too |
| "Edit .env with your OpenAI API key" | 27 | The variable read is `GEMINI_API_KEY`. Following the README verbatim yields a silently demo-mode app |
| "LangChain — RAG orchestration and **RetrievalQA** chain" | 15 | No `RetrievalQA` anywhere; the chain is hand-built LCEL |
| Architecture diagram showing `RetrievalQA` | 8 | Same, and it omits the double retrieval and the separate source pass |
| "**MLflow** — Experiment tracking" | 19 | Zero tracking occurs; the module is orphaned and broken |
| "POST /ingest — Add new documents" | 55 | A stub returning `chunks_added=0` |
| "`pytest tests/ -v`" | 60 | The suite does not run |
| "An **autonomous** customer support agent" | 3 | No agent loop, no tools, no planning, no memory. Single-shot RAG |

**Omissions:** the README never mentions demo mode, the canned-response table, the 4.1 s sleep, the
Render deployment, or the chat UI at `/` — arguably the five most user-visible behaviours. The parent
`resume/README.md:15-18` repeats the "autonomous" claim.

---

## 13. Evaluation code

**None.** A case-insensitive grep across all `.py`/`.md`/`.yml`/`.txt`/`.sh` files for
`eval|ragas|recall|precision|ndcg|mrr|groundedness|faithfulness|benchmark|seed` returns **zero
matches**. No golden set, no retrieval metrics, no answer-quality metrics, no judge, no ablation
harness, no latency or cost benchmark, no regression baseline. The only quality signal in the
repository is the single passing unit test.

This is the gap `rag-evaluation-lab` exists to fill.

---

## 14. Knowledge base

`data/sample_kb.txt` — 4,380 bytes, 82 lines, one H1, **7 H2 sections, 24 Q&A pairs** in strict
`Q:`/`A:` format. Domain: "NovaPay", a fictional payment processor. Topics include fees, payouts,
refunds, error codes `PAY_001`–`PAY_003`, SDK languages, sandbox test cards, rate limits, webhooks,
PCI DSS Level 1 / SAQ-A, "NovaPay Radar" fraud scoring, plan tiers, and support channels.

**Content quality: good.** A plausible payment-processor FAQ with coherent fee structures and correct
compliance vocabulary.

**Corpus quality for evaluation: unusable.**

- 11 chunks total, so `k=4` returns a third of the corpus and retrieval metrics saturate.
- Single file, single domain, single format. No multi-document reasoning is possible.
- Every answer is self-contained in one Q&A pair — **no multi-hop question can be constructed**.
- No distractors, no unanswerable questions, no versioned or conflicting documents — so abstention
  and version-confusion cannot be measured at all.
- `DemoAgent.RESPONSES` is a near-verbatim paraphrase of this file, so demo mode and RAG mode produce
  suspiciously similar output — an observer cannot tell whether retrieval is working.

---

## 15. Licensing

**Neither repository carries a LICENSE file.** Not in the working tree, not in history, no SPDX
headers, no licence statement in either README. Both are public on GitHub. With no licence, default
copyright applies — all rights reserved.

Both repositories are the same author's own work, so relicensing the reused material is the author's
to do. `rag-evaluation-lab` carries MIT for code and CC BY 4.0 for the corpus, and its corpus README
records that the material derives from this project's `sample_kb.txt`.

---

## 16. Reuse decision

### Reused

| Component | Basis |
|---|---|
| **Knowledge-base facts** (`data/sample_kb.txt`, 24 Q&A pairs) | Coherent, plausible, internally consistent domain content. Carried forward as *factual seeds* into `data/corpus/novapay/fact_ledger.yaml`, then expanded ~40× into 14 structured documents with the distractors, multi-hop chains, version conflicts and deliberate gaps the original lacks |

**That is the entire reuse.** No source file is copied.

### Replaced, and why

| Component | Reason |
|---|---|
| Citation mechanism | String-scraping, per-answer, non-resolvable, unverified, sourced from a different retrieval pass than the answer (§5). Rebuilding it correctly *is the project* |
| Retrieval flow | Double retrieval; sources and context can disagree (§2.1) |
| Chunking | Structure-blind, no offsets — so citations cannot resolve to source spans (§4) |
| Index construction | No metadata, random UUID IDs, non-deterministic across rebuilds (§4) |
| `allow_dangerous_deserialization=True` | Unconditional pickle load with no integrity check (§11) |
| `DemoAgent` | 14 canned strings emitting fake citations in the real citation field (§9). An offline mode must exercise the real path, not bypass it |
| `_rate_limit()` | Blocks the async event loop; global non-thread-safe state (§5) |
| `/ingest`, `/health` | A stub and a wrong answer respectively (§2.1) |
| `mlflow_config.py` | Orphaned and broken. Replaced by structured local JSONL tracing (§6) |
| Inline `CHAT_HTML` | 178-line UI inside the API module with an `innerHTML` XSS sink (§11) |
| Both test files | Reference symbols that do not exist and assert values the code cannot produce (§7) |
| `requirements.txt` | Fully floating, no lock (§3) |
| `demo.sh` / `demo.cmd` / `render.yaml` | Gate on the wrong provider's key; force demo mode over a valid one (§9) |
| README | Systematically describes a different system (§12) |

### Carried forward as design lessons, not code

The audited repo's failure modes became the new project's requirements. Each of these is now
something `rag-evaluation-lab` measures rather than something it hopes to avoid:

| Failure observed here | Becomes |
|---|---|
| Citations that resolve to nothing | `citation_unresolvable` failure class; "all cited IDs resolve" is a CI-enforced test |
| Sources disagreeing with context | One retrieval pass, and a trace that records exactly what the model saw |
| Structure-blind chunking splitting headings from content | `chunk_boundary` failure class; structure-aware chunking as a *tested* intervention |
| No abstention behaviour | Four unanswerable cases and an abstention confusion matrix |
| Demo mode indistinguishable from RAG | Scripted offline integration tests exercise the real pipeline path |
| CI red with nobody noticing | Linux and Windows CI are configured before publication claims |
| README describing a different system | Every reported number generated from `comparison.json`, enforced by a test |

---

## 17. Disposition

The audited repository is **left unchanged**. It is not deleted, not rewritten, and not
re-pointed. `rag-evaluation-lab` is a separate repository with its own history.

Two things there are worth fixing independently of this project, neither of which is in scope here:
the README's provider claims (§12), and the missing `.gitmodules` in the parent repo (§1).
