"""Live-network checks that the SDK reads real order books the right way round.

Everything else in the forecast suite feeds the algorithm hand-written numbers,
which proves the maths but cannot prove the SDK is reading the CHAIN correctly.
If the node ever flipped the sign convention on bids, every one of those tests
would still pass while the forecast silently inverted. That is the gap this
file covers.

Gated, because it needs the network and live markets carrying real orders. Run
it with:

    TN_LIVE_NODE_URL=https://gateway.mainnet.truf.network pytest tests/test_forecast_live.py

All calls are view actions, so the signing key needs no funds and controls
nothing; a throwaway is generated unless TN_LIVE_PRIVATE_KEY is set.

These assert SHAPES, not numbers. Live books move minute to minute, so pinning
an expected value would fail by tomorrow. Exact numbers belong in the unit
tests. A wrong FORMULA will pass here quite happily — this only proves the
plumbing between the SDK and the chain is connected the right way round.
"""

import os
from collections import defaultdict

import pytest

from trufnetwork_sdk_py.market_buckets import bucket_bounds_from_market_data

pytestmark = pytest.mark.skipif(
    not os.getenv("TN_LIVE_NODE_URL"),
    reason="live node not configured; set TN_LIVE_NODE_URL to run",
)

# Discovery costs one call per open market, so it is bounded. Mainnet carried
# ~110 open markets when this was written; the cap is headroom, not a target.
MAX_MARKETS_SCANNED = 500

# Candidate groups to probe for quotes before giving up. A market can tile the
# line perfectly and still have nobody quoting it, which is not a code defect,
# so candidates are ranked by how much of the line is actually quoted rather
# than by bucket count alone -- most open markets carry no orders at all.
MAX_GROUPS_PROBED = 25

# Below this many quoted buckets the forecast rests on residuals more than on
# orders, which is not what this test is trying to exercise.
MIN_QUOTED_BUCKETS = 2


def _tiles_the_line(members) -> bool:
    """One bucket open below, one open above, at least one in between."""
    types = [md["type"] for _, md, _ in members]
    return len(members) >= 3 and types.count("below") == 1 and types.count("above") == 1


def _discover_groups(client):
    """Every open market, grouped into candidate bucket sets.

    A market's buckets share a data stream and a settlement time, which is
    enough to reassemble them from chain data alone — no local config needed.
    """
    groups = defaultdict(list)
    offset = 0
    scanned = 0

    while scanned < MAX_MARKETS_SCANNED:
        page = client.list_markets(settled_filter=False, limit=100, offset=offset)
        if not page:
            break
        for market in page:
            scanned += 1
            try:
                info = client.get_market_info(market["id"])
                query_components = info.get("query_components") or b""
                if not query_components:
                    continue
                market_data = client.decode_market_data(query_components)
                bounds = bucket_bounds_from_market_data(market_data)
            except (ValueError, KeyError):
                # Legacy or non-bucket markets: not what this test is about.
                continue
            key = (market_data["stream_id"], market["settle_time"])
            groups[key].append((market["id"], market_data, bounds))
        if len(page) < 100:
            break
        offset += 100

    tiling = {k: v for k, v in groups.items() if _tiles_the_line(v)}
    # Widest first: more buckets means more of the line actually quoted.
    return sorted(tiling.values(), key=len, reverse=True)


@pytest.fixture(scope="session")
def live_client():
    from eth_account import Account

    from trufnetwork_sdk_py.client import TNClient

    key = os.getenv("TN_LIVE_PRIVATE_KEY") or Account.create().key.hex()
    return TNClient(os.environ["TN_LIVE_NODE_URL"], key)


@pytest.fixture(scope="session")
def live_forecast(live_client):
    """A real market and the forecast it implies.

    Skips rather than fails when the network has nothing quotable: an empty
    book is a fact about the market that day, not a defect in this code.
    """
    candidates = _discover_groups(live_client)
    if not candidates:
        pytest.skip("no open market on this network currently tiles the line")

    # One cheap call per bucket to find where the orders are. Ranking on this
    # rather than on bucket count matters: most open markets tile the line
    # perfectly and carry no orders whatsoever.
    ranked = []
    for members in candidates[:MAX_GROUPS_PROBED]:
        query_ids = [query_id for query_id, _, _ in members]
        quoted = 0
        for query_id in query_ids:
            best = live_client.get_best_prices(query_id, True)
            if best["best_bid"] is not None or best["best_ask"] is not None:
                quoted += 1
        if quoted >= MIN_QUOTED_BUCKETS:
            ranked.append((quoted, max(query_ids), query_ids))

    if not ranked:
        pytest.skip(
            f"no market among {min(len(candidates), MAX_GROUPS_PROBED)} tiling "
            f"candidates had {MIN_QUOTED_BUCKETS}+ quoted buckets"
        )

    # Most quoted first, then newest. Recency is only a tie-break: settled
    # markets are already excluded, and on mainnet the newest markets are
    # routinely the ones with no orders yet, so it is a poor primary signal.
    ranked.sort(reverse=True)
    for _, _, query_ids in ranked:
        forecast = live_client.get_market_forecast(query_ids)
        if forecast is not None:
            return query_ids, forecast

    pytest.skip("quoted markets found, but none yielded a usable forecast")


def _median_bucket(forecast):
    """The bucket where the implied CDF crosses 50%.

    NOT the most probable bucket: with probabilities [0.40, 0.35, 0.25] the
    leader is the first, but the cumulative only reaches half way through the
    second, so that is where the median belongs.
    """
    running = 0.0
    for bucket in forecast.buckets:
        running += bucket.probability
        if running >= 0.5:
            return bucket
    return forecast.buckets[-1]


def test_a_real_market_produces_a_forecast(live_forecast):
    query_ids, forecast = live_forecast

    assert len(query_ids) >= 3
    assert forecast.value == forecast.value, "value is NaN"
    assert forecast.method in {"rank", "discrete"}
    assert forecast.value_basis in {"interior", "tail", "unresolved"}


def test_probabilities_form_a_distribution(live_forecast):
    _, forecast = live_forecast

    probabilities = [b.probability for b in forecast.buckets]
    assert all(0.0 <= p <= 1.0 for p in probabilities)
    assert sum(probabilities) == pytest.approx(1.0)


def test_value_falls_in_the_bucket_where_the_cdf_crosses_half(live_forecast):
    """The point estimate is the median, so it must land in the median bucket.

    This is the assertion that would catch a bounds-derivation or ordering
    mistake: get the buckets in the wrong order and the value lands in the
    wrong one.
    """
    _, forecast = live_forecast
    if forecast.value_basis == "unresolved":
        pytest.skip("median unresolvable from this market's strikes")

    bucket = _median_bucket(forecast)
    if bucket.lower is not None:
        assert forecast.value >= bucket.lower
    if bucket.upper is not None:
        assert forecast.value <= bucket.upper


def test_band_brackets_the_value(live_forecast):
    _, forecast = live_forecast
    if forecast.p10 is None or forecast.p90 is None:
        pytest.skip("band unresolvable from this market's strikes")

    assert forecast.p10 <= forecast.value <= forecast.p90
    assert forecast.margin_of_error > 0


def test_buckets_are_ordered_and_tile_the_line(live_forecast):
    """Assembly must hand the algorithm an ascending, gap-free ladder."""
    _, forecast = live_forecast
    buckets = forecast.buckets

    assert buckets[0].lower is None, "bottom bucket should be open below"
    assert buckets[-1].upper is None, "top bucket should be open above"
    for lower, upper in zip(buckets, buckets[1:]):
        assert lower.upper == upper.lower, "gap or overlap between buckets"


def test_bid_sign_convention_still_holds(live_client, live_forecast):
    """The canary.

    get_order_book marks bids with a NEGATIVE price; get_best_prices reports
    the same bid as POSITIVE. Two independent node paths for one fact, so if
    either convention ever changes they stop agreeing here — loudly — instead
    of silently inverting every one-sided bucket in the forecast.
    """
    query_ids, _ = live_forecast

    checked = 0
    for query_id in query_ids:
        for outcome in (True, False):
            bids, asks = live_client._order_book_ladders(query_id, outcome)
            best = live_client.get_best_prices(query_id, outcome)

            for level in bids + asks:
                assert 0 < level.price < 100, (
                    f"price {level.price} outside the 1-99 cent convention"
                )
                assert level.size > 0

            if bids and best["best_bid"] is not None:
                assert max(l.price for l in bids) == best["best_bid"]
                checked += 1
            if asks and best["best_ask"] is not None:
                assert min(l.price for l in asks) == best["best_ask"]
                checked += 1

    if not checked:
        pytest.skip("no resting orders to cross-check the sign convention against")
