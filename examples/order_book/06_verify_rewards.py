"""
Verification Script: Fee Distribution & Reward History

Checks the fee distribution and reward history for a settled market.
Verifies that LP, Data Provider, and Validator rewards are correctly distributed.

Usage:
    python 06_verify_rewards.py                   # Reads query_id from .query_id (saved by 05)
    python 06_verify_rewards.py 12345             # Check a specific market
"""

import argparse
import os
import time
from datetime import datetime, timezone
import requests

# --- Configuration ---
INDEXER_URL = "http://ec2-52-15-66-172.us-east-2.compute.amazonaws.com:8080"

# Known participant wallets (from 05_verify_pnl.py)
MARKET_MAKER_ADDR = "0xc11Ff6d3cC60823EcDCAB1089F1A4336053851EF"
BUYER_TAKER_ADDR = "0x1c6790935a3a1A6B914399Ba743BEC8C41Fe89Fb"
DATA_PROVIDER_ADDR = "0xe5252596672cd0208a881bdb67c9df429916ba92"
VALIDATOR_ADDR = "0x231ea6C42aD77036237EF1C6398b76D0afc7Fd9e"


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


def format_wei(wei_str):
    """Format wei string to human-readable TRUF amount."""
    try:
        wei = int(wei_str)
        truf = wei / 1e18
        return f"{truf:.4f} TRUF ({wei_str} wei)"
    except (ValueError, TypeError):
        return str(wei_str)


def format_timestamp(ts):
    """Format unix timestamp to human-readable string."""
    try:
        if ts and isinstance(ts, (int, float)) and ts > 0:
            return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    except (OSError, ValueError):
        pass
    return "N/A"


def main(query_id: int):
    print("=" * 60)
    print("Fee Distribution & Reward Verification")
    print(f"Market Query ID: {query_id}")
    print("=" * 60)

    # =========================================================================
    # 1. Distribution Summary
    # =========================================================================
    print(f"\n1. Distribution Summary for Market {query_id}...")

    dist_url = f"{INDEXER_URL}/v0/prediction-market/markets/{query_id}/distribution"
    resp = with_retry(requests.get, dist_url, max_retries=5, initial_backoff=3)

    distributed_at = None
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        distributed_at = data.get("distributed_at")

        print(f"  Total Fees Distributed: {format_wei(data.get('total_fees_distributed', '0'))}")
        print(f"  Total DP Fees:          {format_wei(data.get('total_dp_fees', '0'))}")
        print(f"  Total Validator Fees:   {format_wei(data.get('total_validator_fees', '0'))}")
        print(f"  LP Count:               {data.get('total_lp_count')}")
        print(f"  Block Count:            {data.get('block_count')}")
        print(f"  Distributed At:         {format_timestamp(distributed_at)}")

        # Verify 75/12.5/12.5 split
        try:
            total = int(data.get('total_fees_distributed', '0'))
            dp = int(data.get('total_dp_fees', '0'))
            val = int(data.get('total_validator_fees', '0'))
            lp = total
            if total > 0:
                print(f"\n  Fee Split Verification:")
                print(f"    LP share:        {lp / (lp + dp + val) * 100:.1f}% (expected: 75%)")
                print(f"    DP share:        {dp / (lp + dp + val) * 100:.1f}% (expected: 12.5%)")
                print(f"    Validator share:  {val / (lp + dp + val) * 100:.1f}% (expected: 12.5%)")
        except (ValueError, ZeroDivisionError):
            pass
    elif resp.status_code == 404:
        print(f"  Distribution not available yet for market {query_id}.")
        print(f"  Settlement runs asynchronously after settle_time.")
        print(f"  Check back later: {dist_url}")
    else:
        print(f"  Unexpected response: {resp.status_code} {resp.text[:200]}")

    # =========================================================================
    # 2. Participant Rewards
    # =========================================================================
    print(f"\n2. Participant Reward History...")

    participants = [
        ("Market Maker (LP)", MARKET_MAKER_ADDR),
        ("Data Provider",     DATA_PROVIDER_ADDR),
        ("Validator",         VALIDATOR_ADDR),
    ]

    for label, wallet in participants:
        print(f"\n--- {label} ({wallet[:10]}...{wallet[-4:]}) ---")

        # Build URL with cursor if we know the distribution timestamp
        rewards_url = f"{INDEXER_URL}/v0/prediction-market/participants/{wallet}/rewards"
        params = {"limit": 5}
        if distributed_at:
            params["cursor"] = str(distributed_at)

        resp = with_retry(requests.get, rewards_url, params=params, max_retries=5, initial_backoff=3)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            rewards = data.get("rewards", [])
            total = data.get("total_rewards", "0")
            print(f"  Total Rewards (all markets): {format_wei(total)}")

            # Find reward for our specific market
            market_reward = None
            for r in rewards:
                if r.get("query_id") == query_id:
                    market_reward = r
                    break

            if market_reward:
                print(f"  Reward for Market {query_id}:")
                print(f"    Amount:          {format_wei(market_reward.get('reward_amount', '0'))}")
                print(f"    Reward Percent:  {market_reward.get('total_reward_percent')}%")
                print(f"    Blocks Sampled:  {market_reward.get('blocks_sampled')}")
                print(f"    Distributed At:  {format_timestamp(market_reward.get('distributed_at'))}")
            else:
                print(f"  No reward found for market {query_id} in recent history.")
                if rewards:
                    print(f"  (Latest rewards are for markets: {[r.get('query_id') for r in rewards[:3]]})")
        else:
            print(f"  Failed to get rewards: {resp.status_code}")

    # =========================================================================
    # 3. Buyer/Taker Settlement
    # =========================================================================
    print(f"\n3. Buyer/Taker Settlement...")

    print(f"\n--- Buyer Taker ({BUYER_TAKER_ADDR[:10]}...{BUYER_TAKER_ADDR[-4:]}) ---")

    settle_url = f"{INDEXER_URL}/v0/prediction-market/participants/{BUYER_TAKER_ADDR}/settlements"
    resp = with_retry(requests.get, settle_url, max_retries=5, initial_backoff=3)
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        settlements = data.get("settlements", [])
        print(f"  Total Won:  {data.get('total_won', 0)}")
        print(f"  Total Lost: {data.get('total_lost', 0)}")

        market_settle = None
        for s in settlements:
            if s.get("query_id") == query_id:
                market_settle = s
                break

        if market_settle:
            print(f"  Settlement for Market {query_id}:")
            print(f"    Winning Shares:      {market_settle.get('winning_shares', 0)}")
            print(f"    Losing Shares:       {market_settle.get('losing_shares', 0)}")
            print(f"    Payout:              {format_wei(market_settle.get('payout', '0'))}")
            print(f"    Refunded Collateral: {format_wei(market_settle.get('refunded_collateral', '0'))}")
            print(f"    Timestamp:           {format_timestamp(market_settle.get('timestamp'))}")
        else:
            print(f"  No settlement found for market {query_id}.")
            if settlements:
                print(f"  (Latest settlements: markets {[s.get('query_id') for s in settlements[:3]]})")
    else:
        print(f"  Failed to get settlements: {resp.status_code}")

    # Also check buyer P&L
    pnl_url = f"{INDEXER_URL}/v0/prediction-market/participants/{BUYER_TAKER_ADDR}/pnl"
    resp = with_retry(requests.get, pnl_url, max_retries=5, initial_backoff=3)
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        print(f"  P&L Summary:")
        print(f"    Realized:   {data.get('realized')}")
        print(f"    Unrealized: {data.get('unrealized')}")
        print(f"    Total:      {data.get('total')}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("Verification complete!")
    print(f"\nQuick links for Market {query_id}:")
    print(f"  Distribution: {INDEXER_URL}/v0/prediction-market/markets/{query_id}/distribution")
    print(f"  MM Rewards:   {INDEXER_URL}/v0/prediction-market/participants/{MARKET_MAKER_ADDR}/rewards")
    print(f"  DP Rewards:   {INDEXER_URL}/v0/prediction-market/participants/{DATA_PROVIDER_ADDR}/rewards")
    print(f"  Val Rewards:  {INDEXER_URL}/v0/prediction-market/participants/{VALIDATOR_ADDR}/rewards")
    print(f"  Settlements:  {INDEXER_URL}/v0/prediction-market/participants/{BUYER_TAKER_ADDR}/settlements")
    print("=" * 60)


def load_default_query_id():
    """Load query_id from .query_id file saved by 05_run_market_demo.py."""
    query_id_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".query_id")
    try:
        with open(query_id_file) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


if __name__ == "__main__":
    default_id = load_default_query_id()
    parser = argparse.ArgumentParser(description="Check fee distribution and rewards for a settled market.")
    parser.add_argument("query_id", type=int, nargs="?", default=default_id,
                        help="The Query ID of the market to check (reads .query_id from 05 if omitted).")
    args = parser.parse_args()

    if args.query_id is None:
        parser.error("No query_id provided and .query_id file not found. Run 05_run_market_demo.py first or pass a query_id.")

    main(args.query_id)
