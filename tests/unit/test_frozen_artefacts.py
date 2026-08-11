"""The held-out result is closed evidence. These tests are the lock on it.

A checksum written into a document is a claim. A checksum a build verifies is a
control. The difference matters here more than usual: the single most damaging
thing that could happen to this repository's credibility is a held-out artefact
being regenerated -- innocently, by re-running a command -- and nobody noticing,
because a regenerated file looks exactly like an original one.

If these fail, do not update the checksums. Restore the files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# scripts/ is not a package and is not on the path in a plain `pytest` run.
# Importing the verifier rather than reimplementing it keeps one definition of
# "which files are frozen" shared by the CLI script and this test.
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from verify_frozen import recorded_checksums, verify  # noqa: E402

RECORD = REPO_ROOT / "docs" / "frozen-held-out-result.md"
LEDGER = REPO_ROOT / "runs" / ".test_ledger.jsonl"


@pytest.mark.unit
def test_frozen_artefacts_match_recorded_checksums() -> None:
    problems = verify(REPO_ROOT)
    assert not problems, (
        "Frozen held-out artefacts differ from docs/frozen-held-out-result.md:\n\n"
        + "\n".join(problems)
        + "\n\nRestore them with `git checkout -- <path>`. A re-issued result must be "
        "written to a NEW path, never by overwriting these."
    )


@pytest.mark.unit
def test_every_frozen_file_is_actually_recorded() -> None:
    """The record must not silently omit one of the artefacts it claims to cover.

    Without this, deleting a line from the document would make the checksum test
    pass by having nothing to check.
    """
    recorded = set(recorded_checksums())
    required = {
        "runs/baseline-test-20260806T182019Z-66ee099b/trace.jsonl",
        "runs/baseline-test-20260806T182019Z-66ee099b/metrics.json",
        "runs/baseline-test-20260806T182019Z-66ee099b/config.resolved.yaml",
        "runs/improved-test-20260806T182251Z-1e6a1bf8/trace.jsonl",
        "runs/improved-test-20260806T182251Z-1e6a1bf8/metrics.json",
        "runs/improved-test-20260806T182251Z-1e6a1bf8/config.resolved.yaml",
        "reports/held-out/comparison.json",
        "reports/held-out/comparison.md",
        "reports/held-out/metrics.csv",
        "runs/.test_ledger.jsonl",
    }
    assert required <= recorded, f"not recorded: {sorted(required - recorded)}"


@pytest.mark.unit
def test_held_out_split_was_accessed_exactly_twice() -> None:
    """The ledger is the evidence that the split stayed frozen until the end.

    A third entry is not necessarily misconduct -- but it is a fact that must be
    disclosed and explained, and a silent one defeats the entire design.
    """
    entries = [
        json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(entries) == 2, (
        f"the held-out split has been accessed {len(entries)} times, not 2.\n"
        f"reasons: {[e.get('reason') for e in entries]}\n"
        "If a further access was authorised, update docs/frozen-held-out-result.md "
        "to disclose it and adjust this test deliberately."
    )
    assert all(e["n_cases"] == 22 for e in entries)
    assert all(not e["ci"] for e in entries), "CI must never read the held-out split"


@pytest.mark.unit
def test_frozen_record_states_the_no_tuning_constraint() -> None:
    """The document's purpose is the constraint, not the numbers."""
    text = RECORD.read_text(encoding="utf-8").lower()
    assert "no later development work may tune" in text
    assert "new report version" in text, "the re-issue rule must be stated"
    assert "b0d4fa4" in text, "the intervention-freeze commit must be recorded"
    assert "f4ac2b1" in text, "the result commit must be recorded"
