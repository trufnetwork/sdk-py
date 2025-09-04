# Transaction Lifecycle Example

This example demonstrates best practices for handling transaction lifecycles in the TRUF.NETWORK Python SDK using `wait_for_tx()` to avoid race conditions and ensure reliable sequential operations.

## Problem Statement

By default, SDK methods return success when transactions are submitted to the mempool, NOT when they're executed on-chain. This can cause race conditions in sequential workflows:

```python
# ⚠️ DANGEROUS: Race condition possible
client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)  # Returns immediately
client.insert_record(stream_id, record)  # May fail if deployment not complete
```

## Solution

Use `wait_for_tx()` to wait for on-chain confirmation:

```python
# ✅ SAFE: Wait for confirmation
tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
client.wait_for_tx(tx_hash)  # Wait for confirmation
client.insert_record(stream_id, record)  # Now guaranteed to succeed
```

## Running the Example

### Prerequisites

1. **Python 3.8+** and the TRUF.NETWORK Python SDK installed
2. **Private key** for transaction signing
3. **Network access** to TRUF.NETWORK mainnet or local node

### Setup

1. **Install the SDK** (if not already installed):
   ```bash
   pip install https://github.com/trufnetwork/sdk-py/releases/download/v0.3.2/trufnetwork_sdk_py-0.3.2-py3-none-manylinux_2_28_x86_64.whl
   ```

2. **Update the private key** in `main.py`:
   ```python
   # Replace this placeholder with your actual private key
   private_key = "YOUR_PRIVATE_KEY_HERE"
   ```

3. **Run the example**:
   ```bash
   python main.py
   ```

### For Local Node Testing

If you want to test against a local node instead of mainnet:

1. **Start a local node** (see [Local Node Setup](../../README.md#local-node-testing-and-development))

2. **Update the endpoint** in `main.py`:
   ```python
   endpoint = "http://localhost:8484"  # Local node
   ```

## What the Example Demonstrates

### 1. Safe Stream Deployment
- Uses `deploy_stream()` + `wait_for_tx()` to wait for on-chain confirmation
- Proper error handling with try/catch blocks
- Shows transaction hash and confirmation process

### 2. Record Insertion
- Shows how `insert_record()` has built-in confirmation
- Demonstrates inserting multiple records safely
- Error handling for failed insertions

### 3. Record Verification
- Retrieves and displays inserted records
- Shows how to use date ranges for queries
- Confirms data integrity after operations

### 4. Safe Stream Destruction
- Uses `destroy_stream()` + `wait_for_tx()` to wait for confirmation
- Verifies destruction by testing failed operations
- Demonstrates proper cleanup patterns

## Key Learning Points

### Transaction Lifecycle Pattern

```python
# The safe pattern for all lifecycle operations
tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
client.wait_for_tx(tx_hash)  # Wait for confirmation

tx_hash = client.destroy_stream(stream_id)
client.wait_for_tx(tx_hash)  # Wait for confirmation
```

### Error Handling Best Practices

```python
try:
    tx_hash = client.deploy_stream(stream_id, STREAM_TYPE_PRIMITIVE)
    client.wait_for_tx(tx_hash)
    print("✅ Stream deployed successfully")
except Exception as e:
    print(f"❌ Deployment failed: {e}")
```

### Race Condition Prevention

1. **Use `wait_for_tx()` for lifecycle operations** (deploy/destroy)
2. **Wait for confirmation before dependent operations**
3. **Test sequential workflows** to catch timing issues
4. **Verify operations completed** before proceeding

## Expected Output

When you run the example successfully, you should see:

```
🔄 Transaction Lifecycle Best Practices Demo
==================================================
Stream ID: st_generated_stream_id
Endpoint: https://gateway.mainnet.truf.network
Data Provider: 0x...

📋 EXAMPLE 1: Safe Stream Deployment
----------------------------------------
📝 Deploying stream...
   Deployment submitted: 0xabc123...
   ⏳ Waiting for deployment to be mined...
✅ Stream deployed and confirmed on-chain

📋 EXAMPLE 2: Record Insertion
----------------------------------------
📝 Inserting record 1...
   ✅ Record 1 inserted: 123.45
📝 Inserting record 2...
   ✅ Record 2 inserted: 456.78
📝 Inserting record 3...
   ✅ Record 3 inserted: 789.01

📋 EXAMPLE 3: Verify Records After Insertion
----------------------------------------
✅ Retrieved 3 records from stream:
   Record 1: 123.45 (Time: 2025-09-04 18:30:00)
   Record 2: 456.78 (Time: 2025-09-04 18:30:01)
   Record 3: 789.01 (Time: 2025-09-04 18:30:02)

📋 EXAMPLE 4: Safe Stream Destruction with Verification
------------------------------------------------------
🗑️  Destroying stream...
   Destruction submitted: 0xdef456...
   ⏳ Waiting for destruction to be mined...
✅ Stream destroyed and confirmed on-chain
🧪 Testing insertion after destruction...
✅ PERFECT: Insertion failed as expected after destruction
   Error: stream not found...
🧪 Testing record retrieval after destruction...
✅ PERFECT: Record retrieval failed as expected
   Error: stream not found...

📚 KEY TAKEAWAYS:
============================================================
✅ Use wait_for_tx() for DeployStream and DestroyStream
✅ insert_record() has built-in confirmation for data integrity
✅ Always use try/catch blocks for proper error handling
✅ Verify operations completed before proceeding with dependent actions
⚠️  Async operations can cause race conditions in sequential workflows
```

## Troubleshooting

### Common Issues

1. **"Stream not found" during insertion**
   - **Cause**: Race condition - deployment not complete
   - **Solution**: Use `wait_for_tx()` after `deploy_stream()`

2. **"Permission denied" errors**
   - **Cause**: Account lacks `system:network_writer` role
   - **Solution**: Contact TRUF.NETWORK team for role assignment

3. **Network connection errors**
   - **Cause**: Endpoint unreachable or invalid private key
   - **Solution**: Check endpoint URL and private key validity

### Testing with Different Networks

- **Mainnet**: `https://gateway.mainnet.truf.network`
- **Local Node**: `http://localhost:8484` (after starting local node)

## Next Steps

After understanding transaction lifecycles:

1. **Explore the [Complex Example](../complex_example/)** for advanced stream management
2. **Read the [API Reference](../../docs/api-reference.md)** for complete method documentation
3. **Check out [Custom Procedures](../custom_procedure_example/)** for advanced functionality

## Related Documentation

- [Main README - Transaction Lifecycle Section](../../README.md#understanding-transaction-lifecycle)
- [API Reference - Transaction Management](../../docs/api-reference.md#transaction-management)
- [Go SDK Transaction Lifecycle Example](https://github.com/trufnetwork/sdk-go/tree/main/examples/transaction-lifecycle-example) (reference implementation)