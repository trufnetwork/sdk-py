import os
from datetime import datetime, timezone
from trufnetwork_sdk_py.client import TNClient, STREAM_TYPE_PRIMITIVE, STREAM_TYPE_COMPOSED
from trufnetwork_sdk_py.utils import generate_stream_id

def create_example_streams(client):
    """
    Demonstrates creating primitive and composed streams with full lifecycle management.
    
    This example shows:
    1. Generating unique stream IDs
    2. Creating primitive streams
    3. Creating a composed stream
    4. Setting taxonomy for the composed stream
    5. Inserting records into primitive streams
    6. Reading records from streams
    7. Cleaning up (destroying) streams
    """
    # Generate unique stream IDs
    market_stream_id = generate_stream_id("market_performance")
    tech_stream_id = generate_stream_id("tech_sector")
    ai_stream_id = generate_stream_id("ai_innovation")
    composite_stream_id = generate_stream_id("tech_innovation_index")

    print("🚀 Stream Creation Process")
    
    # Preliminary cleanup: Attempt to destroy streams if they exist
    print("\n0. Preliminary Cleanup:")
    stream_ids_to_cleanup = [
        market_stream_id, 
        tech_stream_id, 
        ai_stream_id, 
        composite_stream_id
    ]
    
    for stream_id in stream_ids_to_cleanup:
        try:
            destroy_tx = client.destroy_stream(stream_id)
            client.wait_for_tx(destroy_tx)
            print(f"   Destroyed existing stream: {stream_id}")
        except Exception as e:
            print(f"   No existing stream to destroy or error: {stream_id}")
            print(f"   Error details: {e}")
    
    # Deploy primitive streams
    print("\n1. Deploying Primitive Streams:")
    market_tx = client.deploy_stream(market_stream_id, STREAM_TYPE_PRIMITIVE)
    client.wait_for_tx(market_tx)
    print(f"   Market Performance Stream: {market_stream_id}")
    
    tech_tx = client.deploy_stream(tech_stream_id, STREAM_TYPE_PRIMITIVE)
    client.wait_for_tx(tech_tx)
    print(f"   Tech Sector Stream: {tech_stream_id}")
    
    ai_tx = client.deploy_stream(ai_stream_id, STREAM_TYPE_PRIMITIVE)
    client.wait_for_tx(ai_tx)
    print(f"   AI Innovation Stream: {ai_stream_id}")

    # Insert records into primitive streams
    print("\n2. Inserting Records into Primitive Streams:")
    current_time = int(datetime.now(timezone.utc).timestamp())
    
    market_records = [
        {"date": current_time - 86400, "value": 100.5},
        {"date": current_time, "value": 102.3}
    ]
    market_insert_tx = client.insert_records(market_stream_id, market_records)
    client.wait_for_tx(market_insert_tx)
    print(f"   Inserted {len(market_records)} records into Market Performance Stream")
    
    tech_records = [
        {"date": current_time - 86400, "value": 75.2},
        {"date": current_time, "value": 78.6}
    ]
    tech_insert_tx = client.insert_records(tech_stream_id, tech_records)
    client.wait_for_tx(tech_insert_tx)
    print(f"   Inserted {len(tech_records)} records into Tech Sector Stream")
    
    ai_records = [
        {"date": current_time - 86400, "value": 50.1},
        {"date": current_time, "value": 55.7}
    ]
    ai_insert_tx = client.insert_records(ai_stream_id, ai_records)
    client.wait_for_tx(ai_insert_tx)
    print(f"   Inserted {len(ai_records)} records into AI Innovation Stream")

    # Deploy composed stream
    print("\n3. Deploying Composed Stream:")
    composite_tx = client.deploy_stream(composite_stream_id, STREAM_TYPE_COMPOSED)
    client.wait_for_tx(composite_tx)
    print(f"   Tech Innovation Index Stream: {composite_stream_id}")

    # Set taxonomy for composed stream
    print("\n4. Setting Taxonomy for Composed Stream:")
    taxonomy_tx = client.set_taxonomy(
        composite_stream_id, 
        {
            market_stream_id: 0.4,  # 40% weight
            tech_stream_id: 0.3,    # 30% weight
            ai_stream_id: 0.3       # 30% weight
        }
    )
    client.wait_for_tx(taxonomy_tx)
    print("   Taxonomy set successfully")

    # Read records from streams
    print("\n5. Reading Stream Records:")
    market_records_read = client.get_records(market_stream_id)
    print(f"   Market Performance Records: {market_records_read}")
    
    composite_records = client.get_records(composite_stream_id)
    print(f"   Composite Stream Records: {composite_records}")

    # Optional: Describe taxonomy to verify
    print("\n6. Describing Taxonomy:")
    taxonomy_details = client.describe_taxonomy(composite_stream_id)
    print(f"   Taxonomy Details: {taxonomy_details}")

    # Stream cleanup
    print("\n7. Cleaning Up Streams:")
    market_destroy_tx = client.destroy_stream(market_stream_id)
    client.wait_for_tx(market_destroy_tx)
    
    tech_destroy_tx = client.destroy_stream(tech_stream_id)
    client.wait_for_tx(tech_destroy_tx)
    
    ai_destroy_tx = client.destroy_stream(ai_stream_id)
    client.wait_for_tx(ai_destroy_tx)
    
    composite_destroy_tx = client.destroy_stream(composite_stream_id)
    client.wait_for_tx(composite_destroy_tx)
    
    print("   All streams destroyed successfully")

def main():
    client = TNClient(
        "http://localhost:8484", # Use the mainnet gateway if needed
        os.getenv("TRUF_PRIVATE_KEY", "0000000000000000000000000000000000000000000000000000000000000001") # Use the private key of the account you want to use
    )
    
    create_example_streams(client)

if __name__ == "__main__":
    main() 