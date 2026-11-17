"""Node-free tests for the outcome actions (ids 13-16, node v2.6.8).

Each answers YES, NO or INVALID, and a market on one is refunded when its print
has not arrived by block time timestamp + window. The encoding, decoding and
bounds live in sdk-go; these tests check that the Python layer reaches them
with the right arguments and that its own checks are never stricter than the
node.
"""

import json
import struct
from pathlib import Path

import pytest

from trufnetwork_sdk_py.client import (
    BINARY_ACTION_IDS,
    OUTCOME_ACTION_IDS,
    OUTCOME_INVALID,
    OUTCOME_MAX_SPAN_SECONDS,
    OUTCOME_MAX_TOLERANCE_SECONDS,
    OUTCOME_NO,
    OUTCOME_YES,
    TNClient,
    is_market_refunded,
)

GOLDEN = json.loads(
    (Path(__file__).parent / "testdata" / "outcome_v2_golden.json").read_text()
)

PROVIDER = "0x4710a8d8f0d845da110086812a32de6d90d7ff5c"
STREAM = "stbtcusd000000000000000000000000"
T = 1767139200
DAY = 86400
YEAR = 31536000


def build(action_id: int, **inputs):
    """Call the builder for an action id with snake_case kwargs."""
    builders = {
        13: TNClient.build_index_change_in_range_v2_query_components,
        14: TNClient.build_price_above_threshold_v2_query_components,
        15: TNClient.build_price_below_threshold_v2_query_components,
        16: TNClient.build_value_in_range_v2_query_components,
    }
    return builders[action_id](**inputs)


def daily(**overrides):
    """Daily ladder defaults for ids 14-16."""
    return {
        "data_provider": PROVIDER,
        "stream_id": STREAM,
        "timestamp": T,
        "window": 3 * DAY,
        "tolerance": DAY,
        **overrides,
    }


def month_start(**overrides):
    """Month-start defaults for id 13."""
    return {
        "data_provider": PROVIDER,
        "stream_id": "stcpiyoy000000000000000000000000",
        "timestamp": 1759276800,
        "window": 7776000,
        "tolerance": 172800,
        "time_interval": YEAR,
        **overrides,
    }


# --- hash parity with sdk-go --------------------------------------------------


@pytest.mark.parametrize("action_id", ["13", "14", "15", "16"])
def test_builders_match_the_sdk_go_golden_bytes(action_id):
    """The market hash is taken over these bytes, so they must match sdk-go and
    sdk-js exactly. The golden provider is mixed case: the args carry it
    lowercased."""
    golden = GOLDEN[action_id]
    encoded = build(int(action_id), **golden["inputs"])

    assert encoded.hex() == golden["components_hex"]
    decoded = TNClient.decode_query_components(encoded)
    assert decoded["action_id"] == golden["action"]
    assert decoded["args"] == golden["args_hex"]


# --- decoding -----------------------------------------------------------------


def test_price_v2_markets_decode_as_above_and_below():
    for action_id, action, market_type in (
        (14, "price_above_threshold_v2", "above"),
        (15, "price_below_threshold_v2", "below"),
    ):
        decoded = TNClient.decode_market_data(build(action_id, **daily(threshold="100000")))

        assert decoded["action_id"] == action
        assert decoded["type"] == market_type
        assert decoded["thresholds"] == ["100000.000000000000000000"]
        assert decoded["timestamp"] == T
        assert decoded["window"] == 3 * DAY
        assert decoded["tolerance"] == DAY
        assert decoded["frozen_at"] is None
        assert decoded["base_time"] is None
        assert decoded["time_interval"] is None


def test_value_in_range_v2_decodes_as_range_with_open_tails_in_place():
    """Not "between": that type is inclusive and always has two numbers."""
    decoded = TNClient.decode_market_data(build(16, **daily(min_value="90", max_value="110")))
    assert decoded["action_id"] == "value_in_range_v2"
    assert decoded["type"] == "range"
    assert decoded["thresholds"] == ["90.000000000000000000", "110.000000000000000000"]
    assert decoded["window"] == 3 * DAY
    assert decoded["tolerance"] == DAY
    assert decoded["frozen_at"] is None

    bottom = TNClient.decode_market_data(build(16, **daily(max_value="90")))
    assert bottom["thresholds"] == ["", "90.000000000000000000"]
    top = TNClient.decode_market_data(build(16, **daily(min_value="110")))
    assert top["thresholds"] == ["110.000000000000000000", ""]


def test_index_change_v2_decodes_as_change_between_without_base_time():
    decoded = TNClient.decode_market_data(build(13, **month_start(min_change="2", max_change="3")))
    assert decoded["action_id"] == "index_change_in_range_v2"
    assert decoded["type"] == "change_between"
    assert decoded["thresholds"] == ["2.000000000000000000", "3.000000000000000000"]
    assert decoded["timestamp"] == 1759276800
    assert decoded["window"] == 7776000
    assert decoded["tolerance"] == 172800
    assert decoded["time_interval"] == YEAR
    assert decoded["base_time"] is None
    assert decoded["frozen_at"] is None

    bottom = TNClient.decode_market_data(build(13, **month_start(max_change="1.5")))
    assert bottom["thresholds"] == ["", "1.500000000000000000"]


def test_v1_markets_carry_no_window_or_tolerance():
    v1 = TNClient.build_index_change_in_range_query_components(
        PROVIDER, STREAM, T, YEAR, min_change="2", max_change="3"
    )
    decoded = TNClient.decode_market_data(v1)
    assert decoded["window"] is None
    assert decoded["tolerance"] is None


def test_a_v2_ladder_tiles_the_line():
    """value_in_range_v2 with open outer tails: each upper edge is the next
    bucket's lower edge, so exactly one bucket holds any value."""
    from trufnetwork_sdk_py.market_buckets import bucket_bounds_from_market_data

    edges = ["100", "105", "110"]
    strikes = (
        [(None, edges[0])]
        + [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
        + [(edges[-1], None)]
    )
    bounds = [
        bucket_bounds_from_market_data(
            TNClient.decode_market_data(build(16, **daily(min_value=lo, max_value=hi)))
        )
        for lo, hi in strikes
    ]
    assert bounds[0] == (None, 100.0)
    assert bounds[-1] == (110.0, None)
    for (_, upper), (lower, _) in zip(bounds, bounds[1:]):
        assert upper == lower


# --- refusals, never stricter than the node -----------------------------------


@pytest.mark.parametrize(
    "action_id,inputs,message",
    [
        (16, daily(), "at least one of min_value or max_value"),
        (13, month_start(), "at least one of min_change or max_change"),
        (16, daily(min_value="", max_value="3"), "cannot be empty strings"),
        (16, daily(min_value="2", max_value=""), "cannot be empty strings"),
        (13, month_start(min_change="", max_change="3"), "cannot be empty strings"),
        (14, daily(threshold=""), "threshold is required"),
        (15, daily(threshold=None), "threshold is required"),
    ],
)
def test_python_layer_refuses_what_has_no_meaning(action_id, inputs, message):
    """"" is the binding's open-tail sentinel, so nothing below this layer can
    tell it from None. Both bounds open, and a NULL threshold, the node refuses."""
    with pytest.raises(ValueError, match=message):
        build(action_id, **inputs)


@pytest.mark.parametrize(
    "action_id,inputs,message",
    [
        (16, daily(min_value="2.0", max_value="2"), "min_value must be less than max_value"),
        (13, month_start(min_change="3", max_change="2"), "min_change must be less than max_change"),
        (14, daily(threshold="NaN"), "NaN"),
        (16, daily(min_value="NaN"), "NaN"),
        (14, daily(threshold="100", window=DAY, tolerance=DAY + 1), "must not be less than tolerance"),
        (14, daily(threshold="100", window=0), "window must be in"),
        (14, daily(threshold="100", window=OUTCOME_MAX_SPAN_SECONDS + 1), "window must be in"),
        (
            14,
            daily(threshold="100", window=OUTCOME_MAX_SPAN_SECONDS,
                  tolerance=OUTCOME_MAX_TOLERANCE_SECONDS + 1),
            "tolerance must be in",
        ),
        (14, daily(threshold="100", tolerance=-1), "tolerance must be in"),
        (14, daily(threshold="100", timestamp=-1), "timestamp must not be negative"),
        (13, month_start(min_change="2", time_interval=2 * 172800), "more than twice tolerance"),
        (13, month_start(min_change="2", time_interval=0), "time_interval must be in"),
        (14, daily(threshold="100", stream_id="short"), "stream_id must be exactly 32"),
        (14, daily(threshold="100", data_provider="0x1234"), "data_provider must be 42"),
    ],
)
def test_sdk_go_applies_the_node_bounds(action_id, inputs, message):
    with pytest.raises(RuntimeError, match=message):
        build(action_id, **inputs)


@pytest.mark.parametrize(
    "action_id,inputs",
    [
        (14, daily(threshold="100", timestamp=0)),
        (14, daily(threshold="100", tolerance=0)),
        (14, daily(threshold="100", window=DAY, tolerance=DAY)),
        (
            14,
            daily(threshold="100", window=OUTCOME_MAX_SPAN_SECONDS,
                  tolerance=OUTCOME_MAX_TOLERANCE_SECONDS),
        ),
        (13, month_start(min_change="2", time_interval=2 * 172800 + 1)),
        (13, month_start(min_change="2", tolerance=0, time_interval=1)),
        (13, month_start(max_change="2", time_interval=OUTCOME_MAX_SPAN_SECONDS)),
        (16, daily(min_value="-5", max_value="-4.999999999999999999")),
        (14, daily(threshold="100", data_provider="0X" + PROVIDER[2:].upper())),
    ],
)
def test_node_edges_are_accepted(action_id, inputs):
    """Each of these is at a node bound and the node accepts it, so the SDK
    must too."""
    assert len(build(action_id, **inputs)) > 0


def test_bound_constants_match_the_node():
    assert OUTCOME_MAX_SPAN_SECONDS == 315360000
    assert OUTCOME_MAX_TOLERANCE_SECONDS == 3888000


def _offline_client() -> TNClient:
    """A TNClient with no connection. The checks below run before any call
    that needs one."""
    return TNClient.__new__(TNClient)


MARKET = {"bridge": "eth_usdc", "settle_time": T + 4 * DAY, "max_spread": 5, "min_order_size": 20}


@pytest.mark.parametrize(
    "create,inputs,message",
    [
        ("create_value_in_range_v2_market", {**daily(), **MARKET}, "at least one of min_value"),
        ("create_value_in_range_v2_market",
         {**daily(min_value="", max_value="1"), **MARKET}, "cannot be empty strings"),
        ("create_index_change_in_range_v2_market",
         {**month_start(), **MARKET}, "at least one of min_change"),
        ("create_index_change_in_range_v2_market",
         {**month_start(max_change=""), **MARKET}, "cannot be empty strings"),
        ("create_price_above_threshold_v2_market",
         {**daily(threshold=""), **MARKET}, "threshold is required"),
        ("create_price_below_threshold_v2_market",
         {**daily(threshold="1"), **MARKET, "bridge": "hoodi_tt"}, "bridge must be one of"),
        ("create_price_above_threshold_v2_market",
         {**daily(threshold="1"), **MARKET, "max_spread": 0}, "max_spread must be between"),
    ],
)
def test_create_helpers_check_their_inputs_before_sending(create, inputs, message):
    with pytest.raises(ValueError, match=message):
        getattr(_offline_client(), create)(**inputs, wait=False)


# --- reading the result ----------------------------------------------------------


def _word(n: int) -> bytes:
    """One 32-byte ABI word, two's complement."""
    return (n % (1 << 256)).to_bytes(32, "big")


def _points(values, event_time=1767225600) -> bytes:
    """abi.encode(uint256[] event_times, int256[] values)."""
    n = len(values)
    times = _word(n) + b"".join(_word(event_time) for _ in values)
    vals = _word(n) + b"".join(_word(v) for v in values)
    return _word(0x40) + _word(0x40 + len(times)) + times + vals


def _payload(action_id: int, result: bytes) -> bytes:
    """A canonical attestation payload (no signature)."""
    def lp(b: bytes) -> bytes:
        return struct.pack(">I", len(b)) + b

    return (
        bytes([1, 0])
        + struct.pack(">Q", 123)
        + lp(bytes.fromhex(PROVIDER[2:]))
        + lp(STREAM.encode())
        + struct.pack(">H", action_id)
        + lp(struct.pack("<I", 0))
        + lp(result)
    )


E18 = 10**18


@pytest.mark.parametrize("action_id", [13, 14, 15, 16])
@pytest.mark.parametrize(
    "value,outcome", [(E18, OUTCOME_YES), (0, OUTCOME_NO), (-E18, OUTCOME_INVALID)]
)
def test_parse_outcome_result_maps_the_three_values(action_id, value, outcome):
    got = TNClient.parse_outcome_result(_payload(action_id, _points([value])))
    assert got == {"outcome": outcome, "action_id": action_id}


def test_parse_outcome_result_refuses_other_values_and_shapes():
    with pytest.raises(RuntimeError, match="1e18, 0 or -1e18"):
        TNClient.parse_outcome_result(_payload(14, _points([2 * E18])))
    with pytest.raises(RuntimeError, match="exactly one data point"):
        TNClient.parse_outcome_result(_payload(14, _points([E18, 0])))
    with pytest.raises(RuntimeError, match="not an outcome action"):
        TNClient.parse_outcome_result(_payload(12, _points([E18])))
    with pytest.raises(ValueError, match="too short"):
        TNClient.parse_outcome_result(b"\x01\x00")


def test_parse_boolean_result_reads_a_binary_payload():
    """It passed Python bytes to a binding that takes a Go slice, so every call
    raised AttributeError."""
    got = TNClient.parse_boolean_result(_payload(6, _word(1)))
    assert got == {"result": True, "action_id": 6}


def test_parse_boolean_result_refuses_an_outcome_action():
    """A boolean cannot carry INVALID."""
    with pytest.raises(RuntimeError, match="not a binary action"):
        TNClient.parse_boolean_result(_payload(13, _points([E18])))


def test_parse_attestation_payload_reads_an_outcome_value():
    client = TNClient.__new__(TNClient)  # no connection needed
    parsed = client.parse_attestation_payload(_payload(16, _points([-E18])))
    assert parsed.action_id == 16
    assert parsed.result[0]["values"][1] == "-1"


# --- registry and refunded markets ---------------------------------------------


def test_outcome_ids_are_not_binary():
    assert OUTCOME_ACTION_IDS == frozenset({13, 14, 15, 16})
    assert BINARY_ACTION_IDS == frozenset({6, 7, 8, 9, 12})


@pytest.mark.parametrize(
    "market,refunded",
    [
        ({"settled": True, "winning_outcome": None}, True),
        ({"settled": True}, True),
        ({"settled": True, "winning_outcome": True}, False),
        ({"settled": True, "winning_outcome": False}, False),
        ({"settled": False, "winning_outcome": None}, False),
        ({}, False),
    ],
)
def test_is_market_refunded(market, refunded):
    """settled with no winner is refunded, never unsettled. An indexer market
    leaves winning_outcome out when it is null."""
    assert is_market_refunded(market) is refunded
