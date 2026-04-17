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
    """Raised when BulkInserter fails to broadcast a chunk or drain inflight
    transactions after exhausting retries.

    Attributes
    ----------
    tx_hashes : list[str]
        Tx hashes broadcast successfully before the failure. Use this to
        recover: when ``drain_failure`` is False, resume the workload from
        ``records[failed_chunk_index * batch_size:]``.
    drain_failure : bool
        True when all chunks were broadcast successfully but the final
        ``WaitTx`` drain failed. In that case ``tx_hashes`` is the full set
        of submitted hashes — investigate inclusion separately.
    failed_chunk_index : int
        Index of the failing chunk (when ``drain_failure`` is False) or the
        total number of chunks broadcast (when ``drain_failure`` is True).
    """

    def __init__(
        self,
        message: str,
        tx_hashes: Optional[List[str]] = None,
        drain_failure: bool = False,
        failed_chunk_index: int = 0,
    ):
        super().__init__(message)
        self.tx_hashes: List[str] = list(tx_hashes) if tx_hashes else []
        self.drain_failure = drain_failure
        self.failed_chunk_index = failed_chunk_index


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
        exception carries the partial tx hashes (``tx_hashes`` attribute),
        the failing chunk index (``failed_chunk_index``), and a flag
        indicating whether the failure was during broadcast or during the
        final drain (``drain_failure``).
        """
        if not batches:
            return []

        # Resolve the data provider ONCE, not per record. NewInsertRecordInput
        # in the Go binding calls GetCurrentAccount on every invocation —
        # cheap individually, but for thousands of records that's thousands
        # of redundant lookups, and a transient failure would silently
        # produce zero-valued inputs.
        data_provider = self._client.get_current_account()
        if not data_provider:
            raise BulkInsertError(
                "could not resolve data provider for the current signer"
            )

        # Flatten batches into a single list of InsertRecordInput Go structs
        # (one per record). Each input carries its own stream_id + data
        # provider, so chunks may mix streams.
        go_inputs = []
        for batch in batches:
            stream_id = batch["stream_id"]
            if not stream_id:
                raise BulkInsertError("batch is missing stream_id")
            for record in batch["inputs"]:
                go_inputs.append(
                    truf_sdk.NewInsertRecordInputForProvider(
                        data_provider,
                        stream_id,
                        record["date"],
                        record["value"],
                    )
                )

        if not go_inputs:
            return []

        go_input_slice = truf_sdk.Slice_s1_types_InsertRecordInput(go_inputs)
        result = truf_sdk.BulkInsertAll(self._inner, go_input_slice)

        # Always materialize hashes — gopy gives us a Go slice; copy to a
        # plain Python list for safe handling regardless of success/failure.
        tx_hashes = list(result.TxHashes) if result.TxHashes else []

        if result.ErrorMsg:
            raise BulkInsertError(
                result.ErrorMsg,
                tx_hashes=tx_hashes,
                drain_failure=result.DrainFailure,
                failed_chunk_index=result.FailedChunkIndex,
            )

        return tx_hashes
