from datetime import datetime, timezone
from trufnetwork_sdk_py.client import TNClient
from trufnetwork_sdk_py.utils import generate_stream_id

TEST_PROVIDER_URL = "http://localhost:8484"
TEST_PRIVATE_KEY = "0000000000000000000000000000000000000000000000000000000000000001"

def main():
    # initialize TN client
    client = TNClient(TEST_PROVIDER_URL, TEST_PRIVATE_KEY)

    # generate example stream id
    primitive_stream_id = generate_stream_id("test_primitive_stream")
    composed_stream_id = generate_stream_id("test_composed_stream")

    # example of deploying a primitive stream
    tx_hash = client.deploy_stream(primitive_stream_id)
    print("primitive stream, transaction hash: ", tx_hash)

    # example of deploying a composed stream
    tx_hash =  client.deploy_stream(composed_stream_id, "composed")
    print("composed stream, transaction hash: ", tx_hash)

    # example of inserting records to primitive stream
    records_to_insert = [
        {"date": date_string_to_unix("2023-01-01"), "value": 10.5},
        {"date": date_string_to_unix("2023-01-02"), "value": 12.2},
        {"date": date_string_to_unix("2023-01-03"), "value": 8.8},
    ]
    insert_tx_hash = client.insert_records(primitive_stream_id, records_to_insert)
    print("insert record, transaction hash: ", insert_tx_hash)

    # get records from streams
    retrieved_records = client.get_records(
        primitive_stream_id, date_from=date_string_to_unix("2023-01-01"), date_to=date_string_to_unix("2023-01-03")
    )
    print("\nRecords:")
    for _, record in enumerate(retrieved_records):
        print("Record Time (UNIX): ", record["EventTime"])
        print("Value: ", record["Value"])

    # example of defining taxonomy for composed stream
    child_streams = {
        primitive_stream_id: 1 # stream_id : weight
    }
    tx_hash = client.set_taxonomy(composed_stream_id, child_streams)
    print("\ndefine taxonomy, transaction hash: ", tx_hash)

    taxonomy = client.describe_taxonomy(composed_stream_id)
    print("\nTaxonomy:")
    print(taxonomy)

    # example of destroying/deleting a stream
    client.destroy_stream(primitive_stream_id)
    client.destroy_stream(composed_stream_id)

def date_string_to_unix(date_str, date_format="%Y-%m-%d"):
    """Convert a date string to a Unix timestamp (integer)."""
    dt = datetime.strptime(date_str, date_format).replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

if __name__ == "__main__":
    main()