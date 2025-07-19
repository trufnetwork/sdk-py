from datetime import datetime, timezone
import pytest
from trufnetwork_sdk_py.client import TNClient, TaxonomyDefinition
from trufnetwork_sdk_py.utils import generate_stream_id
import trufnetwork_sdk_c_bindings.exports as truf_sdk

# Test configuration
TEST_PRIVATE_KEY = "0121234567890123456789012345678901234567890123456789012345178901"


@pytest.fixture(scope="module")
def client(tn_node, grant_network_writer):
    """
    Pytest fixture to create a TNClient instance for testing.
    Uses the tn_node fixture to get a running server.
    """
    client = TNClient(tn_node, TEST_PRIVATE_KEY)
    grant_network_writer(client)
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

    record_to_insert = {"date": date_string_to_unix("2023-01-01"), "value": 10.5}

    insert_tx_hash = client.insert_record(stream_id, record_to_insert)
    assert insert_tx_hash is not None

    retrieved_records = client.get_records(
        stream_id,
        date_from=date_string_to_unix("2023-01-01"),
        date_to=date_string_to_unix("2023-01-03"),
    )
    assert len(retrieved_records) == 1
    for i, record in enumerate(retrieved_records):
        assert record["EventTime"] == str(record_to_insert["date"])
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
        {"date": date_string_to_unix("2023-01-01"), "value": 10.5},
        {"date": date_string_to_unix("2023-01-02"), "value": 12.2},
        {"date": date_string_to_unix("2023-01-03"), "value": 8.8},
    ]
    insert_tx_hash = client.insert_records(stream_id, records_to_insert)
    assert insert_tx_hash is not None

    data_provider = client.get_current_account()

    retrieved_records = client.get_records(
        stream_id,
        data_provider,
        date_from=date_string_to_unix("2023-01-01"),
        date_to=date_string_to_unix("2023-01-03"),
    )
    assert len(retrieved_records) == len(records_to_insert)
    for i, record in enumerate(retrieved_records):
        assert record["EventTime"] == str(records_to_insert[i]["date"])
        assert float(record["Value"]) == records_to_insert[i]["value"]

    # Clean up
    client.destroy_stream(stream_id)


def test_get_first_record(client: TNClient):
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

    # Insert some records
    records = [
        {"date": date_string_to_unix("2024-01-01"), "value": 100.0},
        {"date": date_string_to_unix("2024-01-02"), "value": 200.0},
        {"date": date_string_to_unix("2024-01-03"), "value": 300.0},
    ]
    insert_tx = client.insert_records(stream_id, records)
    assert insert_tx is not None

    # Test getting first record with no parameters
    first_record = client.get_first_record(stream_id)
    assert first_record is not None
    assert first_record.EventTime == str(records[0]["date"])
    assert first_record.Value == 100.0

    # Test getting first record after a specific date
    first_after = client.get_first_record(
        stream_id, after_date=date_string_to_unix("2024-01-02")
    )
    assert first_after is not None
    assert first_after.EventTime == str(records[1]["date"])
    assert first_after.Value == 200.0

    # Test getting first record with non-existent date
    first_nonexistent = client.get_first_record(
        stream_id, after_date=date_string_to_unix("2024-12-31")
    )
    assert first_nonexistent is None

    # Clean up
    destroy_tx = client.destroy_stream(stream_id)
    assert destroy_tx is not None


def test_get_index(client):
    """
    Test getting index from a stream.
    """
    stream_id = generate_stream_id("test_stream_index")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass

    client.deploy_stream(stream_id)

    records_to_insert = [
        {"date": date_string_to_unix("2023-01-01"), "value": 10.5},
        {"date": date_string_to_unix("2023-01-02"), "value": 12.2},
        {"date": date_string_to_unix("2023-01-03"), "value": 8.8},
    ]
    insert_tx_hash = client.insert_records(stream_id, records_to_insert)
    assert insert_tx_hash is not None

    data_provider = client.get_current_account()

    retrieved_indexes = client.get_index(
        stream_id,
        data_provider,
        date_from=date_string_to_unix("2023-01-01"),
        date_to=date_string_to_unix("2023-01-03"),
    )
    assert len(retrieved_indexes) == len(records_to_insert)
    for i, record in enumerate(retrieved_indexes):
        assert record["EventTime"] == str(records_to_insert[i]["date"])
        assert round(float(record["Value"]), 3) == round(
            float(
                (records_to_insert[i]["value"] / records_to_insert[0]["value"]) * 100
            ),
            3,
        )

    # Clean up
    client.destroy_stream(stream_id)


def test_get_type(client):
    """
    Test that gets the type of the stream.
    """
    stream_id = generate_stream_id("stream_for_primitive_type")
    composed_stream_id = generate_stream_id("stream_for_composed_type")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id)
        client.destroy_stream(composed_stream_id)
    except Exception:
        pass

    client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitive, wait=True)
    client.deploy_stream(
        composed_stream_id, stream_type=truf_sdk.StreamTypeComposed, wait=True
    )

    stream_type = client.get_type(stream_id, client.get_current_account())
    assert stream_type == truf_sdk.StreamTypePrimitive, (
        "Stream type should be primitive"
    )

    stream_type = client.get_type(composed_stream_id, client.get_current_account())
    assert stream_type == truf_sdk.StreamTypeComposed, "Stream type should be composed"

    client.destroy_stream(stream_id)
    client.destroy_stream(composed_stream_id)


def test_taxonomy(client: TNClient):
    """
    Test set and retrieve taxonomy of composed stream
    """
    stream_id = generate_stream_id("test_taxonomy")
    child_stream_id_1 = generate_stream_id("test_child_stream1")
    child_stream_id_2 = generate_stream_id("test_child_stream2")

    # Cleanup in case the stream already exists from a previous test run
    try:
        client.destroy_stream(stream_id)
        client.destroy_stream(child_stream_id_1)
        client.destroy_stream(child_stream_id_2)
    except Exception:
        pass

    client.deploy_stream(stream_id, "composed")
    client.deploy_stream(child_stream_id_1)
    client.deploy_stream(child_stream_id_2)

    taxonomies = [
        TaxonomyDefinition(
            stream={
                "stream_id": child_stream_id_1,
                "data_provider": "0x1234567890123456789012345678901234567890",
            },
            weight=0.5,
        ),
        TaxonomyDefinition(
            stream={
                "stream_id": child_stream_id_2,
                "data_provider": None,
            },
            weight=0.5,
        ),
    ]
    tx_hash = client.set_taxonomy(stream_id, taxonomies, wait=True)
    assert tx_hash is not None

    taxonomy_details = client.describe_taxonomy(stream_id)
    assert taxonomy_details is not None
    assert taxonomy_details["stream_id"] == stream_id

    described_taxonomies = taxonomy_details["child_streams"]
    assert len(described_taxonomies) == 2

    taxonomy_map = {t.stream["stream_id"]: t for t in described_taxonomies}

    # Check first taxonomy
    assert child_stream_id_1 in taxonomy_map
    taxonomy1 = taxonomy_map[child_stream_id_1]
    assert taxonomy1.weight == 0.5
    assert (
        taxonomy1.stream["data_provider"]
        == "0x1234567890123456789012345678901234567890"
    )

    # Check second taxonomy
    assert child_stream_id_2 in taxonomy_map
    taxonomy2 = taxonomy_map[child_stream_id_2]
    assert taxonomy2.weight == 0.5
    assert taxonomy2.stream["data_provider"] == client.get_current_account()

    client.destroy_stream(stream_id)
    client.destroy_stream(child_stream_id_1)
    client.destroy_stream(child_stream_id_2)


def date_string_to_unix(date_str, date_format="%Y-%m-%d"):
    """Convert a date string to a Unix timestamp (integer)."""
    dt = datetime.strptime(date_str, date_format).replace(tzinfo=timezone.utc)
    return int(dt.timestamp())
