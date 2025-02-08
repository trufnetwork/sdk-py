import pytest
import time
from trufnetwork_sdk_py.client import TNClient, UnixRecordBatch, UnixRecord
from trufnetwork_sdk_py.utils import generate_stream_id
import trufnetwork_sdk_c_bindings.exports as truf_sdk
from typing import List

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

def test_batch_small_batches(client, helper_contract_id, current_account):
    """
    Test inserting 20 small batches of records (5 records each) in a single batch call.
    """
    stream_id = generate_stream_id("test_batch_small")

    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass

    client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitiveUnix)
    client.init_stream(stream_id)

    try:
        NUM_BATCHES = 500
        RECORDS_PER_BATCH = 5

        # Time the insertions
        insert_start = time.time()
        
        # Prepare all batches
        batches: List[UnixRecordBatch] = []
        for batch in range(NUM_BATCHES):
            base_timestamp = 1672531200 + (batch * 86400)  # Start from 2023-01-01
            records = [
                UnixRecord(
                    date=base_timestamp + (i * 3600),
                    value=float(batch * 100 + i)
                )
                for i in range(RECORDS_PER_BATCH)
            ]
            batches.append(UnixRecordBatch(
                stream_id=stream_id,
                inputs=records
            ))
        
        # Insert all batches at once
        tx_hash = client.batch_insert_records_unix(batches, helper_contract_stream_id=helper_contract_id, helper_contract_data_provider=current_account, wait=False)['tx_hash']
        assert tx_hash

        insert_duration = time.time() - insert_start
        print(f"[Small Batches] All insertions completed in {insert_duration:.2f}s "
              f"(avg {(insert_duration/NUM_BATCHES)*1000:.2f}ms per batch, "
              f"{(insert_duration/(NUM_BATCHES*RECORDS_PER_BATCH))*1000:.2f}ms per record)")

        # Time the confirmations
        confirm_start = time.time()
        
        # Wait for all transactions after sending them all
        client.wait_for_tx(tx_hash)

        confirm_duration = time.time() - confirm_start
        print(f"[Small Batches] All transactions confirmed in {confirm_duration:.2f}s")

        # Verify total number of records
        total_records = NUM_BATCHES * RECORDS_PER_BATCH
        retrieved_records = client.get_records_unix(
            stream_id,
            date_from=1672531200,
            date_to=1672531200 + (NUM_BATCHES * 86400)
        )
        assert len(retrieved_records) == total_records

    finally:
        client.destroy_stream(stream_id)

def test_batch_large_batches(client, helper_contract_id, current_account):
    """
    Test inserting 5 large batches of records (100 records each) in a single batch call.
    This test expects to fail with a "Request too large" error.
    """
    stream_id = generate_stream_id("test_batch_large")
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass

    client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitiveUnix)
    client.init_stream(stream_id)

    try:
        NUM_BATCHES = 500
        RECORDS_PER_BATCH = 100

        # Time the insertions
        insert_start = time.time()
        
        # Prepare all batches
        batches: List[UnixRecordBatch] = []
        for batch in range(NUM_BATCHES):
            base_timestamp = 1672531200 + (batch * 86400)
            records = [
                UnixRecord(
                    date=base_timestamp + (i * 300),  # 5-minute intervals
                    value=float(batch * 1000 + i)
                )
                for i in range(RECORDS_PER_BATCH)
            ]
            batches.append(UnixRecordBatch(
                stream_id=stream_id,
                inputs=records
            ))
        
        # Insert all batches at once - this should fail with a "Request too large" error
        with pytest.raises(ValueError, match="Request too large: The batch size exceeds the maximum allowed size"):
            client.batch_insert_records_unix(batches, helper_contract_stream_id=helper_contract_id, helper_contract_data_provider=current_account, wait=False)

        print("[Large Batches] Test passed: Request was correctly rejected as too large")

    finally:
        client.destroy_stream(stream_id)

def test_batch_single_record_inserts(client, helper_contract_id, current_account):
    """
    Test inserting individual records in a single batch call.
    """
    stream_id = generate_stream_id("test_batch_singles")

    try:
        client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitiveUnix)
        client.init_stream(stream_id)
        NUM_RECORDS = 500

        # Time the insertions
        insert_start = time.time()
        
        # Prepare all records as individual batches
        base_timestamp = 1672531200
        batches: List[UnixRecordBatch] = []
        for i in range(NUM_RECORDS):
            batches.append(UnixRecordBatch(
                stream_id=stream_id,
                inputs=[UnixRecord(
                    date=base_timestamp + (i * 3600),
                    value=float(i)
                )]
            ))
        
        # Insert all records at once
        tx_hash = client.batch_insert_records_unix(batches, helper_contract_stream_id=helper_contract_id, helper_contract_data_provider=current_account, wait=False)['tx_hash']
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
        retrieved_records = client.get_records_unix(
            stream_id,
            date_from=base_timestamp,
            date_to=base_timestamp + (NUM_RECORDS * 3600)
        )
        assert len(retrieved_records) == NUM_RECORDS

    finally:
        client.destroy_stream(stream_id) 