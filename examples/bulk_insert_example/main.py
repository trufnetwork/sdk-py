"""
BulkInserter example — pipelined high-throughput record insertion.

Flow:
  1. Connect to a local node with the dev private key
  2. Generate a stream ID; if a stream with that ID already exists, drop it
  3. Deploy a fresh primitive stream
  4. Bulk-insert 25 records via BulkInserter (3 chunks of 10/10/5)
  5. Read the records back and confirm the count + values
  6. Drop the test stream

Run against a local node spun up with `task single:start` from the node repo.
The dev key already has system:network_writer (granted by `task action:migrate:dev`).
"""

import time
from datetime import datetime, timedelta, timezone

from trufnetwork_sdk_py import (
    BulkInserter,
    BulkInsertError,
    STREAM_TYPE_PRIMITIVE,
    TNClient,
)
from trufnetwork_sdk_py.utils import generate_stream_id

# Test-only private key. NEVER use this for real funds.
TEST_PRIVATE_KEY = "0000000000000000000000000000000000000000000000000000000000000001"
TEST_PROVIDER_URL = "http://localhost:8484"
NUM_RECORDS = 25


def _date_to_unix(date: datetime) -> int:
    return int(date.replace(tzinfo=timezone.utc).timestamp())


def _safe_drop(client: TNClient, stream_id: str) -> None:
    """Best-effort drop — never raises."""
    try:
        tx_hash = client.destroy_stream(stream_id)
        client.wait_for_tx(tx_hash)
        print(f"   dropped existing stream (tx {tx_hash})")
    except Exception as e:
        print(f"   (no existing stream to drop: {e})")


def main() -> None:
    # 1. Connect
    client = TNClient(TEST_PROVIDER_URL, TEST_PRIVATE_KEY)
    print(f"connected as {client.get_current_account()}")

    # 2. Generate stream id + best-effort drop
    stream_id = generate_stream_id("bulk-insert-example")
    print(f"stream id: {stream_id}")
    _safe_drop(client, stream_id)

    # 3. Deploy fresh primitive stream
    deploy_tx = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
    client.wait_for_tx(deploy_tx)
    print(f"stream deployed (tx {deploy_tx})")

    try:
        # 4. Bulk-insert via BulkInserter
        inserter = BulkInserter(client)

        start_date = datetime(2024, 1, 1)
        records = [
            {
                "date": _date_to_unix(start_date + timedelta(days=i)),
                "value": float(i + 1),  # +1 to avoid zero (filtered by consensus)
            }
            for i in range(NUM_RECORDS)
        ]
        batches = [{"stream_id": stream_id, "inputs": records}]

        print(f"broadcasting {NUM_RECORDS} records via BulkInserter (batch_size=10)...")
        start = time.time()
        try:
            tx_hashes = inserter.insert_all(batches)
        except BulkInsertError as e:
            print(f"bulk insert failed: {e}")
            return
        duration = time.time() - start

        chunks = max(len(tx_hashes), 1)
        print(
            f"done: {len(tx_hashes)} chunks broadcast + drained in {duration:.2f}s "
            f"({duration / chunks * 1000:.0f}ms/chunk avg)"
        )

        # 5. Read back and confirm
        retrieved = client.get_records(
            stream_id=stream_id,
            data_provider=client.get_current_account(),
            date_from=_date_to_unix(datetime(2023, 1, 1)),
        )

        if len(retrieved) != NUM_RECORDS:
            print(f"record count mismatch: got {len(retrieved)}, want {NUM_RECORDS}")
            return

        print("\nFirst 3 records read back:")
        for r in retrieved[:3]:
            print(f"  EventTime={r['EventTime']} Value={r['Value']}")
        print(f"...\nTotal verified: {len(retrieved)} records")
    finally:
        # 6. Cleanup
        _safe_drop(client, stream_id)


if __name__ == "__main__":
    main()
