import pytest
from trufnetwork_sdk_py.client import TNClient

def test_decode_market_data():
    # Use realistic test data
    data_provider = "0x4710a8d8f0d845da110086812a32de6d90d7ff5c"
    stream_id = "stbtcusd000000000000000000000000"
    
    # 1. Test ABOVE market
    threshold = "100000.0"
    args = [data_provider, stream_id, 1735689600, threshold, None]
    encoded_args = TNClient.encode_action_args(args)
    query_components = TNClient.encode_query_components(
        data_provider, stream_id, "price_above_threshold", encoded_args
    )
    
    decoded = TNClient.decode_market_data(query_components)
    
    assert decoded["type"] == "above"
    assert decoded["thresholds"] == [threshold]
    assert decoded["data_provider"].lower() == data_provider.lower()
    assert decoded["stream_id"] == stream_id

    # 2. Test BETWEEN market
    min_val = "90000.0"
    max_val = "110000.0"
    args2 = [data_provider, stream_id, 1735689600, min_val, max_val, None]
    encoded_args2 = TNClient.encode_action_args(args2)
    query_components2 = TNClient.encode_query_components(
        data_provider, stream_id, "value_in_range", encoded_args2
    )
    
    decoded2 = TNClient.decode_market_data(query_components2)
    
    assert decoded2["type"] == "between"
    assert decoded2["thresholds"] == [min_val, max_val]

def test_decode_query_components_raw():
    data_provider = "0x4710a8d8f0d845da110086812a32de6d90d7ff5c"
    stream_id = "stbtcusd000000000000000000000000"
    args = b"\x01\x02\x03"
    
    encoded = TNClient.encode_query_components(
        data_provider, stream_id, "get_record", args
    )
    
    decoded = TNClient.decode_query_components(encoded)
    
    assert decoded["data_provider"].lower() == data_provider.lower()
    assert decoded["stream_id"] == stream_id
    assert decoded["action_id"] == "get_record"
    assert decoded["args"] == args.hex()


# ═══════════════════════════════════════════════════════════════
# index_change_in_range (action id 12)
# ═══════════════════════════════════════════════════════════════

INDEX_CHANGE_PROVIDER = "0x4710a8d8f0d845da110086812a32de6d90d7ff5c"
INDEX_CHANGE_STREAM = "stcpiyoy000000000000000000000000"
YEAR_IN_SECONDS = 31536000
OBSERVE_AT = 1735689600


def _build(min_change=None, max_change=None, **kwargs):
    return TNClient.build_index_change_in_range_query_components(
        INDEX_CHANGE_PROVIDER,
        INDEX_CHANGE_STREAM,
        OBSERVE_AT,
        YEAR_IN_SECONDS,
        min_change=min_change,
        max_change=max_change,
        **kwargs,
    )


def test_index_change_market_decodes_as_its_own_type():
    """Not "between": that type's consumers parse both thresholds as numbers and
    would reject the open tail this action is allowed to strike."""
    decoded = TNClient.decode_market_data(_build("2", "3"))

    assert decoded["action_id"] == "index_change_in_range"
    assert decoded["type"] == "change_between"
    assert decoded["thresholds"] == [
        "2.000000000000000000",
        "3.000000000000000000",
    ]
    assert decoded["data_provider"].lower() == INDEX_CHANGE_PROVIDER
    assert decoded["stream_id"] == INDEX_CHANGE_STREAM
    assert decoded["timestamp"] == OBSERVE_AT
    assert decoded["frozen_at"] is None


def test_index_change_open_tail_holds_its_slot():
    """An open bound decodes as an empty string in place. If it were dropped,
    the surviving bound would slide into the other position and the market would
    read as its own mirror image."""
    bottom = TNClient.decode_market_data(_build(max_change="1"))
    assert bottom["thresholds"] == ["", "1.000000000000000000"]

    top = TNClient.decode_market_data(_build(min_change="4"))
    assert top["thresholds"] == ["4.000000000000000000", ""]


def test_index_change_frozen_at_round_trips():
    decoded = TNClient.decode_market_data(_build("2", "3", frozen_at=1735000000))
    assert decoded["frozen_at"] == 1735000000


def test_index_change_bounds_are_compared_as_decimals():
    """sdk-go parses both bounds to NUMERIC(36,18) before ordering them. As
    strings "2.0" and "2" are unequal, so a string comparison would let an empty
    bucket through."""
    with pytest.raises(Exception, match="min_change must be less than max_change"):
        _build("2.0", "2")

    # "10" sorts below "9" as a string and above it as a number.
    decoded = TNClient.decode_market_data(_build("9", "10"))
    assert decoded["thresholds"] == [
        "9.000000000000000000",
        "10.000000000000000000",
    ]


def test_index_change_needs_at_least_one_bound():
    with pytest.raises(Exception, match="at least one of min_change or max_change"):
        _build()


def test_index_change_builder_refuses_an_empty_bound():
    """The builder has to refuse "" for the same reason the create helper does.

    An empty string is the sentinel the binding reads as an open tail, so it
    would be accepted as one rather than rejected, and the caller would get a
    market struck on different bounds than they asked for.
    """
    for lo, hi in (("", "3"), ("2", "")):
        with pytest.raises(ValueError, match="cannot be empty strings"):
            _build(lo, hi)


def test_index_change_market_feeds_the_bucket_reader():
    """The decode output is what bucket_bounds_from_market_data consumes, so the
    two have to agree about where an open tail lives."""
    from trufnetwork_sdk_py.market_buckets import bucket_bounds_from_market_data

    edges = ["1", "2", "3"]
    strikes = (
        [(None, edges[0])]
        + [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
        + [(edges[-1], None)]
    )
    bounds = [
        bucket_bounds_from_market_data(TNClient.decode_market_data(_build(lo, hi)))
        for lo, hi in strikes
    ]

    assert bounds[0][0] is None
    assert bounds[-1][1] is None
    for (_, upper), (lower, _) in zip(bounds, bounds[1:]):
        assert upper == lower
