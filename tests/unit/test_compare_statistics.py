"""Tests for the comparison statistics.

These are the routines that turn per-case numbers into the sentences a reader
acts on, so a defect here is worse than a defect almost anywhere else in the
repository: it does not crash, it does not look wrong, it just reports an effect
that is not there. Each test below pins one property the reported intervals are
assumed to have.

Written against known-answer constructions rather than the real traces wherever
possible -- a test that only asserts "the numbers are what the code currently
produces" cannot detect that the code was always wrong.
"""

from __future__ import annotations

import numpy as np
import pytest

from rag_eval.reporting.compare import (
    METRICS,
    MetricComparison,
    compare_metric,
    paired_bootstrap,
    render_csv,
)

# ---------------------------------------------------------------------------
# paired_bootstrap
# ---------------------------------------------------------------------------


def _case(cid: str, **metrics: object) -> dict:
    return {"case_id": cid, "metrics": dict(metrics)}


def _arm(values: dict[str, dict]) -> dict[str, dict]:
    return {cid: _case(cid, **m) for cid, m in values.items()}


@pytest.mark.unit
def test_paired_bootstrap_mean_delta_is_the_mean_of_per_case_differences() -> None:
    base = [0.0, 0.5, 1.0, 0.25]
    impr = [1.0, 0.5, 1.0, 0.75]
    delta, _, _ = paired_bootstrap(base, impr, resamples=200)
    assert delta == pytest.approx(np.mean(np.array(impr) - np.array(base)))


@pytest.mark.unit
def test_paired_bootstrap_is_paired_not_independent() -> None:
    """Perfectly correlated arms must give a zero-width interval.

    Every case improves by exactly 0.1. A paired procedure sees a constant
    difference and returns [0.1, 0.1]. An unpaired procedure would resample the
    two arms separately, see the spread WITHIN each arm, and return a wide
    interval -- the exact error this pins.
    """
    base = [0.0, 0.2, 0.4, 0.6, 0.8]
    impr = [b + 0.1 for b in base]
    delta, lo, hi = paired_bootstrap(base, impr, resamples=2000)
    assert delta == pytest.approx(0.1)
    assert lo == pytest.approx(0.1)
    assert hi == pytest.approx(0.1)


@pytest.mark.unit
def test_paired_bootstrap_is_deterministic_under_a_fixed_seed() -> None:
    base = [0.1, 0.9, 0.3, 0.7, 0.5, 0.2]
    impr = [0.4, 0.6, 0.9, 0.1, 0.8, 0.3]
    first = paired_bootstrap(base, impr, resamples=1000, seed=12345)
    second = paired_bootstrap(base, impr, resamples=1000, seed=12345)
    third = paired_bootstrap(base, impr, resamples=1000, seed=999)
    assert first == second
    assert first[1:] != third[1:], "different seeds must give different resamples"


@pytest.mark.unit
def test_paired_bootstrap_interval_brackets_the_point_estimate() -> None:
    rng = np.random.default_rng(7)
    base = list(rng.uniform(0, 1, 30))
    impr = list(rng.uniform(0, 1, 30))
    delta, lo, hi = paired_bootstrap(base, impr, resamples=4000)
    assert lo <= delta <= hi


@pytest.mark.unit
def test_paired_bootstrap_percentiles_are_two_sided_at_the_stated_alpha() -> None:
    """alpha=0.05 must cut 2.5% from each tail, not 5% from one."""
    base = [0.0] * 40
    impr = list(np.linspace(-1, 1, 40))
    _, lo, hi = paired_bootstrap(base, impr, resamples=8000, alpha=0.05)
    _, lo90, hi90 = paired_bootstrap(base, impr, resamples=8000, alpha=0.10)
    assert lo < lo90 and hi > hi90, "a 95% interval must be wider than a 90% one"
    assert lo == pytest.approx(-hi, abs=0.05), "a symmetric sample gives a ~symmetric interval"


# ---------------------------------------------------------------------------
# compare_metric: pairing, exclusion, direction
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_metrics_are_aligned_by_case_id_not_by_position() -> None:
    """Insertion order must not affect the result.

    A positional zip would silently compare case A's baseline against case B's
    improved value the moment two traces were written in different orders.
    """
    base = _arm({"c1": {"m": 0.0}, "c2": {"m": 1.0}, "c3": {"m": 0.5}})
    forward = _arm({"c1": {"m": 1.0}, "c2": {"m": 0.0}, "c3": {"m": 0.5}})
    shuffled = _arm({"c3": {"m": 0.5}, "c2": {"m": 0.0}, "c1": {"m": 1.0}})

    a = compare_metric("m", base, forward, resamples=500, seed=1)
    b = compare_metric("m", base, shuffled, resamples=500, seed=1)
    assert (a.delta, a.ci_low, a.ci_high) == (b.delta, b.ci_low, b.ci_high)


@pytest.mark.unit
def test_case_missing_from_one_arm_is_excluded_entirely() -> None:
    base = _arm({"c1": {"m": 0.0}, "c2": {"m": 0.0}, "c3": {"m": 0.0}, "orphan": {"m": 0.0}})
    impr = _arm({"c1": {"m": 1.0}, "c2": {"m": 1.0}, "c3": {"m": 1.0}})
    result = compare_metric("m", base, impr, resamples=200, seed=1)
    assert result.n_paired == 3


@pytest.mark.unit
def test_none_valued_cases_are_excluded_rather_than_treated_as_zero() -> None:
    """None means 'not applicable', never 'scored zero'.

    If None were coerced to 0.0 the baseline mean below would be 0.5 rather than
    1.0, and an unanswerable case would be reported as a retrieval failure.
    """
    base = _arm({"a": {"m": 1.0}, "b": {"m": 1.0}, "c": {"m": 1.0}, "d": {"m": None}})
    impr = _arm({"a": {"m": 1.0}, "b": {"m": 1.0}, "c": {"m": 1.0}, "d": {"m": None}})
    result = compare_metric("m", base, impr, resamples=200, seed=1)
    assert result.n_paired == 3
    assert result.baseline_mean == 1.0


@pytest.mark.unit
def test_case_defined_in_only_one_arm_is_excluded_from_both() -> None:
    """Otherwise the two means in one row would describe different case sets."""
    base = _arm({"a": {"m": 0.0}, "b": {"m": 0.0}, "c": {"m": 0.0}, "d": {"m": 0.0}})
    impr = _arm({"a": {"m": 1.0}, "b": {"m": 1.0}, "c": {"m": 1.0}, "d": {"m": None}})
    result = compare_metric("m", base, impr, resamples=200, seed=1)
    assert result.n_paired == 3
    assert result.baseline_mean == 0.0 and result.improved_mean == 1.0


@pytest.mark.unit
def test_booleans_are_not_silently_accepted_as_metric_values() -> None:
    """bool is a subclass of int in Python, so isinstance(True, int) is True.

    A metric that became boolean upstream would therefore average as 0/1 without
    complaint. That is currently harmless -- abstention correctness is genuinely
    a proportion -- so this test documents the behaviour rather than forbidding
    it, and will fail if the coercion rule is ever tightened without updating it.
    """
    base = _arm({"a": {"m": True}, "b": {"m": False}, "c": {"m": True}})
    impr = _arm({"a": {"m": True}, "b": {"m": True}, "c": {"m": True}})
    result = compare_metric("m", base, impr, resamples=200, seed=1)
    assert result.n_paired == 3
    # Means are rounded to 4dp on the way into the report.
    assert result.baseline_mean == pytest.approx(2 / 3, abs=1e-4)


@pytest.mark.unit
def test_fewer_than_three_paired_cases_reports_insufficient_data() -> None:
    base = _arm({"a": {"m": 0.0}, "b": {"m": 0.0}})
    impr = _arm({"a": {"m": 1.0}, "b": {"m": 1.0}})
    result = compare_metric("m", base, impr, resamples=200, seed=1)
    assert result.direction == "insufficient data"
    assert result.ci_excludes_zero is False
    assert result.ci_low is None and result.ci_high is None


@pytest.mark.unit
def test_identical_arms_give_a_zero_delta_and_no_measurable_difference() -> None:
    values = {"a": {"m": 0.2}, "b": {"m": 0.9}, "c": {"m": 0.4}, "d": {"m": 0.7}}
    result = compare_metric("m", _arm(values), _arm(values), resamples=500, seed=1)
    assert result.delta == 0.0
    assert result.direction == "no measurable difference"
    assert result.ci_excludes_zero is False


@pytest.mark.unit
def test_a_clear_regression_is_reported_as_regressed_not_as_no_difference() -> None:
    base = _arm({f"c{i}": {"m": 1.0} for i in range(10)})
    impr = _arm({f"c{i}": {"m": 0.0} for i in range(10)})
    result = compare_metric("m", base, impr, resamples=1000, seed=1)
    assert result.direction == "regressed"
    assert result.ci_excludes_zero is True
    assert result.ci_high < 0


@pytest.mark.unit
def test_an_interval_touching_zero_is_not_counted_as_excluding_it() -> None:
    """The boundary case. `lo <= 0 <= hi` must be inclusive at both ends."""
    m = MetricComparison("m", 5, 0.0, 0.0, 0.0, 0.0, 0.3, not (0.0 <= 0.0 <= 0.3), "x")
    assert m.ci_excludes_zero is False


@pytest.mark.unit
def test_direction_assumes_higher_is_better_for_every_declared_metric() -> None:
    """`direction` maps a positive delta to "improved" unconditionally.

    That is correct only because every metric in METRICS is higher-is-better. If
    a lower-is-better metric (an error rate, a latency) is ever added to that
    list, this test fails and forces the direction logic to be revisited rather
    than reporting a regression as an improvement.
    """
    lower_is_better_markers = ("error", "latency", "cost", "loss", "_ms", "rate_of_")
    offenders = [m for m in METRICS if any(marker in m for marker in lower_is_better_markers)]
    assert not offenders, (
        f"{offenders} look lower-is-better, but compare_metric maps delta>0 to 'improved'. "
        "Give MetricComparison a polarity before adding these."
    )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_csv_header_uses_the_precise_field_name() -> None:
    """`significant` was renamed: it claimed a hypothesis test that never ran."""

    class _Stub:
        metrics = [MetricComparison("m", 4, 0.1, 0.2, 0.1, 0.05, 0.15, True, "improved")]

    header = render_csv(_Stub()).splitlines()[0]
    assert "ci_excludes_zero" in header
    assert "significant" not in header


@pytest.mark.unit
def test_metric_comparison_dict_uses_the_precise_field_name() -> None:
    m = MetricComparison("m", 4, 0.1, 0.2, 0.1, 0.05, 0.15, True, "improved")
    payload = m.to_dict()
    assert payload["ci_excludes_zero"] is True
    assert "significant" not in payload
