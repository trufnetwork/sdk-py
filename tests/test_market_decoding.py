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
