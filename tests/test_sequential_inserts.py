import pytest
import time
from trufnetwork_sdk_py.client import TNClient, RecordBatch, Record
from trufnetwork_sdk_py.utils import generate_stream_id
import trufnetwork_sdk_c_bindings.exports as truf_sdk
from typing import List
from tests.fixtures.test_trufnetwork import DEFAULT_TN_PRIVATE_KEY, tn_node
from datetime import datetime, timedelta, timezone  # Import datetime and timedelta


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

def test_batch_small_batches(client):
    """
    Test inserting 20 small batches of records (5 records each) in a single batch call.
    """
    stream_id = generate_stream_id("test_batch_small_batch")

    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass

    client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitive)

    try:
        NUM_BATCHES = 500
        RECORDS_PER_BATCH = 5

        # Time the insertions
        insert_start = time.time()

        # Prepare all batches
        batches: List[RecordBatch] = []
        start_date = datetime(2023, 1, 1)  # Start date
        for batch in range(NUM_BATCHES):
            records = []
            for i in range(RECORDS_PER_BATCH):
                # Use timedelta to increment the date correctly
                record_date = start_date + timedelta(days=batch * RECORDS_PER_BATCH + i)
                records.append(
                    Record(
                        date=date_string_to_unix(record_date.strftime("%Y-%m-%d")),  # Format the date
                        value=float(batch * 100 + i + 1)  # prevent 0 values
                    )
                )
            batches.append(RecordBatch(
                stream_id=stream_id,
                inputs=records
            ))

        # Insert all batches at once
        tx_hash = client.batch_insert_records(batches, wait=False)
        assert tx_hash

        insert_duration = time.time() - insert_start
        print(f"[Small Batches] All insertions completed in {insert_duration:.2f}s "
              f"(avg {(insert_duration/NUM_BATCHES)*1000:.2f}ms per batch, "
              f"{(insert_duration/(NUM_BATCHES*RECORDS_PER_BATCH))*1000:.2f}ms per record)")

        # Time the confirmations
        confirm_start = time.time()
        
        # Wait for the single transaction after sending all records
        client.wait_for_tx(tx_hash)

        confirm_duration = time.time() - confirm_start
        print(f"[Small Batches] Transaction confirmed in {confirm_duration:.2f}s")

        # Verify total number of records
        total_records = NUM_BATCHES * RECORDS_PER_BATCH
        retrieved_records = client.get_records(
            stream_id,
            date_from=date_string_to_unix("2023-01-01"),
        )
        assert len(retrieved_records) == total_records

    finally:
        client.destroy_stream(stream_id)

def test_batch_single_record_inserts(client):
    """
    Test inserting individual records in a single batch call.
    """
    stream_id = generate_stream_id("test_batch_singles")

    try:
        client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitive)
        NUM_RECORDS = 500

        # Time the insertions
        insert_start = time.time()

        # Prepare all records as individual batches
        batches: List[RecordBatch] = []
        start_date = datetime(2023, 1, 1)  # Start date
        for i in range(NUM_RECORDS):
            # Use timedelta to increment the date
            record_date = start_date + timedelta(days=i)
            batches.append(RecordBatch(
                stream_id=stream_id,
                inputs=[Record(
                    date=date_string_to_unix(record_date.strftime("%Y-%m-%d")),  # Format the date
                    value=float(i+1) # prevent 0 values
                )]
            ))

        # Insert all records at once
        tx_hash = client.batch_insert_records(batches, wait=False)
        assert tx_hash

        insert_duration = time.time() - insert_start
        print(f"[Single Records] All insertions completed in {insert_duration:.2f}s "
              f"(avg {(insert_duration/NUM_RECORDS)*1000:.2f}ms per record)")

        # Time the confirmations
        confirm_start = time.time()
        
        # Wait for the single transaction after sending all records
        client.wait_for_tx(tx_hash)

        confirm_duration = time.time() - confirm_start
        print(f"[Single Records] Transaction confirmed in {confirm_duration:.2f}s")

        # Verify all records were inserted
        retrieved_records = client.get_records(
            stream_id,
            date_from=date_string_to_unix("2023-01-01")
        )
        assert len(retrieved_records) == NUM_RECORDS

    finally:
        client.destroy_stream(stream_id) 

def date_string_to_unix(date_str, date_format="%Y-%m-%d"):
    """Convert a date string to a Unix timestamp (integer)."""
    dt = datetime.strptime(date_str, date_format).replace(tzinfo=timezone.utc)
    return int(dt.timestamp())