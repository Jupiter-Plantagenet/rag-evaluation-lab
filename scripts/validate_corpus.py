"""Validate the NovaPay corpus against its fact ledger.

The ledger was written before any prose so that the prose could be checked
against something. This script is that check. Without it, "the ledger is the
source of truth" is an aspiration; with it, a drifted number fails the build.

Five invariants:

  1. AUTHORITY      -- each fact has exactly one authoritative document, and that
                       document exists.
  2. PRESENCE       -- each fact's value appears verbatim in its authoritative doc.
  3. RESTATEMENT    -- each doc listed in `restated_in` also contains the value,
                       and declares that it restates rather than owns it.
  4. GAPS           -- no probe term for a deliberate gap appears in ANY document.
                       This is what makes the unanswerable eval cases principled
                       rather than accidental: if prose drift ever covers a gap,
                       the corresponding case is silently invalid, and only this
                       check would notice.
  5. FRONT MATTER   -- every document parses, declares the required keys, and
                       marks itself synthetic.

Run:  python scripts/validate_corpus.py [--corpus data/corpus/novapay]
Exit: 0 clean, 1 on any violation.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
REQUIRED_KEYS = {"doc_id", "title", "version", "effective_date", "synthetic"}


def normalise(text: str) -> str:
    """Fold the differences that should not count as a mismatch.

    Folded, because they are presentation rather than content:
      - NFC, because the corpus is authored on Windows and validated on Linux CI;
      - whitespace, because a Markdown table and a paragraph wrap the same value
        differently ("$50,000 per\ncalendar month" is the ledger's value);
      - Markdown emphasis and code markers (``*``, ``_``, `````), because
        ``**2.9% + $0.30**`` and ``2.9% + $0.30`` are the same assertion;
      - table cell pipes, so a value split across two cells still reads as one
        string.

    NOT folded, because they are content: digits, currency symbols, casing,
    and word order. A drifted number still fails, which is the point.
    """
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[*_`|]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def accepted_forms(fact: dict[str, Any]) -> list[str]:
    """Every surface form that counts as stating this fact.

    ``aliases`` exists because a comparison table legitimately writes "100 req/s"
    where the authoritative prose writes "100 requests per second". Forcing one
    spelling everywhere would make the corpus read like it was generated, which
    would undermine the retrieval difficulty it exists to create.
    """
    return [fact["value"], *fact.get("aliases", [])]


def contains_fact(body: str, fact: dict[str, Any]) -> bool:
    """True if ``body`` states the fact in any accepted form.

    ``value_components`` handles facts that are genuinely compound -- a retry
    schedule is six intervals, and requiring the ledger's comma-joined spelling
    to appear verbatim would only force the prose into an unnatural shape. Every
    component must be present; their arrangement is the author's business.
    """
    if components := fact.get("value_components"):
        return all(normalise(c) in body for c in components)
    return any(normalise(f) in body for f in accepted_forms(fact))


def check_encoding(path: Path) -> list[str]:
    """Catch the two ways a Windows toolchain silently corrupts a UTF-8 corpus.

    Learned the hard way: PowerShell 5.1's ``Get-Content -Raw`` reads a BOM-less
    UTF-8 file using the ANSI codepage, and ``Set-Content -Encoding utf8`` writes
    a BOM. A read-modify-write round trip therefore turns every em dash into
    ``a-circumflex-euro-quot`` AND prepends a BOM that breaks the front-matter
    regex.

    That matters more here than it would elsewhere: corpus bytes are hashed into
    every run manifest, so a platform-dependent corruption would make the
    reproducibility claim false rather than merely making the prose ugly.
    """
    errors: list[str] = []
    raw = path.read_bytes()

    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append(
            f"[encoding] {path.name}: starts with a UTF-8 BOM. Front-matter parsing "
            f"expects the file to begin with '---'. Write UTF-8 without a BOM."
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        errors.append(f"[encoding] {path.name}: not valid UTF-8 ({e})")
        return errors

    # Mojibake signature: UTF-8 bytes that were decoded as cp1252 and re-encoded.
    for marker in ("â€", "Ã©", "Â "):
        if marker in text:
            errors.append(
                f"[encoding] {path.name}: mojibake detected ({marker!r}). The file was "
                f"round-tripped through a non-UTF-8 codepage. Restore it from git rather "
                f"than trying to repair the characters individually."
            )
            break
    return errors


def load_docs(corpus_dir: Path) -> dict[str, tuple[dict[str, Any], str, Path]]:
    """Return {doc_id: (front_matter, body, path)}."""
    docs: dict[str, tuple[dict[str, Any], str, Path]] = {}
    for path in sorted(corpus_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        m = FRONT_MATTER_RE.match(raw)
        if m is None:
            raise SystemExit(f"{path.name}: no YAML front matter")
        fm = yaml.safe_load(m.group(1)) or {}
        doc_id = fm.get("doc_id") or path.stem
        docs[doc_id] = (fm, m.group(2), path)
    return docs


def check(corpus_dir: Path) -> list[str]:
    errors: list[str] = []

    # --- 0. encoding, before anything tries to parse -------------------------
    for path in sorted(corpus_dir.glob("*.md")) + [corpus_dir / "fact_ledger.yaml"]:
        errors.extend(check_encoding(path))
    if errors:
        return errors  # parsing corrupted bytes only produces confusing errors

    ledger = yaml.safe_load((corpus_dir / "fact_ledger.yaml").read_text(encoding="utf-8"))
    docs = load_docs(corpus_dir)
    bodies = {d: normalise(body) for d, (_, body, _) in docs.items()}

    # --- 5. front matter ----------------------------------------------------
    for doc_id, (fm, _, path) in docs.items():
        missing = REQUIRED_KEYS - fm.keys()
        if missing:
            errors.append(f"[front-matter] {path.name}: missing keys {sorted(missing)}")
        if fm.get("synthetic") is not True:
            errors.append(f"[front-matter] {path.name}: must declare `synthetic: true`")
        if not fm.get("disclaimer"):
            errors.append(f"[front-matter] {path.name}: missing synthetic-data disclaimer")

    # --- 1-3. facts ---------------------------------------------------------
    authority_count: dict[str, list[str]] = {}
    for fact in ledger.get("facts", []):
        fid, value, auth = fact["id"], fact["value"], fact["authoritative_doc"]
        authority_count.setdefault(fid, []).append(auth)

        if auth not in docs:
            errors.append(f"[authority] {fid}: authoritative_doc '{auth}' does not exist")
            continue

        if not contains_fact(bodies[auth], fact):
            errors.append(
                f"[presence] {fid}: value {value!r} not found in "
                f"{docs[auth][2].name} (its authoritative document)"
            )

        for restater in fact.get("restated_in", []):
            if restater not in docs:
                errors.append(f"[restatement] {fid}: restated_in '{restater}' does not exist")
                continue
            if not contains_fact(bodies[restater], fact):
                errors.append(
                    f"[restatement] {fid}: {docs[restater][2].name} is declared as "
                    f"restating {value!r} but does not contain it (in any accepted form)"
                )
            fm = docs[restater][0]
            if fid in (fm.get("authoritative_for") or []):
                errors.append(
                    f"[authority] {fid}: {restater} claims authority in its front matter "
                    f"but the ledger names {auth}. Exactly one document owns each fact."
                )

    for fid, auths in authority_count.items():
        if len(auths) > 1:
            errors.append(f"[authority] {fid}: {len(auths)} authoritative documents {auths}")

    # --- superseded facts: both values present, in the right documents ------
    for sup in ledger.get("superseded", []):
        for side in ("current", "previous"):
            spec = sup[side]
            doc_id, value = spec["doc"], spec["value"]
            if doc_id not in docs:
                errors.append(f"[superseded] {sup['id']}.{side}: doc '{doc_id}' does not exist")
                continue
            if normalise(value) not in bodies[doc_id]:
                errors.append(
                    f"[superseded] {sup['id']}.{side}: value {value!r} not found in "
                    f"{docs[doc_id][2].name}. Both versions must be present and dated, or "
                    f"policy_version_confusion cannot be measured."
                )

    # --- 4. gaps ------------------------------------------------------------
    # The strictest check here. A gap that stops being a gap invalidates an eval
    # case silently, so this fails loudly on the first sign of prose drift.
    for gap in ledger.get("gaps", []):
        for term in gap["probe_terms"]:
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            for doc_id, body in bodies.items():
                if pattern.search(body):
                    errors.append(
                        f"[gap] {gap['id']}: probe term {term!r} appears in "
                        f"{docs[doc_id][2].name}. This topic is supposed to be ABSENT so "
                        f"that an unanswerable case is principled. Either remove the term "
                        f"from the prose or remove the gap from the ledger."
                    )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=Path("data/corpus/novapay"))
    args = ap.parse_args()

    errors = check(args.corpus)
    if errors:
        print(f"Corpus validation FAILED -- {len(errors)} violation(s):\n", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    docs = load_docs(args.corpus)
    words = sum(len(b.split()) for _, (_, b, _) in docs.items())
    ledger = yaml.safe_load((args.corpus / "fact_ledger.yaml").read_text(encoding="utf-8"))
    print(
        f"Corpus OK: {len(docs)} documents, ~{words:,} words, "
        f"{len(ledger['facts'])} facts, {len(ledger.get('superseded', []))} superseded pairs, "
        f"{len(ledger.get('gaps', []))} deliberate gaps -- all invariants hold."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
