"""
Investigate corrupted hash data in list_markets pagination.

Systematically paginates through markets to find offsets where
base64 decoding fails, then reports the affected market IDs.

Usage:
    source .venv/bin/activate
    python examples/investigate_corrupted_hashes.py
"""

import sys
import traceback
from trufnetwork_sdk_py.client import TNClient


def scan_markets(client: TNClient, settled_filter: bool, label: str, limit: int = 100):
    """Paginate through all markets, collecting errors."""
    offset = 0
    total_ok = 0
    errors_found = []

    while True:
        try:
            markets = client.list_markets(
                settled_filter=settled_filter,
                limit=limit,
                offset=offset,
            )
            count = len(markets)
            if count == 0:
                break
            total_ok += count
            print(f"  [{label}] offset={offset:>6} limit={limit} => {count} markets OK")
            offset += limit
        except Exception as e:
            err_msg = str(e)
            errors_found.append({"offset": offset, "error": err_msg})
            print(f"  [{label}] offset={offset:>6} limit={limit} => ERROR: {err_msg}")

            # Try to narrow down the exact failing row by fetching one-by-one
            print(f"    -> Narrowing down failing row(s) in this page...")
            for i in range(limit):
                try:
                    page = client.list_markets(
                        settled_filter=settled_filter,
                        limit=1,
                        offset=offset + i,
                    )
                    if not page:
                        break
                except Exception as inner_e:
                    print(f"    -> CORRUPT at offset={offset + i}: {inner_e}")
                    errors_found[-1].setdefault("corrupt_offsets", []).append(offset + i)

            offset += limit

    return total_ok, errors_found


def main():
    print("=" * 70)
    print(" Corrupted Hash Investigation - list_markets pagination")
    print("=" * 70)

    endpoint = "https://gateway.testnet.truf.network"
    # Dummy key - read-only operations don't need funded account
    private_key = "0000000000000000000000000000000000000000000000000000000000000001"

    print(f"[*] Connecting to: {endpoint}")
    client = TNClient(endpoint, private_key)

    for settled_filter, label in [(False, "UNSETTLED"), (True, "SETTLED")]:
        print(f"\n{'=' * 70}")
        print(f" Scanning {label} markets")
        print(f"{'=' * 70}")

        total_ok, errors = scan_markets(client, settled_filter, label)

        print(f"\n[{label}] Summary: {total_ok} markets OK, {len(errors)} pages with errors")
        if errors:
            print(f"[{label}] Failing offsets:")
            for e in errors:
                corrupt = e.get("corrupt_offsets", [])
                print(f"  - offset={e['offset']}: {len(corrupt)} corrupt row(s) at {corrupt}")
                print(f"    error: {e['error'][:200]}")

    print("\nDone.")


if __name__ == "__main__":
    main()
