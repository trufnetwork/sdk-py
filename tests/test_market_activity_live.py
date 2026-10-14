"""Live-network check that get_market_activity reads the node action from a real
network and that the figures it returns hang together.

The unit tests prove the forwarding and the decoding of the binding's JSON, and
the node's own tests prove the action's definition on a local chain. What they
cannot prove is that a live network serves the action through the whole stack,
Python to Go to the node, and filters the window the way the definition says.
That is the gap this file covers.

Gated, because it needs a network carrying markets with real fills. Run it
with:

    TN_LIVE_NODE_URL=https://gateway.mainnet.truf.network pytest tests/test_market_activity_live.py

The network must run a node carrying get_market_activity (node migration 058).
The action is a view, so the signing key needs no funds and controls nothing; a
throwaway is generated unless TN_LIVE_PRIVATE_KEY is set.

These assert INVARIANTS, not numbers. The node trims order events once they are
indexed, so figures pinned here would drift.
"""

import os
import time

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TN_LIVE_NODE_URL"),
    reason="live node not configured; set TN_LIVE_NODE_URL to run",
)

# How far back the suite looks for fills.
ACTIVITY_WINDOW_SECONDS = 30 * 24 * 3600

# Discovery reads the action once per market, newest market first, so it is
# bounded.
MAX_MARKETS_SCANNED = 100

# A live market can take a fill, or lose old events to a trim, between two
# reads. A check that needs several reads to agree retries this many times.
STABLE_READ_ATTEMPTS = 3

# No market has this id: query_id is an INT and this is its largest value.
MISSING_MARKET = 2_147_483_647

TO_TS = int(time.time())
FROM_TS = TO_TS - ACTIVITY_WINDOW_SECONDS


@pytest.fixture(scope="module")
def live_client():
    from eth_account import Account

    from trufnetwork_sdk_py.client import TNClient

    key = os.getenv("TN_LIVE_PRIVATE_KEY") or Account.create().key.hex()
    return TNClient(os.environ["TN_LIVE_NODE_URL"], key)


def _fills(activity) -> dict:
    """The part of an activity that depends only on the fills in the window.

    Coverage is left out: it moves whenever the node trims old events.
    """
    return {
        key: value
        for key, value in activity.items()
        if key not in ("coverage_from_block", "coverage_complete")
    }


@pytest.fixture(scope="module")
def market_with_fills(live_client):
    """The newest market with a fill inside the window, with its activity.

    Skip rather than fail when the network has none: a quiet month is a fact
    about the network, not a defect.
    """
    scanned = 0
    offset = 0
    while scanned < MAX_MARKETS_SCANNED:
        page = live_client.list_markets(limit=100, offset=offset)
        if not page:
            break
        for market in page:
            if scanned >= MAX_MARKETS_SCANNED:
                break
            scanned += 1
            activity = live_client.get_market_activity(market["id"], FROM_TS, TO_TS)
            if activity["fill_count"] > 0:
                print(f"market {market['id']}, window [{FROM_TS}, {TO_TS}]: {activity}")
                return market["id"], activity
        if len(page) < 100:
            break
        offset += 100

    pytest.skip(f"none of the newest {MAX_MARKETS_SCANNED} markets has a fill in the window")


def test_the_figures_hang_together(market_with_fills):
    _, activity = market_with_fills

    assert activity["bridge"]
    assert int(activity["volume_cents"]) == int(activity["direct_cents"]) + int(
        activity["mint_burn_cents"]
    )
    assert activity["direct_fill_count"] <= activity["fill_count"]
    assert activity["unique_traders"] >= 1

    first, last = activity["first_event_ts"], activity["last_event_ts"]
    assert first is not None and last is not None
    assert FROM_TS <= first <= last <= TO_TS


def test_the_window_includes_both_of_its_ends(live_client, market_with_fills):
    """Narrow the window to the first and last fill inside it.

    It must count exactly the same fills, which holds only if both bounds are
    inclusive, and the seconds just outside it must count none. Reading the
    full window again afterwards and finding it unchanged shows the reads in
    between saw the same fills.
    """
    query_id, _ = market_with_fills

    for attempt in range(1, STABLE_READ_ATTEMPTS + 1):
        before = live_client.get_market_activity(query_id, FROM_TS, TO_TS)
        first, last = before["first_event_ts"], before["last_event_ts"]
        if first is None or last is None:
            pytest.skip(f"market {query_id} lost its fills before the check ran")

        narrow = live_client.get_market_activity(query_id, first, last)
        head = (
            live_client.get_market_activity(query_id, FROM_TS, first - 1)
            if first > FROM_TS
            else None
        )
        tail = (
            live_client.get_market_activity(query_id, last + 1, TO_TS) if last < TO_TS else None
        )

        after = live_client.get_market_activity(query_id, FROM_TS, TO_TS)
        if _fills(before) != _fills(after):
            print(f"market {query_id} moved during attempt {attempt}")
            continue

        assert _fills(narrow) == _fills(before)
        if head is not None:
            assert head["fill_count"] == 0
            assert head["first_event_ts"] is None
        if tail is not None:
            assert tail["fill_count"] == 0
            assert tail["last_event_ts"] is None
        return

    pytest.skip(f"market {query_id} kept moving across {STABLE_READ_ATTEMPTS} attempts")


def test_a_market_that_does_not_exist_is_an_error(live_client):
    with pytest.raises(RuntimeError, match="not found"):
        live_client.get_market_activity(MISSING_MARKET, FROM_TS, TO_TS)
