"""The held-out split guard.

Every claim this project makes about not tuning on held-out data reduces to the
behaviour asserted here. These tests are therefore about a *methodological*
guarantee, not a coding convenience -- if they pass and the ledger stays small,
"the split stayed frozen" is a checkable fact; if they are weakened, it becomes
an assertion nobody can verify.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_eval.data.loader import load_all_cases, load_cases, read_test_access_ledger
from rag_eval.errors import HeldOutSplitError
from rag_eval.types import Split

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET = REPO_ROOT / "data" / "eval" / "novapay_v1.yaml"


@pytest.mark.unit
def test_test_split_refuses_to_load_without_explicit_optin() -> None:
    with pytest.raises(HeldOutSplitError) as exc:
        load_cases(DATASET, split=Split.TEST)

    msg = str(exc.value)
    assert "--final" in msg, "the error must say how to proceed deliberately"
    assert "invisibly" in msg or "nothing about the resulting" in msg, (
        "the error must say WHY this matters -- a guard whose rationale is not "
        "stated at the point of refusal gets disabled by the next person in a hurry"
    )


@pytest.mark.unit
def test_dev_split_loads_freely() -> None:
    """The guard must not be so strict that ordinary work routes around it."""
    cases = load_cases(DATASET, split=Split.DEV)
    assert len(cases) >= 15
    assert all(c.split is Split.DEV for c in cases)


@pytest.mark.unit
def test_dev_load_does_not_touch_the_access_ledger(tmp_path: Path) -> None:
    load_cases(DATASET, split=Split.DEV, repo_root=tmp_path)
    assert not (tmp_path / "runs" / ".test_ledger.jsonl").exists()


@pytest.mark.unit
def test_test_split_access_is_recorded_with_a_reason(tmp_path: Path) -> None:
    """The ledger is the part that actually proves anything.

    A guard that only blocks proves nothing after the fact -- anyone can pass the
    flag. A guard that counts turns the claim into a number a reviewer reads.
    """
    cases = load_cases(
        DATASET,
        split=Split.TEST,
        allow_test=True,
        reason="unit test: verifying the ledger records access",
        repo_root=tmp_path,
    )
    assert len(cases) >= 12

    entries = read_test_access_ledger(tmp_path)
    assert len(entries) == 1
    assert entries[0]["reason"] == "unit test: verifying the ledger records access"
    assert entries[0]["n_cases"] == len(cases)
    assert "ts" in entries[0]


@pytest.mark.unit
def test_repeated_access_appends_rather_than_overwrites(tmp_path: Path) -> None:
    """Access count must be monotonic, or the evidence can be quietly reset."""
    for i in range(3):
        load_cases(
            DATASET, split=Split.TEST, allow_test=True, reason=f"run {i}", repo_root=tmp_path
        )

    entries = read_test_access_ledger(tmp_path)
    assert len(entries) == 3
    assert [e["reason"] for e in entries] == ["run 0", "run 1", "run 2"]

    raw = (tmp_path / "runs" / ".test_ledger.jsonl").read_text(encoding="utf-8")
    assert all(json.loads(line) for line in raw.splitlines() if line), "must stay valid JSONL"


@pytest.mark.unit
def test_load_all_cases_is_not_a_backdoor(tmp_path: Path) -> None:
    """``load_all_cases`` exists for validation and reporting, not for runs.

    It deliberately does not log, so it must also not be usable to obtain test
    cases for scoring. The protection is that it returns every case undivided --
    a caller wanting only the held-out set has to filter deliberately, which is
    visible in review, rather than receiving them from an innocuous-looking call.
    """
    every = load_all_cases(DATASET)
    assert len({c.split for c in every}) == 2, "returns both splits, undivided"
    assert not (tmp_path / "runs" / ".test_ledger.jsonl").exists()


@pytest.mark.unit
def test_split_sizes_match_the_documented_design() -> None:
    every = load_all_cases(DATASET)
    dev = [c for c in every if c.split is Split.DEV]
    test = [c for c in every if c.split is Split.TEST]

    assert len(dev) + len(test) == len(every)
    assert len(test) >= 12, "held-out set must stay large enough to report"
    # Dev must be the larger split: interventions are designed against it, and a
    # dev set smaller than the held-out set would mean tuning on less evidence
    # than is used to judge the result.
    assert len(dev) > len(test)
