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

### `client.allow_read_wallet(stream_id: str, wallet_address: str) -> str`
Grants read permissions to specific wallets.

#### Parameters
- `stream_id: str` - Stream identifier
- `wallet_address: str` - Ethereum wallet address

#### Example
```python
client.allow_read_wallet(stream_id, "0x1234...")
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