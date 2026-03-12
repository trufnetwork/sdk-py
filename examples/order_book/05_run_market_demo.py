"""
Complete Prediction Market Demo: LP Setup, Trading, Settlement & Rewards

End-to-end demo that exercises every part of the prediction market:

1. Creates a new market (settles in 5 minutes).
2. Market Maker places LP pair orders (two-sided liquidity).
3. Buyer Taker buys YES shares that MATCH against the order book.
4. Waits for settlement (YES wins — BTC is above $10k threshold).
5. Verifies everything:
   - Fee Distribution (75% LP / 12.5% DP / 12.5% Validator)
   - LP Rewards (Market Maker)
   - Data Provider Rewards
   - Validator Rewards
   - Buyer Settlement (winning shares + payout)
   - P&L for all participants

After this script completes, use 06_verify_rewards.py to re-check.
The query_id is saved to .query_id for 06 to pick up automatically.
"""

import os
import time
import requests
from datetime import datetime, timezone, timedelta
from trufnetwork_sdk_py.client import TNClient

# Configuration
NODE_URL = "http://ec2-3-141-77-16.us-east-2.compute.amazonaws.com:8484"
INDEXER_URL = "http://ec2-52-15-66-172.us-east-2.compute.amazonaws.com:8080"

# Wallets
## WARNING: These are throwaway private keys provided for testnet examples only.
## DO NOT use these keys for production or store any real funds in these wallets.
MARKET_CREATOR_KEY = "a537437df2ed8d3bcb3b99b4f88818cadf8ac365cd0a66595bb50973ac4ecf51"
MARKET_MAKER_KEY = "1b94f77f8eeb3ff78aa091b0965bf1b54305e3af50f9a6cd24cb457edc8c77ed"
MARKET_MAKER_ADDR = "0xc11Ff6d3cC60823EcDCAB1089F1A4336053851EF"
BUYER_TAKER_KEY = "9b70937b21176cfa48f0859f4063c66a7998964cc2dfde873ef3d54c8fe04d74"
BUYER_TAKER_ADDR = "0x1c6790935a3a1A6B914399Ba743BEC8C41Fe89Fb"

# Known infrastructure participants
DATA_PROVIDER = "0xe5252596672cd0208a881bdb67c9df429916ba92"
VALIDATOR_ADDR = "0x231ea6C42aD77036237EF1C6398b76D0afc7Fd9e"

# Market Parameters
BITCOIN_STREAM_ID = "st9058219c3c3247faf2b0a738de7027"
THRESHOLD = "10000"  # Guaranteed to be above (BTC price is high) → YES wins
BRIDGE = "hoodi_tt2"


def with_retry(fn, *args, max_retries=5, initial_backoff=2, **kwargs):
    """Executes a function with exponential backoff on failure."""
    retries = 0
    while retries < max_retries:
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                raise

            backoff = initial_backoff * (2 ** (retries - 1))
            print(f"   Warning: {e}")
            print(f"   Retrying in {backoff}s... ({retries}/{max_retries})")
            time.sleep(backoff)


def create_client(url, key):
    """Create a TNClient with retry for transient network errors."""
    return with_retry(TNClient, url, key, max_retries=10, initial_backoff=3)


def format_wei(wei_str):
    """Format wei string to human-readable TRUF amount."""
    try:
        wei = int(wei_str)
        return f"{wei / 1e18:.4f} TRUF ({wei_str} wei)"
    except (ValueError, TypeError):
        return str(wei_str)


def format_ts(ts):
    """Format unix timestamp to human-readable string."""
    try:
        if ts and isinstance(ts, (int, float)) and ts > 0:
            return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    except (OSError, ValueError):
        pass
    return "N/A"


def main():
    print("=" * 60)
    print("Complete Prediction Market Demo")
    print("=" * 60)

    # =========================================================================
    # 1. Create Market
    # =========================================================================
    client_creator = create_client(NODE_URL, MARKET_CREATOR_KEY)

    now = datetime.now(timezone.utc)
    settle_time = now + timedelta(minutes=5)
    settle_timestamp = int(settle_time.timestamp())

    print(f"\n1. Creating market settling at {settle_time.strftime('%H:%M:%S UTC')}...")
    print(f"   Threshold: BTC > ${THRESHOLD} → YES wins (guaranteed)")
    try:
        with_retry(client_creator.create_price_above_threshold_market,
            data_provider=DATA_PROVIDER,
            stream_id=BITCOIN_STREAM_ID,
            timestamp=settle_timestamp,
            threshold=THRESHOLD,
            bridge=BRIDGE,
            settle_time=settle_timestamp,
            max_spread=10,
            min_order_size=1_000_000_000_000_000_000,
        )
    except Exception as e:
        print(f"Error creating market: {e}")
        return

    time.sleep(5)
    markets = with_retry(client_creator.list_markets, limit=10)
    query_id = None
    for m in markets:
        if m.get('settle_time') == settle_timestamp:
            query_id = m.get('id')
            break

    if not query_id:
        print("Could not find created market query_id")
        return
    print(f"   Market Created: Query ID {query_id}")

    # Save query_id for 06_verify_rewards.py to pick up
    query_id_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".query_id")
    with open(query_id_file, "w") as f:
        f.write(str(query_id))
    print(f"   Saved to .query_id for 06_verify_rewards.py")

    # =========================================================================
    # 2. Market Maker: Create holdings + LP pair orders
    # =========================================================================
    #
    # LP reward scoring requires BOTH:
    #   - TRUE-side pair:  YES sell + NO buy  (prices sum to 100)
    #   - FALSE-side pair: NO sell  + YES buy (prices sum to 100)
    #
    # The LEAST(TRUE-side score, FALSE-side score) ensures both sides are needed.
    #
    # Market midpoint will be ~50 (from bid/ask), dynamic spread = 5 cents.
    # LP pairs must have prices within [mid-spread, mid+spread] = [45, 55].
    #
    # IMPORTANT: Buy prices must be strictly BELOW existing sell prices of the
    # same outcome to avoid the matching engine consuming the LP pair orders.
    #
    # Order of operations:
    #   1. Split order: creates YES holdings (price=0) + NO sell@50
    #   2. Bid/ask far from LP prices to establish midpoint
    #   3. TRUE-side: YES sell@51 + NO buy@49 (49 < 50, won't match NO sell@50)
    #   4. FALSE-side: YES buy@50 (50 < 51, won't match YES sell@51)
    # =========================================================================

    print(f"\n2. Market Maker ({MARKET_MAKER_ADDR[:10]}...) setting up LP positions...")
    client_mm = create_client(NODE_URL, MARKET_MAKER_KEY)

    # Step 1: Split order -- creates YES holdings + NO sell@50
    print("   a) Split order: 300 shares at price 50...")
    with_retry(client_mm.place_split_limit_order, query_id, true_price=50, amount=300)
    print("      Created: 300 YES holdings + 300 NO sell@50")

    # Step 2: Establish bid/ask for midpoint calculation (far from LP prices)
    print("   b) Setting bid/ask for midpoint...")
    with_retry(client_mm.place_buy_order, query_id, outcome=True, price=46, amount=50)
    print("      YES buy@46 (bid)")
    with_retry(client_mm.place_sell_order, query_id, outcome=True, price=54, amount=50)
    print("      YES sell@54 (ask)")

    # Step 3: TRUE-side LP pair -- YES sell@51 + NO buy@49
    print("   c) TRUE-side LP pair...")
    with_retry(client_mm.place_sell_order, query_id, outcome=True, price=51, amount=100)
    print("      YES sell@51 (amount=100)")
    with_retry(client_mm.place_buy_order, query_id, outcome=False, price=49, amount=100)
    print("      NO buy@49 (amount=100) -- safe: 49 < NO sell@50")

    # Step 4: FALSE-side LP pair -- NO sell@50 (from split) + YES buy@50
    print("   d) FALSE-side LP pair...")
    with_retry(client_mm.place_buy_order, query_id, outcome=True, price=50, amount=300)
    print("      YES buy@50 (amount=300) -- matches NO sell@50, safe: 50 < YES sell@51")

    print("   LP setup complete!")
    print("   Expected LP pairs:")
    print("     TRUE-side:  YES sell@51 + NO buy@49  (amount=100 each)")
    print("     FALSE-side: NO sell@50  + YES buy@50  (amount=300 each)")

    # =========================================================================
    # 3. Buyer Taker: Buy YES shares (order MATCHES the order book)
    # =========================================================================
    #
    # The matching engine supports price-crossing: a buy order at price P
    # matches any sell at or below P (standard order book behavior).
    # The buyer places buy@52, which crosses the MM's YES sell@51.
    # Match executes at sell price ($0.51), buyer is refunded $0.01/share.
    #
    # Result: Buyer acquires 5 YES shares at $0.51 each (not $0.52).
    # Since YES wins at settlement, buyer gets 5 × $1.00 = 5 TRUF payout (minus 2% fee).
    #
    # This generates trading fees that fund LP/DP/Validator rewards.
    # =========================================================================
    print(f"\n3. Buyer Taker ({BUYER_TAKER_ADDR[:10]}...) buying YES shares...")
    client_taker = create_client(NODE_URL, BUYER_TAKER_KEY)
    with_retry(client_taker.place_buy_order, query_id, outcome=True, price=52, amount=5)
    print("   Buyer placed YES buy@52 (amount=5)")
    print("   Price-crossing: matches YES sell@51 → Buyer acquires 5 YES shares at $0.51")
    print("   Expected at settlement: 5 shares × $1.00 = 5 TRUF payout (minus fees)")

    # =========================================================================
    # 4. Wait for settlement
    # =========================================================================
    print(f"\n4. Waiting for settlement (approx {settle_time.strftime('%H:%M:%S UTC')})...")
    print("   Settlement process:")
    print("     a) Scheduler detects market is past settle_time")
    print("     b) Requests attestation from data provider")
    print("     c) Attestation signed by validator")
    print("     d) Scheduler calls settle_market → distributes fees")
    # Wait extra 2 minutes for attestation + settlement scheduler
    wait_until = settle_time + timedelta(minutes=2)
    while True:
        now_utc = datetime.now(timezone.utc)
        if now_utc > wait_until:
            break
        remaining = (wait_until - now_utc).total_seconds()
        print(f"   Waiting... {int(remaining)}s left", end="\r")
        time.sleep(10)
    print("\n   Market should be settled now.")

    # =========================================================================
    # 5. Verify Fee Distribution (75% LP / 12.5% DP / 12.5% Validator)
    # =========================================================================
    print("\n5. Fee Distribution...")
    time.sleep(10)  # Wait for indexer sync

    dist_url = f"{INDEXER_URL}/v0/prediction-market/markets/{query_id}/distribution"
    resp = with_retry(requests.get, dist_url, max_retries=5, initial_backoff=5)

    distributed_at = None
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        distributed_at = data.get("distributed_at")
        print(f"   Total LP Fees:        {format_wei(data.get('total_fees_distributed', '0'))}")
        print(f"   Total DP Fees:        {format_wei(data.get('total_dp_fees', '0'))}")
        print(f"   Total Validator Fees: {format_wei(data.get('total_validator_fees', '0'))}")
        print(f"   LP Count:             {data.get('total_lp_count')}")
        print(f"   Distributed At:       {format_ts(distributed_at)}")
    elif resp.status_code == 404:
        print(f"   Not available yet — settlement is async, check back later.")
        print(f"   URL: {dist_url}")
    else:
        print(f"   Unexpected response: {resp.status_code}")

    # =========================================================================
    # 6. Verify Rewards (LP, Data Provider, Validator)
    # =========================================================================
    print("\n6. Reward History...")

    participants = [
        ("Market Maker (LP)", MARKET_MAKER_ADDR),
        ("Data Provider",     DATA_PROVIDER),
        ("Validator",         VALIDATOR_ADDR),
    ]

    for label, wallet in participants:
        print(f"\n   --- {label} ({wallet[:10]}...{wallet[-4:]}) ---")

        rewards_url = f"{INDEXER_URL}/v0/prediction-market/participants/{wallet}/rewards"
        params = {"limit": 5}
        if distributed_at:
            params["cursor"] = str(distributed_at)

        resp = with_retry(requests.get, rewards_url, params=params, max_retries=5, initial_backoff=3)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            rewards = data.get("rewards", [])
            total = data.get("total_rewards", "0")
            print(f"   Total Rewards (all markets): {format_wei(total)}")

            market_reward = next((r for r in rewards if r.get("query_id") == query_id), None)
            if market_reward:
                print(f"   Market {query_id}:")
                print(f"     Amount:  {format_wei(market_reward.get('reward_amount', '0'))}")
                print(f"     Percent: {market_reward.get('total_reward_percent')}%")
            else:
                print(f"   No reward for market {query_id} yet (settlement may be pending).")
        else:
            print(f"   Failed to get rewards: {resp.status_code}")

    # =========================================================================
    # 7. Verify Buyer Settlement (winning shares + payout)
    # =========================================================================
    print(f"\n7. Buyer Settlement ({BUYER_TAKER_ADDR[:10]}...)...")

    settle_url = f"{INDEXER_URL}/v0/prediction-market/participants/{BUYER_TAKER_ADDR}/settlements"
    resp = with_retry(requests.get, settle_url, max_retries=5, initial_backoff=3)
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        settlements = data.get("settlements", [])
        print(f"   Total Won:  {data.get('total_won', 0)}")
        print(f"   Total Lost: {data.get('total_lost', 0)}")

        market_settle = next((s for s in settlements if s.get("query_id") == query_id), None)
        if market_settle:
            print(f"   Market {query_id}:")
            print(f"     Winning Shares:      {market_settle.get('winning_shares', 0)}")
            print(f"     Losing Shares:       {market_settle.get('losing_shares', 0)}")
            print(f"     Payout:              {format_wei(market_settle.get('payout', '0'))}")
            print(f"     Refunded Collateral: {format_wei(market_settle.get('refunded_collateral', '0'))}")
        else:
            print(f"   No settlement for market {query_id} yet.")
    else:
        print(f"   Failed to get settlements: {resp.status_code}")

    # =========================================================================
    # 8. P&L Summary for all participants
    # =========================================================================
    print("\n8. P&L Summary...")

    for label, wallet in [("Market Maker", MARKET_MAKER_ADDR), ("Buyer Taker", BUYER_TAKER_ADDR)]:
        pnl_url = f"{INDEXER_URL}/v0/prediction-market/participants/{wallet}/pnl"
        resp = with_retry(requests.get, pnl_url, max_retries=5, initial_backoff=3)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            print(f"   {label}: Realized={data.get('realized')} Unrealized={data.get('unrealized')} Total={data.get('total')}")
        else:
            print(f"   {label}: Failed ({resp.status_code})")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("Demo complete!")
    print(f"\nMarket {query_id} — run 06_verify_rewards.py to re-check (reads .query_id).")
    print(f"\nQuick links:")
    print(f"  Distribution: {INDEXER_URL}/v0/prediction-market/markets/{query_id}/distribution")
    print(f"  MM Rewards:   {INDEXER_URL}/v0/prediction-market/participants/{MARKET_MAKER_ADDR}/rewards")
    print(f"  DP Rewards:   {INDEXER_URL}/v0/prediction-market/participants/{DATA_PROVIDER}/rewards")
    print(f"  Val Rewards:  {INDEXER_URL}/v0/prediction-market/participants/{VALIDATOR_ADDR}/rewards")
    print(f"  Settlements:  {INDEXER_URL}/v0/prediction-market/participants/{BUYER_TAKER_ADDR}/settlements")
    print("=" * 60)

if __name__ == "__main__":
    main()
