"""Pure unit tests for the market activity read.

The definition of volume lives in the node action get_market_activity and is
tested there; the row parsing and the input checks live in sdk-go. What Python
owns is the wrapper: forwarding the three arguments in order, and decoding the
binding's JSON without turning the cents strings into numbers. Those are
exercised here by monkeypatching the Go binding, so they need no node.
"""

import json

import pytest

import trufnetwork_sdk_py.client as client_mod
from trufnetwork_sdk_py.client import TNClient

# What get_market_activity returned for market 1835 on mainnet, as the binding
# shapes it.
ACTIVITY = {
    "bridge": "eth_usdc",
    "volume_cents": "1145",
    "direct_cents": "545",
    "mint_burn_cents": "600",
    "unique_traders": 2,
    "fill_count": 6,
    "direct_fill_count": 4,
    "shares_traded": 20,
    "first_event_ts": 1791407913,
    "last_event_ts": 1791476117,
    "coverage_from_block": 2692744,
    "coverage_complete": True,
}


def _client_without_connect() -> TNClient:
    """A client that skips __init__, which would open a network client.

    The wrapper only forwards self.client to the binding, which the tests
    replace.
    """
    c = TNClient.__new__(TNClient)
    c.client = object()
    return c


def _binding_returning(monkeypatch, payload: str, captured: dict | None = None):
    """Replace the Go binding with one that returns payload.

    When captured is given, the stand-in records in it the three arguments the
    wrapper passed.
    """

    def fake_get_market_activity(client, query_id, from_ts, to_ts):
        """Return payload as the binding would, recording the arguments if asked."""
        if captured is not None:
            captured["args"] = (query_id, from_ts, to_ts)
        return payload

    monkeypatch.setattr(
        client_mod.truf_sdk, "GetMarketActivity", fake_get_market_activity, raising=False
    )


def test_get_market_activity_forwards_the_window_in_order(monkeypatch):
    """The market id and both ends of the window reach the binding in order."""
    captured: dict = {}
    _binding_returning(monkeypatch, json.dumps(ACTIVITY), captured)

    _client_without_connect().get_market_activity(1835, 1788891555, 1791483555)

    assert captured["args"] == (1835, 1788891555, 1791483555)


def test_get_market_activity_decodes_every_field(monkeypatch):
    """Every key of the binding's JSON comes back with its value."""
    _binding_returning(monkeypatch, json.dumps(ACTIVITY))

    activity = _client_without_connect().get_market_activity(1835, 1788891555, 1791483555)

    assert activity == ACTIVITY


def test_get_market_activity_keeps_cents_as_exact_strings(monkeypatch):
    """The cents fields stay the strings the binding sent.

    The node action returns cents as NUMERIC(78,0), which can pass 2**63, so a
    value that large must come back with every digit, and the parts must still
    add up to the volume.
    """
    big = {
        **ACTIVITY,
        "volume_cents": "123456789012345678901234567890",
        "direct_cents": "123456789012345678901234567290",
    }
    _binding_returning(monkeypatch, json.dumps(big))

    activity = _client_without_connect().get_market_activity(1835, 0, 1791483555)

    assert activity["volume_cents"] == "123456789012345678901234567890"
    assert activity["direct_cents"] == "123456789012345678901234567290"
    assert activity["mint_burn_cents"] == "600"
    assert int(activity["volume_cents"]) == int(activity["direct_cents"]) + int(
        activity["mint_burn_cents"]
    )


def test_get_market_activity_keeps_null_fill_times_and_false_coverage(monkeypatch):
    """A market with no fills keeps None for both fill times and False for coverage.

    A 0 in place of None would read as a fill at time 0.
    """
    # What a node holding no order events returns for a market that exists.
    quiet = {
        **ACTIVITY,
        "bridge": "hoodi_tt2",
        "volume_cents": "0",
        "direct_cents": "0",
        "mint_burn_cents": "0",
        "unique_traders": 0,
        "fill_count": 0,
        "direct_fill_count": 0,
        "shares_traded": 0,
        "first_event_ts": None,
        "last_event_ts": None,
        "coverage_from_block": 0,
        "coverage_complete": False,
    }
    _binding_returning(monkeypatch, json.dumps(quiet))

    activity = _client_without_connect().get_market_activity(7, 0, 1791957600)

    assert activity["first_event_ts"] is None
    assert activity["last_event_ts"] is None
    assert activity["coverage_complete"] is False
    assert activity["coverage_from_block"] == 0


def test_get_market_activity_raises_what_the_binding_raises(monkeypatch):
    """A missing market reaches the caller as the binding's RuntimeError.

    sdk-go errors on a missing market, the binding turns that into a
    RuntimeError, and the wrapper must not swallow it into an empty dict.
    """

    def failing(client, query_id, from_ts, to_ts):
        """Raise what the binding raises for a market that does not exist."""
        raise RuntimeError("failed to get market activity: market 99 not found")

    monkeypatch.setattr(client_mod.truf_sdk, "GetMarketActivity", failing, raising=False)

    with pytest.raises(RuntimeError, match="market 99 not found"):
        _client_without_connect().get_market_activity(99, 0, 1)


def test_get_market_activity_does_not_read_an_empty_answer_as_no_activity(monkeypatch):
    """An empty answer from the binding raises instead of reading as no activity.

    The binding returns one JSON object or an error, so an empty string is never
    a real answer.
    """
    _binding_returning(monkeypatch, "")

    with pytest.raises(ValueError):
        _client_without_connect().get_market_activity(1835, 0, 1)
