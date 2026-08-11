"""Corpus integrity, enforced in CI rather than trusted.

``scripts/validate_corpus.py`` is the implementation; this module makes it a
build gate. Every invariant here protects a downstream claim:

- A drifted fact value silently invalidates the expected answer of every eval
  case that touches it, and the metrics would agree with the corpus rather than
  with reality.
- A gap that stops being a gap turns an "unanswerable" case into an answerable
  one, so abstention correctness would be measured against a false premise.
- An encoding round-trip changes the corpus bytes, which are hashed into every
  run manifest -- making a reproducibility claim platform-dependent.

None of these fail loudly on their own. That is why they are tested.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "data" / "corpus" / "novapay"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_corpus import check, check_encoding, load_docs, normalise  # noqa: E402


@pytest.fixture(scope="module")
def ledger() -> dict:
    return yaml.safe_load((CORPUS_DIR / "fact_ledger.yaml").read_text(encoding="utf-8"))


@pytest.mark.unit
def test_all_corpus_invariants_hold() -> None:
    """The whole validator, as one gate. Individual tests below localise failures."""
    errors = check(CORPUS_DIR)
    assert not errors, "Corpus validation failed:\n" + "\n".join(f"  {e}" for e in errors)


@pytest.mark.unit
def test_corpus_files_are_utf8_without_bom() -> None:
    for path in [*sorted(CORPUS_DIR.glob("*.md")), CORPUS_DIR / "fact_ledger.yaml"]:
        assert not check_encoding(path), f"{path.name} has an encoding problem"


@pytest.mark.unit
def test_every_document_declares_itself_synthetic() -> None:
    """The disclaimer is a correctness property, not decoration.

    This corpus reads like real payment-processor documentation on purpose. If a
    document were ever extracted from the repo without its front matter, the only
    thing distinguishing it from genuine guidance would be this declaration.
    """
    for _doc_id, (fm, _, path) in load_docs(CORPUS_DIR).items():
        assert fm.get("synthetic") is True, f"{path.name} does not declare synthetic: true"
        assert fm.get("disclaimer"), f"{path.name} has no disclaimer"
        assert "fictional" in fm["disclaimer"].lower(), (
            f"{path.name}'s disclaimer does not say the company is fictional"
        )


@pytest.mark.unit
def test_exactly_one_authoritative_document_per_fact(ledger: dict) -> None:
    """Citation precision depends on there being a single right answer to cite.

    The `citation_non_authoritative` failure class is only meaningful if
    'authoritative' is well defined -- two owners for one fact would make the
    class unmeasurable.
    """
    owners: dict[str, list[str]] = {}
    for fact in ledger["facts"]:
        owners.setdefault(fact["id"], []).append(fact["authoritative_doc"])
    duplicated = {k: v for k, v in owners.items() if len(v) > 1}
    assert not duplicated, f"facts with multiple authoritative documents: {duplicated}"


@pytest.mark.unit
def test_deliberate_gaps_are_genuinely_absent(ledger: dict) -> None:
    """The unanswerable cases rest entirely on this.

    Checked separately from the aggregate so that prose drift covering a gap
    produces an obvious failure name rather than a line in a list.
    """
    bodies = {d: normalise(b) for d, (_, b, _) in load_docs(CORPUS_DIR).items()}
    for gap in ledger["gaps"]:
        for term in gap["probe_terms"]:
            hits = [d for d, body in bodies.items() if term.lower() in body.lower()]
            assert not hits, (
                f"Gap {gap['id']!r} is no longer a gap: probe term {term!r} now appears "
                f"in {hits}. Either remove it from the prose, or remove the gap from the "
                f"ledger and retire the eval cases that depend on it."
            )


@pytest.mark.unit
def test_superseded_policies_have_disjoint_validity(ledger: dict) -> None:
    """A temporal question needs an unambiguous answer for any given date.

    Overlapping windows would make `policy_version_confusion` a judgement call
    rather than a fact, and the failure class would stop being measurable.
    """
    for sup in ledger["superseded"]:
        cur, prev = sup["current"], sup["previous"]
        assert prev["effective_until"] < cur["effective_from"], (
            f"{sup['id']}: previous version runs to {prev['effective_until']} but the "
            f"current one starts {cur['effective_from']} -- the windows overlap, so there "
            f"is no single correct answer for a date in the overlap."
        )
        assert cur["value"] != prev["value"], (
            f"{sup['id']}: both versions state the same value, so nothing was superseded "
            f"and no version confusion is possible."
        )


@pytest.mark.unit
def test_corpus_is_large_enough_for_retrieval_to_be_non_trivial() -> None:
    """Guards against the specific defect that motivated this project.

    The predecessor corpus produced 11 chunks, so top-k=4 returned 36% of it for
    any query and every retrieval metric saturated. A floor on document count and
    length is what stops that recurring.
    """
    docs = load_docs(CORPUS_DIR)
    words = sum(len(b.split()) for _, (_, b, _) in docs.items())

    assert len(docs) >= 12, f"only {len(docs)} documents; retrieval would be too easy"
    assert words >= 8000, f"only {words} words; too few chunks for meaningful top-k"

    short = {p.name: len(b.split()) for _, (_, b, p) in docs.items() if len(b.split()) < 300}
    assert not short, f"documents too short to chunk meaningfully: {short}"
