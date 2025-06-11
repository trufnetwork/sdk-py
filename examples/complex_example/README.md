# Complex Stream Management Example

## Overview

This example demonstrates the full lifecycle of stream management in the TRUF.NETWORK SDK, including:

- Generating unique stream IDs
- Creating primitive streams
- Creating a composed stream
- Setting stream taxonomy
- Inserting records into streams
- Reading stream records
- Destroying streams

## Prerequisites

- Python 3.8+
- `venv` module (usually comes with Python standard library)
- A valid private key for the TRUF.NETWORK gateway
- Your wallet must **hold `system:network_writer`** or the deployment steps will fail. Contact the TRUF.NETWORK team if you need access.

## Setup

1. Create and Activate a Virtual Environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install the SDK:
```bash
pip install trufnetwork-sdk-py@git+https://github.com/trufnetwork/sdk-py.git@main
```

3. Set your TRUF.NETWORK private key as an environment variable:
```bash
# On Unix/MacOS:
export TRUF_PRIVATE_KEY=your_private_key_here

# On Windows (PowerShell):
$env:TRUF_PRIVATE_KEY="your_private_key_here"
```

## Running the Example

```bash
# Ensure virtual environment is activated
python main.py
```

## Deactivating the Virtual Environment

When you're done, you can deactivate the virtual environment:
```bash
# On all platforms
deactivate
```

## Example Walkthrough

The script performs the following steps:

1. **Stream ID Generation**: 
   - Creates unique IDs for market, tech, AI, and composite streams using `generate_stream_id()`

2. **Primitive Stream Creation**:
   - Deploys three primitive streams representing different economic indicators

3. **Record Insertion**:
   - Inserts sample records into each primitive stream
   - Demonstrates how to add time-series data

4. **Composed Stream Creation**:
   - Creates a composite stream that combines the primitive streams
   - Sets a taxonomy with weighted contributions from each primitive stream

5. **Stream Reading**:
   - Retrieves and displays records from individual and composite streams
   - Shows how to access stream data

6. **Stream Cleanup**:
   - Destroys all created streams to prevent resource accumulation

## Customization

- Modify stream IDs, record values, and weights to suit your use case
- Adjust the gateway URL and authentication method as needed

## Notes

- Always handle private keys securely
- Be mindful of rate limits and transaction costs
- This is a demonstration; adapt for production use
- Always use a virtual environment to avoid package conflicts

## Troubleshooting

- Ensure your private key is valid
- Check network connectivity
- Verify TRUF.NETWORK gateway status
- If you encounter permission issues, ensure you're using a virtual environment
- Make sure all dependencies are installed within the virtual environment 