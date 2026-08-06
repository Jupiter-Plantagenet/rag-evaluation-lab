"""Validate the evaluation dataset against its schema and against the corpus.

Schema validation alone is not enough. A case can be perfectly well-formed and
still be nonsense -- a quote that no longer appears in the corpus, a fact_id that
was renamed, an "unanswerable" question the corpus actually answers. Each of
those produces a metric rather than an error, which is the worst possible
failure mode for an evaluation harness: it looks like it worked.

So this runs four layers:

  1. SCHEMA        -- structural conformance to eval_case.v1.schema.json.
  2. CROSS-CORPUS  -- every expected_document_id exists; every evidence quote
                      resolves to a verbatim substring of the named document
                      (which is also how character offsets are derived, so a
                      quote that does not resolve has no offsets and cannot be
                      scored); every fact_id exists in the ledger.
  3. UNANSWERABILITY -- every unanswerable case names a declared gap, and the
                      corpus really is silent on it.
  4. DISTRIBUTION  -- category counts meet the design minimums and the split is
                      stratified rather than accidentally sorted.

Run:  python scripts/validate_dataset.py
Exit: 0 clean, 1 on any violation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]

# Minimum counts the design commits to. Spares are allowed above these; the
# check is >=, so adding cases never breaks the build, but quietly dropping a
# category does.
REQUIRED_MIN = {
    "factual": 10,
    "multi_hop": 5,
    "aggregation": 4,
    "unanswerable": 4,
    "ambiguous": 3,
    "temporal": 2,
    "citation_stress": 2,
}

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


def load_corpus(corpus_dir: Path) -> dict[str, str]:
    """{doc_id: body}. Bodies are raw -- quotes must match the real bytes."""
    docs: dict[str, str] = {}
    for path in sorted(corpus_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        m = FRONT_MATTER_RE.match(raw)
        body = m.group(2) if m else raw
        doc_id = (yaml.safe_load(m.group(1)) or {}).get("doc_id", path.stem) if m else path.stem
        docs[doc_id] = unicodedata.normalize("NFC", body)
    return docs


def resolve_quote(body: str, quote: str) -> tuple[int, int] | None:
    """Locate a quote and return its character span, or None.

    Offsets are DERIVED here rather than stored in the dataset. Hand-written
    offsets rot on the first prose edit and rot silently -- they still point
    somewhere, just at the wrong text. A quote either resolves or it does not,
    and a quote that does not resolve fails this script loudly.

    Only whitespace is normalised, because Markdown wraps prose at 80 columns
    and a quote spanning a line break is otherwise unmatchable. Everything else
    must match exactly.
    """
    quote = unicodedata.normalize("NFC", quote)
    idx = body.find(quote)
    if idx >= 0:
        return idx, idx + len(quote)

    flat_body = re.sub(r"\s+", " ", body)
    flat_quote = re.sub(r"\s+", " ", quote).strip()
    idx = flat_body.find(flat_quote)
    if idx < 0:
        return None

    # Map the flattened offset back to a real span by walking the original.
    real, seen, in_ws = 0, 0, False
    for i, ch in enumerate(body):
        if seen == idx:
            real = i
            break
        if ch.isspace():
            if not in_ws:
                seen += 1
                in_ws = True
        else:
            seen += 1
            in_ws = False
    return real, min(len(body), real + len(quote))


def validate(dataset_path: Path, corpus_dir: Path, schema_path: Path) -> list[str]:
    errors: list[str] = []
    data = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = data["cases"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    corpus = load_corpus(corpus_dir)
    ledger = yaml.safe_load((corpus_dir / "fact_ledger.yaml").read_text(encoding="utf-8"))
    fact_ids = {f["id"] for f in ledger["facts"]} | {s["id"] for s in ledger["superseded"]}
    gap_ids = {g["id"] for g in ledger["gaps"]}
    chain_ids = {c["id"] for c in ledger["multihop_chains"]}

    # --- 1. schema ----------------------------------------------------------
    validator = Draft202012Validator(schema)
    for case in cases:
        for err in sorted(validator.iter_errors(case), key=lambda e: e.path):
            loc = "/".join(str(p) for p in err.path) or "<root>"
            errors.append(f"[schema] {case.get('id', '??')} at {loc}: {err.message}")

    seen_ids: set[str] = set()
    for case in cases:
        cid = case["id"]
        if cid in seen_ids:
            errors.append(f"[schema] duplicate case id {cid}")
        seen_ids.add(cid)

        # --- 2. cross-corpus -------------------------------------------------
        for doc_id in case["expected_document_ids"]:
            if doc_id not in corpus:
                errors.append(f"[corpus] {cid}: expected_document_id {doc_id!r} does not exist")

        for i, span in enumerate(case.get("expected_evidence_spans") or []):
            doc_id, quote = span["doc_id"], span["quote"]
            if doc_id not in corpus:
                errors.append(f"[corpus] {cid} span[{i}]: doc {doc_id!r} does not exist")
                continue
            if resolve_quote(corpus[doc_id], quote) is None:
                errors.append(
                    f"[corpus] {cid} span[{i}]: quote does not resolve in {doc_id}.md.\n"
                    f"           quote: {quote[:90]!r}\n"
                    f"           Ground truth that cannot be located is not ground truth. "
                    f"Either the corpus changed or the quote was mistyped."
                )

        # Every document declared as expected must actually carry evidence.
        # Without this, a case can list two documents while all its spans sit in
        # one -- which is how a "multi-hop" case quietly becomes single-hop, and
        # how retrieval recall gets measured against a document the ground truth
        # never justified requiring.
        if case["answerable"]:
            span_docs = {s["doc_id"] for s in (case.get("expected_evidence_spans") or [])}
            unjustified = set(case["expected_document_ids"]) - span_docs
            if unjustified:
                errors.append(
                    f"[corpus] {cid}: expected_document_ids names {sorted(unjustified)} but no "
                    f"evidence span cites them. Either add the span or drop the document -- "
                    f"otherwise retrieval is scored against a requirement the ground truth "
                    f"does not support."
                )

        for i, rf in enumerate(case.get("required_facts") or []):
            if rf["fact_id"] not in fact_ids:
                errors.append(
                    f"[ledger] {cid} required_facts[{i}]: fact_id {rf['fact_id']!r} "
                    f"is not in fact_ledger.yaml"
                )

        if chain := case.get("source_chain_id"):
            if chain not in chain_ids:
                errors.append(f"[ledger] {cid}: source_chain_id {chain!r} is not a declared chain")

        # --- 3. unanswerability ----------------------------------------------
        if not case["answerable"]:
            gap = case.get("gap_id")
            if gap not in gap_ids:
                errors.append(
                    f"[gap] {cid}: gap_id {gap!r} is not declared in fact_ledger.yaml. "
                    f"Every unanswerable case must rest on a designed gap, or "
                    f"'unanswerable' means 'the author did not find an answer'."
                )
            else:
                spec = next(g for g in ledger["gaps"] if g["id"] == gap)
                for term in spec["probe_terms"]:
                    hits = [d for d, b in corpus.items() if term.lower() in b.lower()]
                    if hits:
                        errors.append(
                            f"[gap] {cid}: the corpus now discusses {term!r} in {hits}, so this "
                            f"question may be answerable. Retire the case or restore the gap."
                        )

    # --- 4. distribution ----------------------------------------------------
    counts = Counter(c["category"] for c in cases)
    for cat, minimum in REQUIRED_MIN.items():
        if counts[cat] < minimum:
            errors.append(f"[distribution] {cat}: {counts[cat]} cases, design requires >= {minimum}")

    if len(cases) < 30:
        errors.append(f"[distribution] {len(cases)} cases total; the design requires >= 30")

    # Stratification: no category may sit entirely in one split, or its
    # held-out performance is unmeasurable and its dev performance is untestable.
    for cat in counts:
        splits = {c["split"] for c in cases if c["category"] == cat}
        if len(splits) == 1 and counts[cat] > 1:
            errors.append(
                f"[distribution] every {cat} case is in the {splits.pop()!r} split. "
                f"Stratify, or this category contributes nothing to the comparison."
            )

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", type=Path, default=REPO_ROOT / "data/eval/novapay_v1.yaml")
    ap.add_argument("--corpus", type=Path, default=REPO_ROOT / "data/corpus/novapay")
    ap.add_argument(
        "--schema", type=Path, default=REPO_ROOT / "data/eval/schemas/eval_case.v1.schema.json"
    )
    args = ap.parse_args()

    errors = validate(args.dataset, args.corpus, args.schema)
    if errors:
        print(f"Dataset validation FAILED -- {len(errors)} violation(s):\n", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    data = yaml.safe_load(args.dataset.read_text(encoding="utf-8"))
    cases = data["cases"]
    by_cat = Counter(c["category"] for c in cases)
    by_split = Counter(c["split"] for c in cases)
    spans = sum(len(c.get("expected_evidence_spans") or []) for c in cases)
    print(f"Dataset OK: {len(cases)} cases, {spans} evidence spans, all quotes resolve.")
    print(f"  split:      {dict(by_split)}")
    print(f"  categories: {dict(by_cat)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
