# Revision Backfill Example

Demonstrates how to backfill a primitive stream when the source data
contains multiple revisions for the same date — including reverts
(value A → value B → value A).

## When you need this

Steady-state ingest (one new value per date) does not need this
pattern. You need it on the **first/historical backfill** of a stream
whose source emits corrections, e.g. data that was reported, then
corrected, then re-corrected. To preserve every revision so that
`frozen_at` queries return the right value at each point in time,
each revision must land in its own block.

## Why one big batch doesn't work

TN auto-assigns `created_at` from the block height of the writing
transaction. Every row in one `insert_records` call shares the same
height. That has two consequences for same-date duplicates in one
batch:

- They cannot be distinguished by `frozen_at` (same height = same
  revision slot).
- Depending on the deployed schema, they may also collide on the
  primary key (`stream`, `event_time`, `created_at`).

Splitting same-date rows across separate transactions gives each one
a distinct `created_at`, which is what the frozen-revision model is
built around.

## The pattern

After your normal "fetch from API → fetch existing → reconcile (drop
consecutive duplicates) → sort by date asc" step, the result may
contain >1 row per date. Group those into **revision slots**:

- Slot 0: first occurrence of each date
- Slot 1: second occurrence
- Slot N: Nth occurrence

Submit one `insert_records` call per slot. Number of calls equals the
max revisions-per-date in the batch (typically 2-3, not one per row),
so the cost is bounded.

```python
def split_into_revision_slots(records):
    pending = list(records)
    slots = []
    while pending:
        seen = set()
        slot, leftover = [], []
        for r in pending:
            (slot if r["date"] not in seen else leftover).append(r)
            seen.add(r["date"])
        slots.append(slot)
        pending = leftover
    return slots

for slot in split_into_revision_slots(reconciled_rows):
    client.insert_records(stream_id, slot, wait=True)
```

`wait=True` matters — each slot must land before the next is
submitted, so the chain mints a fresh block (and therefore a fresh
`created_at`) per slot.

## Running

```bash
# from the node repo
task single:start
task action:migrate:dev

# from this repo
.venv/bin/python examples/revision_backfill_example/main.py
```

The example deploys a fresh stream, backfills 7 rows across 4 dates
(one date carries a revert from 2.0 → 2.5 → 2.0), then queries each
historical revision via `frozen_at` to prove all of them are
reachable.
