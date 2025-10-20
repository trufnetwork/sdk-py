# TRUF NETWORK (TN) SDK - Python

Python SDK for interacting with the [TRUF.NETWORK](https://truf.network), a decentralized platform for publishing, composing, and consuming economic data streams. This SDK uses C bindings to load the [TN SDK (Go)](https://github.com/trufnetwork/sdk-go) library under the hood.

## Support

If you need help, don't hesitate to [open an issue](https://github.com/trufnetwork/sdk-py/issues).

## Requirements

- Go (for compiling C bindings)
- Python 3.8 or later

## Quick Start

### Installation

**To install the latest version:**

1. Visit the [**releases page**](https://github.com/trufnetwork/sdk-py/releases/latest)
2. Download the wheel file (`.whl`) for your platform:
   - **Linux**: `*manylinux*.whl`
   - **macOS**: `*macosx*.whl`
3. Install using pip:
   ```bash
   pip install /path/to/downloaded/wheel.whl
   ```

   Or install directly from the URL (right-click the wheel file → copy link):
   ```bash
   pip install https://github.com/trufnetwork/sdk-py/releases/download/vX.X.X/trufnetwork_sdk_py-X.X.X-....whl
   ```

**Alternative: Install from source** (always gets the latest from the `main` branch):

If you are using a `pyproject.toml` file for dependency management, add the following:

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

> **Note:** This approach requires Go to be installed for compiling C bindings during installation.

## Development

It is recommended to use a virtual environment to develop the SDK.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ."[dev]"
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

To run the SDK against a local node, see [Local Node Testing and Development](#local-node-testing-and-development).

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

## Understanding Transaction Lifecycle

**IMPORTANT:** All transaction operations return success when transactions enter the mempool, NOT when they are executed on-chain. This async behavior can cause race conditions if not handled properly.

### The Problem: Race Conditions in Sequential Operations

```python
# ⚠️ DANGEROUS: This can fail due to race conditions
from trufnetwork_sdk_py.client import TNClient, STREAM_TYPE_PRIMITIVE
from trufnetwork_sdk_py.utils import generate_stream_id

client = TNClient("https://gateway.mainnet.truf.network", "YOUR_PRIVATE_KEY")
stream_id = generate_stream_id("my_stream")

# Deploy stream - returns immediately when submitted to mempool
client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)

# Insert record - might fail if deployment isn't complete on-chain yet
client.insert_record(stream_id, {"date": 1725456000, "value": 123.45})  # Race condition!
```

### The Solution: Use `wait_for_tx` for Confirmation

```python
from trufnetwork_sdk_py.client import TNClient, STREAM_TYPE_PRIMITIVE
from trufnetwork_sdk_py.utils import generate_stream_id

client = TNClient("https://gateway.mainnet.truf.network", "YOUR_PRIVATE_KEY")
stream_id = generate_stream_id("my_stream")

# ✅ SAFE: Deploy and wait for confirmation
tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
client.wait_for_tx(tx_hash)  # Wait for on-chain confirmation

# ✅ SAFE: Now insertion will succeed
client.insert_record(stream_id, {"date": 1725456000, "value": 123.45})

# ✅ SAFE: Destroy and wait for confirmation before cleanup
tx_hash = client.destroy_stream(stream_id)
client.wait_for_tx(tx_hash)  # Wait for on-chain confirmation
```

### Best Practices

1. **Use `wait_for_tx()` for lifecycle operations** (deploy/destroy)
2. **Check for errors** and handle them appropriately
3. **Test sequential workflows** to catch race conditions
4. **Understand mempool vs on-chain** completion

```python
try:
    tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
    client.wait_for_tx(tx_hash)
    print("✅ Stream deployed successfully")
except Exception as e:
    print(f"❌ Deployment failed: {e}")
```

For a comprehensive example demonstrating safe transaction patterns, see the [Transaction Lifecycle Example](./examples/transaction_lifecycle_example/).

For more comprehensive examples, please see the following guides:

- **[Basic Example: Reading a Stream](./examples/README.md)**: Learn how to connect and read records from an existing stream.
- **[Advanced Example: Full Stream Lifecycle](./examples/complex_example/README.md)**: A comprehensive walkthrough of creating, managing, and destroying primitive and composed streams.

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

## Role-based Permissions

> **Heads-up:** Deploying streams requires the `system:network_writer` role; reading public streams is permissionless.

Don't have the role? Contact the TRUF.NETWORK team to get whitelisted.

Check your role status using the **Role Management** APIs in the [API Reference](./docs/api-reference.md#role-management).

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

# Initialize client (e.g. connected to a local node)
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

# Get taxonomy information for the composed stream
taxonomy = client.describe_taxonomy(tech_innovation_index)
if taxonomy:
    print(f"Stream: {taxonomy['stream_id']}")
    for child in taxonomy['child_streams']:
        print(f"  Child: {child.stream['stream_id']}, Weight: {child.weight}")
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

## Quick Reference

### Common Operations

| Operation | Method |
|-----------|--------|
| Deploy primitive stream | `client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)` |
| Deploy composed stream | `client.deploy_stream(stream_id, STREAM_TYPE_COMPOSED)` |
| Insert records | `client.insert_record(stream_id, {"date": timestamp, "value": value})` |
| Get stream data | `client.get_records(stream_id, date_from=from_ts, date_to=to_ts)` |
| Set stream taxonomy | `client.set_taxonomy(stream_id, {child_id: weight}, start_date)` |
| Get stream taxonomy | `client.describe_taxonomy(stream_id, latest_version=True)` |
| Destroy stream | `client.destroy_stream(stream_id)` |

### Key Constants

- `STREAM_TYPE_PRIMITIVE` - Raw data streams
- `STREAM_TYPE_COMPOSED` - Aggregated streams with taxonomy
- `TaxonomyDetails` - Taxonomy information with child streams and weights

## Local Node Testing and Development

This section describes how to set up a local development environment, including running a local node for testing and running the SDK's test suite.

### Setting Up a Local Node for Development

For development and testing, you can run a local TRUF.NETWORK node. This will start a node with a fresh, empty database.

**Prerequisites:**

- Docker
- Docker Compose
- Git

**Steps:**

1.  **Clone the TN Node Repository:**

    ```bash
    git clone https://github.com/trufnetwork/node.git
    cd node
    ```

2.  **Start the Local Node:**

    ```bash
    # Start the node in development mode
    task single:start
    ```

    When your local node is running, you can connect to it from the SDK by initializing the `TNClient` with the local node's URL, which is typically `http://localhost:8484`.

    > **Note:** Note: Setting up a local node as described above will initialize an empty database. This setup is primarily for testing the technology or development purposes. If you are a node operator and wish to sync with the TRUF.NETWORK to access real data, please follow the [Node Operator Guide](https://github.com/trufnetwork/node/blob/main/docs/node-operator-guide.md#7-verify-node-synchronization) for instructions on connecting to the network and syncing data.

3.  **Connecting the SDK to the Local Node:**

    When your local node is running, initialize the `TNClient` with the local node's URL:

    ```python
    from trufnetwork_sdk_py.client import TNClient

    # Connect to a local node
    client = TNClient("http://localhost:8484", "YOUR_PRIVATE_KEY")
    ```

### Verifying Node Synchronization

When running a local node connected to the network (e.g., as a node operator), it's crucial to ensure it's fully synchronized before querying data. Use the following command to check node status:

```bash
kwild admin status
```

> **Note:** This command is not needed if you are running a local setup for development without connecting to the main network.

### Running the SDK Test Suite

1.  First, ensure you have a local node image available. Follow the steps in "Setting Up a Local Node" to build and start the node once.
2.  Stop the TN Node container if it is running, but do not remove the Docker image as it is needed for the tests.
3.  Before running the tests, make sure the TN Node is not running.
    The tests will start a TN Node in the background and stop it after
    the tests are finished.
4.  Run the tests using `pytest`:
    ```bash
    # Run a specific test file
    python -m pytest tests/<test_file>.py
    ```

## Resources

- [Node Repository](https://github.com/trufnetwork/node): For building and running a local node for testing.
- [Basic Example: Reading a Stream](./examples/README.md): Learn how to connect and read records from an existing stream.
- [Advanced Example: Full Stream Lifecycle](./examples/complex_example/README.md): A comprehensive walkthrough of the entire stream lifecycle.
- **[API Reference](./docs/api-reference.md)**: Detailed documentation of the SDK's public API.
