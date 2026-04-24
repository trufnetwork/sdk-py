# Bulk Insert Example (Python)

Demonstrates `BulkInserter` — pipelined high-throughput record insertion that
keeps a single signer within the protocol's 10-row-per-tx cap while
broadcasting hundreds of transactions per minute.

## What it does

1. Connects to a local TN node with the dev private key
2. Generates a stream ID and best-effort drops any existing stream with that ID
3. Deploys a fresh primitive stream
4. Bulk-inserts 25 synthetic records via `BulkInserter` (3 chunks of 10/10/5)
5. Reads the records back and confirms count + values
6. Drops the test stream

## Why use BulkInserter

Calling `client.batch_insert_records(...)` in a loop forces the SDK to wait for
each transaction to be **included in a block** (~1–2s per call) before
broadcasting the next. For 1,000 records that's 25+ minutes; for the Truflation
CPI ingestor's ~17,000-record runs, it's 4–5 hours.

`BulkInserter` instead:

- Caches the nonce locally (one initial fetch, then increments)
- Broadcasts each chunk fire-and-forget (`wait=False` underneath) — admission
  takes ~50ms versus inclusion's 1–2s
- Drains inflight hashes in batches via `wait_for_tx`
- Retries automatically on `invalid nonce` (resets the cache and refetches),
  `mempool full` (backs off, keeps the cache), and `node is catching up` (backs
  off with a longer base — typical catch-up events resolve in tens of seconds)

Result: 1,000 records land in roughly one minute on a typical node, instead of
half an hour.

## Prerequisites

A local node with migrations applied + the dev key whitelisted. From the
`node` repo:

```bash
task single:start                                                  # spin up postgres + tn-db
PATH="$(pwd)/.build:$PATH" task action:migrate:dev                 # apply migrations + grant network_writer
```

The dev key is `0000000000000000000000000000000000000000000000000000000000000001`,
which derives to address `0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf`. Both
`task action:migrate:dev` and the `single:start` defaults wire this address as
the DB owner and grant it `system:network_writer`.

## Running

From the `sdk-py` repo:

```bash
source .venv/bin/activate
python examples/bulk_insert_example/main.py
```

## Expected output

```text
connected as 0x7e5f4552091a69125d5dfcb7b8c2659029395bdf
stream id: stbulkinsertxxxxxxxxxxxxxxxxxxxxx
   (no existing stream to drop: ...)
stream deployed (tx 0x...)
broadcasting 25 records via BulkInserter (batch_size=10)...
done: 3 chunks broadcast + drained in 1.05s (350ms/chunk avg)

First 3 records read back:
  EventTime=1704067200 Value=1.000000000000000000
  EventTime=1704153600 Value=2.000000000000000000
  EventTime=1704240000 Value=3.000000000000000000
...
Total verified: 25 records
   dropped existing stream (tx 0x...)
```

## Customizing

- **Larger workloads**: change `NUM_RECORDS` at the top of `main.py`. Chunks =
  `ceil(NUM_RECORDS / 10)`.
- **Throughput knobs**: pass kwargs to `BulkInserter`:

  ```python
  inserter = BulkInserter(
      client,
      batch_size=10,                # records per insert_records tx; protocol cap is 10
      max_inflight=500,             # broadcasts queued before forced drain
      max_attempts=5,               # initial + retries on transient errors
                                    # (invalid nonce, mempool full, "node is catching up")
      catchup_backoff_seconds=5,    # base backoff (sec) for "node is catching up";
                                    # bump for backends prone to longer lag events
  )
  ```
- **Testnet/mainnet**: change `TEST_PROVIDER_URL` and the private key. Note
  that the account must hold `system:network_writer` to deploy streams.

## Related

- Python wrapper source: [`src/trufnetwork_sdk_py/bulk_inserter.py`](../../src/trufnetwork_sdk_py/bulk_inserter.py)
- Underlying Go implementation: [`sdk-go/core/contractsapi/bulk_inserter.go`](https://github.com/trufnetwork/sdk-go/blob/main/core/contractsapi/bulk_inserter.go)
- Pattern reference: [`tn_attestation/extension.go`](https://github.com/trufnetwork/node/blob/main/extensions/tn_attestation/extension.go)
  in the node repo (PR #1356) — same cached-nonce design that solved the
  attestation cron's "invalid nonce" noise.
