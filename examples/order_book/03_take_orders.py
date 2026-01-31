"""
Order Book E2E Test - Step 3: Takers Execute Trades

Buyer and Seller takers execute against Market Maker's orders.

- OBBuyerTaker: Buys YES shares (takes from NO sell orders)
- OBSellerTaker: Sells YES shares (takes from YES buy orders)
"""

from trufnetwork_sdk_py.client import TNClient

# Testnet configuration
TESTNET_URL = "http://ec2-3-141-77-16.us-east-2.compute.amazonaws.com:8484"

# Market ID from Step 1 (read from file or use default)
import os

def get_query_id():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    query_id_file = os.path.join(script_dir, ".query_id")
    try:
        with open(query_id_file, "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        print(f"Warning: {query_id_file} not found. Run 01_create_market.py first.")
        raise SystemExit(1)

QUERY_ID = get_query_id()

# WARNING: These are throwaway private keys provided for testnet examples only.
# DO NOT use these keys for production or store any real funds in these wallets.
# Always use secure key management practices in production environments.
BUYER_TAKER_PRIVATE_KEY = "9b70937b21176cfa48f0859f4063c66a7998964cc2dfde873ef3d54c8fe04d74"
BUYER_TAKER_ADDRESS = "0x1c6790935a3a1A6B914399Ba743BEC8C41Fe89Fb"

SELLER_TAKER_PRIVATE_KEY = "9ce79cafa66d736da853941c5cd32f996d5e45a29d3001ba6b8d51bdfa608b97"
SELLER_TAKER_ADDRESS = "0x51125FD33c366595d24aa42229085D30c95a62dA"


def run_buyer_taker():
    """Buyer taker buys YES shares by taking NO sell orders."""
    print("\n" + "=" * 50)
    print("BUYER TAKER: Buying YES shares")
    print("=" * 50)

    client = TNClient(TESTNET_URL, BUYER_TAKER_PRIVATE_KEY)
    print(f"Wallet: {BUYER_TAKER_ADDRESS}")

    # Strategy: Buy YES shares at different prices
    # This executes against Market Maker's NO sell orders
    # When you buy YES @ price X, you're taking NO sell @ (100-X)

    buy_orders = [
        {"outcome": True, "price": 60, "amount": 5, "desc": "Buy 5 YES @ 60c"},
        {"outcome": True, "price": 55, "amount": 5, "desc": "Buy 5 YES @ 55c"},
    ]

    print("\n--- Placing Buy Orders ---")
    for order in buy_orders:
        try:
            print(f"\n  {order['desc']}")
            tx_hash = client.place_buy_order(
                query_id=QUERY_ID,
                outcome=order["outcome"],
                price=order["price"],
                amount=order["amount"],
            )
            print(f"  ✓ TX: {tx_hash[:16]}...")
        except Exception as e:
            print(f"  ✗ Failed: {e}")


def run_seller_taker():
    """Seller taker creates YES shares and sells them."""
    print("\n" + "=" * 50)
    print("SELLER TAKER: Creating and Selling YES shares")
    print("=" * 50)

    client = TNClient(TESTNET_URL, SELLER_TAKER_PRIVATE_KEY)
    print(f"Wallet: {SELLER_TAKER_ADDRESS}")

    # Strategy: Use split limit order to create shares, then sell YES
    # First create some shares using split limit order
    print("\n--- Creating Shares via Split Limit Order ---")
    try:
        print("  Creating 20 share pairs @ true_price=45")
        tx_hash = client.place_split_limit_order(
            query_id=QUERY_ID,
            true_price=45,
            amount=20,
        )
        print(f"  ✓ TX: {tx_hash[:16]}...")
        print("  Result: 20 YES holdings + 20 NO sell orders @ 55c")
    except Exception as e:
        print(f"  ✗ Failed: {e}")

    # Now place sell orders for YES shares
    # This will match against Market Maker's YES buy orders
    print("\n--- Placing Sell Orders for YES ---")
    sell_orders = [
        {"outcome": True, "price": 45, "amount": 10, "desc": "Sell 10 YES @ 45c"},
        {"outcome": True, "price": 40, "amount": 5, "desc": "Sell 5 YES @ 40c"},
    ]

    for order in sell_orders:
        try:
            print(f"\n  {order['desc']}")
            tx_hash = client.place_sell_order(
                query_id=QUERY_ID,
                outcome=order["outcome"],
                price=order["price"],
                amount=order["amount"],
            )
            print(f"  ✓ TX: {tx_hash[:16]}...")
        except Exception as e:
            print(f"  ✗ Failed: {e}")


def main():
    print("=" * 60)
    print("Order Book E2E Test - Step 3: Takers Execute Trades")
    print("=" * 60)

    # Run buyer taker
    run_buyer_taker()

    # Run seller taker
    run_seller_taker()

    print("\n" + "=" * 60)
    print("Trades executed!")
    print("Next: Run 04_verify_state.py to check final order book state")
    print("=" * 60)


if __name__ == "__main__":
    main()
