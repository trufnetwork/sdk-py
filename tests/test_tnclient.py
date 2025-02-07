import pytest
from trufnetwork_sdk_py.client import TNClient
from trufnetwork_sdk_py.utils import generate_stream_id
import trufnetwork_sdk_c_bindings.exports as truf_sdk

# Test configuration
TEST_PROVIDER_URL = "http://localhost:8484"  
TEST_PRIVATE_KEY = (
    "0121234567890123456789012345678901234567890123456789012345178901"
)

@pytest.fixture(scope="module")
def client():
    """
    Pytest fixture to create a TNClient instance for testing.
    """
    client = TNClient(TEST_PROVIDER_URL, TEST_PRIVATE_KEY)
    return client

def test_client_initialization(client):
    """
    Test that the TNClient can be initialized.
    """
    assert client.client is not None

def test_deploy_and_initialize_stream(client):
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

    init_tx_hash = client.init_stream(stream_id)
    assert init_tx_hash is not None

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
    client.init_stream(stream_id)

    records_to_insert = [
        {"date": "2023-01-01", "value": 10.5},
        {"date": "2023-01-02", "value": 12.2},
        {"date": "2023-01-03", "value": 8.8},
    ]
    insert_tx_hash = client.insert_records(stream_id, records_to_insert)
    assert insert_tx_hash is not None

    retrieved_records = client.get_records(
        stream_id, date_from="2023-01-01", date_to="2023-01-03"
    )
    assert len(retrieved_records) == len(records_to_insert)
    for i, record in enumerate(retrieved_records):
        assert record["DateValue"] == records_to_insert[i]["date"]
        assert float(record["Value"]) == records_to_insert[i]["value"]

    # Clean up
    client.destroy_stream(stream_id)

def test_insert_and_retrieve_records_unix(client):
    """
    Test inserting and retrieving records with Unix timestamps.
    """
    stream_id = generate_stream_id("test_stream_records_unix")

    try:
        # Cleanup in case the stream already exists from a previous test run
        try:
            client.destroy_stream(stream_id)
        except Exception:
            pass

        client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitiveUnix)
        client.init_stream(stream_id)

        records_to_insert = [
            {"date": 1672531200, "value": 10.5},  # 2023-01-01 in Unix time
            {"date": 1672617600, "value": 12.2},  # 2023-01-02 in Unix time
            {"date": 1672704000, "value": 8.8},  # 2023-01-03 in Unix time
        ]
        insert_tx_hash = client.insert_records_unix(stream_id, records_to_insert)
        assert insert_tx_hash is not None

        retrieved_records = client.get_records_unix(
            stream_id, date_from=1672531200, date_to=1672704000
        )
        assert len(retrieved_records) == len(records_to_insert)
        for i, record in enumerate(retrieved_records):
            assert int(record["DateValue"]) == records_to_insert[i]["date"]
            assert float(record["Value"]) == records_to_insert[i]["value"]

    finally:
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