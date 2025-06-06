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

## Visibility and Permissions

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
- Use batch record insertions
- Handle errors with specific exception handling

## SDK Compatibility
- Minimum Python Version: 3.8 