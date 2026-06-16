"""
Unit tests for execute_agent_action input building (the maa_exec transaction).

These are pure unit tests: they exercise TNClient._maa_exec_args, the Python-side validation and
JSON serialization that feeds the maa_exec binding — no network, no node, no fixtures. The on-chain
wire format (the MAAExec payload and its byte-for-byte golden vector) is locked in sdk-go
(core/contractsapi/maa_exec_test.go); here we only guard the normalization that produces its inputs.
"""

import json

import pytest

from trufnetwork_sdk_py.client import TNClient

ADDR20 = b"\x11" * 20
ADDR_HEX = "0x" + "11" * 20


def test_accepts_bytes_and_hex_address():
    addr_b, _, _, _ = TNClient._maa_exec_args(ADDR20, "ob_place_order", "main", [])
    assert addr_b == ADDR20
    # A 0x-hex address normalizes to the same 20 raw bytes the binding receives.
    addr_h, _, _, _ = TNClient._maa_exec_args(ADDR_HEX, "ob_place_order", "main", [])
    assert addr_h == ADDR20


def test_namespace_defaults_to_main():
    _, ns_empty, _, _ = TNClient._maa_exec_args(ADDR20, "a", "", None)
    assert ns_empty == "main"  # mirrors the node's empty-namespace normalization
    _, ns_explicit, _, _ = TNClient._maa_exec_args(ADDR20, "a", "custom", None)
    assert ns_explicit == "custom"


def test_action_is_passed_through():
    _, _, action, _ = TNClient._maa_exec_args(ADDR20, "ob_cancel_order", "main", None)
    assert action == "ob_cancel_order"


def test_rejects_bad_address_length():
    with pytest.raises(ValueError):
        TNClient._maa_exec_args(b"\x11" * 19, "a", "main", None)
    with pytest.raises(ValueError):
        TNClient._maa_exec_args(b"\x11" * 21, "a", "main", None)


def test_rejects_empty_action():
    with pytest.raises(ValueError):
        TNClient._maa_exec_args(ADDR20, "", "main", None)


def test_args_json_preserves_types():
    # int stays int, decimal/string stays string, bool and null pass through. The binding decodes this
    # JSON with UseNumber() so the node sees the argument types it expects, not float64 for every number.
    _, _, _, args_json = TNClient._maa_exec_args(
        ADDR20, "ob_place_order", "main", [1, "100.5", True, None, "0xabc"]
    )
    assert json.loads(args_json) == [1, "100.5", True, None, "0xabc"]


def test_none_and_empty_args_serialize_to_empty_array():
    _, _, _, none_json = TNClient._maa_exec_args(ADDR20, "a", "main", None)
    _, _, _, empty_json = TNClient._maa_exec_args(ADDR20, "a", "main", [])
    assert none_json == "[]"
    assert empty_json == "[]"


def test_non_serializable_args_raise_valueerror():
    with pytest.raises(ValueError):
        TNClient._maa_exec_args(ADDR20, "a", "main", [object()])


def test_non_finite_float_args_raise_valueerror():
    # NaN/Infinity would serialize to invalid JSON ("[NaN]") that the Go decoder rejects downstream;
    # they must be caught early at the Python layer with a clear error.
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            TNClient._maa_exec_args(ADDR20, "a", "main", [bad])
