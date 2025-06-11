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