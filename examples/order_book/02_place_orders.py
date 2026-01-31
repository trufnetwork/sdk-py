"""
Order Book E2E Test - Step 2: Place Orders

Market Maker provides liquidity by placing orders on both sides.
Uses OBMarketMaker wallet.

Order Book Strategy:
- Place split limit orders to create YES holdings and sell NO shares
- Place buy orders for YES at lower prices
"""

import os
from trufnetwork_sdk_py.client import TNClient

# Testnet configuration
TESTNET_URL = "http://ec2-3-141-77-16.us-east-2.compute.amazonaws.com:8484"


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

# WARNING: This is a throwaway private key provided for testnet examples only.
# DO NOT use this key for production or store any real funds in this wallet.
# Always use secure key management practices in production environments.
MARKET_MAKER_PRIVATE_KEY = "1b94f77f8eeb3ff78aa091b0965bf1b54305e3af50f9a6cd24cb457edc8c77ed"
MARKET_MAKER_ADDRESS = "0xc11Ff6d3cC60823EcDCAB1089F1A4336053851EF"


def main():
    print("=" * 60)
    print("Order Book E2E Test - Step 2: Place Orders (Market Maker)")
    print("=" * 60)

    # Initialize client with market maker wallet
    print(f"\nConnecting to testnet: {TESTNET_URL}")
    client = TNClient(TESTNET_URL, MARKET_MAKER_PRIVATE_KEY)
    print(f"Market Maker: {MARKET_MAKER_ADDRESS}")

    # Get market info
    print(f"\n--- Market Info (Query ID: {QUERY_ID}) ---")
    try:
        market = client.get_market_info(QUERY_ID)
        print(f"  Settled: {market.get('settled')}")
        print(f"  Settle Time: {market.get('settle_time')}")
    except Exception as e:
        print(f"Could not fetch market info: {e}")

    # Strategy: Market maker provides liquidity at multiple price levels
    # Using split limit orders:
    # - true_price=60 → holds YES, sells NO @ 40 cents
    # - true_price=55 → holds YES, sells NO @ 45 cents
    # - true_price=50 → holds YES, sells NO @ 50 cents

    print("\n--- Placing Split Limit Orders ---")
    print("(Creates YES holdings + NO sell orders)")

    split_orders = [
        {"true_price": 60, "amount": 10, "desc": "YES@60, sell NO@40"},
        {"true_price": 55, "amount": 10, "desc": "YES@55, sell NO@45"},
        {"true_price": 50, "amount": 10, "desc": "YES@50, sell NO@50"},
    ]

    for order in split_orders:
        try:
            print(f"\n  Placing: {order['desc']} (amount: {order['amount']} shares)")
            tx_hash = client.place_split_limit_order(
                query_id=QUERY_ID,
                true_price=order["true_price"],
                amount=order["amount"],
            )
            print(f"  ✓ Success! TX: {tx_hash[:16]}...")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

    # Also place some direct buy orders for YES shares
    print("\n--- Placing Buy Orders for YES ---")

    buy_orders = [
        {"outcome": True, "price": 45, "amount": 15, "desc": "Buy YES @ 45c"},
        {"outcome": True, "price": 40, "amount": 20, "desc": "Buy YES @ 40c"},
    ]

    for order in buy_orders:
        try:
            print(f"\n  Placing: {order['desc']} (amount: {order['amount']} shares)")
            tx_hash = client.place_buy_order(
                query_id=QUERY_ID,
                outcome=order["outcome"],
                price=order["price"],
                amount=order["amount"],
            )
            print(f"  ✓ Success! TX: {tx_hash[:16]}...")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

    # Display order book
    print("\n--- Current Order Book ---")
    try:
        print("\nYES Order Book:")
        yes_orders = client.get_order_book(QUERY_ID, outcome=True)
        if yes_orders:
            print(f"  {'Price':>6} | {'Amount':>8} | {'Type':>10}")
            print(f"  {'-'*6} | {'-'*8} | {'-'*10}")
            for order in yes_orders:
                price = order.get("price", 0)
                amount = order.get("amount", 0)
                order_type = "BUY" if price < 0 else "SELL"
                print(f"  {abs(price):>6}c | {amount:>8} | {order_type:>10}")
        else:
            print("  No orders")

        print("\nNO Order Book:")
        no_orders = client.get_order_book(QUERY_ID, outcome=False)
        if no_orders:
            print(f"  {'Price':>6} | {'Amount':>8} | {'Type':>10}")
            print(f"  {'-'*6} | {'-'*8} | {'-'*10}")
            for order in no_orders:
                price = order.get("price", 0)
                amount = order.get("amount", 0)
                order_type = "BUY" if price < 0 else "SELL"
                print(f"  {abs(price):>6}c | {amount:>8} | {order_type:>10}")
        else:
            print("  No orders")

    except Exception as e:
        print(f"Could not fetch order book: {e}")

    # Display user positions
    print("\n--- Market Maker Positions ---")
    try:
        all_positions = client.get_user_positions()
        positions = [p for p in all_positions if p.get("query_id") == QUERY_ID]
        if positions:
            print(f"  {'Outcome':>7} | {'Price':>6} | {'Amount':>8} | {'Type':>12}")
            print(f"  {'-'*7} | {'-'*6} | {'-'*8} | {'-'*12}")
            for pos in positions:
                outcome = "YES" if pos.get("outcome") else "NO"
                price = pos.get("price", 0)
                amount = pos.get("amount", 0)
                pos_type = pos.get("position_type", "unknown")
                print(f"  {outcome:>7} | {abs(price):>6}c | {amount:>8} | {pos_type:>12}")
        else:
            print("  No positions")
    except Exception as e:
        print(f"Could not fetch positions: {e}")

    print("\n" + "=" * 60)
    print("Market Maker has provided liquidity!")
    print("Next: Run 03_take_orders.py for takers to execute trades")
    print("=" * 60)


if __name__ == "__main__":
    main()
