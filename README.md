# Truf Network (TN) SDK - Python

Python SDK for interacting with the Truf Network. Uses C bindings to load the TN SDK (Go) library under the hood.

## Requirements
- Go
- Python

## Development

It is recommended to use a virtual environment to develop the SDK.
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### Recompile the C bindings

To recompile the C bindings, run the following command:
```bash
make
```

## Usage

### Connect to Truf Network

```python
from trufnetwork_sdk_py.client import TNClient

# Connect to mainnet
client = TNClient("https://gateway.infra.truf.network", "YOUR_PRIVATE_KEY")
```

### Example: Query AI Index Stream

The following example demonstrates how to query data from the AI Index stream:

```python
from trufnetwork_sdk_py.client import TNClient
from datetime import datetime, timezone

# Connect to Truf Network mainnet
client = TNClient("https://gateway.infra.truf.network", "YOUR_PRIVATE_KEY")

# AI Index stream details from explorer
stream_id = "st527bf3897aa3d6f5ae15a0af846db6"
data_provider = "0x4710a8d8f0d845da110086812a32de6d90d7ff5c"

# Convert date strings to Unix timestamps
def date_to_unix(date_str, format="%Y-%m-%d"):
    dt = datetime.strptime(date_str, format).replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

# Get records for last 30 days (assuming today is 2025-02-09)
records = client.get_records(
    stream_id=stream_id,
    data_provider=data_provider,
    date_from=date_to_unix("2025-01-10"),
    date_to=date_to_unix("2025-02-09")
)

# Display the records
for record in records:
    date = datetime.fromtimestamp(record["EventTime"], tz=timezone.utc)
    print(f"Date: {date.strftime('%Y-%m-%d')}, Value: {record['Value']}")
```

For more examples, check the [examples](./examples/main.py).

## Testing

1. Build the TN Node container image by running the `task single:start` command on `node` repository.
2. Stop the TN Node container if it is running, but do not remove the image as it is needed.
3. Before running the tests, make sure the TN Node is not running. The tests will start a TN Node in the background and stop it after the tests are finished.
4. Then, run the tests with the following command:
```bash
python -m pytest tests/<test_file>.py
```