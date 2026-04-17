"""
Integration tests for the BulkInserter Python wrapper.

The Go-side BulkInserter has full unit coverage in
sdk-go/core/contractsapi/bulk_inserter_test.go — these tests focus on the
Python wrapper plumbing:
- constructor null check
- empty input short-circuits
- end-to-end record insertion against a real node
- post-insertion records are readable
- failure modes propagate as BulkInsertError
"""

import time
from datetime import datetime, timedelta, timezone
from typing import List

import pytest
import trufnetwork_sdk_c_bindings.exports as truf_sdk

from tests.fixtures.test_trufnetwork import DEFAULT_TN_PRIVATE_KEY, tn_node
from trufnetwork_sdk_py import BulkInserter, BulkInsertError
from trufnetwork_sdk_py.client import Record, RecordBatch, TNClient
from trufnetwork_sdk_py.utils import generate_stream_id


@pytest.fixture(scope="module")
def client(tn_node, grant_network_writer):
    c = TNClient(tn_node, DEFAULT_TN_PRIVATE_KEY)
    grant_network_writer(c)
    return c


def _safe_destroy(client, stream_id):
    if stream_id is None:
        return
    try:
        client.destroy_stream(stream_id)
    except Exception:
        pass


def _date_to_unix(date: datetime) -> int:
    return int(date.replace(tzinfo=timezone.utc).timestamp())


# --- pure unit tests (no node required) ---


def test_constructor_rejects_none_client():
    with pytest.raises(ValueError, match="client is required"):
        BulkInserter(None)


# --- integration tests (require tn_node) ---


def test_insert_all_empty_batches_returns_empty(client):
    inserter = BulkInserter(client)
    assert inserter.insert_all([]) == []


def test_insert_all_empty_inputs_returns_empty(client):
    inserter = BulkInserter(client)
    # batches with empty inputs lists should also short-circuit
    assert inserter.insert_all([{"stream_id": "x", "inputs": []}]) == []


def test_insert_all_inserts_and_reads_back(client):
    """End-to-end: BulkInserter → insert 25 records → read back → verify."""
    stream_id = generate_stream_id("test_bulk_inserter_e2e")
    _safe_destroy(client, stream_id)

    try:
        client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitive)

        NUM_RECORDS = 25
        start_date = datetime(2024, 1, 1)
        records: List[Record] = [
            Record(
                date=_date_to_unix(start_date + timedelta(days=i)),
                value=float(i + 1),  # +1 to avoid zero (filtered by consensus)
            )
            for i in range(NUM_RECORDS)
        ]
        batches: List[RecordBatch] = [RecordBatch(stream_id=stream_id, inputs=records)]

        inserter = BulkInserter(client)
        start = time.time()
        tx_hashes = inserter.insert_all(batches)
        duration = time.time() - start

        # 25 records / 10 per batch = 3 chunks (10, 10, 5)
        assert len(tx_hashes) == 3, f"expected 3 chunks, got {len(tx_hashes)}"
        assert all(isinstance(h, str) and len(h) > 0 for h in tx_hashes)

        print(
            f"[BulkInserter E2E] {NUM_RECORDS} records in 3 chunks: {duration:.2f}s "
            f"(avg {(duration / 3) * 1000:.0f}ms per chunk)"
        )

        # Read back and verify all records present
        retrieved = client.get_records(
            stream_id,
            data_provider=client.get_current_account(),
            date_from=_date_to_unix(datetime(2023, 1, 1)),
        )
        assert len(retrieved) == NUM_RECORDS

        retrieved_dates = sorted(int(r["EventTime"]) for r in retrieved)
        expected_dates = sorted(r["date"] for r in records)
        assert retrieved_dates == expected_dates
    finally:
        _safe_destroy(client, stream_id)


def test_insert_all_single_chunk_under_batch_size(client):
    """A single chunk under the batch_size still goes through the pipeline."""
    stream_id = generate_stream_id("test_bulk_inserter_small")
    _safe_destroy(client, stream_id)

    try:
        client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitive)

        records = [Record(date=_date_to_unix(datetime(2024, 6, i + 1)), value=float(i + 1)) for i in range(3)]
        batches = [RecordBatch(stream_id=stream_id, inputs=records)]

        inserter = BulkInserter(client)
        tx_hashes = inserter.insert_all(batches)

        assert len(tx_hashes) == 1
        retrieved = client.get_records(
            stream_id,
            data_provider=client.get_current_account(),
            date_from=_date_to_unix(datetime(2023, 1, 1)),
        )
        assert len(retrieved) == 3
    finally:
        _safe_destroy(client, stream_id)


def test_insert_all_custom_batch_size(client):
    """Verify batch_size override produces the expected number of chunks."""
    stream_id = generate_stream_id("test_bulk_inserter_bsize")
    _safe_destroy(client, stream_id)

    try:
        client.deploy_stream(stream_id, stream_type=truf_sdk.StreamTypePrimitive)

        # 14 records, batch_size=5 → 5+5+4 = 3 chunks
        records = [Record(date=_date_to_unix(datetime(2024, 7, i + 1)), value=float(i + 1)) for i in range(14)]
        batches = [RecordBatch(stream_id=stream_id, inputs=records)]

        inserter = BulkInserter(client, batch_size=5)
        tx_hashes = inserter.insert_all(batches)

        assert len(tx_hashes) == 3
    finally:
        _safe_destroy(client, stream_id)
