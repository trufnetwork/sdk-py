"""
Prediction Market Indexer API Example (Python)

Demonstrates how to query the TrufNetwork Prediction Market Indexer
to retrieve historical market data, settlements, snapshots, and LP rewards.

For full API documentation, endpoint details, field descriptions, and architecture:
  https://github.com/trufnetwork/node/blob/main/docs/prediction-market-indexer.md

Usage:
  python examples/indexer/query_indexer.py
"""

import json
import requests

# Indexer URLs
# Production: https://indexer.infra.truf.network
# Testnet:    http://ec2-52-15-66-172.us-east-2.compute.amazonaws.com:8080
INDEXER_URL = "http://ec2-52-15-66-172.us-east-2.compute.amazonaws.com:8080"

# Example wallet addresses (from testnet order book examples)
BUYER_WALLET = "1c6790935a3a1A6B914399Ba743BEC8C41Fe89Fb"
LP1_WALLET = "c11Ff6d3cC60823EcDCAB1089F1A4336053851EF"


def query_markets():
    """Endpoint 1: List historical markets and their settlement results."""
    print("=" * 60)
    print("Endpoint 1: List Historical Markets")
    print("=" * 60)

    # Basic: list all markets (most recent first)
    resp = requests.get(f"{INDEXER_URL}/v0/prediction-market/markets", params={
        "limit": 5,
    })
    resp.raise_for_status()
    data = resp.json()

    print(f"\nFound {len(data['data'])} markets:")
    for m in data["data"]:
        status = "SETTLED" if m["settled"] else "ACTIVE"
        outcome = ""
        if m.get("winning_outcome") is not None:
            outcome = f" (YES wins)" if m["winning_outcome"] else f" (NO wins)"
        print(f"  Market #{m['query_id']}: {status}{outcome}")
        print(f"    Hash: {m['query_hash'][:16]}...")
        print(f"    Bridge: {m['bridge']}, Max Spread: {m['max_spread']}c")

    # Filter: only settled markets
    print("\n--- Settled markets only ---")
    resp = requests.get(f"{INDEXER_URL}/v0/prediction-market/markets", params={
        "status": "settled",
        "limit": 3,
    })
    resp.raise_for_status()
    settled = resp.json()
    print(f"  Found {len(settled['data'])} settled markets")

    return data["data"]


def query_snapshots(query_id):
    """Endpoint 2: Market order book snapshots (for charting)."""
    print("\n" + "=" * 60)
    print(f"Endpoint 2: Order Book Snapshots (Market #{query_id})")
    print("=" * 60)

    resp = requests.get(
        f"{INDEXER_URL}/v0/prediction-market/markets/{query_id}/snapshots",
        params={"limit": 5},
    )
    resp.raise_for_status()
    data = resp.json()

    snapshots = data["data"]
    if not snapshots:
        print("  No snapshots found for this market.")
        return

    print(f"\nFound {len(snapshots)} snapshots:")
    for s in snapshots:
        mid = s.get("midpoint_price", "N/A")
        spread = s.get("spread", "N/A")
        print(f"  Block {s['block_height']}: midpoint={mid}c, spread={spread}c")


def query_settlements(wallet_address):
    """Endpoint 3: Historical settlement results by participant."""
    print("\n" + "=" * 60)
    print(f"Endpoint 3: Participant Settlements ({wallet_address[:10]}...)")
    print("=" * 60)

    resp = requests.get(
        f"{INDEXER_URL}/v0/prediction-market/participants/{wallet_address}/settlements",
        params={"limit": 10},
    )
    resp.raise_for_status()
    data = resp.json()["data"]

    print(f"\n  Wallet: {data['wallet_address']}")
    print(f"  Total Won: {data['total_won']}, Total Lost: {data['total_lost']}")

    for s in data["settlements"]:
        payout_usdc = int(s["payout"]) / 1e18
        refund_usdc = int(s["refunded_collateral"]) / 1e18
        print(f"\n  Market #{s['query_id']}:")
        print(f"    Winning shares: {s['winning_shares']}, Losing shares: {s['losing_shares']}")
        print(f"    Payout: {payout_usdc:.2f} USDC, Refund: {refund_usdc:.2f} USDC")


def query_rewards(wallet_address):
    """Endpoint 4: Historical LP liquidity rewards by participant."""
    print("\n" + "=" * 60)
    print(f"Endpoint 4: LP Rewards ({wallet_address[:10]}...)")
    print("=" * 60)

    resp = requests.get(
        f"{INDEXER_URL}/v0/prediction-market/participants/{wallet_address}/rewards",
        params={"limit": 10},
    )
    resp.raise_for_status()
    data = resp.json()["data"]

    print(f"\n  Wallet: {data['wallet_address']}")
    total = int(data["total_rewards"]) / 1e18
    print(f"  Total Rewards: {total:.4f} USDC")

    for r in data["rewards"]:
        amount_usdc = int(r["reward_amount"]) / 1e18
        print(f"\n  Market #{r['query_id']}:")
        print(f"    Reward: {amount_usdc:.4f} USDC ({r['total_reward_percent']:.2f}%)")
        print(f"    Blocks Sampled: {r['blocks_sampled']}")


def main():
    print("TrufNetwork Prediction Market Indexer - Python Example")
    print("Indexer URL:", INDEXER_URL)

    # 1. List markets
    markets = query_markets()

    # 2. Snapshots for the most recent market
    if markets:
        query_snapshots(markets[0]["query_id"])

    # 3. Settlement results for buyer
    query_settlements(BUYER_WALLET)

    # 4. LP rewards for LP1
    query_rewards(LP1_WALLET)

    print("\n" + "=" * 60)
    print("Done! All 4 indexer endpoints demonstrated.")
    print("=" * 60)


if __name__ == "__main__":
    main()
