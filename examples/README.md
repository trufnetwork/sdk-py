# Basic Example

## Overview

This example demonstrates how to use the TRUF.NETWORK SDK to read records from an existing stream, specifically the AI Index stream.

## Prerequisites

- Python 3.8+
- TRUF.NETWORK SDK installed
- Access to a TRUF.NETWORK node (local or mainnet)

## Setup

1. Install the SDK:
```bash
pip install trufnetwork-sdk-py@git+https://github.com/trufnetwork/sdk-py.git@main
```

2. Prepare Your Environment:
   - For local node: Use `http://localhost:8484`
   - For mainnet: Use `https://gateway.mainnet.truf.network`
   - Ensure you have a valid private key

## Configuration

In the script, you can modify two key variables:

### Provider URL
```python
TEST_PROVIDER_URL = "http://localhost:8484"  # Or mainnet URL
```

### Private Key
```python
TEST_PRIVATE_KEY = "your_private_key_here"
```

## Running the Example

```bash
python main.py
```

## What This Example Does

1. Initializes a TRUF.NETWORK client
2. Reads records from the AI Index stream
3. Retrieves records from the last 7 days
4. Prints out the date and value for each record

## Example Output

```
Reading AI Index Stream:
AI Index Records:
Date: 2024-01-15, Value: 105.25
Date: 2024-01-16, Value: 106.50
...
```

## Customization

- Change `ai_stream_id` to explore different streams
- Modify the date range by adjusting `week_ago` and `now`
- Experiment with different data providers

## Troubleshooting

- Ensure your private key is correct
- Check network connectivity
- Verify the stream ID and data provider are valid

## Notes

- Always handle private keys securely
- Be mindful of rate limits
- This is a basic example; adapt for your specific use case

## Further Reading

- [API Reference](../docs/api-reference.md)