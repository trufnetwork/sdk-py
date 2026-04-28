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
    max_attempts : int, default 15
        Max attempts per chunk on non-catchup transient errors (invalid
        nonce, mempool full). Catch-up errors have their own larger budget
        — see ``catchup_max_attempts``. Default of 15 is sized so a
        thousand-chunk insert can ride out brief mempool congestion without
        bottlenecking on the adapter resume layer above (which only gets 5
        partial-progress passes); with the default 2s linear backoff that's
        ~4 minutes of waiting per chunk before bubbling up.
    catchup_backoff_seconds : int, default 15
        Base backoff in seconds when the broadcast backend rejects with
        "node is catching up". Actual delay per attempt is
        base * (attempt + 1). With the default of 15s and
        ``catchup_max_attempts=20`` the loop runs 20 attempts with 19
        backoffs in between (the 20th attempt's failure exits without
        sleeping), so the worst-case wait per chunk is
        ``15 + 30 + … + 285s = 2850s ≈ 47.5 minutes`` — comfortably long
        enough to ride out every catch-up event seen in production so far
        without abandoning the whole batch.
    catchup_max_attempts : int, default 20
        Max attempts per chunk on "node is catching up" rejections
        specifically. Separate from ``max_attempts`` because real catch-up
        events on the public RPC backend (sentry replaying blocks) routinely
        run minutes long; sharing one budget aborted multi-hour bulk loads
        after just 75 seconds in the 2026-04-25 incident.
    infra_max_attempts : int, default 10
        Max attempts per chunk on **pre-broadcast** infrastructure errors
        — KGW returning "no available backend", TCP "connection refused",
        DNS "no such host". These are unambiguously safe to retry because
        the request demonstrably never reached kwild. Errors that may fire
        post-admit (EOF, connection reset, context deadline exceeded) stay
        fatal at the SDK layer and bubble up to the caller's resume layer,
        which can recover via partial-progress slicing without risking
        duplicate inserts. Reuses the 2s base linear backoff, so default
        gives ~90s wait per chunk before bubbling up.
    progress_log_every_n : int, default 500
        Emit an INFO log line every N chunks reporting chunks done / total,
        rows done, elapsed time, current chunks/sec rate, and ETA. Pass 0
        to disable. Defaults to 500 here (the underlying Go default is 0)
        because the Python wrapper is primarily used for hours-long Prefect
        bulk loads, where without progress logs the only output between
        "Submitting N records" and the final result is hours of silence.
        Logs go to stderr via the Go-side logger, which the prefect.engine
        subprocess captures into Prefect task logs.
    """

    def __init__(
        self,
        client: TNClient,
        batch_size: int = 10,
        max_inflight: int = 200,
        max_attempts: int = 15,
        catchup_backoff_seconds: int = 15,
        catchup_max_attempts: int = 20,
        infra_max_attempts: int = 10,
        progress_log_every_n: int = 500,
    ):
        if client is None:
            raise ValueError("client is required")
        # Pass 0 for any value to use the Go-side defaults.
        self._inner = truf_sdk.NewBulkInserter(
            client.client,
            batch_size,
            max_inflight,
            max_attempts,
            catchup_backoff_seconds,
            catchup_max_attempts,
            infra_max_attempts,
            progress_log_every_n,
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
