"""
Revision-aware backfill example — multiple revisions per date, same stream.

Use case
--------
Some sources emit a sequence of corrections for the same date — e.g.
"2024-02-01 was originally reported as 2.0, corrected to 2.5, then
re-corrected back to 2.0." For historical / `frozen_at` queries to
return the right value at each point in time, every revision must
land on TN as its own row with its own `created_at` (block height).

The catch
---------
TN auto-assigns `created_at` from the block height of the transaction
that wrote the row. All rows in one `insert_records` call share the
same height, so two rows for the same date in one batch cannot be
told apart by `frozen_at` — and depending on the deployed schema may
also collide on the primary key. The fix is to spread same-date rows
across separate transactions so each lands in its own block.

Pattern
-------
After your normal "reconcile + sort by date asc" step, the result may
contain >1 row per date when the source has revisions. Group those
rows into **revision slots**: slot 0 = first occurrence of each date,
slot 1 = second occurrence, and so on. Submit one `insert_records`
call per slot. Number of calls = max revisions per date in the batch
(usually 2-3, not one per row).

```
while pending:
    batch = pick first row per unique date from pending
    insert_records(batch)
    pending -= batch
```

Run against a local node spun up with `task single:start` from the
node repo. The dev key already has system:network_writer (granted by
`task action:migrate:dev`).
"""

from collections import OrderedDict
from datetime import datetime, timezone

from trufnetwork_sdk_py import STREAM_TYPE_PRIMITIVE, TNClient
from trufnetwork_sdk_py.utils import generate_stream_id

TEST_PRIVATE_KEY = "0000000000000000000000000000000000000000000000000000000000000001"
TEST_PROVIDER_URL = "http://localhost:8484"


def _date_to_unix(d: datetime) -> int:
    return int(d.replace(tzinfo=timezone.utc).timestamp())


def _safe_drop(client: TNClient, stream_id: str) -> None:
    try:
        tx = client.destroy_stream(stream_id)
        client.wait_for_tx(tx)
        print(f"   dropped existing stream (tx {tx[:10]}...)")
    except Exception as e:
        print(f"   (no existing stream to drop: {e})")


def split_into_revision_slots(records: list[dict]) -> list[list[dict]]:
    """
    Group records so each slot contains at most one row per date.

    Slot 0 holds the first occurrence of each date, slot 1 the second,
    and so on. Records keep their original order within each slot, so
    inserting slot N after slot N-1 preserves revision ordering for
    each date.

    Returns [] if `records` is empty.
    """
    pending = list(records)
    slots: list[list[dict]] = []
    while pending:
        seen_dates: set[int] = set()
        slot: list[dict] = []
        leftover: list[dict] = []
        for r in pending:
            if r["date"] in seen_dates:
                leftover.append(r)
            else:
                seen_dates.add(r["date"])
                slot.append(r)
        slots.append(slot)
        pending = leftover
    return slots


def main() -> None:
    client = TNClient(TEST_PROVIDER_URL, TEST_PRIVATE_KEY)
    print(f"connected as {client.get_current_account()}")

    stream_id = generate_stream_id("revision-backfill-example")
    print(f"stream id: {stream_id}")
    _safe_drop(client, stream_id)

    deploy_tx = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
    client.wait_for_tx(deploy_tx)
    print(f"stream deployed (tx {deploy_tx[:10]}...)\n")

    try:
        # Simulated source data after your normal reconcile step. Two
        # of the dates carry corrections; one is a revert (value 2.0
        # appears as both the first and the third revision for Feb 2).
        d1 = datetime(2024, 2, 1)
        d2 = datetime(2024, 2, 2)
        d3 = datetime(2024, 2, 3)
        d4 = datetime(2024, 2, 4)
        source = [
            {"date": _date_to_unix(d1), "value": 1.0},
            {"date": _date_to_unix(d2), "value": 2.0},
            {"date": _date_to_unix(d2), "value": 2.5},
            {"date": _date_to_unix(d2), "value": 2.0},
            {"date": _date_to_unix(d3), "value": 3.0},
            {"date": _date_to_unix(d3), "value": 3.5},
            {"date": _date_to_unix(d4), "value": 4.0},
        ]
        print(f"source: {len(source)} rows across 4 unique dates")

        # Group into revision slots and submit one tx per slot.
        slots = split_into_revision_slots(source)
        print(f"split into {len(slots)} slot(s) of size "
              f"{[len(s) for s in slots]}\n")

        # Track block height per (date, value) so we can prove the
        # frozen_at semantics work. In a real backfill you would not
        # need this — it's purely for the demo at the end.
        revision_heights: list[tuple[int, float, int]] = []
        for slot_idx, slot in enumerate(slots):
            tx = client.insert_records(stream_id, slot, wait=True)
            evt = client.get_transaction_event(tx)
            height = evt["block_height"]
            print(f"slot {slot_idx}: inserted {len(slot)} row(s) "
                  f"at block {height} (tx {tx[:10]}...)")
            for r in slot:
                revision_heights.append((r["date"], r["value"], height))

        # Read back without frozen_at — should see the LATEST revision
        # per date (highest created_at), so 4 rows with the final values.
        print("\nlatest snapshot (no frozen_at):")
        latest = client.get_records(
            stream_id=stream_id,
            data_provider=client.get_current_account(),
            date_from=_date_to_unix(d1),
            use_cache=False,
        ).data
        for r in latest:
            print(f"  date={_unix_to_iso(int(r['EventTime']))} "
                  f"value={r['Value']}")

        # Walk each revision and query with frozen_at = its block
        # height to prove every step in the history is reachable.
        print("\nrevision-by-revision (frozen_at per block):")
        by_date: OrderedDict[int, list[tuple[float, int]]] = OrderedDict()
        for d, v, h in revision_heights:
            by_date.setdefault(d, []).append((v, h))
        for date_unix, revs in by_date.items():
            print(f"  {_unix_to_iso(date_unix)}: "
                  f"{len(revs)} revision(s)")
            for v, h in revs:
                got = client.get_records(
                    stream_id=stream_id,
                    data_provider=client.get_current_account(),
                    date_from=date_unix,
                    date_to=date_unix,
                    frozen_at=h,
                    use_cache=False,
                ).data
                got_value = float(got[0]["Value"]) if got else None
                ok = "OK" if got_value == v else "MISMATCH"
                print(f"    frozen_at={h}: stored={v} read={got_value} [{ok}]")
    finally:
        _safe_drop(client, stream_id)


def _unix_to_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    main()
