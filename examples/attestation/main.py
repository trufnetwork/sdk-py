"""
Attestation Example - TN Python SDK

This example demonstrates the complete attestation workflow:
1. Connect to TN network
2. Request a signed attestation for query results
3. Wait for validator signature
4. Retrieve signed attestation payload
5. Verify signature and extract validator address
6. Parse the attestation payload
7. Display attested query results
8. List recent attestations

⚠️  IMPORTANT: This example connects to the PRODUCTION TRUF network by default.
Attestation requests incur real costs (40 TRUF flat fee ≈ $0.47 USD).
To use a different network, set the PROVIDER_URL environment variable.

Prerequisites:
- Access to TN network (defaults to https://gateway.mainnet.truf.network)
- Private key with network_writer role
- Test stream with data
"""

import os
import time
from trufnetwork_sdk_py.client import TNClient

def main():
    # Get configuration from environment
    # WARNING: Defaults to mainnet - attestations will incur real costs!
    # Set PROVIDER_URL env var to use a different network (e.g., local node)
    provider_url = os.getenv("PROVIDER_URL", "https://gateway.mainnet.truf.network")
    private_key = os.getenv("PRIVATE_KEY")

    if not private_key:
        print("Error: PRIVATE_KEY environment variable is required")
        return

    # Create client
    print(f"Connecting to TN network at {provider_url}")
    client = TNClient(provider_url, private_key)

    my_address = client.get_current_account()
    print(f"Using address: {my_address}\n")

    # Configuration for AI Index stream
    data_provider = "0x4710a8d8f0d845da110086812a32de6d90d7ff5c"
    stream_id = "stai0000000000000000000000000000"

    # Prepare query parameters (last 7 days)
    now = int(time.time())
    week_ago = now - (7 * 24 * 60 * 60)

    # Arguments for get_record action
    args = [
        data_provider,
        stream_id,
        week_ago,
        now,
        None,   # frozen_at
        False,  # use_cache (will be forced to false by node for attestation)
    ]

    print("=== Requesting Attestation ===")
    print(f"Data Provider: {data_provider}")
    print(f"Stream ID: {stream_id}")
    print(f"Time Range: {week_ago} to {now}\n")

    # Request attestation
    try:
        request_tx_id = client.request_attestation(
            data_provider=data_provider,
            stream_id=stream_id,
            action_name="get_record",
            args=args,
            encrypt_sig=False,
            max_fee="100000000000000000000",  # 100 TRUF (100 * 10^18)
            wait=True,
        )

        print(f"✓ Attestation requested successfully!")
        print(f"Request TX ID: {request_tx_id}\n")

    except Exception as e:
        print(f"✗ Failed to request attestation: {e}")
        return

    # Wait for attestation to be signed
    print("=== Retrieving Signed Attestation ===")
    print("Polling for signed attestation (max 30 seconds)...")

    max_attempts = 15
    payload = None

    for attempt in range(max_attempts):
        try:
            payload = client.get_signed_attestation(request_tx_id)
            if len(payload) > 65:  # Has signature
                break
        except Exception:
            pass

        print(f"  Attempt {attempt + 1}/{max_attempts}...")
        time.sleep(2)

    if payload and len(payload) > 65:
        print(f"\n✓ Retrieved signed attestation!")
        print(f"Payload size: {len(payload)} bytes")
        print(f"Payload (hex): {payload[:64].hex()}...\n")

        # Verify signature and extract validator address
        print("=== Verifying Signature ===")
        try:
            verification = client.verify_attestation_signature(payload)
            print(f"✓ Validator Address: {verification['validator_address']}")
            print("  This address should be used in your smart contract's verify() function\n")
        except Exception as e:
            print(f"✗ Failed to verify signature: {e}\n")
            verification = None

        # Parse the attestation payload
        if verification:
            print("=== Parsing Attestation Payload ===")
            try:
                parsed = client.parse_attestation_payload(verification['canonical_payload'])

                print(f"\n📋 Attestation Details:")
                print(f"   Version: {parsed.version}")
                print(f"   Algorithm: {parsed.algorithm} (0 = secp256k1)")
                print(f"   Block Height: {parsed.block_height}")
                print(f"   Data Provider: {parsed.data_provider}")
                print(f"   Stream ID: {parsed.stream_id}")
                print(f"   Action ID: {parsed.action_id}")

                print(f"\n📊 Attested Query Result (from get_record):")
                if len(parsed.result) == 0:
                    print("   No records found")
                else:
                    print(f"   Found {len(parsed.result)} row(s):\n")
                    for i, row in enumerate(parsed.result[:5], 1):  # Show first 5
                        if 'values' in row and len(row['values']) >= 2:
                            timestamp, value = row['values'][0], row['values'][1]
                            print(f"   Row {i}: Timestamp={timestamp}, Value={value}")
                        else:
                            print(f"   Row {i}: {row.get('values', [])}")

                    if len(parsed.result) > 5:
                        print(f"   ... and {len(parsed.result) - 5} more")

                print("\n   💡 How to use this payload:")
                print("   1. Send this payload to your EVM smart contract")
                print("   2. The contract can verify the signature using ecrecover")
                print("   3. Parse the payload to extract the attested query results")
                print("   4. Use the verified data in your on-chain logic\n")

            except Exception as e:
                print(f"✗ Failed to parse payload: {e}\n")
    else:
        print("\n⚠ Warning: Timed out waiting for signature")
        print("The attestation may still be processing. Try checking again later.\n")

    # List recent attestations
    print("=== Listing My Recent Attestations ===")

    try:
        my_address_bytes = bytes.fromhex(my_address[2:])
        attestations = client.list_attestations(
            requester=my_address_bytes,
            limit=10,
            order_by="created_height desc",
        )

        print(f"Found {len(attestations)} recent attestations:")

        for i, att in enumerate(attestations, 1):
            status = "unsigned"
            if att["signed_height"] is not None:
                status = f"signed at height {att['signed_height']}"

            print(f"{i}. TX: {att['request_tx_id']}")
            print(f"   Created: height {att['created_height']}, Status: {status}")

    except Exception as e:
        print(f"Warning: Failed to list attestations: {e}")

    print("\n=== Example Complete ===")
    print("✓ Successfully demonstrated attestation workflow")

if __name__ == "__main__":
    main()
