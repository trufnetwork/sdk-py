#!/usr/bin/env python

import argparse
import time
from datetime import datetime, timezone
import requests

# --- Configuration ---
# Kwil/Node Configuration
INDEXER_URL = "http://ec2-52-15-66-172.us-east-2.compute.amazonaws.com:8080"

# Wallets
MARKET_MAKER_ADDR = "0xc11Ff6d3cC60823EcDCAB1089F1A4336053851EF"
BUYER_TAKER_ADDR = "0x1c6790935a3a1A6B914399Ba743BEC8C41Fe89Fb"

# --- Helper Functions ---
def with_retry(fn, *args, max_retries=5, initial_backoff=1, **kwargs):
    """
    Executes a function with exponential backoff on failure.
    Returns None if all retries fail.
    """
    retries = 0
    err_msg = ""
    while retries < max_retries:
        try:
            resp = fn(*args, **kwargs)
            if hasattr(resp, "status_code") and resp.status_code == 200:
                return resp
            
            err_msg = f"Status {resp.status_code}" if hasattr(resp, "status_code") else "Unknown failure"
        except Exception as e:
            err_msg = str(e)
            
        retries += 1
        if retries >= max_retries:
            print(f"  ❌ All {max_retries} attempts failed: {err_msg}")
            return None
            
        backoff = initial_backoff * (2 ** (retries - 1))
        print(f"  ⚠️ Attempt {retries} failed ({err_msg}). Retrying in {backoff}s... ({retries}/{max_retries})")
        time.sleep(backoff)

def main(query_id: int):
    """
    Checks the LP reward distribution status for a given market.
    """
    print("=" * 60)
    print("LP Reward Distribution Verification Script")
    print(f"Market Query ID: {query_id}")
    print("=" * 60)

    # 1. Verify Distribution Summary
    dist_url = f"{INDEXER_URL}/v0/prediction-market/markets/{query_id}/distribution"
    resp = with_retry(requests.get, dist_url)
    if resp and resp.status_code == 200:
        data = resp.json().get("data", {})
        print(f"1. Distribution Summary for Market {query_id}:")
        print(f"  - Total Fees Distributed: {data.get('total_fees_distributed')}")
        
        dist_at = data.get('distributed_at', 0)
        if dist_at > 0:
            dist_time = datetime.fromtimestamp(dist_at, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"  - Distributed At:         {dist_time}")
        else:
            print("  - Distributed At:         Not yet distributed")
            
        print(f"  - Total LP Count:         {data.get('total_lp_count')}")
        print(f"  - Data Provider Fees:     {data.get('total_dp_fees')}")
        print(f"  - Validator Fees:         {data.get('total_validator_fees')}")
    else:
        print(f"1. Failed to get distribution summary (Status 404 or Timeout)")

    # 2. Check Reward History for known participants
    print("\n2. Participant Reward History:")
    for label, wallet in [("Market Maker", MARKET_MAKER_ADDR), ("Buyer Taker", BUYER_TAKER_ADDR)]:
        rewards_url = f"{INDEXER_URL}/v0/prediction-market/participants/{wallet}/rewards?query_id={query_id}"
        resp = with_retry(requests.get, rewards_url)
        if resp and resp.status_code == 200:
            data = resp.json().get("data", {})
            rewards = data.get("rewards", [])
            print(f"  - {label} ({wallet[:10]}...):")
            if rewards:
                for r in rewards:
                    reward_amount = r.get('reward_amount', 0)
                    ts = r.get('distributed_at')
                    if ts is not None and isinstance(ts, (int, float)):
                        dist_time = datetime.fromtimestamp(ts, timezone.utc).strftime('%H:%M:%S')
                    else:
                        dist_time = "unknown time"
                    print(f"    - Earned: {reward_amount} (at {dist_time})")
            else:
                print("    - No rewards found for this market.")
        else:
            print(f"  - {label}: Failed to get rewards history.")

    print("" + "=" * 60)
    print("Verification complete!")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check LP reward distribution for a given market.")
    parser.add_argument("query_id", type=int, nargs="?", default=14164, help="The Query ID of the market to check (defaults to 14164).")
    args = parser.parse_args()
    
    main(args.query_id)
