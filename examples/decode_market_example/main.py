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

        # 2. List the most recently created markets
        # We'll look at the top 3 active markets.
        limit = 3
        print(f"[*] Fetching the {limit} latest markets...")
        markets = client.list_markets(limit=limit)

        if not markets:
            print("[!] No markets found on the network.")
            return

        print(f"[+] Found {len(markets)} markets.\n")

        # 3. Process each market
        for m in markets:
            market_id = m['id']
            print(f"{'-' * 40}")
            print(f" MARKET ID: {market_id}")
            print(f"{'-' * 40}")
            
            try:
                # Fetch the FULL market info, which includes the 'query_components'
                # list_markets only returns a summary for performance.
                market_info = client.get_market_info(market_id)

                # Use the SDK's built-in decoder to parse the binary components
                # This handles ABI-decoding the (address, bytes32, string, bytes) tuple
                # and further parsing the 'args' based on the action type.
                details = TNClient.decode_market_data(market_info['query_components'])

                # Display the decoded information
                print(f"  [Action]      {details['action_id']}")
                print(f"  [Market Type] {details['type'].upper()}")
                
                # Format thresholds for readability
                thresholds_str = ", ".join(details['thresholds'])
                print(f"  [Thresholds]  {thresholds_str}")
                
                print(f"  [Provider]    {details['data_provider']}")
                print(f"  [Stream ID]   {details['stream_id']}")
                
                # Print the raw decoded dictionary for reference
                # print(f"\n  [Raw Data] {json.dumps(details, indent=4)}")
                print()

            except Exception as e:
                print(f"  [!] Error processing market {market_id}: {e}")

    except Exception as e:
        print(f"[!] Critical error: {e}")
        sys.exit(1)

    print("=" * 60)
    print(" Done.")
    print("=" * 60)

if __name__ == "__main__":
    main()
