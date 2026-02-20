# Programmatic Bridging Examples

This directory contains examples for programmatically bridging assets between the TRUF.NETWORK (Kwil) and Ethereum (Hoodi Testnet) using the Python SDK.

## Prerequisites

1.  **Install Dependencies**: These examples require the `web3` library to interact with Ethereum.
    ```bash
    pip install web3
    ```

2.  **SDK Installation**: Ensure `trufnetwork-sdk-py` is installed in your environment.

## Configuration

Both scripts require a funded Ethereum wallet private key.

1.  Open the script you want to run (`deposit_tt.py` or `withdraw_and_claim.py`).
2.  Locate the `private_key` variable.
3.  Replace the placeholder with your actual private key (hex string, with or without `0x`).

**⚠️ SECURITY WARNING**: Never commit your private key to version control. Use environment variables for production applications.

## Examples

### 1. Depositing Tokens (`deposit_tt.py`)

This script demonstrates how to bridge ERC20 tokens (TT) from Ethereum (Hoodi) to Kwil.

**Actions performed:**
1.  Connects to Hoodi Testnet RPC.
2.  Checks balances (ETH and TT).
3.  Approves the Bridge Escrow contract to spend your tokens.
4.  Calls `deposit()` on the bridge contract.

**Usage:**
```bash
python deposit_tt.py
```

### 2. Withdrawing Tokens (`withdraw_and_claim.py`)

This script demonstrates the full withdrawal lifecycle: burning tokens on Kwil and claiming them on Ethereum.

**Actions performed:**
1.  Connects to Kwil Gateway and Hoodi RPC.
2.  Initiates a withdrawal on Kwil (burns tokens).
3.  **Polls** the bridge history until the withdrawal status is `completed` (this waits for the epoch to finalize).
4.  Fetches the cryptographic **Withdrawal Proof** from the Kwil node.
5.  Submits the proof to the Ethereum bridge contract to claim the funds.

**Usage:**
```bash
python withdraw_and_claim.py
```

> **Note:** Withdrawal finalization depends on the epoch duration and can take 10-15 minutes on testnet. The script handles the polling automatically.
