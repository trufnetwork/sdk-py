import os
import sys
from trufnetwork_sdk_py.client import TNClient

def main():
    print("--- TRUF.NETWORK: LP Rewards SDK Demonstration ---")
    
    # Configuration
    endpoint = "https://gateway.testnet.truf.network"
    dummy_key = "0000000000000000000000000000000000000000000000000000000000000001"
    client = TNClient(endpoint, dummy_key)
    
    # Known testnet data for demonstration
    address = "0xC11FF6D3cC60823ECdcab1089f1A4336053851EF"
    query_id = 34
    distribution_id = 7 # Obtained from the summary of query_id 34

    # 1. get_participant_reward_history(address) -> list
    # Returns all rewards earned by a specific wallet across the network.
    print(f"\n[*] 1. get_participant_reward_history('{address}')")
    history = client.get_participant_reward_history(address)
    print(f"Result Type: {type(history).__name__}, Count: {len(history)}")
    if history:
        print(f"Sample Entry: {history[0]}")

    # 2. get_distribution_summary(query_id) -> dict | None
    # Returns the high-level audit record for a specific market settlement.
    print(f"\n[*] 2. get_distribution_summary({query_id})")
    summary = client.get_distribution_summary(query_id)
    print(f"Result Type: {type(summary).__name__ if summary else 'NoneType'}")
    if summary:
        print(f"Summary Data: {summary}")

    # 3. get_distribution_details(distribution_id) -> list
    # Returns the granular per-LP breakdown for a specific distribution event.
    print(f"\n[*] 3. get_distribution_details({distribution_id})")
    details = client.get_distribution_details(distribution_id)
    print(f"Result Type: {type(details).__name__}, Count: {len(details)}")
    if details:
        # Create a "pretty" version for display
        sample = details[0].copy()
        if isinstance(sample['wallet_address'], bytes):
            sample['wallet_address'] = "0x" + sample['wallet_address'].hex()
        
        # Convert wei string to float TRUF for readability
        reward_truf = int(sample['reward_amount']) / 1e18
        sample['reward_amount'] = f"{reward_truf:.4f} TRUF"
        
        print(f"Sample Detail: {sample}")

if __name__ == "__main__":
    main()
