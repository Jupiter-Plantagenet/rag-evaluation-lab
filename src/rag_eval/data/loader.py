"""The only reader of the evaluation dataset, and the guard on the held-out split.

Every claim this project makes about not tuning on held-out data rests on this
module. The guarantee is deliberately mechanical rather than procedural:

  - ``load_cases()`` returns dev cases. Asking for the test split without
    ``allow_test=True`` raises. There is no flag on the object, no default that
    can drift, and no way to get test cases by accident.
  - Every access to the test split appends a line to ``runs/.test_ledger.jsonl``
    recording who asked, when, and why. The report prints that count.

The ledger is the part that matters. A guard that merely blocks access proves
nothing after the fact -- anyone can pass the flag. A guard that *counts* access
turns "the split stayed frozen" into a number a reviewer can look at, and a
number that grows during development is visible evidence that it did not.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from rag_eval.data.spans import resolve_quote
from rag_eval.errors import DatasetError, HeldOutSplitError
from rag_eval.types import (
    AbstentionBehaviour,
    EvalCase,
    EvidenceSpan,
    RequiredFact,
    Split,
)

TEST_LEDGER_PATH = Path("runs") / ".test_ledger.jsonl"


def _record_test_access(reason: str, n_cases: int, repo_root: Path) -> None:
    """Append one line per held-out access. Never raises -- see below."""
    ledger = repo_root / TEST_LEDGER_PATH
    ledger.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "reason": reason,
        "n_cases": n_cases,
        "host": platform.node(),
        "user": getpass.getuser(),
        "ci": bool(os.environ.get("CI")),
    }
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def _parse_case(raw: dict[str, Any], corpus: dict[str, str] | None) -> EvalCase:
    spans: list[EvidenceSpan] = []
    for s in raw.get("expected_evidence_spans") or []:
        start, end = -1, -1
        if corpus is not None:
            doc_body = corpus.get(s["doc_id"])
            if doc_body is None:
                raise DatasetError(f"{raw['id']}: evidence cites unknown document {s['doc_id']!r}")
            located = resolve_quote(doc_body, s["quote"])
            if located is None:
                raise DatasetError(
                    f"{raw['id']}: evidence quote does not resolve in {s['doc_id']}.\n"
                    f"  quote: {s['quote'][:80]!r}\n"
                    f"  Offsets are derived from this quote, so a case whose quote does not "
                    f"resolve has no ground-truth span and cannot be scored on retrieval."
                )
            start, end = located
        spans.append(
            EvidenceSpan(
                doc_id=s["doc_id"],
                quote=s["quote"],
                char_start=start,
                char_end=end,
                heading_path=tuple(s.get("heading_path") or ()),
                authoritative=s.get("authoritative", True),
            )
        )

    return EvalCase(
        id=raw["id"],
        category=raw["category"],
        question=raw["question"].strip(),
        answerable=raw["answerable"],
        expected_abstention_behaviour=AbstentionBehaviour(raw["expected_abstention_behaviour"]),
        split=Split(raw["split"]),
        reference_answer=raw.get("reference_answer"),
        required_facts=tuple(
            RequiredFact(fact_id=f["fact_id"], matcher=f["matcher"], weight=f.get("weight", 1.0))
            for f in (raw.get("required_facts") or [])
        ),
        acceptable_answer_notes=raw.get("acceptable_answer_notes", ""),
        expected_document_ids=tuple(raw.get("expected_document_ids") or ()),
        expected_evidence_spans=tuple(spans),
        forbidden_or_unsupported_claims=tuple(raw.get("forbidden_or_unsupported_claims") or ()),
        scoring_notes=raw.get("scoring_notes", ""),
        source_chain_id=raw.get("source_chain_id"),
        gap_id=raw.get("gap_id"),
    )


def load_cases(
    dataset_path: Path,
    *,
    split: Split | str = Split.DEV,
    allow_test: bool = False,
    reason: str = "unspecified",
    corpus: dict[str, str] | None = None,
    repo_root: Path | None = None,
) -> Sequence[EvalCase]:
    """Load cases for one split.

    Args:
        split: which split to load. ``Split.TEST`` requires ``allow_test``.
        allow_test: must be True to read held-out cases. Set only by the CLI's
            explicit ``--final`` flag -- never defaulted, never inferred.
        reason: recorded in the access ledger. Make it specific; it is what a
            reviewer reads when deciding whether the split stayed frozen.
        corpus: {doc_id: body}. Required to derive evidence offsets. Omitting it
            yields cases with unresolved spans, which is useful for schema
            inspection and useless for scoring -- so scoring paths always pass it.

    Raises:
        HeldOutSplitError: if the test split is requested without ``allow_test``.
    """
    split = Split(split)
    repo_root = repo_root or Path.cwd()

    if split is Split.TEST and not allow_test:
        raise HeldOutSplitError(
            "Refusing to load the held-out test split.\n"
            "\n"
            "The held-out split exists so that the improved pipeline's interventions can be\n"
            "shown to generalise beyond the cases used to design them. Reading it during\n"
            "development destroys that, and does so invisibly -- nothing about the resulting\n"
            "numbers looks wrong.\n"
            "\n"
            "If you genuinely intend a final evaluation, pass --final (CLI) or\n"
            "allow_test=True (API) with a specific reason. Every such access is appended to\n"
            f"{TEST_LEDGER_PATH.as_posix()} and the access count is printed in the report."
        )

    raw = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    cases = [_parse_case(c, corpus) for c in raw["cases"] if c["split"] == split.value]

    if not cases:
        raise DatasetError(f"no cases found for split {split.value!r} in {dataset_path}")

    if split is Split.TEST:
        _record_test_access(reason, len(cases), repo_root)

    return tuple(cases)


def load_all_cases(
    dataset_path: Path,
    *,
    corpus: dict[str, str] | None = None,
) -> Sequence[EvalCase]:
    """Load every case regardless of split, WITHOUT logging an access.

    Deliberately narrow in purpose: dataset validation, schema checks, and
    reporting dataset composition. It does not return which split a case belongs
    to any differently than the file states, and it must never be used to obtain
    test cases for a run -- ``load_cases`` is the only path that produces cases
    for scoring, and it is the one that logs.
    """
    raw = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    return tuple(_parse_case(c, corpus) for c in raw["cases"])


def read_test_access_ledger(repo_root: Path | None = None) -> list[dict[str, Any]]:
    """Return every recorded held-out access. Printed in the comparison report."""
    ledger = (repo_root or Path.cwd()) / TEST_LEDGER_PATH
    if not ledger.exists():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line]
