"""
Index-Change Market Example

Creates a set of prediction markets that settle on how far an index moved,
rather than on the level it published.

A stream that publishes an index level (CPI at ~335, PCE at ~131) cannot back an
inflation-rate market through the value actions: those compare a level against a
rate. ``index_change_in_range`` computes the percentage change over an interval
and returns one boolean, so a market can be struck on the rate while reading a
stream that only publishes levels.

Run with:

    python examples/index_change_market/main.py
"""

import os
import time
from datetime import datetime, timedelta, timezone

from trufnetwork_sdk_py.client import TNClient
from trufnetwork_sdk_py.market_buckets import bucket_bounds_from_market_data

TESTNET_URL = "https://gateway.testnet.truf.network"

# WARNING: throwaway private key, provided for testnet examples only.
# DO NOT use this key in production or hold anything of value in this wallet.
# It is the same OBMarketCreator wallet the order_book examples use.
# Override it with the PRIVATE_KEY environment variable to use your own.
MARKET_CREATOR_PRIVATE_KEY = "a537437df2ed8d3bcb3b99b4f88818cadf8ac365cd0a66595bb50973ac4ecf51"

# A testnet stream with roughly fifteen years of daily history, so a
# year-over-year lookback lands on real data.
DATA_PROVIDER = "0x4710a8d8f0d845da110086812a32de6d90d7ff5c"
STREAM_ID = "st9f212b7c208afd83705cc0dbdadfe8"

# The last event time in that stream. Used only to show what the rate currently
# is; the markets below observe their settlement time instead.
LAST_RECORD_AT = 1783296000

YEAR_IN_SECONDS = 31_536_000

# Collateral namespace. The 2 TRUF creation fee is taken from hoodi_tt whatever
# this is set to.
BRIDGE = "hoodi_tt2"

MAX_SPREAD = 10  # cents, for LP reward eligibility
MIN_ORDER_SIZE = 1_000_000_000_000_000_000  # 1 token

# The buckets of one market set. Every bucket shares an observation time and an
# interval and differs only in where it is struck, so exactly one of them can
# settle YES.
#
# Bounds are half-open, [min, max): a change landing exactly on a boundary
# belongs to the bucket above it. That is what lets the set tile the number line
# without two buckets settling YES at once. The outer two are struck with an open
# tail, which is what None means here -- the node rejects a market with both
# tails open, since that is every outcome at once.
BUCKETS = [
    ("below 2%", None, "2"),
    ("between 2% and 3%", "2", "3"),
    ("3% or more", "3", None),
]


def describe_the_rate(client: TNClient) -> None:
    """Show the number a market on this stream settles against.

    ``get_index_change`` is a plain read, so this costs nothing.
    """
    print("--- What such a market measures ---")

    try:
        # get_index_change($data_provider, $stream_id, $from, $to, $frozen_at,
        #                  $base_time, $time_interval, $use_cache)
        #
        # $use_cache is passed as None rather than False on purpose:
        # call_procedure sends every argument as a string and the binding infers
        # int, float or text from it, so there is no way to send a boolean.
        # None becomes SQL NULL, which this action treats as "no cache".
        result = client.call_procedure(
            "get_index_change",
            [DATA_PROVIDER, STREAM_ID, LAST_RECORD_AT, LAST_RECORD_AT,
             None, None, YEAR_IN_SECONDS, None],
        )
    except Exception as exc:
        print(f"Could not read the current rate: {exc}\n")
        return

    rows = result.get("values") or []
    if not rows:
        print("The stream has no value at that point.\n")
        return

    ending = datetime.fromtimestamp(LAST_RECORD_AT, timezone.utc).strftime("%Y-%m-%d")
    print(f"Stream {STREAM_ID} moved {rows[0][-1]}% over the year ending {ending}.\n")


def read_the_buckets_offline() -> None:
    """Build each bucket's query components and read them back without touching
    the network, which is where the encoding contract is easiest to see."""
    print("--- The bucket set, built and decoded locally ---")

    for question, min_change, max_change in BUCKETS:
        components = TNClient.build_index_change_in_range_query_components(
            DATA_PROVIDER,
            STREAM_ID,
            LAST_RECORD_AT,
            YEAR_IN_SECONDS,
            min_change=min_change,
            max_change=max_change,
        )
        market = TNClient.decode_market_data(components)
        lower, upper = bucket_bounds_from_market_data(market)

        # An open tail decodes as an empty string holding its slot, not as a
        # shorter list. Dropping the empty entry would slide the surviving bound
        # into the other position and turn "below 2%" into "2% and up".
        print(
            f"  {question:<20} type={market['type']} "
            f"thresholds={market['thresholds']} "
            f"bounds=[{_bound(lower)}, {_bound(upper)})"
        )
    print()


def create_the_markets(client: TNClient) -> None:
    """Put the set on testnet. Each market costs 2 TRUF from the wallet's
    hoodi_tt balance."""
    print("--- Creating the set on testnet (2 TRUF each) ---")

    # The market observes the stream at its settlement time, so it cannot be
    # resolved before then. Using a fresh time each run also keeps each run's
    # markets distinct: a market's identity is a hash of its query components,
    # and re-creating an identical market is refused.
    settle_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    settle_timestamp = int(settle_at.timestamp())

    for question, min_change, max_change in BUCKETS:
        try:
            tx_hash = client.create_index_change_in_range_market(
                data_provider=DATA_PROVIDER,
                stream_id=STREAM_ID,
                timestamp=settle_timestamp,
                time_interval=YEAR_IN_SECONDS,
                bridge=BRIDGE,
                settle_time=settle_timestamp,
                max_spread=MAX_SPREAD,
                min_order_size=MIN_ORDER_SIZE,
                min_change=min_change,
                max_change=max_change,
            )
        except Exception as exc:
            print(f"  {question:<20} failed: {exc}")
            continue
        print(f"  {question:<20} tx {tx_hash}")

    print(f"\nSettles at {settle_at.strftime('%Y-%m-%d %H:%M:%S UTC')}.")
    print("Read any market back with examples/decode_market_example.")


def _bound(value: float | None) -> str:
    return "open" if value is None else f"{value:g}"


def main() -> None:
    private_key = os.getenv("PRIVATE_KEY", MARKET_CREATOR_PRIVATE_KEY)
    client = TNClient(TESTNET_URL, private_key)

    print("=== Index-change prediction markets ===")
    print(f"Endpoint: {TESTNET_URL}")
    print(f"Wallet:   {client.get_current_account()}\n")

    describe_the_rate(client)
    read_the_buckets_offline()
    create_the_markets(client)


if __name__ == "__main__":
    main()
