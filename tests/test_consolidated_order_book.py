"""Pure unit tests for the consolidated order book wrapper.

The folding rule itself lives in sdk-go and is tested there. What Python owns is
the wrapper: forwarding the frame to the binding, and decoding the JSON without
losing the native/inverse split or the crossed flag. Those are exercised here by
monkeypatching the Go binding, so they need no node.
"""

import json

import trufnetwork_sdk_py.client as client_mod
from trufnetwork_sdk_py.client import TNClient

# A YES ask at 60 that is entirely native, and a bid at 40 that is entirely
# inverse: the NO sell at 60 folded into the YES frame. Two levels that are
# indistinguishable by size alone, so a wrapper that dropped the split or
# mixed up the sides would show here.
BOOK_JSON = json.dumps(
    {
        "query_id": 419,
        "outcome": True,
        "bids": [{"price": 40, "total": 20, "native": 0, "inverse": 20}],
        "asks": [{"price": 60, "total": 10, "native": 10, "inverse": 0}],
        "is_crossed": False,
    }
)


def _client_without_connect() -> TNClient:
    # Bypass __init__ (which would open a network client); the wrapper only
    # forwards self.client to the (monkeypatched) binding.
    c = TNClient.__new__(TNClient)
    c.client = object()
    return c


def test_get_consolidated_order_book_forwards_and_parses(monkeypatch):
    captured = {}

    def fake_get_book(client, query_id, outcome):
        captured["query_id"] = query_id
        captured["outcome"] = outcome
        return BOOK_JSON

    monkeypatch.setattr(client_mod.truf_sdk, "GetConsolidatedOrderBook", fake_get_book, raising=False)

    book = _client_without_connect().get_consolidated_order_book(419, True)

    assert captured == {"query_id": 419, "outcome": True}
    assert book["query_id"] == 419
    assert book["is_crossed"] is False
    assert book["asks"] == [{"price": 60, "total": 10, "native": 10, "inverse": 0}]
    assert book["bids"] == [{"price": 40, "total": 20, "native": 0, "inverse": 20}], (
        "the inverse volume must survive decoding: it is the NO liquidity that "
        "reading the YES book alone would miss"
    )


def test_get_consolidated_order_book_defaults_to_the_yes_frame(monkeypatch):
    captured = {}

    def fake_get_book(client, query_id, outcome):
        captured["outcome"] = outcome
        return BOOK_JSON

    monkeypatch.setattr(client_mod.truf_sdk, "GetConsolidatedOrderBook", fake_get_book, raising=False)

    _client_without_connect().get_consolidated_order_book(419)

    assert captured["outcome"] is True


def test_get_consolidated_order_book_passes_the_no_frame_through(monkeypatch):
    captured = {}

    def fake_get_book(client, query_id, outcome):
        captured["outcome"] = outcome
        return json.dumps(
            {"query_id": 419, "outcome": False, "bids": [], "asks": [], "is_crossed": False}
        )

    monkeypatch.setattr(client_mod.truf_sdk, "GetConsolidatedOrderBook", fake_get_book, raising=False)

    book = _client_without_connect().get_consolidated_order_book(419, False)

    assert captured["outcome"] is False
    assert book["outcome"] is False


def test_get_consolidated_order_book_reports_a_crossed_book(monkeypatch):
    # A YES bid at 61 against a NO bid at 45 reads as a bid at 61 over an ask at
    # 55 and never matches, because 61 + 45 is not 100. It is a state to render,
    # not bad data, so the flag has to reach the caller intact.
    crossed = json.dumps(
        {
            "query_id": 419,
            "outcome": True,
            "bids": [{"price": 61, "total": 100, "native": 100, "inverse": 0}],
            "asks": [{"price": 55, "total": 100, "native": 0, "inverse": 100}],
            "is_crossed": True,
        }
    )
    monkeypatch.setattr(
        client_mod.truf_sdk, "GetConsolidatedOrderBook", lambda c, q, o: crossed, raising=False
    )

    assert _client_without_connect().get_consolidated_order_book(419)["is_crossed"] is True


def test_get_consolidated_order_book_empty_returns_an_empty_book(monkeypatch):
    monkeypatch.setattr(
        client_mod.truf_sdk, "GetConsolidatedOrderBook", lambda c, q, o: "", raising=False
    )

    assert _client_without_connect().get_consolidated_order_book(419, False) == {
        "query_id": 419,
        "outcome": False,
        "bids": [],
        "asks": [],
        "is_crossed": False,
    }
