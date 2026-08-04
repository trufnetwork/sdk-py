"""Tests for the market-implied point forecast."""

import math

import pytest

from trufnetwork_sdk_py.forecast import (
    BucketBook,
    bucket_probability,
    forecast_from_buckets,
)

# MSFT EPS 2026 Q3 bucket layout, as configured on mainnet.
MSFT_BOUNDS = [(None, 4.04), (4.04, 4.33), (4.33, 4.62), (4.62, 4.92), (4.92, None)]


def build(probs_cents, bounds=MSFT_BOUNDS, spread=2):
    """Books quoting each bucket at the given cents, with a symmetric spread."""
    out = []
    for (lo, hi), c in zip(bounds, probs_cents):
        if c is None:
            out.append(BucketBook(lo, hi))
        else:
            out.append(
                BucketBook(lo, hi, max(1, c - spread / 2), min(99, c + spread / 2))
            )
    return out


# --- bracket logic -----------------------------------------------------------


def test_two_sided_quote_is_the_midpoint():
    p, conf, one_sided, quoted = bucket_probability(38, 42)
    assert p == pytest.approx(0.40)
    assert conf == pytest.approx(0.96)
    assert not one_sided and quoted


def test_tighter_spread_means_more_confidence():
    _, tight, _, _ = bucket_probability(39, 41)
    _, wide, _, _ = bucket_probability(20, 60)
    assert tight > wide


def test_one_sided_book_steps_across_by_the_half_spread():
    """A lone bid is real information, but it is a BID: the fair value sits a
    half-spread above it, not at the midpoint of [bid, 1]."""
    p, conf, one_sided, quoted = bucket_probability(30, None, half_spread=0.06)
    assert one_sided and quoted
    assert p == pytest.approx(0.36)
    assert conf < 0.75, "we inferred one side rather than observing it"


def test_lone_penny_bid_is_not_a_coin_flip():
    """The bug live books exposed: [0.01, 1.0] midpoint made dead tails 50%."""
    p, _, _, _ = bucket_probability(1, None, half_spread=0.06)
    assert p == pytest.approx(0.07)
    assert p < 0.15


def test_empty_book_returns_none_not_a_number():
    p, conf, one_sided, quoted = bucket_probability(None, None)
    assert p is None
    assert conf == pytest.approx(0.0)
    assert not quoted and not one_sided


def test_crossed_book_is_distrusted():
    _, conf, _, _ = bucket_probability(60, 40)
    assert conf <= 1e-3


# --- the core estimate -------------------------------------------------------


def test_symmetric_market_centres_on_the_middle_bucket():
    """Mass symmetric about bucket 3 must imply its midpoint, (4.33+4.62)/2."""
    f = forecast_from_buckets(build([5, 20, 50, 20, 5]))
    assert f is not None and f.method == "rank"
    assert f.value == pytest.approx(4.475, abs=0.03)
    assert f.value_basis == "interior"


def test_forecast_moves_with_the_mass():
    low = forecast_from_buckets(build([40, 30, 20, 7, 3])).value
    mid = forecast_from_buckets(build([5, 20, 50, 20, 5])).value
    high = forecast_from_buckets(build([3, 7, 20, 30, 40])).value
    assert low < mid < high


def test_forecast_lands_inside_the_leading_bucket():
    f = forecast_from_buckets(build([5, 10, 60, 20, 5]))
    assert 4.33 <= f.value <= 4.62


def test_open_tails_do_not_need_an_assumed_value():
    """Heavy mass in the unbounded top bucket must still give a finite answer
    that sits above the last boundary."""
    f = forecast_from_buckets(build([1, 2, 7, 20, 70]))
    assert f is not None
    assert math.isfinite(f.value)
    assert f.value > 4.92


def test_probabilities_are_normalised():
    f = forecast_from_buckets(build([10, 25, 55, 25, 10]))  # sums to 125c
    assert sum(b.probability for b in f.buckets) == pytest.approx(1.0)
    assert any("sum to" in w for w in f.warnings)


# --- the two uncertainties ---------------------------------------------------


def test_band_is_the_published_uncertainty():
    """Under the rank method the band IS the uncertainty statement: the market
    says the outcome lands in [p10, p90] with 80% probability. margin and
    sigma are derived from it for compatibility."""
    f = forecast_from_buckets(build([5, 20, 50, 20, 5]))
    assert f.p10 is not None and f.p90 is not None
    assert f.p10 < f.value < f.p90
    assert f.margin_of_error == pytest.approx((f.p90 - f.p10) / 2)
    assert f.sigma == pytest.approx((f.p90 - f.p10) / 2.5631)


def test_tight_books_pin_the_value_better_than_wide_ones():
    tight = forecast_from_buckets(build([5, 20, 50, 20, 5], spread=2))
    wide = forecast_from_buckets(build([5, 20, 50, 20, 5], spread=30))
    assert wide.margin_of_error > tight.margin_of_error


def test_one_sided_books_widen_the_margin():
    two_sided = forecast_from_buckets(build([5, 20, 50, 20, 5]))
    half = [
        BucketBook(lo, hi, c, None)
        for (lo, hi), c in zip(MSFT_BOUNDS, [5, 20, 50, 20, 5])
    ]
    one_sided = forecast_from_buckets(half)
    assert one_sided.margin_of_error > two_sided.margin_of_error
    assert any("one-sided" in w for w in one_sided.warnings)


def test_low_high_bracket_the_value():
    f = forecast_from_buckets(build([5, 20, 50, 20, 5]))
    assert f.low < f.value < f.high
    assert f.high - f.low == pytest.approx(2 * f.margin_of_error)


# --- degenerate input --------------------------------------------------------


def test_no_quotes_at_all_returns_none():
    assert forecast_from_buckets(build([None] * 5)) is None


def test_too_few_buckets_returns_none():
    assert forecast_from_buckets([BucketBook(None, 4.0, 40, 44)]) is None


def test_partial_book_still_produces_an_estimate():
    f = forecast_from_buckets(build([None, 20, 50, 20, None]))
    assert f is not None and math.isfinite(f.value)
    assert any("unquoted" in w for w in f.warnings)


def test_unquoted_buckets_take_the_residual_not_a_flat_half():
    """Quoted buckets sum to ~0.9, so the two unquoted ones share ~0.1 between
    them, rather than being handed 0.5 each and swamping the distribution."""
    f = forecast_from_buckets(build([None, 20, 50, 20, None]))
    probs = [b.probability for b in f.buckets]
    assert probs[0] == pytest.approx(probs[4])
    assert probs[0] < 0.10, f"unquoted tail took {probs[0]:.0%}"
    assert probs[2] > 0.4, "the quoted leading bucket must still dominate"


def test_dead_tails_do_not_dominate_a_live_middle():
    """Reproduces the live MSFT book: penny-bid one-sided tails around a tight
    two-sided middle. The tails must not come out level with the leader."""
    f = forecast_from_buckets(
        [
            BucketBook(None, 4.04, 1, None),
            BucketBook(4.04, 4.33, 16, 28),
            BucketBook(4.33, 4.62, 44, 56),
            BucketBook(4.62, 4.92, 9, 21),
            BucketBook(4.92, None, 1, None),
        ]
    )
    probs = [b.probability for b in f.buckets]
    assert probs[2] == max(probs), "the tight 44-56 bucket must lead"
    assert probs[0] < 0.15 and probs[4] < 0.15, f"tails took {probs[0]:.0%}/{probs[4]:.0%}"
    assert 4.2 <= f.value <= 4.7


def test_all_mass_in_one_bucket_does_not_explode():
    f = forecast_from_buckets(build([1, 1, 95, 1, 1]))
    assert f is not None
    assert math.isfinite(f.value) and math.isfinite(f.margin_of_error)
    assert 4.0 <= f.value <= 5.0


def test_flat_book_falls_back_rather_than_dividing_by_zero():
    """Identical quotes everywhere say nothing about spread, so the probit
    slope is unidentifiable and the discrete path must take over."""
    f = forecast_from_buckets(build([20, 20, 20, 20, 20]))
    assert f is not None and math.isfinite(f.value)


def test_as_dict_is_serialisable():
    d = forecast_from_buckets(build([5, 20, 50, 20, 5])).as_dict()
    assert set(d) >= {"value", "margin_of_error", "low", "high", "sigma", "method"}
    assert len(d["probabilities"]) == 5
    assert all(isinstance(v, (int, float, str, list)) for v in d.values())


def test_monotonic_cdf_is_enforced():
    """Noisy quotes can imply a tiny negative probability step; the probit
    transform must not see a decreasing CDF."""
    f = forecast_from_buckets(build([30, 1, 40, 1, 28]))
    assert f is not None and math.isfinite(f.value)
