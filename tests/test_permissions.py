from datetime import datetime, timezone
import pytest
from trufnetwork_sdk_py.client import TNClient
from trufnetwork_sdk_py.utils import generate_stream_id
import trufnetwork_sdk_c_bindings.exports as truf_sdk

# Test configuration
TEST_PROVIDER_URL = "http://localhost:8484"  
TEST_OWNER_PRIVATE_KEY = (
    "0121234567890123456789012345678901234567890123456789012345178901"
)
TEST_READER_PRIVATE_KEY = (
    "0000000000000000000000000000000000000000000000000000000000000001"
)

@pytest.fixture(scope="module")
def owner_client():
    """
    Pytest fixture to create a TNClient instance for testing.
    Uses the tn_node fixture to get a running server.
    """
    client = TNClient(TEST_PROVIDER_URL, TEST_OWNER_PRIVATE_KEY)
    return client

@pytest.fixture(scope="module")
def reader_client():
    """
    Pytest fixture to create a TNClient instance for testing.
    Uses the tn_node fixture to get a running server.
    """
    client = TNClient(TEST_PROVIDER_URL, TEST_READER_PRIVATE_KEY)
    return client

def test_primitive_permissions(owner_client, reader_client):
    """
    Test primitive stream permissions
    """
    stream_id = generate_stream_id("test_primitive_permission")

    # Cleanup in case the stream already exists from a previous test run
    try:
        owner_client.destroy_stream(stream_id)
    except Exception:
        pass

    owner_client.deploy_stream(stream_id)

    # insert records to the stream
    record_to_insert = {"date": "2023-01-01", "value": 10.5}

    insert_tx_hash = owner_client.insert_record(stream_id, record_to_insert)
    assert insert_tx_hash is not None

    data_provider = owner_client.get_current_account()

    # ok - public read
    retrieved_records = reader_client.get_records(
        stream_id, data_provider, date_from="2023-01-01", date_to="2023-01-03"
    )
    assert len(retrieved_records) == 1
    for i, record in enumerate(retrieved_records):
        assert record["EventTime"] == str(date_string_to_unix(record_to_insert["date"]))
        assert float(record["Value"]) == record_to_insert["value"]

    # set the stream read to private
    owner_client.set_read_visibility(stream_id, "private")
    visibility = owner_client.get_read_visibility(stream_id)
    assert visibility == "private"

    # ok - owner access their own private stream
    retrieved_records = owner_client.get_records(
        stream_id, data_provider, date_from="2023-01-01", date_to="2023-01-03"
    )
    assert len(retrieved_records) == 1

    # fail - reader access private stream
    with pytest.raises(Exception):
        retrieved_records = reader_client.get_records(
            stream_id, data_provider, date_from="2023-01-01", date_to="2023-01-03"
        )

    # allow read access to reader
    owner_client.allow_read_wallet(stream_id, reader_client.get_current_account())

    # ok - reader with access
    retrieved_records = reader_client.get_records(
        stream_id, data_provider, date_from="2023-01-01", date_to="2023-01-03"
    )

    owner_client.destroy_stream(stream_id)

def test_composed_permissions(client):
    """
    Test composed stream permissions
    """
    composed_stream_id = generate_stream_id("test_composed_permission")
    primitive_stream_id = generate_stream_id("test_primitive_permission")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(composed_stream_id)
        client.destroy_stream(primitive_stream_id)
    except Exception:
        pass

    client.destroy_stream(composed_stream_id)
    client.destroy_stream(primitive_stream_id)

def test_stream_composition_permissions(client):
    """
    Test composed stream permissions
    """
    composed_stream_id = generate_stream_id("test_composed_permission")
    primitive_stream_id = generate_stream_id("test_primitive_permission")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(composed_stream_id)
        client.destroy_stream(primitive_stream_id)
    except Exception:
        pass

    client.destroy_stream(composed_stream_id)
    client.destroy_stream(primitive_stream_id)

def date_string_to_unix(date_str, date_format="%Y-%m-%d"):
    """Convert a date string to a Unix timestamp (integer)."""
    dt = datetime.strptime(date_str, date_format).replace(tzinfo=timezone.utc)
    return int(dt.timestamp())