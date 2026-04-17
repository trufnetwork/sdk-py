"""
BulkInserter — pipelined high-throughput insert helper.

Wraps the sdk-go BulkInserter (`sdk-go/core/contractsapi/bulk_inserter.go`)
which mirrors the cached-nonce + fire-and-forget pattern from
`node/extensions/tn_attestation/extension.go` (PR kwilteam/node#1356).

Use this instead of looping `client.batch_insert_records(...)` when you
need to push more than a few hundred records — the underlying SDK forces a
wait-for-inclusion between every broadcast, which serializes throughput to
~one tx per block (1-2s). BulkInserter caches the nonce locally and uses
fire-and-forget broadcasts so admission (~50ms) becomes the rate limit
instead of inclusion.

Example:

    from trufnetwork_sdk_py import TNClient, BulkInserter, RecordBatch

    client = TNClient(provider_url, private_key)
    inserter = BulkInserter(client)

    batches: list[RecordBatch] = [
        {"stream_id": "...", "inputs": [{"date": 1700000000, "value": 1.5}, ...]},
        ...
    ]
    tx_hashes = inserter.insert_all(batches)

Constraints:
- One BulkInserter per signer key. Concurrent inserters from the same
  signer will collide on nonces (mempool admits strictly in-order;
  out-of-order broadcasts are rejected).
- Inputs are flattened, then chunked into `batch_size` (default 10) per tx.
"""

from typing import List, Optional

import trufnetwork_sdk_c_bindings.exports as truf_sdk

from .client import RecordBatch, TNClient


class BulkInsertError(Exception):
    """Raised when BulkInserter fails to broadcast a chunk after exhausting
    retries.

    The underlying error message includes the failing chunk index in the
    format "bulk insert failed at chunk N: <reason>", e.g. so callers can
    parse it if they want to resume from that chunk.
    """

    pass


class BulkInserter:
    """Pipelined batch inserter for high-throughput record ingestion.

    Parameters
    ----------
    client : TNClient
        The TN client to broadcast through. Must use HTTP transport (the
        default).
    batch_size : int, default 10
        Records per insert_records transaction. Must be <= the protocol cap
        (currently 10).
    max_inflight : int, default 200
        How many broadcasts may queue before draining via WaitTx.
    max_attempts : int, default 5
        Max attempts per chunk (initial + retries) on transient errors
        (invalid nonce, mempool full).
    """

    def __init__(
        self,
        client: TNClient,
        batch_size: int = 10,
        max_inflight: int = 200,
        max_attempts: int = 5,
    ):
        if client is None:
            raise ValueError("client is required")
        # Pass 0 for any value to use the Go-side defaults.
        self._inner = truf_sdk.NewBulkInserter(
            client.client, batch_size, max_inflight, max_attempts
        )
        self._client = client

    def insert_all(self, batches: List[RecordBatch]) -> List[str]:
        """Broadcast all records pipelined and return the tx hashes in
        submission order.

        Records are flattened across batches and chunked by batch_size.
        Each chunk becomes one insert_records transaction.

        On chunk failure after retries, raises BulkInsertError. The
        message includes the failing chunk index.
        """
        if not batches:
            return []

        # Flatten batches into a single list of InsertRecordInput Go
        # structs (one per record). Each input carries its own stream_id +
        # data_provider, so chunks may mix streams.
        go_inputs = []
        for batch in batches:
            stream_id = batch["stream_id"]
            for record in batch["inputs"]:
                go_inputs.append(
                    truf_sdk.NewInsertRecordInput(
                        self._client.client,
                        stream_id,
                        record["date"],
                        record["value"],
                    )
                )

        if not go_inputs:
            return []

        go_input_slice = truf_sdk.Slice_s1_types_InsertRecordInput(go_inputs)
        try:
            hashes = truf_sdk.BulkInsertAll(self._inner, go_input_slice)
        except Exception as e:
            raise BulkInsertError(str(e)) from e

        # gopy returns a Go slice; convert to plain Python list of strings.
        return list(hashes)
