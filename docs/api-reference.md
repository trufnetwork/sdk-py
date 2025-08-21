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