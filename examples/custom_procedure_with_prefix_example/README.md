# Custom Index with Prefix Integration

## Overview

This example demonstrates the retrieval of custom indexes with prefix functionality from existing streams within the TRUF.NETWORK (TN) SDK framework.

> **Note:** Data provider partnership is required to integrate custom methods with prefix functionality into standard operations as shown in this implementation.

## Objectives

This implementation illustrates:
- Establishing connections to TN nodes (local or mainnet environments)
- Retrieving indexed data from predefined streams using standard methods enhanced with prefix capabilities

## Core Components

- TN client initialization and configuration
- Stream records retrieval operations
- Time-based record query

## System Requirements

- Python 3.8+
- TRUF.NETWORK Python SDK
- Active TN node access (local or mainnet)
- Valid stream for data retrieval operations

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

## Implementation Notes

This example utilizes a preconfigured AI Index stream
- Stream parameters should be adjusted to match specific implementation requirements
- Production environments require robust error handling mechanisms
- Prefix functionality is currently supported for `get_record` and `get_index` operations only

## Extension Possibilities
This framework can be extended to:

- Interface with multiple stream sources
- Implement custom time range parameters for record queries
- Integrate advanced data processing and analytics capabilities