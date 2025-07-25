import pytest
import warnings
from trufnetwork_sdk_py.client import CacheMetadata, StreamRecord, TNClient, CacheAwareResponse
from trufnetwork_sdk_py.utils import generate_stream_id

# Test configuration
TEST_PRIVATE_KEY = (
    "0121234567890123456789012345678901234567890123456789012345178901"
)

@pytest.fixture(scope="module")
def client(tn_node, grant_network_writer):
    """
    Pytest fixture to create a TNClient instance for testing.
    Uses the tn_node fixture to get a running server.
    """
    client = TNClient(tn_node, TEST_PRIVATE_KEY)
    grant_network_writer(client)
    return client

def test_cache_ovld_dispatch_legacy_signature(client: TNClient):
    """Test that legacy signature emits warning and works correctly"""
    stream_id = generate_stream_id("test_cache_legacy")
    
    # Clean up any existing stream
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass
    
    # Deploy stream
    client.deploy_stream(stream_id)
    
    # Insert test record
    test_record = {"date": 1234567890, "value": 42.0}
    client.insert_record(stream_id, test_record)
    
    # Test legacy signature with warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = client.get_records(stream_id)
        
        # Check that warning was emitted
        assert len(w) > 0
        # find our deprecation warning
        deprecation_warning = next((warning for warning in w if issubclass(warning.category, DeprecationWarning)), None)
        assert deprecation_warning is not None
        assert "use_cache" in str(deprecation_warning.message)
        
        # Check that result is in legacy format
        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0]["EventTime"] == str(test_record["date"])
        assert result[0]["Value"] == test_record["value"]
    
    # Clean up
    client.destroy_stream(stream_id)

def test_cache_aware_signature_false(client):
    """Test cache-aware signature with use_cache=False"""
    stream_id = generate_stream_id("test_cache_false")
    
    # Clean up any existing stream
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass
    
    # Deploy stream
    client.deploy_stream(stream_id)
    
    # Insert test record
    test_record = {"date": 1234567890, "value": 42.0}
    client.insert_record(stream_id, test_record)
    
    # Test cache-aware signature with use_cache=False
    result = client.get_records(stream_id, use_cache=False)
    
    # Should return CacheAwareResponse structure, because we are using the cache-aware signature
    assert isinstance(result, CacheAwareResponse)
    assert result.data is not None
    assert result.cache is not None
    assert result.cache.hit == False
    assert result.cache.cache_height == None
    
    # Clean up
    client.destroy_stream(stream_id)

def test_cache_aware_signature_true(client: TNClient):
    """Test cache-aware signature with use_cache=True"""
    stream_id = generate_stream_id("test_cache_true")
    
    # Clean up any existing stream
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass
    
    # Deploy stream
    client.deploy_stream(stream_id)
    
    # Insert test record
    test_record = {"date": 1234567890, "value": 42.0}
    client.insert_record(stream_id, test_record)
    
    # Test cache-aware signature with use_cache=True
    result = client.get_records(stream_id, use_cache=True)
    
    # Should return CacheAwareResponse structure
    assert isinstance(result, CacheAwareResponse)
    assert result.data is not None
    assert result.cache is not None
    
    # Check data structure
    assert isinstance(result.data, list)
    assert len(result.data) > 0
    assert result.data[0].EventTime == str(test_record["date"])
    assert result.data[0].Value == test_record["value"]
    
    # Check cache metadata structure (should be cache miss)
    assert isinstance(result.cache, CacheMetadata)
    assert result.cache.hit == False
    assert result.cache.cache_height == None
    
    # Clean up
    client.destroy_stream(stream_id)

def test_get_first_record_cache_support(client):
    """Test get_first_record with cache support"""
    stream_id = generate_stream_id("test_first_record_cache")
    
    # Clean up any existing stream
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass
    
    # Deploy stream
    client.deploy_stream(stream_id)
    
    # Insert test record
    test_record = {"date": 1234567890, "value": 42.0}
    client.insert_record(stream_id, test_record)
    
    # Test legacy signature with warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = client.get_first_record(stream_id)
        
        # Check that warning was emitted
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "use_cache" in str(w[0].message)
        
        # Check result format
        assert isinstance(result, StreamRecord)
        assert result.EventTime == str(test_record["date"])
        assert result.Value == test_record["value"]
    
    # Test cache-aware signature
    result = client.get_first_record(stream_id, use_cache=True)
    
    # Should return CacheAwareResponse structure
    assert isinstance(result, CacheAwareResponse)
    assert result.data is not None
    assert result.cache is not None
    assert result.cache.cache_height == None
    
    # Clean up
    client.destroy_stream(stream_id)

def test_get_index_cache_support(client):
    """Test get_index with cache support"""
    stream_id = generate_stream_id("test_index_cache")
    
    # Clean up any existing stream
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass
    
    # Deploy stream
    client.deploy_stream(stream_id)
    
    # Insert test records
    test_records = [
        {"date": 1234567890, "value": 100.0},
        {"date": 1234567891, "value": 110.0}
    ]
    for record in test_records:
        client.insert_record(stream_id, record)
    
    # Test legacy signature with warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = client.get_index(stream_id)
        
        # Check that warning was emitted
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "use_cache" in str(w[0].message)
        
        # Check result format
        assert isinstance(result, list)
    
    # Test cache-aware signature
    result = client.get_index(stream_id, use_cache=True)
    
    # Should return CacheAwareResponse structure
    assert isinstance(result, CacheAwareResponse)
    assert result.data is not None
    assert result.cache is not None
    assert result.cache.cache_height == None
    
    # Clean up
    client.destroy_stream(stream_id)

def test_map_cache_metadata_with_height(client):
    """Test mapping cache metadata with height"""
    # Test cache hit with height
    mock_response = {
        'CacheHit': True,
        'Height': {'IsSet': True, 'Value': 123456}
    }
    metadata = client._map_cache_metadata(mock_response)  # type: ignore
    assert metadata.hit == True
    assert metadata.cache_height == 123456

    # Test miss case
    mock_miss = {'CacheHit': False}
    metadata = client._map_cache_metadata(mock_miss)  # type: ignore
    assert metadata.hit == False
    assert metadata.cache_height == None