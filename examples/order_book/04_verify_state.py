"""
Order Book E2E Test - Step 4: Verify Final State

Queries the order book state using SDK methods to verify the E2E test results.
"""

import os
from trufnetwork_sdk_py.client import TNClient

# Testnet configuration
TESTNET_URL = "http://ec2-3-141-77-16.us-east-2.compute.amazonaws.com:8484"

# Wallet addresses for display (derived from private keys in other scripts)
WALLET_NAMES = {
    "32a46917df74808b9add7dc6ef0c34520412fdf3": "MarketCreator",
    "c11ff6d3cc60823ecdcab1089f1a4336053851ef": "MarketMaker",
    "1c6790935a3a1a6b914399ba743bec8c41fe89fb": "BuyerTaker",
    "51125fd33c366595d24aa42229085d30c95a62da": "SellerTaker",
}


def get_query_id():
    """Read query_id from file created by 01_create_market.py."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    query_id_file = os.path.join(script_dir, ".query_id")
    try:
        with open(query_id_file, "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        print(f"Warning: {query_id_file} not found. Run 01_create_market.py first.")
        raise SystemExit(1) from None


QUERY_ID = get_query_id()

# Use MarketMaker wallet to query (any wallet works for read operations)
MARKET_MAKER_PRIVATE_KEY = "1b94f77f8eeb3ff78aa091b0965bf1b54305e3af50f9a6cd24cb457edc8c77ed"


def get_wallet_name(address_bytes: bytes) -> str:
    """Get human-readable name for known wallet addresses."""
    addr_hex = address_bytes.hex().lower()
    return WALLET_NAMES.get(addr_hex, f"0x{addr_hex[:8]}...")


def main():
    print("=" * 70)
    print("Order Book E2E Test - Step 4: Verify Final State")
    print("=" * 70)

    client = TNClient(TESTNET_URL, MARKET_MAKER_PRIVATE_KEY)
    print(f"\nChecking Market ID: {QUERY_ID}")

    # Market info
    print("\n--- Market Info ---")
    try:
        market = client.get_market_info(QUERY_ID)
        print(f"  Query ID: {market['id']}")
        print(f"  Bridge: {market['bridge']}")
        print(f"  Settle Time: {market['settle_time']}")
        print(f"  Settled: {market['settled']}")
        if market['settled']:
            print(f"  Winning Outcome: {'YES' if market['winning_outcome'] else 'NO'}")
        print(f"  Max Spread: {market['max_spread']}c")
        print(f"  Min Order Size: {market['min_order_size']}")
    except Exception as e:
        print(f"  Error: {e}")

    # Order book for YES
    print("\n--- YES Order Book ---")
    try:
        yes_orders = client.get_order_book(QUERY_ID, outcome=True)
        if yes_orders:
            print(f"  {'Wallet':<14} | {'Price':>6} | {'Amount':>8} | {'Type':>8}")
            print(f"  {'-'*14} | {'-'*6} | {'-'*8} | {'-'*8}")
            for order in yes_orders:
                wallet = get_wallet_name(order["wallet_address"])
                price = order["price"]
                amount = order["amount"]
                if price == 0:
                    order_type = "HOLDING"
                elif price < 0:
                    order_type = "BUY"
                else:
                    order_type = "SELL"
                print(f"  {wallet:<14} | {abs(price):>6}c | {amount:>8} | {order_type:>8}")
        else:
            print("  No orders")
    except Exception as e:
        print(f"  Error: {e}")

    # Order book for NO
    print("\n--- NO Order Book ---")
    try:
        no_orders = client.get_order_book(QUERY_ID, outcome=False)
        if no_orders:
            print(f"  {'Wallet':<14} | {'Price':>6} | {'Amount':>8} | {'Type':>8}")
            print(f"  {'-'*14} | {'-'*6} | {'-'*8} | {'-'*8}")
            for order in no_orders:
                wallet = get_wallet_name(order["wallet_address"])
                price = order["price"]
                amount = order["amount"]
                if price == 0:
                    order_type = "HOLDING"
                elif price < 0:
                    order_type = "BUY"
                else:
                    order_type = "SELL"
                print(f"  {wallet:<14} | {abs(price):>6}c | {amount:>8} | {order_type:>8}")
        else:
            print("  No orders")
    except Exception as e:
        print(f"  Error: {e}")

    # Best prices
    print("\n--- Best Prices ---")
    for outcome_name, outcome in [("YES", True), ("NO", False)]:
        try:
            prices = client.get_best_prices(QUERY_ID, outcome)
            bid = prices.get("best_bid")
            ask = prices.get("best_ask")
            spread = prices.get("spread")
            print(f"  {outcome_name}: Bid={bid}c, Ask={ask}c, Spread={spread}c")
        except Exception as e:
            print(f"  {outcome_name}: Error - {e}")

    # Market depth
    print("\n--- Market Depth (YES) ---")
    try:
        depth = client.get_market_depth(QUERY_ID, outcome=True)
        if depth:
            print(f"  {'Price':>6} | {'Volume':>10}")
            print(f"  {'-'*6} | {'-'*10}")
            for level in depth:
                print(f"  {level['price']:>6}c | {level['total_amount']:>10}")
        else:
            print("  No depth data")
    except Exception as e:
        print(f"  Error: {e}")

    # Collateral validation
    print("\n--- Market Collateral Validation ---")
    try:
        validation = client.validate_market_collateral(QUERY_ID)
        print(f"  Valid Token Binaries: {validation['valid_token_binaries']}")
        print(f"  Valid Collateral: {validation['valid_collateral']}")
        print(f"  Total YES: {validation['total_true']}")
        print(f"  Total NO: {validation['total_false']}")
        print(f"  Vault Balance: {validation['vault_balance']}")
        print(f"  Expected Collateral: {validation['expected_collateral']}")
        print(f"  Open Buys Value: {validation['open_buys_value']}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n" + "=" * 70)
    print("Verification Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
