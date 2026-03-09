#!/usr/bin/env python

import argparse
import time
from datetime import datetime, timezone, timedelta
import requests
from web3 import Web3

# --- Configuration ---
# Kwil/Node Configuration
NODE_URL = "http://ec2-3-141-77-16.us-east-2.compute.amazonaws.com:8484"
INDEXER_URL = "http://ec2-52-15-66-172.us-east-2.compute.amazonaws.com:8080"
TEST_CHAIN_ID = "testnet-v1"

# Wallets
MARKET_MAKER_ADDR = "0xc11Ff6d3cC60823EcDCAB1089F1A4336053851EF"
BUYER_TAKER_ADDR = "0x1c6790935a3a1A6B914399Ba743BEC8C41Fe89Fb"

# --- Helper Functions ---
def with_retry(func, *args, **kwargs):
    """Simple retry for network calls."""
    for i in range(3):
        try:
            resp = func(*args, **kwargs)
            if resp.status_code == 200:
                return resp
            print(f"  Attempt {i+1} failed with status {resp.status_code}, retrying...")
        except requests.exceptions.RequestException as e:
            print(f"  Attempt {i+1} failed with exception: {e}")
        time.sleep(2)
    return requests.Response() # Return empty response if all retries fail

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
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        print(f"1. Distribution Summary for Market {query_id}:")
        print(f"  - Total Fees Distributed: {data.get('total_fees_distributed')}")
        
        dist_at = data.get('distributed_at', 0)
        if dist_at > 0:
            dist_time = datetime.fromtimestamp(dist_at, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"  - Distributed At:         {dist_time}")
        else:
            print(f"  - Distributed At:         Not yet distributed")
            
        print(f"  - Total LP Count:         {data.get('total_lp_count')}")
        print(f"  - Data Provider Fees:     {data.get('total_dp_fees')}")
        print(f"  - Validator Fees:         {data.get('total_validator_fees')}")
    else:
        print(f"1. Failed to get distribution summary: {resp.status_code}")

    # 2. Check Reward History for known participants
    print("2. Participant Reward History:")
    for label, wallet in [("Market Maker", MARKET_MAKER_ADDR), ("Buyer Taker", BUYER_TAKER_ADDR)]:
        rewards_url = f"{INDEXER_URL}/v0/prediction-market/participants/{wallet}/rewards?query_id={query_id}"
        resp = with_retry(requests.get, rewards_url)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            rewards = data.get("rewards", [])
            print(f"  - {label} ({wallet[:10]}...):")
            if rewards:
                for r in rewards:
                    print(f"    - Earned: {r['reward_amount']} (at {datetime.fromtimestamp(r['distributed_at'], timezone.utc).strftime('%H:%M:%S')})")
            else:
                print("    - No rewards found for this market.")
        else:
            print(f"  - {label}: Failed to get rewards history ({resp.status_code})")

    print("" + "=" * 60)
    print("Verification complete!")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check LP reward distribution for a given market.")
    parser.add_argument("query_id", type=int, nargs="?", default=14164, help="The Query ID of the market to check (defaults to 14164).")
    args = parser.parse_args()
    
    main(args.query_id)
