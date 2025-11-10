"""
Attestation Example - TN Python SDK

This example demonstrates the complete attestation workflow:
1. Connect to TN network
2. Request a signed attestation for query results
3. Wait for validator signature
4. Retrieve signed attestation payload
5. List recent attestations

Prerequisites:
- Local TN node running on http://localhost:8484
- Private key with network_writer role
- Test stream with data
"""

import os
import time
from trufnetwork_sdk_py.client import TNClient

def main():
    # Get configuration from environment
    provider_url = os.getenv("PROVIDER_URL", "http://localhost:8484")
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

        # In a real application, you would:
        # 1. Parse the canonical payload
        # 2. Verify the signature
        # 3. Extract and use the attested data
        # 4. Potentially pass this to an EVM contract
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
