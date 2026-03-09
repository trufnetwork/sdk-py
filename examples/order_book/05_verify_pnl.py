"""
Verification Script: Portfolio P&L Tracking

1. Creates a new market (settles in 5 minutes).
2. Performs trades using different wallets (Market Maker, Buyer Taker).
3. Waits for settlement.
4. Verifies the Indexer P&L and Charting endpoints.
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

# Market Parameters
BITCOIN_STREAM_ID = "st9058219c3c3247faf2b0a738de7027"
DATA_PROVIDER = "0xe5252596672cd0208a881bdb67c9df429916ba92"
THRESHOLD = "10000"  # Guaranteed to be above (BTC price is high)
BRIDGE = "hoodi_tt2"

def with_retry(fn, *args, max_retries=5, initial_backoff=1, **kwargs):
    """
    Executes a function with exponential backoff on failure.
    """
    retries = 0
    while retries < max_retries:
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                raise e
            
            backoff = initial_backoff * (2 ** (retries - 1))
            print(f"   ⚠️ Operation failed ({e}). Retrying in {backoff}s... ({retries}/{max_retries})")
            time.sleep(backoff)

def main():
    print("=" * 60)
    print("Portfolio P&L Verification Script")
    print("=" * 60)

    # 1. Create Market
    client_creator = TNClient(NODE_URL, MARKET_CREATOR_KEY)
    
    # Settle in 5 minutes
    now = datetime.now(timezone.utc)
    settle_time = now + timedelta(minutes=5)
    settle_timestamp = int(settle_time.timestamp())
    
    print(f"\n1. Creating market settling at {settle_time.strftime('%H:%M:%S UTC')}...")
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

    time.sleep(5)  # Wait for indexer to pick up the market
    markets = with_retry(client_creator.list_markets, limit=10)
    query_id = None
    for m in markets:
        if m.get('settle_time') == settle_timestamp:
            query_id = m.get('id')
            break
    
    if not query_id:
        print("Could not find created market query_id")
        return
    print(f"✓ Market Created: Query ID {query_id}")

    # 2. Market Maker: Create YES holdings via split order
    print(f"\n2. Market Maker ({MARKET_MAKER_ADDR[:10]}...) placing split order...")
    client_mm = TNClient(NODE_URL, MARKET_MAKER_KEY)
    # MM locks 10 tokens (10 YES, 10 NO). Collateral change should be -10.
    with_retry(client_mm.place_split_limit_order, query_id, true_price=50, amount=10)
    print("✓ MM Split order placed (-10 Collateral impact)")

    # 3. Buyer Taker: Buy 5 YES from MM
    print(f"\n3. Buyer Taker ({BUYER_TAKER_ADDR[:10]}...) buying 5 YES from MM...")
    client_taker = TNClient(NODE_URL, BUYER_TAKER_KEY)
    # Buy 5 YES at 50c = -2.5 collateral.
    with_retry(client_taker.place_buy_order, query_id, outcome=True, price=50, amount=5)
    print("✓ Buyer Taker matched MM (-2.5 Collateral impact)")
    # MM should gain 2.5 collateral from the sell.

    # 4. Wait for settlement
    print(f"\n4. Waiting for settlement (approx {settle_time.strftime('%H:%M:%S UTC')})...")
    while True:
        now = datetime.now(timezone.utc)
        if now > settle_time + timedelta(seconds=30):
            break
        remaining = (settle_time + timedelta(seconds=30) - now).total_seconds()
        print(f"   Waiting... {int(remaining)}s left", end="\r")
        time.sleep(10)
    print("\n✓ Market should be settled now.")

    # 5. Verify Indexer P&L
    print("\n5. Verifying LP Reward Distribution...")
    dist_url = f"{INDEXER_URL}/v0/prediction-market/markets/{query_id}/distribution"
    resp = with_retry(requests.get, dist_url)
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        print(f"  Distribution Summary for Market {query_id}:")
        print(f"    Total Fees:     {data.get('total_fees_distributed')}")
        print(f"    Distributed At: {data.get('distributed_at')}")
    else:
        print(f"  Failed to get distribution summary: {resp.status_code}")

    print("\n6. Verifying Indexer Endpoints...")
    time.sleep(10) # Wait for final sync cycle

    for label, wallet in [("Market Maker", MARKET_MAKER_ADDR), ("Buyer Taker", BUYER_TAKER_ADDR)]:
        print(f"\n--- {label} ({wallet}) ---")
        
        # Check P&L Summary
        pnl_url = f"{INDEXER_URL}/v0/prediction-market/participants/{wallet}/pnl"
        resp = with_retry(requests.get, pnl_url)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            print(f"  Summary P&L:")
            print(f"    Realized:   {data.get('realized')}")
            print(f"    Unrealized: {data.get('unrealized')}")
            print(f"    Total:      {data.get('total')}")
        else:
            print(f"  Failed to get P&L summary: {resp.status_code}")

        # Check Chart
        chart_url = f"{INDEXER_URL}/v0/prediction-market/participants/{wallet}/chart"
        resp = with_retry(requests.get, chart_url)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            print(f"  Chart points: {len(data)}")
            if len(data) > 0:
                latest = data[-1]
                print(f"    Latest Snapshot ({datetime.fromtimestamp(latest['timestamp'], timezone.utc).strftime('%H:%M:%S')}):")
                print(f"      Realized: {latest.get('realized')}")
                print(f"      Total:    {latest.get('total')}")
        else:
            print(f"  Failed to get Chart: {resp.status_code}")

        # Check Rewards History
        rewards_url = f"{INDEXER_URL}/v0/prediction-market/participants/{wallet}/rewards"
        resp = with_retry(requests.get, rewards_url)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            print(f"  Reward History (Total: {data.get('total_rewards')}):")
            for r in data.get("rewards", [])[:3]:
                print(f"    - Market {r['query_id']}: {r['reward_amount']} (at {r['distributed_at']})")
        else:
            print(f"  Failed to get rewards history: {resp.status_code}")

    print("\n" + "=" * 60)
    print("Verification complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
