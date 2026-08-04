"""Tests for the depth-weighted forecast path.

The depth path consolidates the YES and NO ladders inside the module (the
inversion is executable via exact-inverse mint/burn matching, verified on
testnet 2026-08-03) and weights each bucket by committed notional rather than
reading best quotes alone.
"""

import math

import pytest

from trufnetwork_sdk_py.forecast import (
    BookLevel,
    BucketBook,
    BucketDepth,
    bucket_estimate_from_depth,
    forecast_from_buckets,
    forecast_from_depth,
)

# MSFT-shaped bounds, as on mainnet.
BOUNDS = [(None, 4.04), (4.04, 4.33), (4.33, 4.62), (4.62, 4.92), (4.92, None)]


def ladder(mid, size=100, levels=3, spread=2.0, step=1.0):
    """Symmetric YES ladders plus the exact NO mirror our MM would post."""
    yb = [BookLevel(round(mid - spread / 2 - k * step, 4), size) for k in range(levels)]
    ya = [BookLevel(round(mid + spread / 2 + k * step, 4), size) for k in range(levels)]
    nb = [BookLevel(round(100 - l.price, 4), l.size) for l in ya]
    na = [BookLevel(round(100 - l.price, 4), l.size) for l in yb]
    return yb, ya, nb, na


def build(mids, sizes=None, bounds=BOUNDS):
    out = []
    for i, ((lo, hi), m) in enumerate(zip(bounds, mids)):
        if m is None:
            out.append(BucketDepth(lo, hi))
            continue
        yb, ya, nb, na = ladder(m, size=(sizes[i] if sizes else 100))
        out.append(BucketDepth(lo, hi, yb, ya, nb, na))
    return out


# --- consolidation ----------------------------------------------------------


def test_no_bid_becomes_executable_ask():
    d = BucketDepth(None, 4.04, no_bids=[BookLevel(83, 50)])
    asks = d.consolidated_asks()
    assert asks and asks[0].price == pytest.approx(17.0)
    assert asks[0].size == 50


def test_no_ask_becomes_executable_bid():
    d = BucketDepth(None, 4.04, no_asks=[BookLevel(95, 40)])
    bids = d.consolidated_bids()
    assert bids and bids[0].price == pytest.approx(5.0)


def test_consolidated_sides_are_sorted_best_first():
    d = BucketDepth(
        None, 4.04,
        yes_bids=[BookLevel(30, 10)],
        yes_asks=[BookLevel(40, 10)],
        no_bids=[BookLevel(65, 10)],   # -> ask at 35, better than the YES ask
        no_asks=[BookLevel(68, 10)],   # -> bid at 32, better than the YES bid
    )
    assert d.consolidated_bids()[0].price == pytest.approx(32.0)
    assert d.consolidated_asks()[0].price == pytest.approx(35.0)


# --- the walk mid -----------------------------------------------------------


def test_symmetric_depth_gives_the_mid():
    yb, ya, nb, na = ladder(40.0)
    p, quality, n_usd, one_sided, quoted = bucket_estimate_from_depth(
        BucketDepth(None, 4.04, yb, ya, nb, na)
    )
    assert p == pytest.approx(0.40, abs=1e-6)
    assert quoted and not one_sided
    assert n_usd > 0


def test_ladder_imbalance_does_not_move_the_price():
    """Size imbalance is denomination and inventory, not opinion (issue #36):
    on this venue all resting flow is the MM's own, so extra size behind the
    walk must leave the estimate exactly where it was."""
    yb, ya, nb, na = ladder(40.0)
    heavy_bids = [BookLevel(l.price, l.size * 10) for l in yb]
    p_heavy = bucket_estimate_from_depth(
        BucketDepth(None, 4.04, heavy_bids, ya, [], [])
    )[0]
    p_flat = bucket_estimate_from_depth(
        BucketDepth(None, 4.04, yb, ya, [], [])
    )[0]
    assert p_heavy == pytest.approx(p_flat)


def test_estimate_stays_between_best_bid_and_ask():
    """The book only pins the truth to [best bid, best ask]; a published
    probability outside the executable bracket is dutch-bookable. The old
    microprice gave 18.4 on this real NVDA bucket against a best ask of 17."""
    d = BucketDepth(
        None, 1.91,
        yes_bids=[BookLevel(4, 386), BookLevel(3, 519), BookLevel(1, 1558)],
        no_bids=[BookLevel(83, 6), BookLevel(81, 25)],
        no_asks=[BookLevel(97, 3), BookLevel(99, 20)],
    )
    p = bucket_estimate_from_depth(d)[0]
    bids, asks = d.consolidated_bids(), d.consolidated_asks()
    assert bids[0].price / 100.0 <= p <= asks[0].price / 100.0


def test_fragmented_side_is_priced_not_dropped():
    """$5.77 of real asks split across two sub-$5 levels must still price the
    side (the floor is on the side total, never per level), so splitting an
    order into small clips cannot silence a side."""
    d = BucketDepth(
        None, 1.91,
        yes_bids=[BookLevel(4, 386)],
        no_bids=[BookLevel(83, 6), BookLevel(81, 25)],  # asks 17 ($1.02), 19 ($4.75)
    )
    p, quality, n_usd, one_sided, quoted = bucket_estimate_from_depth(d)
    assert quoted and not one_sided
    # sell $5 at 4c; buy $5 = $1.02 at 17 then $3.98 at 19 -> 18.59; mid 11.3
    assert p == pytest.approx(0.113, abs=0.001)


def test_size_behind_the_walk_is_weightless():
    """100k shares added at 1c behind the first $5 of bids must not move the
    estimate by a single bit."""
    yb, ya, nb, na = ladder(40.0)
    base = bucket_estimate_from_depth(BucketDepth(None, 4.04, yb, ya, nb, na))[0]
    spammed = list(yb) + [BookLevel(1, 100_000)]
    p = bucket_estimate_from_depth(BucketDepth(None, 4.04, spammed, ya, nb, na))[0]
    assert p == base


def test_thin_touch_walks_to_the_real_depth():
    """A $1.68 best ask cannot speak for the side alone: the $5 walk carries
    into the next level, blending 42 and 45 by their committed dollars."""
    d = BucketDepth(
        2.06, 2.21,
        yes_bids=[BookLevel(30, 7), BookLevel(29, 54), BookLevel(27, 58)],
        yes_asks=[BookLevel(42, 4), BookLevel(45, 44)],
    )
    p = bucket_estimate_from_depth(d)[0]
    # sell $5: $2.10 at 30 + $2.90 at 29 = 29.42; buy $5: $1.68 at 42 +
    # $3.32 at 45 = 43.99; mid 36.7
    assert p == pytest.approx(0.367, abs=0.001)


def test_confidence_is_standardised_within_the_market():
    """Confidence compares each bucket to its OWN market's median depth, so a
    bucket at typical depth earns the full spread quality and a bucket at a
    fraction of typical depth is discounted proportionally. No external
    dollar constant is involved, and one whale bucket cannot crush the rest
    because the standard is the median."""
    b = build([62.5, 31.25, 6.25],
              sizes=[500, 500, 20],
              bounds=[(None, 1.0), (1.0, 2.0), (2.0, None)])
    f = forecast_from_depth(b)
    confs = [e.confidence for e in f.buckets]
    assert confs[0] == pytest.approx(confs[1])
    assert confs[2] < confs[1] * 0.2, "the thin bucket must be discounted"

    whale = build([62.5, 31.25, 6.25],
                  sizes=[500, 50000, 500],
                  bounds=[(None, 1.0), (1.0, 2.0), (2.0, None)])
    fw = forecast_from_depth(whale)
    assert fw.buckets[0].confidence == pytest.approx(confs[0], rel=0.05), (
        "a whale in one bucket must not crush its siblings' confidence"
    )


# --- the issue #36 book, frozen ---------------------------------------------

# Live NVDA EPS book, 2026-08-03. Under the old share-weighted microprice the
# five raw estimates summed to 1.359 and two buckets priced above their own
# best ask. The walk mid must keep every bucket inside its touch and the raw
# sum near 1 (spread-wide, not ladder-wide).

NVDA_FROZEN = [
    BucketDepth(None, 1.91,
                yes_bids=[BookLevel(4, 386), BookLevel(3, 519), BookLevel(1, 1558)],
                no_bids=[BookLevel(83, 6), BookLevel(81, 25)],
                no_asks=[BookLevel(97, 3), BookLevel(99, 20)]),
    BucketDepth(1.91, 2.06,
                yes_bids=[BookLevel(17, 96), BookLevel(16, 18), BookLevel(14, 122)],
                no_bids=[BookLevel(70, 19), BookLevel(68, 29)],
                no_asks=[BookLevel(84, 5)]),
    BucketDepth(2.06, 2.21,
                yes_bids=[BookLevel(30, 7), BookLevel(29, 54), BookLevel(27, 58)],
                yes_asks=[BookLevel(42, 4), BookLevel(45, 44)],
                no_bids=[BookLevel(57, 7), BookLevel(55, 28)],
                no_asks=[BookLevel(70, 16)]),
    BucketDepth(2.21, 2.35,
                yes_bids=[BookLevel(15, 62), BookLevel(14, 111), BookLevel(12, 130)],
                yes_asks=[BookLevel(27, 35)],
                no_bids=[BookLevel(72, 16), BookLevel(70, 29)],
                no_asks=[BookLevel(99, 6)]),
    BucketDepth(2.35, None,
                yes_bids=[BookLevel(4, 499), BookLevel(3, 667), BookLevel(1, 2000)],
                no_bids=[BookLevel(75, 37), BookLevel(74, 24), BookLevel(73, 51)],
                no_asks=[BookLevel(97, 3), BookLevel(99, 20)]),
]


def test_frozen_book_every_bucket_inside_its_touch():
    for d in NVDA_FROZEN:
        p = bucket_estimate_from_depth(d)[0]
        bids, asks = d.consolidated_bids(), d.consolidated_asks()
        assert bids[0].price / 100.0 <= p <= asks[0].price / 100.0, d.lower


def test_frozen_book_raw_sum_is_spread_wide_not_inflated():
    raw = [bucket_estimate_from_depth(d)[0] for d in NVDA_FROZEN]
    total = sum(raw)
    lo = sum(d.consolidated_bids()[0].price for d in NVDA_FROZEN) / 100.0
    hi = sum(d.consolidated_asks()[0].price for d in NVDA_FROZEN) / 100.0
    assert lo <= total <= hi
    assert total < 1.10, f"was 1.359 under the microprice, got {total:.3f}"


# --- griefing ---------------------------------------------------------------


def test_dust_ladder_is_weightless():
    """A 1-share 90c bid on a dead tail moved the old estimator by 8 units.
    Summed over the full book it is $0.90, under the side floor, so absent."""
    base = build([45, 5, 1, 5, 45],
                 bounds=[(None, -2.0), (-2.0, -1.0), (-1.0, 1.0), (1.0, 2.0), (2.0, None)])
    f0 = forecast_from_depth(base)
    griefed = list(base)
    griefed[4] = BucketDepth(2.0, None, yes_bids=[BookLevel(90, 1)])
    f1 = forecast_from_depth(griefed)
    # the dusted bucket contributes exactly what an unquoted one would
    assert f1.value == pytest.approx(
        forecast_from_depth(base[:4] + [BucketDepth(2.0, None)]).value
    )
    assert abs(f1.value - f0.value) < abs(0.0 - 8.0), "must not swing like before"


def test_real_size_at_the_same_price_does_count():
    base = build([45, 5, 1, 5, 45],
                 bounds=[(None, -2.0), (-2.0, -1.0), (-1.0, 1.0), (1.0, 2.0), (2.0, None)])
    sized = list(base)
    sized[4] = BucketDepth(2.0, None, yes_bids=[BookLevel(90, 50)])  # $45 resting
    f0 = forecast_from_depth(base)
    f1 = forecast_from_depth(sized)
    assert f1.value != pytest.approx(f0.value), "a funded quote must matter"


# --- degenerate input -------------------------------------------------------


def test_all_empty_returns_none():
    assert forecast_from_depth(
        [BucketDepth(lo, hi) for lo, hi in BOUNDS]
    ) is None


def test_one_sided_bucket_survives():
    b = build([62.5, 31.25, None],
              bounds=[(None, 1.0), (1.0, 2.0), (2.0, None)])
    b[2] = BucketDepth(2.0, None, no_bids=[BookLevel(93, 100)])  # ask-only after inversion
    f = forecast_from_depth(b)
    assert f is not None and math.isfinite(f.value)


def test_crossed_consolidated_touch_is_unpriced():
    """YES bid 61.5 vs NO bid 45 -> consolidated ask 55 < bid 61.5: the
    arbitrage state. Must be quarantined, not averaged."""
    b = build([62.5, 31.25, 6.25],
              bounds=[(None, 1.0), (1.0, 2.0), (2.0, None)])
    crossed = BucketDepth(
        None, 1.0,
        yes_bids=[BookLevel(61.5, 100)],
        yes_asks=[],
        no_bids=[BookLevel(45, 100)],   # -> consolidated ask at 55, crossed
        no_asks=[],
    )
    f = forecast_from_depth([crossed] + b[1:])
    assert any("crossed" in w for w in f.warnings)


def test_matches_quote_path_on_symmetric_books():
    """On a symmetric mirrored book the depth path and the best-quote path
    must agree on the probabilities (same mids, same residuals)."""
    depth = build([62.5, 31.25, 6.25],
                  bounds=[(None, 65000.0), (65000.0, 70000.0), (70000.0, None)])
    quotes = [
        BucketBook(lo, hi, m - 1, m + 1)
        for (lo, hi), m in zip(
            [(None, 65000.0), (65000.0, 70000.0), (70000.0, None)],
            [62.5, 31.25, 6.25],
        )
    ]
    fd = forecast_from_depth(depth)
    fq = forecast_from_buckets(quotes)
    for a, b in zip(fd.buckets, fq.buckets):
        assert a.probability == pytest.approx(b.probability, abs=1e-9)
    assert fd.value == pytest.approx(fq.value, abs=1e-6)
