"""
Order Book E2E Test - Step 1: Create Market

Creates a prediction market: "Will Bitcoin be above $85,000?"

Uses OBMarketCreator wallet to create the market on TrufNetwork testnet.
The market uses hoodi_tt2 (USDC) as collateral.
"""

import os
import time
from datetime import datetime, timezone, timedelta
from trufnetwork_sdk_py.client import TNClient

# Testnet configuration
TESTNET_URL = "http://ec2-3-141-77-16.us-east-2.compute.amazonaws.com:8484"

# WARNING: This is a throwaway private key provided for testnet examples only.
# DO NOT use this key for production or store any real funds in this wallet.
# Always use secure key management practices in production environments.
MARKET_CREATOR_PRIVATE_KEY = "a537437df2ed8d3bcb3b99b4f88818cadf8ac365cd0a66595bb50973ac4ecf51"

# Bitcoin stream configuration
BITCOIN_STREAM_ID = "st9058219c3c3247faf2b0a738de7027"
DATA_PROVIDER = "0xe5252596672cd0208a881bdb67c9df429916ba92"

# Market parameters
THRESHOLD = "85000"  # Will BTC be above $85,000?
BRIDGE = "hoodi_tt2"  # USDC collateral
MAX_SPREAD = 10  # 10 cents max spread for LP rewards
MIN_ORDER_SIZE = 1_000_000_000_000_000_000  # 1 USDC (18 decimals)


def main():
    print("=" * 60)
    print("Order Book E2E Test - Step 1: Create Market")
    print("=" * 60)

    # Initialize client with market creator wallet
    print(f"\nConnecting to testnet: {TESTNET_URL}")
    client = TNClient(TESTNET_URL, MARKET_CREATOR_PRIVATE_KEY)
    print("Market Creator: OBMarketCreator (0x32a46917DF74808b9aDD7DC6eF0c34520412FDF3)")

    # Note: Balances can be checked via postgres query on kwil_erc20_meta.balances table

    # Set settlement time (30 minutes from now for testing)
    now = datetime.now(timezone.utc)
    settle_time = now + timedelta(minutes=30)
    settle_timestamp = int(settle_time.timestamp())

    # The timestamp to check the BTC price at (same as settle time for this test)
    check_timestamp = settle_timestamp

    print("\n--- Market Configuration ---")
    print(f"Question: Will Bitcoin be above ${THRESHOLD} at settlement?")
    print(f"Stream ID: {BITCOIN_STREAM_ID}")
    print(f"Data Provider: {DATA_PROVIDER}")
    print(f"Threshold: ${THRESHOLD}")
    print(f"Settlement Time: {settle_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Settlement Timestamp: {settle_timestamp}")
    print(f"Collateral: {BRIDGE}")
    print(f"Max Spread: {MAX_SPREAD} cents")
    print(f"Min Order Size: {MIN_ORDER_SIZE / 1e18} tokens")

    # Create the market
    print("\n--- Creating Market ---")
    try:
        tx_hash = client.create_price_above_threshold_market(
            data_provider=DATA_PROVIDER,
            stream_id=BITCOIN_STREAM_ID,
            timestamp=check_timestamp,
            threshold=THRESHOLD,
            bridge=BRIDGE,
            settle_time=settle_timestamp,
            max_spread=MAX_SPREAD,
            min_order_size=MIN_ORDER_SIZE,
        )
        print(f"Market created! Transaction hash: {tx_hash}")
    except Exception as e:
        print(f"Failed to create market: {e}")
        return

    # Discover query_id by listing markets and finding ours
    # In production, you could also compute the hash beforehand and use get_market_by_hash()
    print("\n--- Discovering Market Query ID ---")
    time.sleep(2)  # Wait for transaction to be indexed

    query_id = None
    try:
        # List recent markets and find the one we just created
        markets = client.list_markets(limit=10)
        print(f"Found {len(markets)} market(s)")

        # Find our market by matching settle_time (or could match by creator address)
        for market in markets:
            if market.get('settle_time') == settle_timestamp:
                query_id = market.get('id')
                print("\n✓ Found our market!")
                print(f"  Query ID: {query_id}")
                print(f"  Hash: {market.get('hash', b'').hex() if isinstance(market.get('hash'), bytes) else market.get('hash', 'N/A')}")
                print(f"  Settle Time: {market.get('settle_time')}")
                print(f"  Settled: {market.get('settled')}")
                break

        if query_id:
            print("\n✓ Market created successfully!")
            print(f"  Use query_id={query_id} for placing orders in the next step.")

            # Save to file for other scripts to use
            script_dir = os.path.dirname(os.path.abspath(__file__))
            query_id_file = os.path.join(script_dir, ".query_id")
            with open(query_id_file, "w") as f:
                f.write(str(query_id))
            print(f"  (Saved to {query_id_file})")
        else:
            print("\n✗ Could not find our market in the list")

    except Exception as e:
        print(f"Could not fetch market info: {e}")

    print("\n" + "=" * 60)
    print("Next: Run 02_place_orders.py to place orders on this market")
    print("=" * 60)


if __name__ == "__main__":
    main()
