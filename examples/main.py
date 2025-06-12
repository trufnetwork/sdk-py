from datetime import datetime, timezone, timedelta
from trufnetwork_sdk_py.client import TNClient

TEST_PROVIDER_URL = "http://localhost:8484" # Replace with mainnet URL https://gateway.mainnet.truf.network if you want to connect to mainnet
TEST_PRIVATE_KEY = "0000000000000000000000000000000000000000000000000000000000000001" # Replace with your private key

def main():
    # initialize TN client
    client = TNClient(TEST_PROVIDER_URL, TEST_PRIVATE_KEY)

    # example of reading AI Index stream
    print("Reading AI Index Stream:")
    ai_stream_id = "stai0000000000000000000000000000"
    ai_data_provider = "0x4710a8d8f0d845da110086812a32de6d90d7ff5c"
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    ai_records = client.get_records(
        stream_id=ai_stream_id,
        data_provider=ai_data_provider,
        date_from=int(week_ago.timestamp()),
        date_to=int(now.timestamp())
    )
    print("AI Index Records:")
    for record in ai_records:
        print(f"Time: {record['EventTime']}, Value: {record['Value']}")

if __name__ == "__main__":
    main()