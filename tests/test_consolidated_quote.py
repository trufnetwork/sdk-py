"""Pure unit tests for quoting a fill against a consolidated ladder.

The model lives in sdk-go, and ``quote_consolidated_*_from_book`` reaches it
through the C extension without touching a node, so these run it for real rather
than mocking it. What matters is that the ladder is not sweepable: an order at
limit P takes every native level past P but exactly ONE inverse level, the one at
P. So fillable size is not monotonic in the limit, the ladder's total is not
reachable by any single order, and a sell pays its limit on every share.

The client methods are wrappers over the same model, so those are exercised by
monkeypatching the binding, which is what the wrapper actually owns.
"""

import json

import pytest

import trufnetwork_sdk_py.client as client_mod
from trufnetwork_sdk_py.client import (
    TNClient,
    quote_consolidated_buy_from_book,
    quote_consolidated_sell_from_book,
)


def level(price, native, inverse):
    """One consolidated level, carrying the total the ladder would show."""
    return {
        "price": price,
        "native": native,
        "inverse": inverse,
        "total": native + inverse,
    }


def book(bids=(), asks=()):
    return {
        "query_id": 419,
        "outcome": True,
        "bids": list(bids),
        "asks": list(asks),
        "is_crossed": False,
    }


# YES asks 100 @ 60, NO bids 200 @ 41 and 50 @ 45.
THREE_LEVEL_ASKS = [level(55, 0, 50), level(59, 0, 200), level(60, 100, 0)]


# --- buys --------------------------------------------------------------------


def test_fills_at_the_one_price_where_the_inverse_leg_is_reachable():
    quote = quote_consolidated_buy_from_book(book(asks=THREE_LEVEL_ASKS), 100)

    assert quote["limit_price"] == 59
    assert quote["filled_shares"] == 100
    assert quote["estimated_total_cost"] == 59


def test_reports_the_best_fill_one_order_can_get_not_the_whole_ladder():
    assert sum(entry["total"] for entry in THREE_LEVEL_ASKS) == 350

    # Summing the ladder says 350. No single order can do better than 200.
    quote = quote_consolidated_buy_from_book(book(asks=THREE_LEVEL_ASKS), 350)

    assert quote["available_shares"] == 200
    assert quote["is_fully_filled"] is False


def test_does_not_gain_fill_by_raising_the_limit_past_the_inverse_leg():
    asks = book(asks=[level(59, 0, 200), level(60, 100, 0)])

    # A limit of 60 reaches 100 native shares; a limit of 59 reaches 200 inverse
    # ones. More fill sits at the lower price.
    assert quote_consolidated_buy_from_book(asks, 150)["limit_price"] == 59
    assert quote_consolidated_buy_from_book(asks, 150)["filled_shares"] == 150
    assert quote_consolidated_buy_from_book(asks, 250)["filled_shares"] == 200
    assert quote_consolidated_buy_from_book(asks, 250)["limit_price"] == 59


def test_prices_native_legs_at_their_own_price_and_the_inverse_leg_at_the_limit():
    quote = quote_consolidated_buy_from_book(
        book(asks=[level(20, 40, 0), level(30, 0, 60)]), 100
    )

    assert quote["limit_price"] == 30
    assert quote["estimated_total_cost"] == 26
    assert quote["fills"] == [
        {"price": 20, "shares": 40, "path": "direct"},
        {"price": 30, "shares": 60, "path": "mint"},
    ]


def test_averages_the_price_actually_paid_across_both_legs():
    quote = quote_consolidated_buy_from_book(
        book(asks=[level(20, 40, 0), level(30, 0, 60)]), 100
    )

    assert quote["average_price"] == 26


# --- sells -------------------------------------------------------------------


def test_pays_the_submitted_limit_on_every_share_not_each_bid_its_own_price():
    # match_direct pays the seller at the ask price, so walking the ladder and
    # crediting 50 at 80 plus 50 at 70 overstates this by $5.
    quote = quote_consolidated_sell_from_book(
        book(bids=[level(80, 50, 0), level(70, 50, 0)]), 100
    )

    assert quote["limit_price"] == 70
    assert quote["filled_shares"] == 100
    assert quote["estimated_proceeds"] == 70


def test_combines_a_direct_leg_and_a_burn_leg_at_the_submitted_limit():
    quote = quote_consolidated_sell_from_book(
        book(bids=[level(70, 30, 40), level(60, 100, 0)]), 70
    )

    assert quote["limit_price"] == 70
    assert quote["filled_shares"] == 70
    assert quote["estimated_proceeds"] == 49
    assert quote["fills"] == [
        {"price": 70, "shares": 30, "path": "direct"},
        {"price": 70, "shares": 40, "path": "burn"},
    ]


def test_reaches_the_inverse_leg_only_at_the_exact_limit_price():
    quote = quote_consolidated_sell_from_book(
        book(bids=[level(65, 0, 80), level(60, 40, 0)]), 80
    )

    assert quote["limit_price"] == 65
    assert quote["estimated_proceeds"] == 52
    assert quote["fills"] == [{"price": 65, "shares": 80, "path": "burn"}]


# --- guards and caller-supplied limits ---------------------------------------


def test_ignores_levels_outside_the_tradable_range():
    quote = quote_consolidated_buy_from_book(
        book(asks=[level(0, 500, 0), level(100, 500, 0), level(40, 60, 0)]), 60
    )

    assert quote["limit_price"] == 40
    assert quote["available_shares"] == 60


def test_quotes_a_sell_at_the_limit_the_caller_chose():
    quote = quote_consolidated_sell_from_book(
        book(bids=[level(80, 50, 0), level(70, 50, 0)]), 100, limit_price=80
    )

    # Only the 80 bid is reachable at a limit of 80, and it pays 80 a share.
    assert quote["filled_shares"] == 50
    assert quote["estimated_proceeds"] == 40
    assert quote["is_fully_filled"] is False


def test_quotes_a_buy_at_the_limit_the_caller_chose():
    # Left to choose, the model picks 59 for the larger fill. A caller willing to
    # pay up for the native side gets to say so.
    quote = quote_consolidated_buy_from_book(
        book(asks=[level(59, 0, 200), level(60, 100, 0)]), 250, limit_price=60
    )

    assert quote["limit_price"] == 60
    assert quote["filled_shares"] == 100
    assert quote["estimated_total_cost"] == 60
    assert quote["is_fully_filled"] is False


def test_an_empty_book_quotes_nothing():
    buy = quote_consolidated_buy_from_book(book(), 100)
    assert buy["limit_price"] is None
    assert buy["average_price"] is None
    assert buy["filled_shares"] == 0
    assert buy["available_shares"] == 0
    assert buy["fills"] == []

    sell = quote_consolidated_sell_from_book(book(), 100)
    assert sell["limit_price"] is None
    assert sell["filled_shares"] == 0
    assert sell["fills"] == []


def test_sorts_an_unordered_ladder_rather_than_trusting_the_input_order():
    quote = quote_consolidated_buy_from_book(
        book(asks=[level(60, 100, 0), level(20, 40, 0)]), 40
    )

    assert quote["limit_price"] == 20


# --- mainnet market 419 ------------------------------------------------------

# A frozen snapshot read 2026-08-12 through get_full_market_depth.
#
#   YES bids  1c x4283, 3c x1428, 4c x1049
#   YES asks 16c x320, 17c x324, 19c x289
#   NO  bids 81c x53,  83c x51,  84c x29
#   NO  asks 96c x33,  97c x57,  99c x56
#
# The NO orders fold into the YES frame at 100 - price, which lands each of them
# on a price the YES book already quotes.
MARKET_419 = book(
    bids=[level(4, 1049, 33), level(3, 1428, 57), level(1, 4283, 56)],
    asks=[level(16, 320, 29), level(17, 324, 51), level(19, 289, 53)],
)


def test_market_419_one_buy_cannot_take_more_than_the_best_single_price_allows():
    quote = quote_consolidated_buy_from_book(MARKET_419, 99_999)

    assert quote["available_shares"] == 986


def test_market_419_a_buy_inside_native_depth_never_reaches_an_inverse_leg():
    quote = quote_consolidated_buy_from_book(MARKET_419, 700)

    assert quote["limit_price"] == 19
    assert quote["estimated_total_cost"] == pytest.approx(116.92)
    assert all(fill["path"] == "direct" for fill in quote["fills"])


def test_market_419_a_sell_past_the_top_bid_pays_its_limit_on_every_share():
    quote = quote_consolidated_sell_from_book(MARKET_419, 2000)

    # 1049 rest at 4c, but the order only fills in full at a limit of 3c, and
    # every share then pays 3c. Walking the ladder would have quoted 70.49.
    assert quote["limit_price"] == 3
    assert quote["estimated_proceeds"] == pytest.approx(60.0)


# --- the client wrappers -----------------------------------------------------


def _client_without_connect() -> TNClient:
    # Bypass __init__ (which would open a network client); the wrapper only
    # forwards self.client to the (monkeypatched) binding.
    c = TNClient.__new__(TNClient)
    c.client = object()
    return c


def test_quote_consolidated_buy_forwards_the_market_and_size(monkeypatch):
    captured = {}

    def fake_quote(client, query_id, outcome, shares, limit):
        captured.update(
            query_id=query_id, outcome=outcome, shares=shares, limit=limit
        )
        return json.dumps({"limit_price": 59, "filled_shares": 100})

    monkeypatch.setattr(
        client_mod.truf_sdk, "QuoteConsolidatedBuy", fake_quote, raising=False
    )

    quote = _client_without_connect().quote_consolidated_buy(419, 100, outcome=False)

    assert captured == {
        "query_id": 419,
        "outcome": False,
        "shares": 100,
        "limit": 0.0,
    }
    assert quote["limit_price"] == 59


def test_quote_consolidated_sell_forwards_a_caller_supplied_limit(monkeypatch):
    captured = {}

    def fake_quote(client, query_id, outcome, shares, limit):
        captured["limit"] = limit
        return json.dumps({"limit_price": limit, "filled_shares": 50})

    monkeypatch.setattr(
        client_mod.truf_sdk, "QuoteConsolidatedSell", fake_quote, raising=False
    )

    quote = _client_without_connect().quote_consolidated_sell(
        419, 50, limit_price=80
    )

    # No limit means "choose one", so a real price has to survive the hop.
    assert captured["limit"] == 80
    assert quote["limit_price"] == 80
