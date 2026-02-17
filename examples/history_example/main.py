import os
import sys
import base64
import binascii
from datetime import datetime, timezone
from trufnetwork_sdk_py.client import TNClient

def main():
    # Configuration
    private_key = os.getenv("TN_PRIVATE_KEY")
    if not private_key:
        private_key = "0000000000000000000000000000000000000000000000000000000000000001"
        
    endpoint = os.getenv("TN_GATEWAY_URL", "https://gateway.testnet.truf.network")
    
    # Initialize client
    print(f"🔄 Transaction History Demo (Python)")
    print(f"==================================")
    print(f"Endpoint: {endpoint}")
    
    try:
        client = TNClient(endpoint, private_key)
        print(f"Wallet:   {client.get_current_account()}\n")
    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        sys.exit(1)

    # Query parameters
    bridge_id = "hoodi_tt2"
    target_wallet = "0xc11Ff6d3cC60823EcDCAB1089F1A4336053851EF"
    limit = 10
    offset = 0

    print(f"📋 Fetching history for bridge '{bridge_id}'...")
    print(f"   Wallet: {target_wallet}")
    print(f"   Limit:  {limit}")
    print(f"   Offset: {offset}")
    print("-" * 60)

    try:
        history = client.get_history(
            bridge_identifier=bridge_id,
            wallet_address=target_wallet,
            limit=limit,
            offset=offset
        )
        
        if not history:
            print("No history records found.")
            return

        # Helper to format bytes/hex strings
        def format_short(val):
            if not val:
                return "null"
            
            s = str(val)
            # Try to decode Base64 if it looks like one (no 0x prefix, correct length)
            if isinstance(val, str) and not val.startswith("0x"):
                try:
                    # Pad if necessary? Standard Base64 usually padded.
                    decoded = base64.b64decode(val)
                    if len(decoded) > 0:
                        s = "0x" + decoded.hex()
                except binascii.Error:
                    pass # Not base64, treat as string

            if isinstance(val, bytes):
                s = "0x" + val.hex()
            
            if len(s) > 12:
                return s[:10] + "..."
            return s

        # Header
        print(f"{'TYPE':<12} {'AMOUNT':<22} {'FROM':<14} {'TO':<14} {'INT TX':<14} {'EXT TX':<14} {'STATUS':<10} {'BLOCK':<8} {'TIMESTAMP'}")
        print(f"{'-'*12} {'-'*22} {'-'*14} {'-'*14} {'-'*14} {'-'*14} {'-'*10} {'-'*8} {'-'*20}")

        for rec in history:
            # Format timestamp
            bt = rec.get('block_timestamp', 0)
            if isinstance(bt, str):
                bt = int(bt)
            ts = datetime.fromtimestamp(bt, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
            
            # Format fields
            f_from = format_short(rec.get('from_address'))
            f_to = format_short(rec.get('to_address'))
            f_int_tx = format_short(rec.get('internal_tx_hash'))
            f_ext_tx = format_short(rec.get('external_tx_hash'))
            status = rec.get('status', 'unknown')
            
            print(f"{rec['type']:<12} {rec['amount']:<22} {f_from:<14} {f_to:<14} {f_int_tx:<14} {f_ext_tx:<14} {status:<10} {rec['block_height']:<8} {ts}")

        print(f"\n✅ Successfully retrieved {len(history)} records.")
        print("\nNote: 'completed' means credited (deposits) or ready to claim (withdrawals). 'claimed' means withdrawn on Ethereum.")

    except Exception as e:
        print(f"❌ Failed to fetch history: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
