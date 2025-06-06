# TRUF NETWORK (TN) SDK - Python

Python SDK for interacting with the TURF NETWORK, a decentralized platform for publishing, composing, and consuming economic data streams. This SDK uses C bindings to load the TN SDK (Go) library under the hood.

## Support

If you need help, don't hesitate to [open an issue](https://github.com/trufnetwork/sdk-py/issues).

## Requirements
- Go (for compiling C bindings)
- Python 3.8 or later

## Quick Start

### Installation

You can install the SDK as a dependency using pip with a git URL:

```bash
pip install trufnetwork-sdk-py@git+https://github.com/trufnetwork/sdk-py.git@main
```

Alternatively, if you are using a `pyproject.toml` file for dependency management, add the following:
```toml
[project]
dependencies = [
    "trufnetwork-sdk-py@git+https://github.com/trufnetwork/sdk-py.git@main"
]
name = "my-truf-project"
version = "0.1.0"
```

Then install the dependencies:
```bash
pip install .
```

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

### Connect to TRUF.NETWORK

```python
from trufnetwork_sdk_py.client import TNClient

# Connect to mainnet
client = TNClient("https://gateway.mainnet.truf.network", "YOUR_PRIVATE_KEY")
```

### Example: Query AI Index Stream

The following example demonstrates how to query data from the AI Index stream:

```python
from trufnetwork_sdk_py.client import TNClient
from datetime import datetime, timezone

# Connect to TRUF.NETWORK mainnet
client = TNClient("https://gateway.mainnet.truf.network", "YOUR_PRIVATE_KEY")

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

## Advanced Usage: Complex Stream Management

For a comprehensive example demonstrating the full lifecycle of stream management, check out the [Complex Example](./examples/complex_example/README.md). 

This example showcases:
- Generating unique stream IDs
- Creating primitive and composed streams
- Setting stream taxonomy
- Inserting and reading records
- Stream destruction

```python
# Quick preview of complex stream creation
from trufnetwork_sdk_py.client import TNClient, STREAM_TYPE_PRIMITIVE, STREAM_TYPE_COMPOSED
from trufnetwork_sdk_py.utils import generate_stream_id

# Create client
client = TNClient("https://gateway.mainnet.truf.network", "YOUR_PRIVATE_KEY")

# Generate stream IDs
market_stream_id = generate_stream_id("market_performance")
composite_stream_id = generate_stream_id("tech_innovation_index")

# Deploy streams
client.deploy_stream(market_stream_id, STREAM_TYPE_PRIMITIVE)
client.deploy_stream(composite_stream_id, STREAM_TYPE_COMPOSED)

# Set taxonomy and insert records...
```

For the full example, refer to the [Complex Example README](./examples/complex_example/README.md).

## Stream Creation and Management

### Stream Types

TRUF.NETWORK supports two primary stream types:

1. **Primitive Streams**: 
   - Basic time-series data streams
   - Represent single, linear data points
   - Ideal for individual metrics or indicators

2. **Composed Streams**: 
   - Aggregate data from multiple primitive streams
   - Allow weighted combination of different data sources
   - Create complex, derived economic indicators

### Creating Streams

#### Primitive Stream Creation

```python
from trufnetwork_sdk_py.client import TNClient, STREAM_TYPE_PRIMITIVE
from trufnetwork_sdk_py.utils import generate_stream_id

# Initialize client
client = TNClient("http://localhost:8484", "YOUR_PRIVATE_KEY")

# Generate a unique stream ID
market_stream_id = generate_stream_id("market_performance")

# Deploy a primitive stream
client.deploy_stream(market_stream_id, STREAM_TYPE_PRIMITIVE)
```

#### Composed Stream Creation

```python
from trufnetwork_sdk_py.client import TNClient, STREAM_TYPE_COMPOSED
from trufnetwork_sdk_py.utils import generate_stream_id

# Initialize client
client = TNClient("https://gateway.mainnet.truf.network", "YOUR_PRIVATE_KEY")

# Generate a unique stream ID for a composite stream
tech_innovation_index = generate_stream_id("tech_innovation_index")

# Deploy a composed stream
client.deploy_stream(tech_innovation_index, STREAM_TYPE_COMPOSED)
```

### Setting Stream Taxonomy

Composed streams allow you to combine multiple primitive streams with custom weights:

```python
# Assuming you have multiple primitive streams
market_stream_id = generate_stream_id("market_performance")
tech_stream_id = generate_stream_id("tech_sector")
ai_stream_id = generate_stream_id("ai_innovation")

# Set taxonomy for the composed stream
client.set_taxonomy(
    tech_innovation_index, 
    {
        market_stream_id: 0.4,  # 40% weight
        tech_stream_id: 0.3,    # 30% weight
        ai_stream_id: 0.3       # 30% weight
    },
    start_date=current_timestamp
)
```

### Stream Visibility and Access Control

Control who can read or compose your streams:

```python
# Set read visibility (public or private)
client.set_read_visibility(stream_id, "private")

# Allow specific wallets to read a private stream
client.allow_read_wallet(stream_id, "0x1234...")

# Set compose visibility for composed streams
client.set_compose_visibility(stream_id, "private")
```

### Stream Lifecycle Management

```python
# Destroy a stream when no longer needed
client.destroy_stream(stream_id)
```

### Best Practices

- Use `generate_stream_id()` to create unique, deterministic stream IDs
- Always handle stream creation and deletion carefully
- Consider stream visibility and access control
- Use composed streams to create complex, derived economic indicators

For a comprehensive example demonstrating the full stream lifecycle, refer to our [Complex Example](./examples/complex_example/README.md).

## Testing

1. Build the TN Node container image by running the `task single:start` command on `node` repository.
2. Stop the TN Node container if it is running, but do not remove the image as it is needed.
3. Before running the tests, make sure the TN Node is not running. The tests will start a TN Node in the background and stop it after the tests are finished.
4. Then, run the tests with the following command:
```bash
python -m pytest tests/<test_file>.py
```