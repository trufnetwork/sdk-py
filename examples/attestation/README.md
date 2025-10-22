# Attestation Example - TN Python SDK

This example demonstrates how to use attestations in the TN Python SDK.

## What Are Attestations?

Attestations are **validator-signed proofs** of query results from the TrufNetwork. They provide cryptographic evidence that specific data existed at a specific block height, making them ideal for:

- Smart contract oracles
- Cross-chain data bridges
- Audit trails
- Compliance verification

## Prerequisites

1. **Local TN Node** running on `http://localhost:8484`
2. **Private key** with `network_writer` role
3. **Python 3.8+**

## Installation

```bash
# Install SDK
pip install trufnetwork-sdk-py

# Or install from source
cd ../..
pip install -e .
```

## Configuration

Create a `.env` file:

```env
PRIVATE_KEY=your_private_key_here
PROVIDER_URL=http://localhost:8484
```

## Running the Example

```bash
python main.py
```

## Expected Output

```
Connecting to TN network at http://localhost:8484
Using address: 0x1234...

=== Requesting Attestation ===
Data Provider: 0x4710a8d8f0d845da110086812a32de6d90d7ff5c
Stream ID: stai0000000000000000000000000000
Time Range: 1729000000 to 1729604800

✓ Attestation requested successfully!
Request TX ID: 0xabc123...

=== Retrieving Signed Attestation ===
Polling for signed attestation (max 30 seconds)...
  Attempt 1/15...
  Attempt 2/15...

✓ Retrieved signed attestation!
Payload size: 342 bytes
Payload (hex): 01005374616930303030303030303030...

=== Listing My Recent Attestations ===
Found 3 recent attestations:
1. TX: 0xabc123..., Created: height 12345, Status: signed at height 12346
2. TX: 0xdef456..., Created: height 12300, Status: signed at height 12301
3. TX: 0xghi789..., Created: height 12250, Status: unsigned

=== Example Complete ===
✓ Successfully demonstrated attestation workflow
```

## API Reference

### request_attestation()

Submit a request for a signed attestation.

```python
request_tx_id = client.request_attestation(
    data_provider="0x4710a8d8f0d845da110086812a32de6d90d7ff5c",
    stream_id="stai0000000000000000000000000000",
    action_name="get_record",
    args=[data_provider, stream_id, from_time, to_time, None, False],
    encrypt_sig=False,
    max_fee=1000000,
    wait=True,
)
```

**Parameters:**
- `data_provider` (str): 0x-prefixed hex address (42 characters)
- `stream_id` (str): Stream ID (32 characters)
- `action_name` (str): Action to attest (e.g., "get_record")
- `args` (list): Action arguments
- `encrypt_sig` (bool): Must be False in MVP
- `max_fee` (int): Maximum fee willing to pay
- `wait` (bool): Whether to wait for transaction confirmation

**Returns:** Transaction ID (str)

### get_signed_attestation()

Retrieve a signed attestation payload.

```python
payload = client.get_signed_attestation(request_tx_id)
```

**Parameters:**
- `request_tx_id` (str): Transaction ID from request_attestation

**Returns:** Signed payload (bytes)

**Note:** Poll this endpoint until you receive a non-empty payload (validator signing takes 1-2 blocks).

### list_attestations()

List attestation metadata with optional filtering.

```python
attestations = client.list_attestations(
    requester=my_address_bytes,
    limit=10,
    offset=0,
    order_by="created_height desc",
)
```

**Parameters:**
- `requester` (bytes | None): Filter by requester address (20 bytes)
- `limit` (int | None): Max results (default/max: 5000)
- `offset` (int | None): Pagination offset
- `order_by` (str | None): Sort order (e.g., "created_height desc")

**Returns:** List of attestation metadata dicts

## Troubleshooting

### "Timed out waiting for signature"

The attestation may still be processing. Wait a few more blocks and try `get_signed_attestation()` again.

### "Invalid data_provider format"

Ensure your data provider address is:
- 42 characters long
- Starts with "0x"
- Contains valid hexadecimal characters

### "Stream not found"

Verify the stream exists and you have permission to read it.

## Next Steps

- Verify attestation payloads in smart contracts (see EVM library docs)
- Implement automatic polling with exponential backoff
- Add error handling and retry logic
- Integrate with your application's data pipeline
