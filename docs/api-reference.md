# API Reference

## Overview

The TRUF.NETWORK Python SDK provides a comprehensive interface for stream management, offering powerful primitives for data streaming, composition, and on-chain interactions.

## Client Initialization

### `TNClient(endpoint: str, private_key: str)`
Initializes a TrufNetwork client with specified configuration.

#### Parameters
- `endpoint: str` - RPC endpoint URL
- `private_key: str` - Ethereum private key (securely managed)

#### Example
```python
from trufnetwork_sdk_py.client import TNClient

client = TNClient(
    "http://localhost:8484", 
    "YOUR_PRIVATE_KEY"
)
```

## Stream Identification

### `generate_stream_id(name: str) -> str`
Generates a deterministic, unique stream identifier.

#### Parameters
- `name: str` - Descriptive name for the stream

#### Returns
- `str` - Unique stream identifier

#### Example
```python
from trufnetwork_sdk_py.utils import generate_stream_id

market_index_stream_id = generate_stream_id('market_index')
```

## Stream Deployment

> **Note: Stream Deployment Permissions**
>
> Deploying new streams on the TRUF.NETWORK requires the `system:network_writer` role.
>
> If you're interested in deploying streams, please contact the TRUF.NETWORK team for assistance.

### `client.deploy_stream(stream_id: str, stream_type: str) -> str`
Deploys a new stream to the TRUF.NETWORK.

#### Parameters
- `stream_id: str` - Unique stream identifier
- `stream_type: str` - Stream type (STREAM_TYPE_PRIMITIVE or STREAM_TYPE_COMPOSED)

#### Returns
- `str` - Transaction hash of the deployment

#### Example
```python
from trufnetwork_sdk_py.client import STREAM_TYPE_PRIMITIVE

tx_hash = client.deploy_stream(market_index_stream_id, STREAM_TYPE_PRIMITIVE)
```

## Stream Destruction

### `client.destroy_stream(stream_id: str) -> str`
Permanently removes a stream from the network.

#### Parameters
- `stream_id: str` - Stream identifier to destroy

#### Returns
- `str` - Transaction hash of the destruction

#### Example
```python
tx_hash = client.destroy_stream(market_index_stream_id)
```

## Transaction Management

### `client.wait_for_tx(tx_hash: str) -> None`
Waits for a transaction to be confirmed on-chain given its hash.

#### Parameters
- `tx_hash: str` - Transaction hash to wait for

#### Returns
- `None` - Method returns when transaction is confirmed

#### Raises
- `Exception` - If transaction fails to execute on-chain (permission errors, invalid input, logic errors)

#### Example
```python
# Deploy stream and wait for confirmation
tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
client.wait_for_tx(tx_hash)  # Wait for on-chain confirmation

# Now safe to proceed with dependent operations
client.insert_record(stream_id, {"date": timestamp, "value": 123.45})
```

### Understanding Transaction Lifecycle

**IMPORTANT:** By default, stream operations return when transactions are submitted to the mempool, NOT when they're executed on-chain. This can cause race conditions in sequential workflows.

#### Best Practices

1. **Use `wait_for_tx()` for lifecycle operations**: Always wait for deployment and destruction confirmation.

```python
# Safe deployment pattern
tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
client.wait_for_tx(tx_hash)  # Wait for confirmation

# Safe destruction pattern  
tx_hash = client.destroy_stream(stream_id)
client.wait_for_tx(tx_hash)  # Wait for confirmation
```

2. **Proper error handling**: Always wrap transaction calls in try/catch blocks.

```python
try:
    tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
    client.wait_for_tx(tx_hash)
    print("✅ Stream deployed successfully")
except Exception as e:
    print(f"❌ Deployment failed: {e}")
```

3. **Sequential workflow patterns**: For operations that must happen in order.

```python
# Safe deployment → insertion → destruction workflow
tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
client.wait_for_tx(tx_hash)
client.insert_record(stream_id, {"date": timestamp, "value": 123.45})
tx_hash = client.destroy_stream(stream_id)
client.wait_for_tx(tx_hash)
```

For a comprehensive example demonstrating these patterns, see the [Transaction Lifecycle Example](../examples/transaction_lifecycle_example/).

## Record Insertion

### `client.insert_record(stream_id: str, record: Dict[str, Union[int, float]]) -> str`
Inserts a single record into a stream.

#### Parameters
- `stream_id: str` - Target stream identifier
- `record: Dict` 
  - `date: int` - UNIX timestamp
  - `value: float` - Record value

#### Returns
- `str` - Transaction hash of the record insertion

#### Example
```python
tx_hash = client.insert_record(
    stream_id, 
    {"date": int(datetime.now().timestamp()), "value": 100.50}
)
```

### `client.insert_records(stream_id: str, records: List[Dict[str, Union[int, float]]]) -> str`
Batch inserts multiple records for efficiency.

#### Parameters
- `stream_id: str` - Target stream identifier
- `records: List[Dict]` - List of records with `date` and `value`

#### Returns
- `str` - Transaction hash of the batch insertion

#### Example
```python
tx_hash = client.insert_records(stream_id, [
    {"date": timestamp1, "value": 150.25},
    {"date": timestamp2, "value": 75.10}
])
```

### `client.batch_insert_records(batches: List[RecordBatch], wait: bool = True) -> str`
Insert multiple batches of records into different streams in a single transaction. This is the most efficient way to insert large amounts of data.

#### Parameters
- `batches: List[RecordBatch]` - List of batch objects, each containing:
  - `stream_id: str` - Target stream identifier
  - `inputs: List[Record]` - List of records with `date` and `value`
- `wait: bool` - Whether to wait for transaction confirmation (default: True)

#### Returns
- `str` - Transaction hash for all inserted records

#### Example
```python
batches = [
    {
        "stream_id": "stream1",
        "inputs": [
            {"date": timestamp1, "value": 100.0},
            {"date": timestamp2, "value": 200.0}
        ]
    },
    {
        "stream_id": "stream2", 
        "inputs": [
            {"date": timestamp1, "value": 50.0}
        ]
    }
]
tx_hash = client.batch_insert_records(batches)
```

## Stream Querying

### `client.get_records(stream_id: str, **kwargs) -> List[Dict]`
Retrieves records from a stream with advanced filtering.

#### Parameters
- `stream_id: str` - Target stream
- `data_provider: Optional[str]` - Specific data provider
- `date_from: Optional[int]` - Start timestamp
- `date_to: Optional[int]` - End timestamp
- `frozen_at: Optional[int]` - Timestamp for frozen state
- `base_date: Optional[int]` - Base time for relative queries

#### Returns
- `List[Dict]` - Retrieved stream records

#### Example
```python
records = client.get_records(
    stream_id,
    date_from=int(datetime.now().timestamp()) - 86400,  # Last 24 hours
    date_to=int(datetime.now().timestamp())
)
```

> **What does `get_records` actually return?**  
> • **Primitive streams** – the raw numeric values recorded at each `date`.  When you request an interval (`date_from`/`date_to`) the function also injects the **last value _before_ the range** so that charts can be plotted without breaks.  
> • **Composed streams** – a synthetic value calculated on-the-fly by recursively aggregating the weighted values of *all* child primitives for every point in time.  The same gap-filling logic is applied so you always get a continuous series.  
> All permission checks (`read`, `compose`) are enforced server-side – if you don't have access the call fails with an explicit error.

### `client.get_first_record(stream_id: str, **kwargs) -> StreamRecord | None`
Get the first record of a stream after a given date. Supports cache-aware responses.

#### Parameters
- `stream_id: str` - Target stream
- `data_provider: Optional[str]` - Specific data provider
- `after_date: Optional[int]` - Find first record after this timestamp
- `frozen_at: Optional[int]` - Timestamp for frozen state
- `use_cache: Optional[bool]` - Enable cache-aware response format

#### Returns
- `StreamRecord | None` or `CacheAwareResponse[StreamRecord | None]` - First record found, or cache-aware response if `use_cache` is specified

#### Example
```python
# Legacy format (deprecated)
first_record = client.get_first_record(stream_id, after_date=timestamp)

# Cache-aware format
response = client.get_first_record(stream_id, after_date=timestamp, use_cache=True)
print(f"Record: {response.data}, Cache hit: {response.cache.hit}")
```

### `client.get_type(stream_id: str, data_provider: Optional[str] = None) -> str`
Get the type of a stream (primitive or composed).

#### Parameters
- `stream_id: str` - Stream identifier
- `data_provider: Optional[str]` - Specific data provider

#### Returns
- `str` - Stream type ("primitive" or "composed")

#### Example
```python
stream_type = client.get_type(stream_id)
print(f"Stream type: {stream_type}")
```

### `client.get_index(stream_id: str, **kwargs) -> List[Dict]`
Returns a **rebased index** of the stream where the value at `base_date` (defaults to the metadata key `default_base_time`) is normalised to **100**.

Mathematically:

```
index(t) = 100 × value(t) / value(baseDate)
```

`get_index` supports the same filtering arguments as `get_records` (`date_from`, `date_to`, `frozen_at`, etc.) and applies *exactly* the same gap-filling and permission rules – the only difference is the final normalisation step.

Typical use-cases include CPI or stock-index style charts where you want to visualise growth relative to a fixed point in time.

#### Additional Parameters
- `base_date: Optional[int]` – Unix timestamp to use as the rebasing point.  If omitted the server falls back to the stream's `default_base_time` metadata or, if that is missing, the first ever record.

#### Example
```python
indexed = client.get_index(
    stream_id,
    date_from=int(datetime.now().timestamp()) - 31_536_000,  # Last 12 months
    date_to=int(datetime.now().timestamp()),
    base_date=int(datetime.now().timestamp()) - 31_536_000    # Re-base 1y ago
)
```

### `client.get_index_change(stream_id: str, time_interval: int, **kwargs) -> List[Dict]`
Computes the **percentage change** of the **index** over a fixed time interval.  Internally the SDK:
1. Calls `get_index` to obtain the rebased series.
2. For every returned row at timestamp `t`, finds the closest index value *at or before* `t – time_interval`.
3. Emits the delta expressed in percent.

Formula:

```
Δindex(t) = ( index(t) − index(t − Δ) ) / index(t − Δ) × 100
```
where `Δ = time_interval` (seconds).

Only rows for which a matching *previous* value exists **and is non-zero** are returned, ensuring the output is well-defined.

#### Required Parameter
- `time_interval: int` – Interval in **seconds** used for the delta computation.  Common values: 86 400 (day-over-day), 31 536 000 (year-over-year).

#### Example – Year-on-Year (%) change
```python
yoy = client.get_index_change(
    stream_id,
    time_interval=31_536_000,             # 365 days
    date_from=int(datetime.now().timestamp()) - 31_536_000 * 2,  # Two years of data
    date_to=int(datetime.now().timestamp())
)
```

## Stream Management

### `client.list_streams(limit: Optional[int] = None, offset: Optional[int] = None, data_provider: Optional[str] = None, order_by: Optional[str] = None, block_height: Optional[int] = 0) -> List[Dict[str, Any]]`
List all streams associated with the client account.

#### Parameters
- `limit: Optional[int]` - Maximum number of results to return
- `offset: Optional[int]` - Number of records to skip for pagination
- `data_provider: Optional[str]` - Filter by specific data provider
- `order_by: Optional[str]` - Sort order for results
- `block_height: Optional[int]` - Query at specific block height (default: 0)

#### Returns
- `List[Dict[str, Any]]` - List of stream information dictionaries

#### Example
```python
streams = client.list_streams(limit=10, offset=0)
for stream in streams:
    print(f"Stream ID: {stream['stream_id']}, Type: {stream['stream_type']}")
```

### `client.get_current_account() -> str`
Get the current account address associated with this client.

#### Returns
- `str` - The hex-encoded address of the current account

#### Example
```python
account_address = client.get_current_account()
print(f"Current account: {account_address}")
```

### `client.batch_deploy_streams(definitions: List[StreamDefinitionInput], wait: bool = True) -> str`
Deploy multiple streams (primitive and composed) in a single transaction.

#### Parameters
- `definitions: List[StreamDefinitionInput]` - List of stream definitions, each containing:
  - `stream_id: str` - Unique stream identifier
  - `stream_type: str` - Stream type ("primitive" or "composed")
- `wait: bool` - Whether to wait for transaction confirmation (default: True)

#### Returns
- `str` - Transaction hash of the batch deployment

#### Example
```python
definitions = [
    {"stream_id": "stream1", "stream_type": "primitive"},
    {"stream_id": "stream2", "stream_type": "composed"}
]
tx_hash = client.batch_deploy_streams(definitions)
```

### `client.batch_stream_exists(locators: List[StreamLocatorInput]) -> List[StreamExistsResult]`
Check for the existence of multiple streams.

#### Parameters
- `locators: List[StreamLocatorInput]` - List of stream locators, each containing:
  - `stream_id: str` - Stream identifier
  - `data_provider: str` - Data provider address

#### Returns
- `List[StreamExistsResult]` - List of existence results, each containing:
  - `stream_id: str` - Stream identifier
  - `data_provider: str` - Data provider address
  - `exists: bool` - Whether the stream exists

#### Example
```python
locators = [
    {"stream_id": "stream1", "data_provider": "0x123..."},
    {"stream_id": "stream2", "data_provider": "0x456..."}
]
results = client.batch_stream_exists(locators)
for result in results:
    print(f"Stream {result['stream_id']} exists: {result['exists']}")
```

### `client.batch_filter_streams_by_existence(locators: List[StreamLocatorInput], return_existing: bool) -> List[StreamLocatorInput]`
Filters a list of streams based on their existence.

#### Parameters
- `locators: List[StreamLocatorInput]` - List of stream locators to filter
- `return_existing: bool` - If True, returns existing streams; if False, returns non-existing streams

#### Returns
- `List[StreamLocatorInput]` - Filtered list of stream locators

#### Example
```python
locators = [
    {"stream_id": "stream1", "data_provider": "0x123..."},
    {"stream_id": "stream2", "data_provider": "0x456..."}
]
existing_streams = client.batch_filter_streams_by_existence(locators, return_existing=True)
```

## Composition Management

### `client.set_taxonomy(stream_id: str, child_streams: Dict[str, float], start_date: Optional[int] = None) -> str`
Configures stream composition and weight distribution.

#### Parameters
- `stream_id: str` - Composed stream identifier
- `child_streams: Dict[str, float]` - Mapping of child stream IDs to their weights
- `start_date: Optional[int]` - Effective date for taxonomy

#### Returns
- `str` - Transaction hash of taxonomy configuration

#### Example
```python
tx_hash = client.set_taxonomy(
    composed_stream_id,
    {
        stock_stream: 0.6,      # 60% weight
        commodity_stream: 0.4   # 40% weight
    },
    start_date=int(datetime.now().timestamp())
)
```

### `client.describe_taxonomy(stream_id: str, latest_version: bool = True) -> TaxonomyDetails | None` 🔍
Get taxonomy structure of a composed stream. This is the primary method for discovering how composed streams aggregate their child streams and understanding composition relationships.

#### Parameters
- `stream_id: str` - Composed stream identifier
- `latest_version: bool` - If True, returns only the latest version of the taxonomy (default: True)

#### Returns
- `TaxonomyDetails | None` - Taxonomy details containing:
  - `stream_id: str` - The composed stream identifier
  - `child_streams: List[TaxonomyDefinition]` - List of child stream definitions with weights
  - `created_at: int` - Creation timestamp

#### Example
```python
# Get taxonomy information for a composed stream
taxonomy = client.describe_taxonomy(composed_stream_id)
if taxonomy:
    print(f"Stream: {taxonomy['stream_id']}")
    total_weight = 0
    for child in taxonomy['child_streams']:
        print(f"  Child: {child.stream['stream_id']}, Weight: {child.weight}")
        total_weight += child.weight
    print(f"Total weight: {total_weight}")
else:
    print("No taxonomy found for this stream")

# Example: Validate taxonomy weights sum to 1.0
if taxonomy:
    weights = [child.weight for child in taxonomy['child_streams']]
    total_weight = sum(weights)
    if abs(total_weight - 1.0) > 0.001:  # Allow small floating point differences
        print(f"Warning: Weights don't sum to 1.0 (actual: {total_weight})")
```

### `client.allow_compose_stream(stream_id: str, wait: bool = True) -> str`
Allows streams to use this stream as child, if composing is private.

#### Parameters
- `stream_id: str` - Stream identifier
- `wait: bool` - Whether to wait for transaction confirmation (default: True)

#### Returns
- `str` - Transaction hash

#### Example
```python
tx_hash = client.allow_compose_stream(stream_id)
```

### `client.disable_compose_stream(stream_id: str, wait: bool = True) -> str`
Disable streams from using this stream as child.

#### Parameters
- `stream_id: str` - Stream identifier
- `wait: bool` - Whether to wait for transaction confirmation (default: True)

#### Returns
- `str` - Transaction hash

#### Example
```python
tx_hash = client.disable_compose_stream(stream_id)
```

## Role Management

> Only wallets with manager privileges (e.g. `system:network_writers_manager`) can grant or revoke roles. Regular users should request access from the TRUF.NETWORK team.

### `client.grant_role(owner: str, role_name: str, wallets: List[str]) -> str`
Grants a specified role to a list of wallet addresses.

#### Parameters
- `owner: str` - The owner of the role (e.g., 'system' or an Ethereum address).
- `role_name: str` - The name of the role to grant.
- `wallets: List[str]` - A list of wallet addresses to grant the role to.

#### Returns
- `str` - Transaction hash of the role grant operation.

#### Example
```python
# Grant the system:network_writer role to a specific wallet
tx_hash = client.grant_role(
    "system",
    "network_writer",
    ["0xAbC...123"]
)
```

### `client.revoke_role(owner: str, role_name: str, wallets: List[str]) -> str`
Revokes a specified role from a list of wallet addresses.

#### Parameters
- `owner: str` - The owner of the role.
- `role_name: str` - The name of the role to revoke.
- `wallets: List[str]` - A list of wallet addresses from which to revoke the role.

#### Returns
- `str` - Transaction hash of the role revocation operation.

#### Example
```python
tx_hash = client.revoke_role(
    "system",
    "network_writer",
    ["0xAbC...123"]
)
```

### `client.are_members_of(owner: str, role_name: str, wallets: List[str]) -> List[Dict]`
Checks if a list of wallets are members of a specific role.

#### Parameters
- `owner: str` - The owner of the role to check against.
- `role_name: str` - The name of the role.
- `wallets: List[str]` - A list of wallet addresses to check.

#### Returns
- `List[Dict]` - A list of objects, each containing:
  - `wallet: str` - The wallet address checked.
  - `is_member: bool` - True if the wallet is a member, false otherwise.

#### Example
```python
wallets_to_check = ["0xAbC...123", "0xDeF...456"]
membership_status = client.are_members_of(
    "system",
    "network_writer",
    wallets_to_check
)
# Example output:
# [
#   {'wallet': '0xabc...123', 'is_member': True},
#   {'wallet': '0xdef...456', 'is_member': False}
# ]
```

### `client.list_role_members(owner: str, role_name: str, limit: Optional[int] = None, offset: Optional[int] = None) -> List[RoleMember]`
Lists the members of a role with optional pagination.

#### Parameters
- `owner: str` - The owner namespace of the role (e.g., 'system')
- `role_name: str` - The role to list members for  
- `limit: Optional[int]` - Maximum number of results to return
- `offset: Optional[int]` - Number of records to skip for pagination

#### Returns
- `List[RoleMember]` - List of role member dictionaries containing:
  - `wallet: str` - The wallet address
  - `granted_at: int` - Unix timestamp when role was granted
  - `granted_by: str` - Address that granted the role

#### Example
```python
members = client.list_role_members("system", "network_writer", limit=10)
for member in members:
    print(f"Wallet: {member['wallet']}, Granted: {member['granted_at']}")
```

## Visibility and Permissions

### System vs. User Roles

| Role Namespace | Example | Who can create/manage | Typical purpose |
|----------------|---------|-----------------------|-----------------|
| `system:`      | `system:network_writer` | Core protocol maintainers | Gate network-wide operations (e.g. create streams) |
| `<wallet>:`    | `0x1234…abcd:pro_subscribers` | The wallet prefix (owner) | Business-specific read/write groups |

> Tip: You can list all roles owned by a wallet with `client.list_role_members(owner, role_name)`.

### `client.set_read_visibility(stream_id: str, visibility: str) -> str`
Controls stream read access.

#### Parameters
- `stream_id: str` - Stream identifier
- `visibility: str` - "public" or "private"

#### Example
```python
client.set_read_visibility(stream_id, "private")
```

### `client.allow_read_wallet(stream_id: str, wallet_address: str, wait: bool = True) -> str`
Grants read permissions to specific wallets.

#### Parameters
- `stream_id: str` - Stream identifier
- `wallet_address: str` - Ethereum wallet address
- `wait: bool` - Whether to wait for transaction confirmation (default: True)

#### Returns
- `str` - Transaction hash

#### Example
```python
tx_hash = client.allow_read_wallet(stream_id, "0x1234...")
```

### `client.disable_read_wallet(stream_id: str, wallet_address: str, wait: bool = True) -> str`
Disables a wallet from reading the stream.

#### Parameters
- `stream_id: str` - Stream identifier
- `wallet_address: str` - Ethereum wallet address
- `wait: bool` - Whether to wait for transaction confirmation (default: True)

#### Returns
- `str` - Transaction hash

#### Example
```python
tx_hash = client.disable_read_wallet(stream_id, "0x1234...")
```

### `client.get_read_visibility(stream_id: str) -> str`
Gets the read visibility of the stream.

#### Parameters
- `stream_id: str` - Stream identifier

#### Returns
- `str` - Visibility setting ("public" or "private")

#### Example
```python
visibility = client.get_read_visibility(stream_id)
print(f"Read visibility: {visibility}")
```

### `client.set_compose_visibility(stream_id: str, visibility: str, wait: bool = True) -> str`
Sets the compose visibility of the stream.

#### Parameters
- `stream_id: str` - Stream identifier
- `visibility: str` - Visibility setting ("public" or "private")
- `wait: bool` - Whether to wait for transaction confirmation (default: True)

#### Returns
- `str` - Transaction hash

#### Example
```python
tx_hash = client.set_compose_visibility(stream_id, "private")
```

### `client.get_compose_visibility(stream_id: str) -> str`
Gets the compose visibility of the stream.

#### Parameters
- `stream_id: str` - Stream identifier

#### Returns
- `str` - Visibility setting ("public" or "private")

#### Example
```python
visibility = client.get_compose_visibility(stream_id)
print(f"Compose visibility: {visibility}")
```

### `client.get_allowed_read_wallets(stream_id: str) -> List[str]`
Gets the wallets allowed to read the stream, if read stream is private.

#### Parameters
- `stream_id: str` - Stream identifier

#### Returns
- `List[str]` - List of allowed wallet addresses

#### Example
```python
allowed_wallets = client.get_allowed_read_wallets(stream_id)
print(f"Allowed read wallets: {allowed_wallets}")
```

### `client.get_allowed_compose_streams(stream_id: str) -> List[str]`
Gets the streams allowed to compose this stream, if compose stream is private.

#### Parameters
- `stream_id: str` - Stream identifier

#### Returns
- `List[str]` - List of allowed stream identifiers

#### Example
```python
allowed_streams = client.get_allowed_compose_streams(stream_id)
print(f"Allowed compose streams: {allowed_streams}")
```

## Transaction Handling

### `client.wait_for_tx(tx_hash: str) -> None`
Waits for transaction confirmation.

#### Parameters
- `tx_hash: str` - Transaction hash to wait for

#### Example
```python
client.wait_for_tx(tx_hash)
```

## Transaction Ledger

The transaction ledger provides comprehensive querying capabilities for transaction history, fees, and distributions. This is useful for auditing, analytics, and tracking transaction costs.

### `client.get_transaction_event(tx_id: str) -> TransactionEvent`
Retrieves detailed information about a specific transaction by its hash.

#### Parameters
- `tx_id: str` - Transaction hash (with or without 0x prefix)

#### Returns
- `TransactionEvent` - Dictionary containing:
  - `tx_id: str` - Transaction hash (normalized with 0x prefix)
  - `block_height: int` - Block height when transaction was included
  - `method: str` - Method name (e.g., "deployStream", "insertRecords")
  - `caller: str` - Ethereum address of the caller
  - `fee_amount: str` - Fee amount in wei as a string (for precision)
  - `fee_recipient: str | None` - Primary fee recipient address (if any)
  - `metadata: str | None` - Optional metadata JSON
  - `fee_distributions: List[FeeDistribution]` - List of fee distribution details
    - Each distribution has: `recipient: str`, `amount: str`

#### Raises
- `ValueError` - If tx_id is empty
- `Exception` - If transaction not found or query fails

#### Example
```python
from trufnetwork_sdk_py.client import TNClient

client = TNClient("https://gateway.mainnet.truf.network", "YOUR_PRIVATE_KEY")

# Get transaction details
tx_event = client.get_transaction_event("0xabcdef123456...")

print(f"Method: {tx_event['method']}")
print(f"Caller: {tx_event['caller']}")
print(f"Fee: {tx_event['fee_amount']} wei")
print(f"Block: {tx_event['block_height']}")

# Check fee distributions
for dist in tx_event['fee_distributions']:
    print(f"  → {dist['recipient']}: {dist['amount']} wei")
```

### `client.list_transaction_fees(wallet: str, mode: str = "paid", limit: int | None = None, offset: int | None = None) -> List[TransactionFeeEntry]`
Lists transactions filtered by wallet address and mode, with pagination support.

#### Parameters
- `wallet: str` - Ethereum address to query (required)
- `mode: str` - Filter mode (default: "paid")
  - `"paid"` - Fees paid by this wallet (as transaction caller)
  - `"received"` - Fees received by this wallet (as fee recipient)
  - `"both"` - All transactions involving this wallet
- `limit: int | None` - Maximum results to return (default: 20, max: 1000)
- `offset: int | None` - Pagination offset (default: 0)

#### Returns
- `List[TransactionFeeEntry]` - List of transaction entries, each containing:
  - `tx_id: str` - Transaction hash
  - `block_height: int` - Block height
  - `method: str` - Method name
  - `caller: str` - Transaction caller address
  - `total_fee: str` - Total fee amount in wei
  - `fee_recipient: str | None` - Primary fee recipient (if any)
  - `metadata: str | None` - Optional metadata
  - `distribution_sequence: int` - Sequence number of this distribution
  - `distribution_recipient: str | None` - Specific distribution recipient
  - `distribution_amount: str | None` - Specific distribution amount

> **Note**: Returns one row per fee distribution. A transaction with multiple distributions will appear multiple times with different `distribution_sequence` values.

#### Raises
- `ValueError` - If wallet is empty, mode is invalid, or pagination parameters are invalid

#### Example: Basic Usage
```python
from trufnetwork_sdk_py.client import TNClient

client = TNClient("https://gateway.mainnet.truf.network", "YOUR_PRIVATE_KEY")
wallet = client.get_current_account()

# List fees paid by this wallet
entries = client.list_transaction_fees(
    wallet=wallet,
    mode="paid",
    limit=10
)

for entry in entries:
    print(f"{entry['method']}: {entry['total_fee']} wei at block {entry['block_height']}")
```

#### Example: Pagination
```python
# Get first page (records 1-20)
page1 = client.list_transaction_fees(wallet=wallet, limit=20, offset=0)

# Get second page (records 21-40)
page2 = client.list_transaction_fees(wallet=wallet, limit=20, offset=20)

# Get all transactions (up to max 1000)
all_entries = client.list_transaction_fees(wallet=wallet, limit=1000)
```

#### Example: Fees Received
```python
# Check if this wallet has received any fee distributions
received = client.list_transaction_fees(
    wallet=wallet,
    mode="received",
    limit=50
)

if received:
    print(f"This wallet has received fees from {len(received)} distributions")
    total = sum(int(e['distribution_amount'] or '0') for e in received)
    print(f"Total received: {total} wei")
```

#### Example: All Transactions
```python
# Get both paid and received transactions
all_txs = client.list_transaction_fees(
    wallet=wallet,
    mode="both",
    limit=100
)

paid_count = sum(1 for e in all_txs if e['caller'].lower() == wallet.lower())
received_count = sum(1 for e in all_txs if e['distribution_recipient'] and
                     e['distribution_recipient'].lower() == wallet.lower())

print(f"Paid {paid_count} transaction fees")
print(f"Received {received_count} fee distributions")
```

### `client.get_history(bridge_identifier: str, wallet: str, limit: int = 20, offset: int = 0) -> List[BridgeHistory]`
Retrieves the transaction history for a wallet on a specific bridge.

#### Parameters
- `bridge_identifier: str` - The name of the bridge instance (e.g., "hoodi_tt2")
- `wallet: str` - The wallet address to query
- `limit: int` - Max number of records to return (default: 20)
- `offset: int` - Number of records to skip (default: 0)

#### Returns
- `List[BridgeHistory]` - List of history records

#### Example
```python
history = client.get_history(
    bridge_identifier="hoodi_tt2",
    wallet="0x..."
)

for rec in history:
    print(f"{rec['type']} - Amount: {rec['amount']}")
```

#### `BridgeHistory` (TypedDict)

Dictionary representing a transaction history record.

```python
class BridgeHistory(TypedDict):
    type: str                # "deposit" or "withdrawal"
    amount: str              # NUMERIC(78,0) as string
    from_address: str | None # Sender address (if available)
    to_address: str | None   # Recipient address
    internal_tx_hash: str | None # Kwil TX hash (base64)
    external_tx_hash: str | None # Ethereum TX hash (base64)
    status: str              # "completed", "claimed", "pending_epoch"
    block_height: int        # Kwil block height
    block_timestamp: int     # Kwil block timestamp
    external_block_height: int | None # Ethereum block height
```

### Transaction Ledger Use Cases

**Auditing**: Track all fees paid and received by your wallets
```python
# Audit monthly spending
wallet = "0x1234..."
monthly_fees = client.list_transaction_fees(wallet, mode="paid", limit=1000)
total_spent = sum(int(e['total_fee']) for e in monthly_fees)
print(f"Total fees paid: {total_spent / 1e18:.4f} TRUF")
```

**Analytics**: Analyze transaction patterns
```python
# Count transactions by method
from collections import Counter
entries = client.list_transaction_fees(wallet, mode="paid", limit=500)
methods = Counter(e['method'] for e in entries)
print(f"Most common operations: {methods.most_common(5)}")
```

**Fee Distribution Tracking**: Monitor where fees go
```python
# Track fee recipients
tx_event = client.get_transaction_event(tx_hash)
if tx_event['fee_distributions']:
    print("Fee distribution breakdown:")
    for dist in tx_event['fee_distributions']:
        percentage = (int(dist['amount']) / int(tx_event['fee_amount'])) * 100
        print(f"  {dist['recipient']}: {percentage:.1f}%")
```

## Performance Recommendations
- Use `batch_insert_records` for multiple records to one or more streams to reduce network overhead and transaction costs.
- Handle errors with specific exception handling to build robust applications.

## SDK Compatibility
- Minimum Python Version: 3.8 

## Custom Procedure Calls

### `client.call_procedure(procedure: str, args: List[Any]) -> Dict`
Invokes a **read-only stored procedure** (sometimes referred to as a _custom procedure_) that is deployed on the TRUF.NETWORK gateway.  This is useful for aggregations, analytics, or any bespoke SQL logic that cannot be expressed via the higher-level SDK helpers.

#### Parameters
- `procedure: str` – The name of the stored procedure to execute.
- `args: List[Any]` – A list of positional arguments that will be forwarded as-is to the procedure.  Use `None` for optional parameters you wish to skip.

#### Returns
- `Dict` – A dictionary with the keys:
  - `column_names: List[str]` – Names of the returned columns.
  - `values: List[List[Any]]` – Row-major 2-D array containing the result set.

#### Example
```python
from datetime import datetime, timezone, timedelta
from trufnetwork_sdk_py.client import TNClient

client = TNClient("https://gateway.mainnet.truf.network", "YOUR_PRIVATE_KEY")

# Call a 5-argument read-only procedure
one_week_ago = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
now = int(datetime.now(timezone.utc).timestamp())
time_interval = 31_536_000  # 1 year in seconds

args = [one_week_ago, now, None, None, time_interval]
result = client.call_procedure("get_divergence_index_change", args)

print("Columns:", result["column_names"])
for row in result["values"]:
    print(row)
```

> **Note**
> `call_procedure` is *read-only* and therefore free of on-chain gas costs.  For state-changing procedures, use `client.execute_procedure` which returns a transaction hash.

## Order Book Operations

The Order Book API provides functionality for binary prediction markets. Markets are automatically settled based on real-world data from trusted data providers.

### Market Creation

#### `client.create_price_above_threshold_market(...) -> str`
Create a binary prediction market that settles TRUE if the stream value exceeds the threshold.

**Parameters:**
- `data_provider: str` - 0x-prefixed Ethereum address of the data provider
- `stream_id: str` - 32-character stream ID
- `timestamp: int` - Unix timestamp to check the value at
- `threshold: str` - Threshold value as decimal string (e.g., "100000")
- `bridge: str` - Bridge namespace (`hoodi_tt2`)
- `settle_time: int` - Unix timestamp when market can be settled
- `max_spread: int` - Maximum spread for LP rewards (1-50 cents)
- `min_order_size: int` - Minimum order size for LP rewards
- `frozen_at: int | None` - Optional Unix timestamp to freeze the value lookup
- `wait: bool` - If True, wait for transaction confirmation (default: True)

**Returns:** Transaction hash

**Example:**
```python
from datetime import datetime, timezone, timedelta

# Create market: "Will BTC be above $100,000?"
settle_time = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())

tx_hash = client.create_price_above_threshold_market(
    data_provider="0xe5252596672cd0208a881bdb67c9df429916ba92",
    stream_id="st9bc3cf61c3a88aa17f4ea5f1bad7b2",
    timestamp=settle_time,
    threshold="100000",
    bridge="hoodi_tt2",
    settle_time=settle_time,
    max_spread=10,
    min_order_size=1_000_000_000_000_000_000,  # 1 token
)
```

#### `client.create_price_below_threshold_market(...) -> str`
Create a binary prediction market that settles TRUE if the stream value is below the threshold.

**Parameters:** Same as `create_price_above_threshold_market`

**Example:**
```python
# Create market: "Will unemployment drop below 4%?"
tx_hash = client.create_price_below_threshold_market(
    data_provider="0x...",
    stream_id="st_unemployment_rate_000000000",
    timestamp=settle_time,
    threshold="4.0",
    bridge="hoodi_tt2",
    settle_time=settle_time,
    max_spread=10,
    min_order_size=1_000_000_000_000_000_000,
)
```

#### `client.create_value_in_range_market(...) -> str`
Create a binary prediction market that settles TRUE if the stream value is within the specified range.

**Additional Parameters:**
- `min_value: str` - Minimum value (inclusive) as decimal string
- `max_value: str` - Maximum value (inclusive) as decimal string

**Example:**
```python
# Create market: "Will BTC stay between $90k-$110k?"
tx_hash = client.create_value_in_range_market(
    data_provider="0x...",
    stream_id="st9bc3cf61c3a88aa17f4ea5f1bad7b2",
    timestamp=settle_time,
    min_value="90000",
    max_value="110000",
    bridge="hoodi_tt2",
    settle_time=settle_time,
    max_spread=10,
    min_order_size=1_000_000_000_000_000_000,
)
```

### Market Queries

#### `client.get_market_info(query_id: int) -> MarketInfo`
Get detailed information about a market.

**Returns:** Dictionary containing:
- `id: int` - Market ID
- `hash: bytes` - Market hash
- `settle_time: int` - Settlement timestamp
- `settled: bool` - Whether market is settled
- `winning_outcome: bool | None` - Winning outcome (if settled)
- `max_spread: int` - Maximum spread for LP rewards
- `min_order_size: int` - Minimum order size

**Example:**
```python
market = client.get_market_info(query_id=1)
print(f"Market {market['id']} - Settled: {market['settled']}")
```

#### `client.list_markets(settled_filter: bool | None = None, limit: int = 100, offset: int = 0) -> list[MarketSummary]`
List markets with optional filtering.

**Parameters:**
- `settled_filter: bool | None` - None=all markets, True=unsettled only, False=settled only (default: None)
- `limit: int` - Maximum results (default: 100)
- `offset: int` - Pagination offset (default: 0)

**Example:**
```python
# Get unsettled markets
unsettled = client.list_markets(settled_filter=True, limit=10)

# Get all markets
all_markets = client.list_markets()
```

### Market Data Decoding

High-level utilities for decoding prediction market query components. This is essential for extracting market types and threshold values from the `query_components` field returned by the node.

#### `TNClient.decode_market_data(query_components: bytes) -> MarketData`
Decodes ABI-encoded query components into structured high-level data.

**Parameters:**
- `query_components: bytes` - The query components from a market info object.

**Returns:** `MarketData` TypedDict

**Example:**
```python
market = client.get_market_info(123)
# market['query_components'] is bytes
data = TNClient.decode_market_data(market['query_components'])

print(f"Type: {data['type']}")             # e.g. "above"
print(f"Thresholds: {data['thresholds']}") # e.g. ["100000.0"]
```

#### `TNClient.decode_query_components(query_components: bytes) -> DecodedQueryComponents`
Decodes ABI-encoded query components back into its basic parts.

**Parameters:**
- `query_components: bytes` - ABI-encoded bytes

**Returns:** `DecodedQueryComponents` TypedDict

#### `MarketData` (TypedDict)
- `data_provider: str`
- `stream_id: str`
- `action_id: str`
- `type: str` - One of: "above", "below", "between", "equals", "unknown"
- `thresholds: List[str]` - Formatted numeric values as strings

#### `DecodedQueryComponents` (TypedDict)
- `data_provider: str`
- `stream_id: str`
- `action_id: str`
- `args: str` - Hex-encoded arguments

### Order Placement

#### `client.place_buy_order(query_id, outcome, price, amount, wait=True) -> str`
Place a buy order for YES or NO shares.

**Parameters:**
- `query_id: int` - Market ID
- `outcome: bool` - True for YES shares, False for NO shares
- `price: int` - Price per share in cents (1-99)
- `amount: int` - Number of shares to buy
- `wait: bool` - If True, wait for transaction confirmation

**Example:**
```python
# Buy 100 YES shares at 56 cents
tx_hash = client.place_buy_order(
    query_id=1,
    outcome=True,
    price=56,
    amount=100
)
```

#### `client.place_sell_order(query_id, outcome, price, amount, wait=True) -> str`
Place a sell order for shares you own.

**Parameters:** Same as `place_buy_order`

**Example:**
```python
# Sell 50 NO shares at 45 cents
tx_hash = client.place_sell_order(
    query_id=1,
    outcome=False,
    price=45,
    amount=50
)
```

#### `client.place_split_limit_order(query_id, true_price, amount, wait=True) -> str`
Mint binary share pairs and list the NO side for sale.

This is the primary way to provide liquidity. It atomically:
1. Locks collateral (amount × $1.00)
2. Mints YES/NO share pairs
3. Keeps YES shares as holdings
4. Places NO shares as a sell order at `100 - true_price`

**Parameters:**
- `query_id: int` - Market ID
- `true_price: int` - YES price in cents (1-99)
- `amount: int` - Number of share PAIRS to mint
- `wait: bool` - If True, wait for transaction confirmation

**Example:**
```python
# Mint 100 share pairs, hold YES, sell NO at 40 cents
tx_hash = client.place_split_limit_order(
    query_id=1,
    true_price=60,  # YES at 60 cents, NO at 40 cents
    amount=100
)
```

### Order Management

#### `client.cancel_order(query_id, outcome, price, wait=True) -> str`
Cancel an open buy or sell order.

**Parameters:**
- `query_id: int` - Market ID
- `outcome: bool` - True for YES, False for NO
- `price: int` - Price of order to cancel (negative for buy, positive for sell)

**Example:**
```python
# Cancel a YES buy order at 56 cents
tx_hash = client.cancel_order(query_id=1, outcome=True, price=-56)
```

#### `client.change_bid(query_id, outcome, old_price, new_price, new_amount, wait=True) -> str`
Atomically modify a buy order's price and amount.

**Example:**
```python
# Change buy order from -50 to -55 with new amount of 200
tx_hash = client.change_bid(
    query_id=1,
    outcome=True,
    old_price=-50,
    new_price=-55,
    new_amount=200
)
```

#### `client.change_ask(query_id, outcome, old_price, new_price, new_amount, wait=True) -> str`
Atomically modify a sell order's price and amount.

**Example:**
```python
# Change sell order from 45 to 50 with new amount of 150
tx_hash = client.change_ask(
    query_id=1,
    outcome=False,
    old_price=45,
    new_price=50,
    new_amount=150
)
```

### Order Book Queries

#### `client.get_order_book(query_id, outcome) -> list[OrderBookEntry]`
Get all buy/sell orders for a market outcome.

**Returns:** List of order entries with:
- `wallet_address: bytes` - Trader's address
- `price: int` - Order price (negative=buy, positive=sell, 0=holding)
- `amount: int` - Order amount

**Example:**
```python
# Get YES order book
yes_orders = client.get_order_book(query_id=1, outcome=True)
for order in yes_orders:
    print(f"Price: {order['price']}, Amount: {order['amount']}")
```

#### `client.get_user_positions() -> list[UserPosition]`
Get all positions for the current user across all markets.

**Example:**
```python
positions = client.get_user_positions()
for pos in positions:
    print(f"Market {pos['query_id']}: {pos['amount']} shares")
```

#### `client.get_market_depth(query_id, outcome) -> list[DepthLevel]`
Get aggregated order book depth for a market outcome.

**Returns:** List of depth levels with aggregated amounts at each price.

### Settlement

Markets are settled **automatically** by the network scheduler. No manual intervention is required.

The settlement process:
1. Scheduler polls for markets past their settlement time
2. Attestation is requested from the data provider's stream
3. TEE signs the attestation cryptographically
4. Settlement executes and determines the winner
5. Payouts are distributed to winning positions

### Price Representation

| Type | Price Range | Description |
|------|-------------|-------------|
| Buy Order | -99 to -1 | Bid to buy at abs(price) cents |
| Holding | 0 | Shares owned |
| Sell Order | 1 to 99 | Ask to sell at price cents |

A YES price of 60 cents implies:
- 60% probability of YES
- Complementary NO price of 40 cents

### Collateral

- Each share pair requires $1.00 collateral
- Winners receive $1.00 per winning share
- Collateral from losing positions funds winner payouts
- Supported bridges: `hoodi_tt2` (testnet)

## Attestation Helpers

### `TNClient.parse_attestation_payload(payload: bytes) -> Dict[str, Any]`

Parses a canonical attestation payload (without signature) into structured data.

**Parameters:**
- `payload: bytes` - The canonical payload from `GetSignedAttestation` (excluding the last 65 bytes of signature).

**Returns:**
- `Dict[str, Any]` - Structured dictionary containing:
  - `version: int`
  - `algorithm: int`
  - `block_height: int`
  - `data_provider: str` (0x-prefixed address)
  - `stream_id: str`
  - `action_id: int`
  - `arguments: List[Any]` (decoded arguments)
  - `result: List[Dict[str, Any]]` (decoded result rows)

## Bridge Actions

The Bridge Actions interface enables programmatic interaction with the TRUF.NETWORK bridge system. It allows bots and applications to manage token balances, initiate withdrawals to external chains, and retrieve cryptographic proofs for claiming assets.

### `client.get_wallet_balance(bridge_identifier: str, wallet_address: str) -> str`

Retrieves the token balance for a wallet on a specific bridge instance.

**Parameters:**
- `bridge_identifier: str` - Unique identifier for the bridge (e.g., "hoodi_tt", "sepolia").
- `wallet_address: str` - The wallet address to query (0x-prefixed).

**Returns:**
- `str` - The balance in wei (as a string to preserve precision).

**Example:**
```python
balance = client.get_wallet_balance("hoodi_tt", "0x123...")
print(f"Balance: {int(balance) / 1e18} TT")
```

### `client.withdraw(bridge_identifier: str, amount: str, recipient: str) -> str`

Initiates a withdrawal by burning tokens on the TRUF.NETWORK. This is the first step in bridging assets back to an external chain.

**Parameters:**
- `bridge_identifier: str` - Unique identifier for the bridge (e.g., "hoodi_tt").
- `amount: str` - The amount to withdraw in wei. Must be a valid numeric string.
- `recipient: str` - The EVM address that will receive the funds on the destination chain.

**Returns:**
- `str` - The transaction hash of the burn operation on Kwil.

**Example:**
```python
# Withdraw 1 token (18 decimals)
tx_hash = client.withdraw(
    bridge_identifier="hoodi_tt", 
    amount="1000000000000000000", 
    recipient="0xRecipient..."
)
print(f"Burn TX Hash: {tx_hash}")
```

### `client.get_withdrawal_proof(bridge_identifier: str, wallet: str) -> List[Dict]`

Retrieves the cryptographic proofs required to claim a withdrawal on the destination chain.

**Parameters:**
- `bridge_identifier: str` - The bridge ID (e.g., "hoodi_tt").
- `wallet: str` - The wallet address that initiated the withdrawal.

**Returns:**
- `List[Dict]` - A list of proof objects, each containing:
  - `block_height: int`
  - `block_hash: str` (Base64)
  - `root: str` (Base64)
  - `signatures: List[str]` (Base64)
  - `amount: str`
  - `recipient: str`

**Example:**
```python
proofs = client.get_withdrawal_proof("hoodi_tt", "0xSender...")

if proofs:
    proof = proofs[0]
    print(f"Ready to claim {proof['amount']} tokens")
    # Use proof data to submit claim transaction on Ethereum
```