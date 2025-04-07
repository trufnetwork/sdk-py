import pytest
import time
from trufnetwork_sdk_py.client import TNClient, UnixRecordBatch, UnixRecord, RecordBatch, Record
from trufnetwork_sdk_py.utils import generate_stream_id
import trufnetwork_sdk_c_bindings.exports as truf_sdk
from typing import List
from tests.fixtures.test_trufnetwork import DEFAULT_TN_PRIVATE_KEY
from datetime import datetime, timedelta  # Import datetime and timedelta

@pytest.fixture(scope="module")
def client(tn_node):
    """
    Pytest fixture to create a TNClient instance for testing.
    Uses the tn_node fixture which provides a running test environment.
    """
    client = TNClient(tn_node, DEFAULT_TN_PRIVATE_KEY)
    return client

@pytest.fixture(scope="module")
def current_account(client):
    """
    Pytest fixture to get the current account address.
    """
    return client.get_current_account()

@pytest.fixture(scope="module")
def helper_contract_id(client):
    """
    Pytest fixture to deploy the helper contract.
    Returns a stream_id that will be automatically cleaned up after tests.
    """
    stream_id = generate_stream_id("test_helper_contract")
    client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypeHelper)
    yield stream_id
    # Cleanup will run after all tests using this fixture are complete
    client.destroy_stream(stream_id)

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
                        date=record_date.strftime("%Y-%m-%d"),  # Format the date
                        value=float(batch * 100 + i)
                    )
                )
            batches.append(RecordBatch(
                stream_id=stream_id,
                inputs=records
            ))

        # Insert all batches at once
        tx_hashes = client.batch_insert_records(batches, wait=False)
        assert tx_hashes

        insert_duration = time.time() - insert_start
        print(f"[Small Batches] All insertions completed in {insert_duration:.2f}s "
              f"(avg {(insert_duration/NUM_BATCHES)*1000:.2f}ms per batch, "
              f"{(insert_duration/(NUM_BATCHES*RECORDS_PER_BATCH))*1000:.2f}ms per record)")

        # Time the confirmations
        confirm_start = time.time()
        
        # Wait for all transactions after sending them all
        for tx_hash in tx_hashes:
            client.wait_for_tx(tx_hash)

        confirm_duration = time.time() - confirm_start
        print(f"[Small Batches] All transactions confirmed in {confirm_duration:.2f}s")

        # Verify total number of records
        total_records = NUM_BATCHES * RECORDS_PER_BATCH
        retrieved_records = client.get_records(
            stream_id,
            date_from="2023-01-01",
        )
        assert len(retrieved_records) == total_records

    finally:
        client.destroy_stream(stream_id)

def test_batch_large_batches(client):
    """
    Test inserting 5 large batches of records (100 records each) in a single batch call.
    This test expects to fail with a "Request too large" error.
    """
    stream_id = generate_stream_id("test_batch_large")
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass

    client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitive)

    try:
        NUM_BATCHES = 500
        RECORDS_PER_BATCH = 100
        
        # Prepare all batches
        batches: List[RecordBatch] = []
        for batch in range(NUM_BATCHES):
            records = [
                Record(
                    date=f"2023-01-{(batch % 28) + 1:02d}",  # Cycle through days 1-28
                    value=float(batch * 1000 + i)
                )
                for i in range(RECORDS_PER_BATCH)
            ]
            batches.append(RecordBatch(
                stream_id=stream_id,
                inputs=records
            ))
        
        # Insert all batches at once - this should fail with a "Request too large" error
        with pytest.raises(ValueError, match="Request too large: The batch size exceeds the maximum allowed size"):
            client.batch_insert_records(batches, wait=False)

        print("[Large Batches] Test passed: Request was correctly rejected as too large")

    finally:
        client.destroy_stream(stream_id)

def test_batch_single_record_inserts(client, current_account):
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
                    date=record_date.strftime("%Y-%m-%d"),  # Format the date
                    value=float(i)
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
        
        # Wait for all transactions after sending them all
        client.wait_for_tx(tx_hash)

        confirm_duration = time.time() - confirm_start
        print(f"[Single Records] All transactions confirmed in {confirm_duration:.2f}s")

        # Verify all records were inserted
        retrieved_records = client.get_records(
            stream_id,
            date_from="2023-01-01"
        )
        assert len(retrieved_records) == NUM_RECORDS

    finally:
        client.destroy_stream(stream_id) 