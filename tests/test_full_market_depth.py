"""Pure unit tests for the whole-market depth read.

The aggregation runs on the node and the row parsing in sdk-go, both tested
there. What Python owns is the wrapper: forwarding the market id, and decoding
rows without losing the outcome tag. Those are exercised here by monkeypatching
the Go binding, so they need no node.
"""

import json

import trufnetwork_sdk_py.client as client_mod
from trufnetwork_sdk_py.client import TNClient

# A YES sell at 60 and a NO sell at 60. In their own books they are the same
# number; only the tag says one is an ask at 60 and the other a bid at 40 once
# framed in YES. Lose the tag and the two are indistinguishable.
DEPTH_JSON = json.dumps(
    [
        {"outcome": True, "price": 60, "buy_volume": 0, "sell_volume": 10},
        {"outcome": False, "price": 60, "buy_volume": 0, "sell_volume": 20},
    ]
)


def _client_without_connect() -> TNClient:
    # Bypass __init__ (which would open a network client); the wrapper only
    # forwards self.client to the (monkeypatched) binding.
    c = TNClient.__new__(TNClient)
    c.client = object()
    return c


def test_get_full_market_depth_forwards_and_parses(monkeypatch):
    captured = {}

    def fake_get_depth(client, query_id):
        captured["query_id"] = query_id
        return DEPTH_JSON

    monkeypatch.setattr(client_mod.truf_sdk, "GetFullMarketDepth", fake_get_depth, raising=False)

    depth = _client_without_connect().get_full_market_depth(419)

    assert captured == {"query_id": 419}
    assert len(depth) == 2
    assert depth[0] == {"outcome": True, "price": 60, "buy_volume": 0, "sell_volume": 10}
    assert depth[1] == {"outcome": False, "price": 60, "buy_volume": 0, "sell_volume": 20}


def test_get_full_market_depth_keeps_the_outcome_tag(monkeypatch):
    monkeypatch.setattr(
        client_mod.truf_sdk, "GetFullMarketDepth", lambda c, q: DEPTH_JSON, raising=False
    )

    depth = _client_without_connect().get_full_market_depth(419)

    assert [level["outcome"] for level in depth] == [True, False], (
        "the tag is the only thing separating a YES level from the NO level at "
        "the same price"
    )


def test_get_full_market_depth_empty_returns_list(monkeypatch):
    monkeypatch.setattr(client_mod.truf_sdk, "GetFullMarketDepth", lambda c, q: "", raising=False)

    assert _client_without_connect().get_full_market_depth(419) == []
