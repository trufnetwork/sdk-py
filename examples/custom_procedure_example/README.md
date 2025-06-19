# Custom Stored Procedure Example

This example demonstrates how to invoke **read-only stored procedures** (aka _custom procedures_) on TRUF.NETWORK directly from the Python SDK.

The accompanying `main.py` script shows how to call the `get_divergence_index_change` procedure, which expects the following positional arguments:

| Position | Name          | Type | Description                                                  |
|----------|---------------|------|--------------------------------------------------------------|
| 1        | `from`        | INT  | Starting UNIX timestamp (inclusive)                          |
| 2        | `to`          | INT  | Ending UNIX timestamp   (inclusive)                          |
| 3        | `frozen_at`   | INT? | _Optional_ timestamp when the stream was frozen              |
| 4        | `base_time`   | INT? | _Optional_ base time for index normalisation                 |
| 5        | `time_interval` | INT | Comparison interval in seconds (e.g. `31_536_000` for 1 y) |

### Running the example

```bash
cd examples/custom_procedure_example
python main.py
```

> **Heads-up**
>
> * Replace `PRIVATE_KEY` in `main.py` with **your own** signer key.
> * Point `ENDPOINT` to the TRUF gateway you want to query (local dev-node or `https://gateway.mainnet.truf.network`).
>
> The procedure used in this snippet is read-only, so no on-chain transaction fees are incurred.

## Overview

This example demonstrates how to call custom procedures in the TRUF.NETWORK SDK using the `call_procedure` method. Custom procedures are server-side functions that can perform complex operations on stream data.

## Features

The example showcases calling custom procedures with different types of arguments:
- String arguments
- Float arguments
- List arguments (lists of strings or floats)

## Prerequisites

- Python 3.8+
- TRUF.NETWORK SDK installed
- A valid RPC endpoint and private key

## Example Procedures

The example demonstrates three hypothetical custom procedures:

1. `get_divergence_index_change`
   - Purpose: Retrieve divergence index changes for a specific stream within a date range
   - Arguments:
     - Stream ID (string)
     - Start date (string)
     - End date (string)

2. `calculate_weighted_average`
   - Purpose: Calculate a weighted average with specific parameters
   - Arguments:
     - Weight (float)
     - Value (float)
     - Threshold (float)

3. `process_multiple_streams`
   - Purpose: Process multiple streams with corresponding weights
   - Arguments:
     - List of stream IDs (list of strings)
     - List of weights (list of floats)

## Usage

```python
from trufnetwork_sdk_py.client import TNClient

# Initialize the client
client = TNClient(
    url="https://rpc.truf.network",
    token="YOUR_PRIVATE_KEY_HERE"
)

# Call a procedure with string arguments
result = client.call_procedure("get_divergence_index_change", [
    "stream_id_1", 
    "2023-01-01", 
    "2023-12-31"
])

# Call a procedure with float arguments
result = client.call_procedure("calculate_weighted_average", [
    1.5, 
    2.7, 
    0.9
])

# Call a procedure with list arguments
result = client.call_procedure("process_multiple_streams", [
    ["stream_id_1", "stream_id_2"],
    [1.0, 2.0]
])
```

## Error Handling

The `call_procedure` method will raise a `ValueError` if:
- An unsupported argument type is passed
- A list contains mixed argument types

## Notes

- Custom procedures are defined on the server-side
- The exact procedure names and argument types depend on your specific TRUF.NETWORK deployment
- Always refer to your specific network's documentation for available procedures

## Troubleshooting

- Ensure your RPC endpoint and private key are correct
- Check that the custom procedure exists on the server
- Verify argument types match the procedure's expected input 