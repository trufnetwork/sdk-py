"""
Order Book E2E Test - Step 2: Place Orders

Market Maker provides two-sided liquidity to earn LP rewards.
Uses OBMarketMaker wallet.

Order Book Strategy:
1. Place split limit orders to create YES holdings (needed for selling)
2. Place LP-eligible paired orders: YES SELL + NO BUY at complementary prices

LP Rewards Eligibility:
- Formula: yes_price == 100 - no_buy_price (using positive API prices)
- Example: YES SELL @ 55 + NO BUY @ 45 → 55 == 100 - 45 ✓
- Both orders must have the same amount
- Note: The system stores NO BUY prices internally as negative values
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
    query_id = get_query_id()
    print(f"Market ID: {query_id}")

    # Get market info
    print(f"\n--- Market Info ---")
    try:
        market = client.get_market_info(query_id)
        print(f"  Settled: {market.get('settled')}")
        print(f"  Settle Time: {market.get('settle_time')}")
    except Exception as e:
        print(f"Could not fetch market info: {e}")

    # ==========================================================================
    # Step 1: Create YES holdings via split limit orders
    # ==========================================================================
    print("\n--- Step 1: Create YES Holdings (Split Limit Orders) ---")
    print("These create YES shares we can sell for LP rewards.")

    split_orders = [
        {"true_price": 60, "amount": 100},
        {"true_price": 55, "amount": 50},
    ]

    for order in split_orders:
        try:
            print(f"\n  Creating {order['amount']} YES holdings @ {order['true_price']}c...")
            tx_hash = client.place_split_limit_order(
                query_id=query_id,
                true_price=order["true_price"],
                amount=order["amount"],
            )
            no_price = 100 - order["true_price"]
            print(f"    Done: {order['amount']} YES holdings + {order['amount']} NO sell @ {no_price}c")
            print(f"    TX: {tx_hash[:16]}...")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

    # ==========================================================================
    # Step 2: Place LP-eligible paired orders (YES SELL + NO BUY)
    # ==========================================================================
    print("\n--- Step 2: Place LP-Eligible Orders ---")
    print("Formula: YES_SELL_PRICE == 100 + NO_BUY_PRICE")
    print("(NO BUY stored as negative in DB, so prices must sum to 100)")

    # LP pairs: YES SELL @ X + NO BUY @ (100-X)
    lp_pairs = [
        {"yes_price": 55, "no_price": 45, "amount": 25},
        {"yes_price": 52, "no_price": 48, "amount": 25},
        {"yes_price": 50, "no_price": 50, "amount": 25},
    ]

    for pair in lp_pairs:
        print(f"\n  LP Pair: YES SELL @ {pair['yes_price']}c + NO BUY @ {pair['no_price']}c (amount: {pair['amount']})")

        # Place YES sell order (we have YES holdings from split limit orders)
        try:
            tx_hash = client.place_sell_order(
                query_id=query_id,
                outcome=True,  # YES
                price=pair["yes_price"],
                amount=pair["amount"],
            )
            print(f"    YES SELL: {tx_hash[:16]}...")
        except Exception as e:
            print(f"    ✗ YES SELL Failed: {e}")
            continue

        # Place NO buy order at complementary price
        try:
            tx_hash = client.place_buy_order(
                query_id=query_id,
                outcome=False,  # NO
                price=pair["no_price"],
                amount=pair["amount"],
            )
            print(f"    NO BUY:   {tx_hash[:16]}...")
        except Exception as e:
            print(f"    ✗ NO BUY Failed: {e}")
            continue

        # Verify LP eligibility
        check = pair["yes_price"] + pair["no_price"] == 100
        check_str = "✓" if check else "✗"
        print(f"    LP Check: {pair['yes_price']} + {pair['no_price']} = {pair['yes_price'] + pair['no_price']} {check_str}")

    # ==========================================================================
    # Step 3: Display positions
    # ==========================================================================
    print("\n--- Current Positions ---")
    try:
        all_positions = client.get_user_positions()
        positions = [p for p in all_positions if p.get("query_id") == query_id]
        if positions:
            print(f"  {'Outcome':>7} | {'Price':>6} | {'Amount':>8} | {'Type':>12}")
            print(f"  {'-'*7} | {'-'*6} | {'-'*8} | {'-'*12}")
            for pos in positions:
                outcome = "YES" if pos.get("outcome") else "NO"
                price = pos.get("price", 0)
                amount = pos.get("amount", 0)
                if price == 0:
                    pos_type = "HOLDING"
                elif price < 0:
                    pos_type = "BUY"
                else:
                    pos_type = "SELL"
                print(f"  {outcome:>7} | {abs(price):>6}c | {amount:>8} | {pos_type:>12}")
        else:
            print("  No positions")
    except Exception as e:
        print(f"Could not fetch positions: {e}")

    # ==========================================================================
    # Step 4: Display market prices
    # ==========================================================================
    print("\n--- Market Prices ---")
    try:
        for name, outcome in [("YES", True), ("NO", False)]:
            prices = client.get_best_prices(query_id, outcome)
            bid = prices.get("best_bid", "N/A")
            ask = prices.get("best_ask", "N/A")
            spread = prices.get("spread", "N/A")
            print(f"  {name}: Bid={bid}c, Ask={ask}c, Spread={spread}c")
    except Exception as e:
        print(f"Could not fetch prices: {e}")

    print("\n" + "=" * 60)
    print("Orders Placed Successfully!")
    print("LP rewards will be sampled every 10 blocks by the scheduler.")
    print("Next: Run 03_take_orders.py for takers to execute trades")
    print("=" * 60)


if __name__ == "__main__":
    main()
