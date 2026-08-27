"""Tests for the SDK-side glue around the forecast algorithm.

The algorithm itself is a verbatim mirror of upstream and is covered by
test_forecast.py / test_forecast_depth.py. What is tested here is only what
the SDK adds: deriving bucket bounds from decoded market data, and assembling
a market's order books into a forecast.
"""

import pytest

from trufnetwork_sdk_py.forecast import BookLevel, BucketDepth, forecast_from_depth
from trufnetwork_sdk_py.market_buckets import bucket_bounds_from_market_data

# --- bucket bounds from decoded market data -----------------------------------


def test_below_market_is_the_open_bottom_bucket():
    assert bucket_bounds_from_market_data(
        {"type": "below", "thresholds": ["4.04"]}
    ) == (None, 4.04)


def test_above_market_is_the_open_top_bucket():
    assert bucket_bounds_from_market_data(
        {"type": "above", "thresholds": ["4.92"]}
    ) == (4.92, None)


def test_between_market_is_an_interior_bucket():
    assert bucket_bounds_from_market_data(
        {"type": "between", "thresholds": ["4.33", "4.62"]}
    ) == (4.33, 4.62)


def test_change_between_market_is_an_interior_bucket():
    assert bucket_bounds_from_market_data(
        {"type": "change_between", "thresholds": ["2.0", "3.0"]}
    ) == (2.0, 3.0)


def test_change_between_open_tails_come_back_as_none():
    """An open tail arrives as an empty string holding its slot, not as a
    shorter list. Dropping the empty entry would slide the surviving bound into
    the other position and invert the bucket."""
    assert bucket_bounds_from_market_data(
        {"type": "change_between", "thresholds": ["", "1.0"]}
    ) == (None, 1.0)
    assert bucket_bounds_from_market_data(
        {"type": "change_between", "thresholds": ["4.0", ""]}
    ) == (4.0, None)


def test_change_between_needs_at_least_one_bound():
    with pytest.raises(ValueError, match="at least one bound"):
        bucket_bounds_from_market_data(
            {"type": "change_between", "thresholds": ["", ""]}
        )


def test_change_between_needs_both_slots_even_when_one_is_open():
    """A one-element list is a market that was decoded wrong, not an open tail."""
    with pytest.raises(ValueError, match="threshold slot"):
        bucket_bounds_from_market_data(
            {"type": "change_between", "thresholds": ["2.0"]}
        )


def test_inverted_or_empty_change_between_bucket_is_rejected():
    for lower, upper in (("3.0", "3.0"), ("3.0", "2.0")):
        with pytest.raises(ValueError, match="lower < upper"):
            bucket_bounds_from_market_data(
                {"type": "change_between", "thresholds": [lower, upper]}
            )


def test_change_between_buckets_tile_without_overlapping():
    """The bounds are half-open, so each bucket's upper edge is the next one's
    lower edge and a change landing there belongs to exactly one of them."""
    edges = ["1.0", "2.0", "3.0", "4.0"]
    strikes = (
        [("", edges[0])]
        + [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
        + [(edges[-1], "")]
    )
    bounds = [
        bucket_bounds_from_market_data(
            {"type": "change_between", "thresholds": [lo, hi]}
        )
        for lo, hi in strikes
    ]
    assert bounds[0][0] is None
    assert bounds[-1][1] is None
    for (_, upper), (lower, _) in zip(bounds, bounds[1:]):
        assert upper == lower


def test_equals_market_is_target_plus_minus_tolerance():
    """Its thresholds are (target, tolerance), NOT (lower, upper). Reading them
    positionally the way `between` is read would yield the bucket (5.25, 0.10):
    inverted, and silently wrong rather than loud."""
    lower, upper = bucket_bounds_from_market_data(
        {"type": "equals", "thresholds": ["5.25", "0.10"]}
    )
    assert (lower, upper) == pytest.approx((5.15, 5.35))
    assert lower < upper


def test_non_finite_thresholds_are_rejected():
    """float() accepts these without complaint; left alone they surface as a NaN
    forecast rather than as an unreadable market."""
    for value in ("nan", "inf", "+inf", "-inf"):
        with pytest.raises(ValueError, match="not finite"):
            bucket_bounds_from_market_data({"type": "below", "thresholds": [value]})


def test_inverted_or_empty_between_bucket_is_rejected():
    """Bounds are half-open [lower, upper): equal bounds are empty and inverted
    ones can never hold an outcome."""
    for thresholds in (["4.62", "4.33"], ["4.33", "4.33"]):
        with pytest.raises(ValueError, match="lower < upper"):
            bucket_bounds_from_market_data(
                {"type": "between", "thresholds": thresholds}
            )


def test_non_positive_equals_tolerance_is_rejected():
    for tolerance in ("0", "-0.10"):
        with pytest.raises(ValueError, match="positive tolerance"):
            bucket_bounds_from_market_data(
                {"type": "equals", "thresholds": ["5.25", tolerance]}
            )


def test_collapsed_or_overflowing_equals_bounds_are_rejected():
    """A positive tolerance is not enough. Absorbed by a large target it leaves
    both edges on the same value, and near the float limits the sum overflows."""
    assert 1e300 - 1e-300 == 1e300 + 1e-300, "the collapse, demonstrated"
    for thresholds in (["1e300", "1e-300"], ["1.7e308", "1.7e308"]):
        with pytest.raises(ValueError, match="usable bucket"):
            bucket_bounds_from_market_data(
                {"type": "equals", "thresholds": thresholds}
            )


def test_unknown_market_type_is_rejected():
    with pytest.raises(ValueError, match="cannot derive bucket bounds"):
        bucket_bounds_from_market_data({"type": "unknown", "thresholds": []})


def test_missing_thresholds_are_rejected():
    with pytest.raises(ValueError, match="threshold"):
        bucket_bounds_from_market_data({"type": "between", "thresholds": ["4.33"]})


# --- client assembly ----------------------------------------------------------

# The live mainnet MSFT book, as five separate markets. Bounds are carried in
# each bucket's own query_components, exactly as on chain. Quotes are
# (yes_bid, yes_ask) in cents; None means nothing resting on that side.
#
# Every bucket carries the same `timestamp`, which is what makes them one
# market: the bindings decode it from argument 2 of the binary action, and
# get_market_forecast refuses a bucket set it cannot read it from.
OBSERVED_AT = 1700000000

MSFT_MARKETS = {
    101: ({"type": "below", "thresholds": ["4.04"], "timestamp": OBSERVED_AT}, (1, None)),
    102: ({"type": "between", "thresholds": ["4.04", "4.33"], "timestamp": OBSERVED_AT}, (16, 28)),
    103: ({"type": "between", "thresholds": ["4.33", "4.62"], "timestamp": OBSERVED_AT}, (44, 56)),
    104: ({"type": "between", "thresholds": ["4.62", "4.92"], "timestamp": OBSERVED_AT}, (9, 21)),
    105: ({"type": "above", "thresholds": ["4.92"], "timestamp": OBSERVED_AT}, (1, None)),
}

# Big enough that even a 1c level clears DEPTH_MIN_SIDE_NOTIONAL_USD, so the
# dust floor never silently empties a side these tests meant to be quoted.
SIZE = 1000


def order_book(bid, ask):
    """SDK order-book rows: bids carry a NEGATIVE price, asks a positive one."""
    rows = []
    if bid is not None:
        rows.append({"price": -bid, "amount": SIZE})
    if ask is not None:
        rows.append({"price": ask, "amount": SIZE})
    return rows


def fake_client(markets=MSFT_MARKETS, query_components=True, no_books=None):
    """A TNClient whose network calls are stubbed.

    Built with __new__ so no connection is attempted: this exercises the
    assembly logic (bounds, sorting, layout checks) with no node.
    """
    from trufnetwork_sdk_py.client import TNClient

    client = TNClient.__new__(TNClient)
    client.get_market_info = lambda query_id: {
        "query_components": str(query_id).encode() if query_components else b""
    }
    client.decode_market_data = lambda qc: markets[int(qc)][0]

    def _order_book(query_id, outcome):
        if outcome:
            return order_book(*markets[query_id][1])
        return (no_books or {}).get(query_id, [])

    client.get_order_book = _order_book
    return client


def depths(markets=MSFT_MARKETS):
    """The same books, built directly, to compare the assembled path against."""
    out = []
    for query_id, (market_data, (bid, ask)) in sorted(markets.items()):
        lower, upper = bucket_bounds_from_market_data(market_data)
        out.append(
            BucketDepth(
                lower=lower,
                upper=upper,
                yes_bids=[BookLevel(bid, SIZE)] if bid is not None else [],
                yes_asks=[BookLevel(ask, SIZE)] if ask is not None else [],
                query_id=query_id,
            )
        )
    return out


def test_client_forecast_matches_a_direct_call():
    """Assembly must not change the answer: same books in, same number out."""
    assembled = fake_client().get_market_forecast(list(MSFT_MARKETS))
    direct = forecast_from_depth(depths())

    assert assembled.value == pytest.approx(direct.value)
    assert assembled.p10 == pytest.approx(direct.p10)
    assert assembled.p90 == pytest.approx(direct.p90)
    assert [b.probability for b in assembled.buckets] == pytest.approx(
        [b.probability for b in direct.buckets]
    )


def test_forecast_lands_inside_the_leading_bucket():
    """The live MSFT book: the tight 44-56 bucket leads, so the value belongs
    inside it."""
    f = fake_client().get_market_forecast(list(MSFT_MARKETS))

    probs = [b.probability for b in f.buckets]
    assert probs[2] == max(probs)
    assert 4.33 <= f.value <= 4.62


def test_no_side_liquidity_is_consolidated_into_the_estimate():
    """A resting BUY NO at p is hittable by a BUY YES at 100-p, so NO depth is
    executable YES depth. Adding a NO bid must therefore supply the missing YES
    ask and stop the bucket reading as one-sided."""
    bare = fake_client().get_market_forecast(list(MSFT_MARKETS))
    # A NO bid at 84 mirrors to a YES ask at 16 on the open bottom bucket.
    with_no = fake_client(
        no_books={101: [{"price": -84, "amount": SIZE}]}
    ).get_market_forecast(list(MSFT_MARKETS))

    assert bare.buckets[0].one_sided
    assert not with_no.buckets[0].one_sided
    assert with_no.buckets[0].confidence > bare.buckets[0].confidence


def test_query_ids_may_be_given_in_any_order():
    """Buckets are sorted by bound here, so callers need not track which
    query_id is the bottom of the line."""
    ordered = fake_client().get_market_forecast([101, 102, 103, 104, 105])
    shuffled = fake_client().get_market_forecast([103, 105, 101, 104, 102])

    assert shuffled.value == pytest.approx(ordered.value)
    assert [b.query_id for b in shuffled.buckets] == [101, 102, 103, 104, 105]


def test_gap_in_the_bucket_layout_is_reported_not_hidden():
    """A market missing an interior bucket still gets an estimate, but the
    caller must be able to see that the line was not fully tiled."""
    f = fake_client().get_market_forecast([101, 102, 104, 105])

    assert f is not None
    assert any("gap" in w for w in f.warnings)


def test_layout_warning_when_the_line_is_not_open_ended():
    """Interior buckets only: nothing covers the tails, so the mass beyond them
    is unrepresented and the caller should know."""
    f = fake_client().get_market_forecast([102, 103, 104])

    assert any("not open below" in w for w in f.warnings)
    assert any("not open above" in w for w in f.warnings)


def test_single_bucket_is_rejected():
    with pytest.raises(ValueError, match="at least 2"):
        fake_client().get_market_forecast([103])


def test_duplicate_query_ids_are_rejected():
    """A repeated bucket would have its probability counted twice, quietly
    reshaping the distribution rather than failing."""
    with pytest.raises(ValueError, match="duplicate"):
        fake_client().get_market_forecast([101, 102, 103, 103])


# A second, independently valid bucket set, on a different stream. Each set
# forecasts fine alone; the two together describe unrelated events.
OTHER_MARKETS = {
    query_id + 100: ({**market_data, "stream_id": "other"}, quotes)
    for query_id, (market_data, quotes) in MSFT_MARKETS.items()
}


def test_buckets_from_two_different_markets_are_rejected():
    """Normalising across two events would divide one market's probabilities by
    the other's total and return a confident number about nothing. Both sets are
    individually valid, so nothing but the identity check catches this."""
    both = {**MSFT_MARKETS, **OTHER_MARKETS}
    with pytest.raises(ValueError, match="different event"):
        fake_client(both).get_market_forecast(list(both))


def test_markets_differing_only_in_the_time_they_observe_are_rejected():
    """The case settle_time alone cannot see: same provider, same stream, same
    settlement, but observing the stream a day apart.

    Both sets carry a readable ``timestamp``; they differ only in its value,
    which is the whole point of comparing it.
    """
    later = {
        query_id + 200: ({**market_data, "timestamp": 1700086400}, quotes)
        for query_id, (market_data, quotes) in MSFT_MARKETS.items()
    }
    earlier = {
        query_id: ({**market_data, "timestamp": 1700000000}, quotes)
        for query_id, (market_data, quotes) in MSFT_MARKETS.items()
    }
    both = {**earlier, **later}
    with pytest.raises(ValueError, match="different event"):
        fake_client(both).get_market_forecast(list(both))


def test_markets_differing_only_in_the_block_they_freeze_are_rejected():
    """`frozen_at` is the other query field settle_time cannot see: the same
    question asked of pinned data and of latest data is two different queries."""
    pinned = {
        query_id + 300: ({**market_data, "frozen_at": 987654}, quotes)
        for query_id, (market_data, quotes) in MSFT_MARKETS.items()
    }
    latest = {
        query_id: ({**market_data, "frozen_at": None}, quotes)
        for query_id, (market_data, quotes) in MSFT_MARKETS.items()
    }
    both = {**latest, **pinned}
    with pytest.raises(ValueError, match="different event"):
        fake_client(both).get_market_forecast(list(both))


def test_markets_differing_only_in_their_bridge_are_rejected():
    """The bridge is the one identity field outside the query components: it is
    a create_market argument, so an identical question can be collateralised two
    ways. Those are separate markets with separate books."""
    other_bridge = {
        query_id + 500: (market_data, quotes)
        for query_id, (market_data, quotes) in MSFT_MARKETS.items()
    }
    both = {**MSFT_MARKETS, **other_bridge}
    client = fake_client(both)
    client.get_market_info = lambda query_id: {
        "query_components": str(query_id).encode(),
        "bridge": "eth_truf" if query_id >= 500 else "eth_usdc",
    }
    with pytest.raises(ValueError, match="different event"):
        client.get_market_forecast(list(both))


YEAR = 31536000
MONTH = 2592000

# A percent-change bucket set over the same stream and observation time as
# MSFT_MARKETS, struck in percent rather than in the stream's own units.
CHANGE_MARKETS = {
    601: ({"type": "change_between", "thresholds": ["", "2"],
           "timestamp": OBSERVED_AT, "time_interval": YEAR}, (1, None)),
    602: ({"type": "change_between", "thresholds": ["2", "3"],
           "timestamp": OBSERVED_AT, "time_interval": YEAR}, (16, 28)),
    603: ({"type": "change_between", "thresholds": ["3", ""],
           "timestamp": OBSERVED_AT, "time_interval": YEAR}, (44, 56)),
}


def test_change_market_set_forecasts_on_its_own():
    """The identity check must separate the scales without refusing a set that
    is entirely percent-change."""
    f = fake_client(CHANGE_MARKETS).get_market_forecast(list(CHANGE_MARKETS))

    assert f is not None
    assert [b.query_id for b in f.buckets] == [601, 602, 603]


def test_change_markets_differing_only_in_their_interval_are_rejected():
    """Year-over-year and month-over-month over the same stream, observed at the
    same moment, settling at the same moment. Every other identity field
    matches, so only ``time_interval`` can tell these two events apart."""
    monthly = {
        query_id + 30: ({**market_data, "time_interval": MONTH}, quotes)
        for query_id, (market_data, quotes) in CHANGE_MARKETS.items()
    }
    both = {**CHANGE_MARKETS, **monthly}
    with pytest.raises(ValueError, match="different event"):
        fake_client(both).get_market_forecast(list(both))


def test_change_markets_differing_only_in_their_index_base_are_rejected():
    """A different base date measures a different change on a composed stream,
    where the base does not cancel out of the ratio."""
    based = {
        query_id + 60: ({**market_data, "base_time": 1600000000}, quotes)
        for query_id, (market_data, quotes) in CHANGE_MARKETS.items()
    }
    both = {**CHANGE_MARKETS, **based}
    with pytest.raises(ValueError, match="different event"):
        fake_client(both).get_market_forecast(list(both))


def test_percent_change_bucket_cannot_join_a_set_struck_in_stream_units():
    """The collision that is actually reachable on mainnet: the index streams
    these markets are built on already carry ``value_in_range`` sets observing
    at their own settle time exactly as a change market does. Only the interval
    separates them, and bounds around 4.04 must never be normalised against
    bounds around 2.5."""
    both = {**MSFT_MARKETS, **CHANGE_MARKETS}
    with pytest.raises(ValueError, match="different event"):
        fake_client(both).get_market_forecast(list(both))


def test_change_market_without_a_readable_interval_is_rejected():
    """A change market always carries a positive ``time_interval`` -- the node
    action refuses to be created without one. Missing here means the bindings
    were built against an sdk-go predating the field, which would leave this SDK
    accepting bucket sets sdk-go and sdk-js both reject."""
    stale = {
        query_id: ({k: v for k, v in market_data.items() if k != "time_interval"}, quotes)
        for query_id, (market_data, quotes) in CHANGE_MARKETS.items()
    }
    with pytest.raises(ValueError, match="no readable time_interval"):
        fake_client(stale).get_market_forecast(list(stale))

    # An explicit None is the same failure, and must not slip through as a value.
    nulled = {
        query_id: ({**market_data, "time_interval": None}, quotes)
        for query_id, (market_data, quotes) in CHANGE_MARKETS.items()
    }
    with pytest.raises(ValueError, match="no readable time_interval"):
        fake_client(nulled).get_market_forecast(list(nulled))


def test_value_markets_need_no_interval():
    """Only a change market carries one. Requiring it of every type would refuse
    every well-formed 040 bucket set."""
    f = fake_client().get_market_forecast(list(MSFT_MARKETS))

    assert f is not None


def test_unreadable_query_timestamp_is_rejected():
    """A None timestamp compares equal across buckets, so two malformed markets
    would collide on it and match each other. The key being ABSENT is different
    -- that is the current bindings not emitting it, which every other test in
    this file relies on."""
    unreadable = {
        query_id: ({**market_data, "timestamp": None}, quotes)
        for query_id, (market_data, quotes) in MSFT_MARKETS.items()
    }
    with pytest.raises(ValueError, match="no readable query timestamp"):
        fake_client(unreadable).get_market_forecast(list(unreadable))


def test_absent_timestamp_key_is_refused_like_an_unreadable_one():
    """A decoded market with no timestamp field at all means the C bindings were
    built against an sdk-go predating it.

    Waving that through would leave this SDK accepting bucket sets that sdk-go
    and sdk-js both reject, so it fails with a hint at the rebuild instead.
    """
    stale = {
        query_id: ({k: v for k, v in market_data.items() if k != "timestamp"}, quotes)
        for query_id, (market_data, quotes) in MSFT_MARKETS.items()
    }
    assert "timestamp" not in stale[101][0]
    with pytest.raises(ValueError, match="make gopy_build"):
        fake_client(stale).get_market_forecast(list(stale))


def test_each_of_those_sets_still_forecasts_on_its_own():
    """The identity check must reject the mixture without rejecting either half."""
    assert fake_client().get_market_forecast(list(MSFT_MARKETS)) is not None
    assert fake_client(OTHER_MARKETS).get_market_forecast(list(OTHER_MARKETS)) is not None


def test_market_without_query_components_is_rejected():
    """Legacy markets carry no bounds, and guessing them would be worse than
    failing."""
    with pytest.raises(ValueError, match="query_components"):
        fake_client(query_components=False).get_market_forecast([101, 102])


def test_unquoted_market_yields_no_forecast():
    dead = {qid: (md, (None, None)) for qid, (md, _) in MSFT_MARKETS.items()}
    assert fake_client(dead).get_market_forecast(list(dead)) is None
