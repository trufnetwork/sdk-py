"""Pure unit tests for the address-parameterized portfolio getters.

These exercise the Python-side wrapper logic of TNClient.get_positions_by_wallet /
get_collateral_by_wallet (argument forwarding, JSON parsing, empty handling) by
monkeypatching the Go binding, so they need no node.
"""

import json

import trufnetwork_sdk_py.client as client_mod
from trufnetwork_sdk_py.client import TNClient

WALLET = "0x12aae9a9cf034cb71cbf17cfa1e9612cda8e8a87"


def _client_without_connect() -> TNClient:
    # Bypass __init__ (which would open a network client); the wrappers only
    # forward self.client to the (monkeypatched) binding.
    c = TNClient.__new__(TNClient)
    c.client = object()
    return c


def test_get_positions_by_wallet_forwards_and_parses(monkeypatch):
    captured = {}

    def fake_get_positions(client, wallet):
        captured["wallet"] = wallet
        return json.dumps(
            [{"query_id": 7, "outcome": True, "price": -55, "amount": 100, "position_type": "buy_order"}]
        )

    monkeypatch.setattr(client_mod.truf_sdk, "GetPositionsByWallet", fake_get_positions, raising=False)

    out = _client_without_connect().get_positions_by_wallet(WALLET)

    assert captured["wallet"] == WALLET, "the wallet must be forwarded verbatim to the binding"
    assert len(out) == 1
    assert out[0]["position_type"] == "buy_order"
    assert out[0]["query_id"] == 7


def test_get_positions_by_wallet_empty_returns_list(monkeypatch):
    monkeypatch.setattr(client_mod.truf_sdk, "GetPositionsByWallet", lambda client, wallet: "", raising=False)
    assert _client_without_connect().get_positions_by_wallet(WALLET) == []


def test_get_collateral_by_wallet_forwards_and_parses(monkeypatch):
    captured = {}

    def fake_get_collateral(client, wallet, bridge):
        captured["wallet"] = wallet
        captured["bridge"] = bridge
        return json.dumps(
            {"total_locked": "55000000000000000000", "buy_orders_locked": "55000000000000000000", "shares_value": "0"}
        )

    monkeypatch.setattr(client_mod.truf_sdk, "GetCollateralByWallet", fake_get_collateral, raising=False)

    out = _client_without_connect().get_collateral_by_wallet(WALLET, "hoodi_tt")

    assert captured["wallet"] == WALLET
    assert captured["bridge"] == "hoodi_tt", "the bridge must be forwarded to the binding"
    assert out["buy_orders_locked"] == "55000000000000000000"
    assert out["total_locked"] == "55000000000000000000"


def test_get_collateral_by_wallet_empty_returns_zeros(monkeypatch):
    monkeypatch.setattr(client_mod.truf_sdk, "GetCollateralByWallet", lambda client, wallet, bridge: "", raising=False)
    out = _client_without_connect().get_collateral_by_wallet(WALLET, "hoodi_tt")
    assert out == {"total_locked": "0", "buy_orders_locked": "0", "shares_value": "0"}
