"""Live-network checks that the consolidated read folds the real chain correctly.

The rest of the consolidated suite feeds the wrapper hand-written JSON, which
proves the decoding but cannot prove the SDK reads the CHAIN the right way
round. If the fold ever put the opposite outcome's quotes on the wrong side --
NO bids arriving as YES bids instead of YES asks -- every one of those tests
would still pass while the ladder pointed traders at quotes that cannot fill.
That is the gap this file covers.

Gated, because it needs a network carrying markets with real orders. Run it
with:

    TN_LIVE_NODE_URL=https://gateway.mainnet.truf.network pytest tests/test_order_book_live.py

All calls are view actions, so the signing key needs no funds and controls
nothing; a throwaway is generated unless TN_LIVE_PRIVATE_KEY is set.

These assert RELATIONSHIPS between reads of the same market, never numbers.
Live books move minute to minute, so a pinned value would fail by tomorrow.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("TN_LIVE_NODE_URL"),
    reason="live node not configured; set TN_LIVE_NODE_URL to run",
)

# Discovery costs two depth reads per market until a two-sided one turns up.
# Mainnet carried ~130 open markets when this was written and the first page
# already held one; the cap is headroom, not a target.
MAX_MARKETS_SCANNED = 400

# Retries before giving up on a market that will not hold still long enough to
# be read twice.
STABLE_READ_ATTEMPTS = 4


@pytest.fixture(scope="module")
def live_client():
    from eth_account import Account

    from trufnetwork_sdk_py.client import TNClient

    key = os.getenv("TN_LIVE_PRIVATE_KEY") or Account.create().key.hex()
    return TNClient(os.environ["TN_LIVE_NODE_URL"], key)


def _quoted(levels) -> bool:
    return any(level["buy_volume"] or level["sell_volume"] for level in levels)


@pytest.fixture(scope="module")
def two_sided_market(live_client) -> int:
    """A market carrying resting orders on BOTH outcomes.

    A one-sided market cannot show a fold: with nothing resting on NO, every
    consolidated level is native and a wrapper that dropped the inverse side
    entirely would still pass. Skip rather than fail when the network has none
    -- an empty book is a fact about the day, not a defect.
    """
    offset = 0
    scanned = 0

    while scanned < MAX_MARKETS_SCANNED:
        page = live_client.list_markets(settled_filter=False, limit=100, offset=offset)
        if not page:
            break
        for market in page:
            scanned += 1
            query_id = market["id"]
            if _quoted(live_client.get_market_depth(query_id, True)) and _quoted(
                live_client.get_market_depth(query_id, False)
            ):
                return query_id
        if len(page) < 100:
            break
        offset += 100

    pytest.skip("no open market on this network quotes both outcomes right now")


@pytest.fixture(scope="module")
def books(live_client, two_sided_market):
    """The raw YES and NO ladders and the consolidated book, read while the
    market holds still.

    Live books move. Comparing a consolidated read against separate raw reads
    is comparing two points in time, so a mismatch there can mean drift rather
    than a defect. Read the raw sides on both sides of the consolidated call and
    only assert when they agree.
    """
    for _ in range(STABLE_READ_ATTEMPTS):
        before_yes = live_client.get_market_depth(two_sided_market, True)
        before_no = live_client.get_market_depth(two_sided_market, False)
        book = live_client.get_consolidated_order_book(two_sided_market, True)
        after_yes = live_client.get_market_depth(two_sided_market, True)
        after_no = live_client.get_market_depth(two_sided_market, False)
        if before_yes == after_yes and before_no == after_no:
            return before_yes, before_no, book

    pytest.skip("the book kept moving between reads; nothing stable to compare")


def test_consolidated_bids_trace_back_to_resting_orders(books):
    """A consolidated bid is a YES buy at p, or a NO SELL at 100-p.

    The NO side is the half that matters. A resting sell of NO at 93c is a
    standing bid for YES at 7c: a trader hits it by SELLING YES, both parties
    sell, and the chain burns the share pair.
    """
    yes, no, book = books
    yes_buy = {level["price"]: level["buy_volume"] for level in yes}
    no_sell = {level["price"]: level["sell_volume"] for level in no}

    for level in book["bids"]:
        assert level["native"] == yes_buy.get(level["price"], 0), (
            f"native bid volume at {level['price']}c is not a YES buy on the chain"
        )
        assert level["inverse"] == no_sell.get(100 - level["price"], 0), (
            f"inverse bid volume at {level['price']}c is not a NO sell at "
            f"{100 - level['price']}c on the chain"
        )
        assert level["total"] == level["native"] + level["inverse"]


def test_consolidated_asks_trace_back_to_resting_orders(books):
    """A consolidated ask is a YES sell at p, or a NO BUY at 100-p.

    Hitting one means both parties buy and the chain mints a share pair.
    """
    yes, no, book = books
    yes_sell = {level["price"]: level["sell_volume"] for level in yes}
    no_buy = {level["price"]: level["buy_volume"] for level in no}

    for level in book["asks"]:
        assert level["native"] == yes_sell.get(level["price"], 0), (
            f"native ask volume at {level['price']}c is not a YES sell on the chain"
        )
        assert level["inverse"] == no_buy.get(100 - level["price"], 0), (
            f"inverse ask volume at {level['price']}c is not a NO buy at "
            f"{100 - level['price']}c on the chain"
        )
        assert level["total"] == level["native"] + level["inverse"]


def test_the_opposite_outcome_reaches_the_ladder(books):
    """The point of the whole method: NO liquidity shows up in the YES frame.

    The market was picked because both outcomes carry orders, so whatever rests
    on NO has to surface as inverse volume on one side or the other. A fold that
    silently discarded the opposite book would pass every assertion above and
    fail this one.
    """
    _, _, book = books

    assert any(level["inverse"] for level in book["bids"] + book["asks"]), (
        "both outcomes are quoted, so the opposite book must contribute at "
        "least one inverse level"
    )


def test_the_no_frame_is_the_yes_frame_reflected(live_client, two_sided_market):
    """One call answers either tab: a YES bid at p is a NO ask at 100-p."""
    # Re-read BOTH frames. Re-reading only YES would miss an order placed after
    # the first read and cancelled before the third: YES comes back identical
    # while no_book was taken from a state that no longer exists, and the
    # comparison below then fails on drift rather than on a defect. Arguing that
    # a settled YES frame implies a settled NO frame would also lean on exactly
    # the mirror property this test exists to verify.
    for _ in range(STABLE_READ_ATTEMPTS):
        yes_book = live_client.get_consolidated_order_book(two_sided_market, True)
        no_book = live_client.get_consolidated_order_book(two_sided_market, False)
        yes_again = live_client.get_consolidated_order_book(two_sided_market, True)
        no_again = live_client.get_consolidated_order_book(two_sided_market, False)
        if yes_book == yes_again and no_book == no_again:
            break
    else:
        pytest.skip("the book kept moving between reads; nothing stable to compare")

    def reflect(levels):
        return sorted((100 - level["price"], level["total"]) for level in levels)

    def flat(levels):
        return sorted((level["price"], level["total"]) for level in levels)

    assert reflect(yes_book["bids"]) == flat(no_book["asks"])
    assert reflect(yes_book["asks"]) == flat(no_book["bids"])
