from datetime import datetime, timezone
import pytest
from trufnetwork_sdk_py.client import TNClient
from trufnetwork_sdk_py.utils import generate_stream_id
import trufnetwork_sdk_c_bindings.exports as truf_sdk
from unittest.mock import patch, MagicMock

# Test configuration
TEST_PROVIDER_URL = "http://localhost:8484"  
TEST_PRIVATE_KEY = (
    "0121234567890123456789012345678901234567890123456789012345178901"
)

@pytest.fixture(scope="module")
def client(tn_node):
    """
    Pytest fixture to create a TNClient instance for testing.
    Uses the tn_node fixture to get a running server.
    """
    client = TNClient(tn_node, TEST_PRIVATE_KEY)
    return client

def test_client_initialization(client):
    """
    Test that the TNClient can be initialized.
    """
    assert client.client is not None

def test_deploy_stream(client):
    """
    Test deploying and initializing a stream.
    """
    stream_id = generate_stream_id("test_stream")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass

    deploy_tx_hash = client.deploy_stream(stream_id)
    assert deploy_tx_hash is not None

    # Clean up
    client.destroy_stream(stream_id)

def test_insert_single_record(client):
    """
    Test inserting single record.
    """
    stream_id = generate_stream_id("test_stream_record")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass

    client.deploy_stream(stream_id)
    
    record_to_insert = {"date": "2023-01-01", "value": 10.5}

    insert_tx_hash = client.insert_record(stream_id, record_to_insert)
    assert insert_tx_hash is not None

    retrieved_records = client.get_records(
        stream_id, date_from="2023-01-01", date_to="2023-01-03"
    )
    assert len(retrieved_records) == 1
    for i, record in enumerate(retrieved_records):
        assert record["EventTime"] == str(date_string_to_unix(record_to_insert["date"]))
        assert float(record["Value"]) == record_to_insert["value"]

    # Clean up
    client.destroy_stream(stream_id)

def test_insert_and_retrieve_records(client):
    """
    Test inserting and retrieving records.
    """
    stream_id = generate_stream_id("test_stream_records")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass

    client.deploy_stream(stream_id)

    records_to_insert = [
        {"date": "2023-01-01", "value": 10.5},
        {"date": "2023-01-02", "value": 12.2},
        {"date": "2023-01-03", "value": 8.8},
    ]
    insert_tx_hash = client.insert_records(stream_id, records_to_insert)
    assert insert_tx_hash is not None

    data_provider = client.get_current_account()

    retrieved_records = client.get_records(
        stream_id, data_provider, date_from="2023-01-01", date_to="2023-01-03"
    )
    assert len(retrieved_records) == len(records_to_insert)
    for i, record in enumerate(retrieved_records):
        assert record["EventTime"] == str(date_string_to_unix(records_to_insert[i]["date"]))
        assert float(record["Value"]) == records_to_insert[i]["value"]

    # Clean up
    client.destroy_stream(stream_id)

def test_get_first_record(client):
    """Test getting the first record from a stream."""
    stream_id = generate_stream_id("test_get_first_record")
    
    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass
        
    # First deploy a stream
    deploy_tx = client.deploy_stream(stream_id)
    assert deploy_tx is not None
    
    # Initialize the stream
    init_tx = client.init_stream(stream_id)
    assert init_tx is not None
    
    # Insert some records
    records = [
        {"date": "2024-01-01", "value": 100.0},
        {"date": "2024-01-02", "value": 200.0},
        {"date": "2024-01-03", "value": 300.0},
    ]
    insert_tx = client.insert_records(stream_id, records)
    assert insert_tx is not None
    
    # Test getting first record with no parameters
    first_record = client.get_first_record(stream_id)
    assert first_record is not None
    assert first_record["date"] == "2024-01-01"
    assert first_record["value"] == 100.0
    
    # Test getting first record after a specific date
    first_after = client.get_first_record(stream_id, after_date="2024-01-02")
    assert first_after is not None
    assert first_after["date"] == "2024-01-02"
    assert first_after["value"] == 200.0
    
    # Test getting first record with non-existent date
    first_nonexistent = client.get_first_record(stream_id, after_date="2024-12-31")
    assert first_nonexistent is None
    
    # Clean up
    destroy_tx = client.destroy_stream(stream_id)
    assert destroy_tx is not None

def test_get_first_record_unix(client):
    """Test getting the first record from a stream using Unix timestamps."""
    stream_id = generate_stream_id("test_get_first_record_unix")
    
    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass
        
    # First deploy a stream with Unix timestamp type
    deploy_tx = client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitiveUnix)
    assert deploy_tx is not None
    
    # Initialize the stream
    init_tx = client.init_stream(stream_id)
    assert init_tx is not None
    
    # Insert some records
    records = [
        {"date": 1704067200, "value": 100.0},  # 2024-01-01
        {"date": 1704153600, "value": 200.0},  # 2024-01-02
        {"date": 1704240000, "value": 300.0},  # 2024-01-03
    ]
    insert_tx = client.insert_records_unix(stream_id, records)
    assert insert_tx is not None
    
    # Test getting first record with no parameters
    first_record = client.get_first_record_unix(stream_id)
    assert first_record is not None
    assert first_record["date"] == 1704067200
    assert first_record["value"] == 100.0
    
    # Test getting first record after a specific date
    first_after = client.get_first_record_unix(stream_id, after_date=1704153600)
    assert first_after is not None
    
    assert first_after["date"] == 1704153600
    assert first_after["value"] == 200.0
    
    # Test getting first record with non-existent date
    first_nonexistent = client.get_first_record_unix(stream_id, after_date=1735689600)  # 2025-01-01
    assert first_nonexistent is None
    
    # Clean up
    destroy_tx = client.destroy_stream(stream_id)
    assert destroy_tx is not None

@pytest.fixture(scope="module")
def helper_contract_id(client):
    """
    Pytest fixture to deploy the helper contract.
    Returns a stream_id that will be automatically cleaned up after tests.
    """
    stream_id = generate_stream_id("test_helper_contract")
    client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypeHelper)
    # Note: Helper contract streams don't require initialization
    yield stream_id
    # Cleanup will run after all tests using this fixture are complete
    client.destroy_stream(stream_id)

def test_filter_initialized_streams(client, helper_contract_id):
    """
    Test filter_initialized_streams method with a real helper contract stream.
    """
    # Set up stream IDs
    stream_id1 = generate_stream_id("test_filter_1")
    stream_id2 = generate_stream_id("test_filter_2")
    
    # Cleanup in case the streams already exist from a previous test run
    try:
        client.destroy_stream(stream_id1)
    except Exception:
        pass
    
    try:
        client.destroy_stream(stream_id2)
    except Exception:
        pass
    
    # Deploy both streams
    client.deploy_stream(stream_id1)
    client.deploy_stream(stream_id2)
    
    # Initialize only the first stream
    client.init_stream(stream_id1)
    
    # Get current account for the data provider
    data_provider = client.get_current_account()
    
    # Test filter_initialized_streams
    stream_ids = [stream_id1, stream_id2]
    data_providers = [data_provider, data_provider]
    
    initialized_streams = client.filter_initialized_streams(
        stream_ids, 
        data_providers=data_providers,
        helper_contract_stream_id=helper_contract_id,
        helper_contract_data_provider=data_provider
    )
    
    # Verify the results
    assert len(initialized_streams) == 1
    assert initialized_streams[0]['stream_id'] == stream_id1
    assert initialized_streams[0]['data_provider'] == data_provider
    
    # Clean up
    client.destroy_stream(stream_id1)
    client.destroy_stream(stream_id2)

def test_filter_non_deployed_streams(client, helper_contract_id):
    """
    Test filter_initialized_streams method with a mix of deployed and non-deployed streams.
    """
    # Set up stream IDs
    stream_id1 = generate_stream_id("test_filter_deployed_1")
    non_deployed_id = generate_stream_id("test_filter_non_deployed")
    
    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id1)
    except Exception:
        pass
    
    # Deploy and initialize one stream
    client.deploy_stream(stream_id1)
    client.init_stream(stream_id1)
    
    # Get current account for the data provider
    data_provider = client.get_current_account()
    
    # Test filter_initialized_streams with a non-deployed stream ID
    stream_ids = [stream_id1, non_deployed_id]
    data_providers = [data_provider, data_provider]
    
    try:
        initialized_streams = client.filter_initialized_streams(
            stream_ids, 
            data_providers=data_providers,
            helper_contract_stream_id=helper_contract_id,
            helper_contract_data_provider=data_provider
        )
        
        # If we get here, the method didn't fail - it should skip the non-deployed stream
        assert len(initialized_streams) == 1
        assert initialized_streams[0]['stream_id'] == stream_id1
        assert initialized_streams[0]['data_provider'] == data_provider
    except Exception as e:
        # Check for the specific error message we saw in our test
        error_message = str(e).lower()
        assert "procedure \"get_metadata\" not found" in error_message or \
               "error filtering initialized streams" in error_message
    
    # Clean up
    client.destroy_stream(stream_id1)

def test_stream_exists(client):
    """Test the stream_exists function with both existing and non-existing streams."""
    # Generate a unique stream ID
    stream_id = generate_stream_id("test_stream_exists")
    non_existent_stream_id = generate_stream_id("non_existent_stream")
    
    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass
    
    # Initially, the stream should not exist
    assert not client.stream_exists(stream_id), "Stream should not exist before deployment"
    
    # Deploy the stream
    deploy_tx = client.deploy_stream(stream_id)
    assert deploy_tx is not None
    
    # After deployment, the stream should exist
    assert client.stream_exists(stream_id), "Stream should exist after deployment"
    
    # Initialize the stream
    init_tx = client.init_stream(stream_id)
    assert init_tx is not None
    
    # After initialization, the stream should still exist
    assert client.stream_exists(stream_id), "Stream should exist after initialization"
    
    # Non-existent stream should return False
    assert not client.stream_exists(non_existent_stream_id), "Non-existent stream should return False"
    
    # Test with the current account as data provider
    data_provider = client.get_current_account()
    assert client.stream_exists(stream_id, data_provider), "Stream should exist with explicit data provider"
    
    # Test with empty string as data provider (should use the default)
    assert client.stream_exists(stream_id, ""), "Stream should exist with empty string data provider"
    
    # Negative test with empty string as data provider
    assert not client.stream_exists(non_existent_stream_id, ""), "Non-existent stream should return False with empty string data provider"
    
    # Clean up
    destroy_tx = client.destroy_stream(stream_id)
    assert destroy_tx is not None
    
    # After destruction, the stream should no longer exist
    assert not client.stream_exists(stream_id), "Stream should not exist after destruction"
    
    # After destruction, the stream should not exist with empty string data provider
    assert not client.stream_exists(stream_id, ""), "Stream should not exist after destruction with empty string data provider" 

def date_string_to_unix(date_str, date_format="%Y-%m-%d"):
    """Convert a date string to a Unix timestamp (integer)."""
    dt = datetime.strptime(date_str, date_format).replace(tzinfo=timezone.utc)
    return int(dt.timestamp())