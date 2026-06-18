"""
Unit tests for execute_agent_action input building (the maa_exec transaction).

These are pure unit tests: they exercise TNClient._maa_exec_args, the Python-side validation and
JSON serialization that feeds the maa_exec binding — no network, no node, no fixtures. The on-chain
wire format (the MAAExec payload and its byte-for-byte golden vector) is locked in sdk-go
(core/contractsapi/maa_exec_test.go); here we only guard the normalization that produces its inputs.
"""

import json

import pytest

from trufnetwork_sdk_py import MAANumericArg
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


# --- MAANumericArg: NUMERIC arguments across the JSON boundary --------------------------------------
# JSON has no decimal type and the node does not coerce text to NUMERIC, so a NUMERIC action parameter
# is driven by a marker that carries the value plus its precision/scale. The binding rebuilds a
# precision/scale-exact *types.Decimal from it (see bindings/maa_decode_test.go for the decode side).


def test_scalar_numeric_marker_serializes_with_precision_and_scale():
    # maa_withdraw($bridge TEXT, $amount NUMERIC(78,0)): the amount must travel as a marker, not a
    # bare string (which would arrive as TEXT and be rejected).
    _, _, _, args_json = TNClient._maa_exec_args(
        ADDR20, "maa_withdraw", "main", ["eth_truf", MAANumericArg("110000000000000000000", 78, 0)]
    )
    assert json.loads(args_json) == [
        "eth_truf",
        {"__tn_type__": "numeric", "value": "110000000000000000000", "precision": 78, "scale": 0},
    ]


def test_nested_numeric_array_and_ints_serialize():
    # insert_records($data_provider TEXT[], $stream_id TEXT[], $event_time INT8[], $value NUMERIC(36,18)[]):
    # event_time stays an integer array; value is an array of numeric markers.
    _, _, _, args_json = TNClient._maa_exec_args(
        ADDR20,
        "insert_records",
        "main",
        [["0xabc"], ["st"], [100, 200], [MAANumericArg("42.5", 36, 18), MAANumericArg("43.75", 36, 18)]],
    )
    assert json.loads(args_json) == [
        ["0xabc"],
        ["st"],
        [100, 200],
        [
            {"__tn_type__": "numeric", "value": "42.5", "precision": 36, "scale": 18},
            {"__tn_type__": "numeric", "value": "43.75", "precision": 36, "scale": 18},
        ],
    ]


def test_numeric_marker_accepts_int_value():
    assert json.loads(TNClient._maa_exec_args(ADDR20, "a", "main", [MAANumericArg(5, 78, 0)])[3]) == [
        {"__tn_type__": "numeric", "value": "5", "precision": 78, "scale": 0}
    ]


def test_numeric_marker_rejects_bad_precision_scale():
    with pytest.raises(ValueError):
        MAANumericArg("1", 0, 0)  # precision must be >= 1
    with pytest.raises(ValueError):
        MAANumericArg("1", 36, 37)  # scale must be <= precision
    with pytest.raises(ValueError):
        MAANumericArg("1", 36, -1)  # scale must be >= 0
