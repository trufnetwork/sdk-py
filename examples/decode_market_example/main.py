import json
import sys
from trufnetwork_sdk_py.client import TNClient

def main():
    """
    This example demonstrates how to fetch real prediction market data from the 
    TRUF.NETWORK node and decode the low-level query components into 
    human-readable structured data.
    """
    print("=" * 60)
    print(" TRUF.NETWORK - Prediction Market Decoding Example")
    print("=" * 60)

    # Configuration
    # We use a direct IP to avoid DNS issues in some environments.
    endpoint = "https://gateway.testnet.truf.network"
    
    # Use a dummy private key. Read-only actions don't require a funded account.
    private_key = "0000000000000000000000000000000000000000000000000000000000000001"

    print(f"[*] Connecting to: {endpoint}")

    try:
        # 1. Initialize the TNClient
        client = TNClient(endpoint, private_key)

        # 2. List Markets (Both Active and Settled)
        states = [
            {"label": "ACTIVE", "filter": False},
            {"label": "SETTLED", "filter": True}
        ]
        limit = 2

        for state in states:
            print(f"\n--- Fetching Latest {state['label']} Markets ---")
            markets = client.list_markets(limit=limit, settled_filter=state['filter'])

            if not markets:
                print(f"[!] No {state['label']} markets found.")
                continue

            print(f"[+] Found {len(markets)} markets.\n")

            # 3. Process each market
            for m in markets:
                market_id = m['id']
                print(f"  MARKET ID: {market_id}")
                
                try:
                    # Fetch the FULL market info
                    market_info = client.get_market_info(market_id)

                    # Use the SDK's built-in decoder
                    details = TNClient.decode_market_data(market_info['query_components'])

                    # Display the decoded information
                    print(f"    [Action]      {details['action_id']}")
                    print(f"    [Market Type] {details['type'].upper()}")
                    
                    # Format thresholds for readability
                    thresholds_str = ", ".join(details['thresholds'])
                    print(f"    [Thresholds]  {thresholds_str}")
                    print(f"    [Stream ID]   {details['stream_id']}")
                    print()

                except Exception as e:
                    print(f"    [!] Error processing market {market_id}: {e}")

    except Exception as e:
        print(f"[!] Critical error: {e}")
        sys.exit(1)

    print("=" * 60)
    print(" Done.")
    print("=" * 60)

if __name__ == "__main__":
    main()
