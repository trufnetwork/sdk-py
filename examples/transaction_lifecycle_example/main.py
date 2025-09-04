#!/usr/bin/env python3
"""
Transaction Lifecycle Best Practices Demo

This example demonstrates proper transaction handling patterns using wait_for_tx
to avoid race conditions and ensure operations complete successfully in sequential workflows.

Key Learning Points:
- Understanding async transaction behavior
- Using wait_for_tx() for transaction confirmation
- Safe patterns for stream deployment and destruction
- Best practices for sequential operations
"""

import time
from datetime import datetime, timezone
from trufnetwork_sdk_py.client import TNClient, STREAM_TYPE_PRIMITIVE
from trufnetwork_sdk_py.utils import generate_stream_id


def deploy_stream_safely(client: TNClient, stream_id: str) -> None:
    """Demonstrates the proper way to deploy a stream with wait_for_tx."""
    print("📝 Deploying stream...")
    
    try:
        # Step 1: Submit deployment transaction
        tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
        print(f"   Deployment submitted: {tx_hash}")
        
        # Step 2: Wait for confirmation
        print("   ⏳ Waiting for deployment to be mined...")
        client.wait_for_tx(tx_hash)
        print("✅ Stream deployed and confirmed on-chain")
        
    except Exception as e:
        raise Exception(f"Failed to deploy stream: {e}")


def destroy_stream_safely(client: TNClient, stream_id: str) -> None:
    """Demonstrates the proper way to destroy a stream with wait_for_tx."""
    print("🗑️  Destroying stream...")
    
    try:
        # Step 1: Submit destruction transaction
        tx_hash = client.destroy_stream(stream_id)
        print(f"   Destruction submitted: {tx_hash}")
        
        # Step 2: Wait for confirmation
        print("   ⏳ Waiting for destruction to be mined...")
        client.wait_for_tx(tx_hash)
        print("✅ Stream destroyed and confirmed on-chain")
        
    except Exception as e:
        raise Exception(f"Failed to destroy stream: {e}")


def main():
    """Main demonstration of transaction lifecycle best practices."""
    
    # Setup client (using placeholder private key - replace with your own)
    endpoint = "https://gateway.mainnet.truf.network"
    private_key = "<YOUR_PRIVATE_KEY_HERE>"  # Replace with your private key
    
    try:
        client = TNClient(endpoint, private_key)
    except Exception as e:
        print(f"❌ Failed to create TN client: {e}")
        return
    
    # Generate unique stream ID
    timestamp = int(time.time())
    stream_id = generate_stream_id("sttest00000000000000000000000000")
    
    print("🔄 Transaction Lifecycle Best Practices Demo")
    print("=" * 50)
    print(f"Stream ID: {stream_id}")

    try:
        # Example 1: Proper stream deployment with wait_for_tx
        print("📋 EXAMPLE 1: Safe Stream Deployment")
        print("-" * 40)
        deploy_stream_safely(client, stream_id)
        print()
        
        # Example 2: Record insertion (has built-in confirmation)
        print("📋 EXAMPLE 2: Record Insertion")
        print("-" * 40)
        
        # Insert test records
        test_records = [
            {"date": int(time.time()), "value": 123.45},
            {"date": int(time.time()) + 1, "value": 456.78},
            {"date": int(time.time()) + 2, "value": 789.01}
        ]
        
        for i, record in enumerate(test_records, 1):
            print(f"📝 Inserting record {i}...")
            try:
                client.insert_record(stream_id, record)
                print(f"   ✅ Record {i} inserted: {record['value']}")
            except Exception as e:
                print(f"   ❌ Failed to insert record {i}: {e}")
        print()
        
        # Example 3: Verify records are accessible
        print("📋 EXAMPLE 3: Verify Records After Insertion")
        print("-" * 40)
        try:
            # Get records with date range
            date_from = int(time.time()) - 10
            date_to = int(time.time()) + 10
            
            response = client.get_records(
                stream_id=stream_id,
                data_provider=client.get_current_account(),
                date_from=date_from,
                date_to=date_to,
                use_cache=False
            )
            
            # Extract the actual records from the CacheAwareResponse
            records = response.data
            
            print(f"✅ Retrieved {len(records)} records from stream:")
            for i, record in enumerate(records, 1):
                # EventTime is returned as string, convert to int first
                timestamp = int(record["EventTime"])
                date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                print(f"   Record {i}: {record['Value']} (Time: {date.strftime('%Y-%m-%d %H:%M:%S')})")
                
        except Exception as e:
            print(f"❌ Failed to retrieve records: {e}")
        print()
        
        # Example 4: Safe stream destruction with wait_for_tx
        print("📋 EXAMPLE 4: Safe Stream Destruction with Verification")
        print("-" * 50)
        destroy_stream_safely(client, stream_id)
        
        # Verify destruction by trying to insert (should fail)
        print("🧪 Testing insertion after destruction...")
        try:
            client.insert_record(stream_id, {"date": int(time.time()) + 5, "value": 999.99})
            print("⚠️  WARNING: Insertion succeeded after destruction!")
            print("   This indicates a race condition - stream destruction wasn't complete")
        except Exception as e:
            print("✅ PERFECT: Insertion failed as expected after destruction")
            print(f"   Error: {e}")
        
        # Try to retrieve records (should also fail)
        print("🧪 Testing record retrieval after destruction...")
        try:
            response = client.get_records(
                stream_id=stream_id,
                data_provider=client.get_current_account(),
                date_from=date_from,
                date_to=date_to,
                use_cache=False
            )
            records = response.data
            print("⚠️  WARNING: Records still accessible after destruction")
        except Exception as e:
            print("✅ PERFECT: Record retrieval failed as expected")
            print(f"   Error: {e}")
        
        print("\n" + "=" * 60)
        print("📚 KEY TAKEAWAYS:")
        print("=" * 60)
        print("✅ Use wait_for_tx() for DeployStream and DestroyStream")
        print("✅ insert_record() has built-in confirmation for data integrity")
        print("✅ Always use try/catch blocks for proper error handling")
        print("✅ Verify operations completed before proceeding with dependent actions")
        print("⚠️  Async operations can cause race conditions in sequential workflows")
    except Exception as e:
        print(f"❌ Demo failed: {e}")


if __name__ == "__main__":
    main()