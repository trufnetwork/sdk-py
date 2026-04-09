import pytest
import time
from trufnetwork_sdk_py.client import TNClient, RecordBatch, Record
from trufnetwork_sdk_py.utils import generate_stream_id
import trufnetwork_sdk_c_bindings.exports as truf_sdk
from typing import List
from tests.fixtures.test_trufnetwork import DEFAULT_TN_PRIVATE_KEY, tn_node
from datetime import datetime, timedelta, timezone


@pytest.fixture(scope="module")
def client(tn_node, grant_network_writer):
    """
    Pytest fixture to create a TNClient instance for testing.
    Uses the tn_node fixture which provides a running test environment.
    """
    client = TNClient(tn_node, DEFAULT_TN_PRIVATE_KEY)
    grant_network_writer(client)
    return client


@pytest.fixture(scope="module")
def current_account(client):
    """
    Pytest fixture to get the current account address.
    """
    return client.get_current_account()


# Maximum records per insert_records call enforced by the node.
# See node/internal/migrations/003-primitive-insertion.sql:42-44.
MAX_RECORDS_PER_TX = 10


def _safe_destroy(client, stream_id):
    """Best-effort stream cleanup — never raises."""
    if stream_id is None:
        return
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass  # cleanup failure must not mask the original test error


def test_batch_small_batches(client):
    """
    Test inserting small batches of records, each within the per-tx cap.
    Each batch_insert_records call sends ≤ MAX_RECORDS_PER_TX records
    and waits for confirmation before the next — matching the post-deadlock
    "many small sequential transactions" design.
    """
    stream_id = generate_stream_id("test_batch_small_batch")

    _safe_destroy(client, stream_id)
    client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitive)

    try:
        NUM_BATCHES = 50
        RECORDS_PER_BATCH = 5
        assert RECORDS_PER_BATCH <= MAX_RECORDS_PER_TX, \
            f"RECORDS_PER_BATCH ({RECORDS_PER_BATCH}) exceeds MAX_RECORDS_PER_TX ({MAX_RECORDS_PER_TX})"

        start_time = time.time()
        start_date = datetime(2023, 1, 1)

        for batch in range(NUM_BATCHES):
            records = []
            for i in range(RECORDS_PER_BATCH):
                record_date = start_date + timedelta(days=batch * RECORDS_PER_BATCH + i)
                records.append(
                    Record(
                        date=date_string_to_unix(record_date.strftime("%Y-%m-%d")),
                        value=float(batch * 100 + i + 1)  # +1 to avoid zero (filtered by consensus)
                    )
                )
            batches: List[RecordBatch] = [RecordBatch(
                stream_id=stream_id,
                inputs=records
            )]
            # Each call sends ≤5 records (under the 10-record cap) and waits.
            tx_hash = client.batch_insert_records(batches, wait=True)
            assert tx_hash

        duration = time.time() - start_time
        print(f"[Small Batches] {NUM_BATCHES} batches of {RECORDS_PER_BATCH} inserted in {duration:.2f}s "
              f"(avg {(duration/NUM_BATCHES)*1000:.1f}ms per batch)")

        # Verify total number of records
        total_records = NUM_BATCHES * RECORDS_PER_BATCH
        retrieved_records = client.get_records(
            stream_id,
            date_from=date_string_to_unix("2023-01-01"),
        )
        assert len(retrieved_records) == total_records

    finally:
        _safe_destroy(client, stream_id)


def test_batch_single_record_inserts(client):
    """
    Test inserting individual records one-per-transaction.
    Each insert_records call sends 1 record and waits for confirmation.
    """
    stream_id = generate_stream_id("test_batch_singles")

    try:
        client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitive)
        NUM_RECORDS = 50

        start_time = time.time()
        start_date = datetime(2023, 1, 1)

        for i in range(NUM_RECORDS):
            record_date = start_date + timedelta(days=i)
            record = {"date": date_string_to_unix(record_date.strftime("%Y-%m-%d")),
                      "value": float(i + 1)}  # +1 to avoid zero
            client.insert_record(stream_id, record, wait=True)

        duration = time.time() - start_time
        print(f"[Single Records] {NUM_RECORDS} records inserted in {duration:.2f}s "
              f"(avg {(duration/NUM_RECORDS)*1000:.1f}ms per record)")

        # Verify all records were inserted
        retrieved_records = client.get_records(
            stream_id,
            date_from=date_string_to_unix("2023-01-01")
        )
        assert len(retrieved_records) == NUM_RECORDS

    finally:
        _safe_destroy(client, stream_id)


def date_string_to_unix(date_str, date_format="%Y-%m-%d"):
    """Convert a date string to a Unix timestamp (integer)."""
    dt = datetime.strptime(date_str, date_format).replace(tzinfo=timezone.utc)
    return int(dt.timestamp())
