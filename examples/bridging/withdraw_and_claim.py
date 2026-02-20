import os
import sys
import json
import time
import base64
import traceback
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from web3.exceptions import TimeExhausted
from eth_account import Account
from trufnetwork_sdk_py.client import TNClient

def parse_withdrawal_proof(proof):
    """
    Parses the withdrawal proof from the SDK into a format compatible with web3.py.
    
    Args:
        proof (dict): The withdrawal proof object from the SDK.
        
    Returns:
        dict: Parsed proof with hex strings and structured signatures.
    """
    # Convert Base64 block_hash and root to Hex
    block_hash = "0x" + base64.b64decode(proof['block_hash']).hex()
    root = "0x" + base64.b64decode(proof['root']).hex()
    
    # Process signatures
    # The contract expects an array of structs: { uint8 v; bytes32 r; bytes32 s; }
    formatted_signatures = []
    
    # Decode signatures from Base64 list
    raw_signatures = proof.get('signatures', [])
    if raw_signatures:
        for sig_b64 in raw_signatures:
            sig_bytes = base64.b64decode(sig_b64)
            
            if len(sig_bytes) < 65:
                print(f"[!] Warning: Skipping malformed signature (length {len(sig_bytes)})")
                continue

            # Extract r, s, v
            r = "0x" + sig_bytes[:32].hex()
            s = "0x" + sig_bytes[32:64].hex()
            v = sig_bytes[64]
            
            # Adjust v for Ethereum (27/28) if needed
            if v < 27:
                v += 27
                
            formatted_signatures.append({"v": v, "r": r, "s": s})
            
    return {
        "blockHash": block_hash,
        "root": root,
        "signatures": formatted_signatures,
        "recipient": proof['recipient'],
        "amount": int(proof['amount'])
    }

def get_raw_transaction(signed_tx):
    """
    Compatibility helper for getting raw bytes from a signed transaction.
    Works across eth-account versions.
    """
    if hasattr(signed_tx, 'raw_transaction'):
        return signed_tx.raw_transaction
    return signed_tx.rawTransaction

def main():
    print("=" * 60)
    print(" TRUF.NETWORK - Programmatic Withdrawal Lifecycle (TT)")
    print("=" * 60)

    # 1. Configuration
    kwil_endpoint = "https://gateway.testnet.truf.network"
    hoodi_rpc_url = "https://rpc.hoodi.ethpandaops.io"
    
    # Bridge Identifier (hoodi_tt for TRUF/TT)
    bridge_id = "hoodi_tt"
    bridge_escrow_address = Web3.to_checksum_address("0x878d6aaeb6e746033f50b8dc268d54b4631554e7")
    
    # Bot Wallet
    private_key = os.getenv("BOT_PRIVATE_KEY", "<your_private_key_here>")
    if not private_key or private_key == "<your_private_key_here>":
        print("[!] Error: BOT_PRIVATE_KEY environment variable is not set or contains placeholder.")
        sys.exit(1)
    
    # Amount to withdraw (1 TRUF)
    amount_to_withdraw = 1 * 10**18
    amount_str = str(amount_to_withdraw)

    # 2. Initialize Clients
    try:
        # Note: TNClient expects private key without 0x prefix
        kwil_key = private_key[2:] if private_key.startswith("0x") else private_key
        tn_client = TNClient(kwil_endpoint, kwil_key)
        
        w3 = Web3(Web3.HTTPProvider(hoodi_rpc_url))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        if not w3.is_connected():
            print(f"[!] Error: Failed to connect to Hoodi RPC at {hoodi_rpc_url}")
            sys.exit(1)
            
        account = Account.from_key(private_key)
        my_address = account.address
        print(f"[*] Bot Address: {my_address}")
    except (ValueError, KeyError) as e:
        print(f"[!] Configuration error (invalid key format): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Failed to initialize clients: {e}")
        traceback.print_exc()
        sys.exit(1)

    # Load Bridge ABI
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(script_dir, "TrufBridge.json")) as f:
            bridge_abi = json.load(f)
    except (FileNotFoundError, OSError) as e:
        print(f"[!] TrufBridge.json error in script directory: {e}")
        sys.exit(1)
        
    bridge_contract = w3.eth.contract(address=bridge_escrow_address, abi=bridge_abi)

    # 3. Check Kwil Balance
    try:
        kwil_balance = tn_client.get_wallet_balance(bridge_id, my_address)
        print(f"[*] Kwil TT Balance: {int(kwil_balance) / 10**18} TT")
        
        if int(kwil_balance) < amount_to_withdraw:
            print("[!] Insufficient Kwil balance for withdrawal")
            sys.exit(1)
    except (ValueError, RuntimeError) as e:
        print(f"[!] Error in tn_client.get_wallet_balance: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Unexpected error in balance check: {e}")
        traceback.print_exc()
        sys.exit(1)

    # 4. Initiate Withdrawal on Kwil (Burn)
    print("\n[*] Initiating withdrawal of 1.0 TT...")
    try:
        burn_tx = tn_client.withdraw(bridge_id, amount_str, my_address)
        print(f"[+] Burn TX Hash: {burn_tx}")
    except (ValueError, RuntimeError) as e:
        print(f"[!] Error in tn_client.withdraw: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Unexpected error in withdrawal initiation: {e}")
        traceback.print_exc()
        sys.exit(1)

    # 5. Wait for Proof (Polling)
    print("\n[*] Waiting for epoch finalization and proof generation...")
    print("    This typically takes 10-15 minutes on Testnet.")
    
    proof = None
    max_retries = 30 # 30 * 30s = 15 minutes
    
    try:
        for i in range(max_retries):
            print(f"    Polling attempt {i+1}/{max_retries}...", end="\r")
            try:
                # Check history to see status (using larger limit to ensure we find it)
                history = tn_client.get_history(bridge_id, my_address, limit=50)
                # Find our withdrawal
                target_tx = None
                for tx in history:
                    # Robust numeric comparison
                    if int(tx['amount']) == amount_to_withdraw and tx['type'] == 'withdrawal':
                        target_tx = tx
                        break
                
                if target_tx:
                    status = target_tx['status']
                    if status == 'completed': # Ready to claim
                        print("\n[+] Withdrawal ready! Fetching proof...")
                        
                        # Fetch the actual proof data
                        proofs = tn_client.get_withdrawal_proof(bridge_id, my_address)
                        
                        # Find the specific proof matching our criteria
                        for p in proofs:
                            # Match by amount and recipient
                            if int(p['amount']) == amount_to_withdraw and p['recipient'].lower() == my_address.lower():
                                proof = p
                                break
                        
                        if proof:
                            break
                        else:
                            print("\n[!] Withdrawal completed in history, but proof not found in tn_client.get_withdrawal_proof.")
                    elif status == 'claimed':
                        print("\n[!] This withdrawal is already claimed.")
                        return
                
            except (ValueError, RuntimeError) as e:
                print(f"\n[!] Polling error in tn_client methods: {e}")
            except Exception as e:
                print(f"\n[!] Unexpected polling error: {e}")
                
            time.sleep(30) # Poll every 30 seconds
    except KeyboardInterrupt:
        print("\n[!] Polling interrupted by user. Exiting...")
        sys.exit(0)

    if not proof:
        print("\n[!] Timeout or match not found. Check back later.")
        sys.exit(1)

    # 6. Parse and Submit Claim to EVM
    print("\n[*] Proof received. Submitting claim to Hoodi...")
    parsed_proof = parse_withdrawal_proof(proof)
    
    try:
        # Use EIP-1559 gas strategy
        latest_block = w3.eth.get_block('latest')
        base_fee = latest_block.get('baseFeePerGas', 0)
        max_priority_fee = w3.eth.max_priority_fee
        max_fee = (base_fee * 2) + max_priority_fee

        # Contract function: withdraw(recipient, amount, blockHash, root, proofs, signatures)
        tx = bridge_contract.functions.withdraw(
            parsed_proof['recipient'],
            parsed_proof['amount'],
            parsed_proof['blockHash'],
            parsed_proof['root'],
            [], # Empty merkle siblings array
            parsed_proof['signatures']
        ).build_transaction({
            'from': my_address,
            'nonce': w3.eth.get_transaction_count(my_address),
            'maxFeePerGas': max_fee,
            'maxPriorityFeePerGas': max_priority_fee,
            'chainId': w3.eth.chain_id,
        })
        
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(get_raw_transaction(signed_tx))
        
        print(f"[*] Claim TX: {tx_hash.hex()}")
        print("[*] Waiting for confirmation (timeout 300s)...")
        
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            if receipt['status'] == 1:
                print("[+] Withdrawal claimed successfully on Hoodi!")
            else:
                print("[!] Claim transaction failed on-chain (reverted).")
        except TimeExhausted:
            print(f"[!] Error: Transaction receipt timeout for {tx_hash.hex()}. Check explorer.")
            
    except (ValueError, TypeError) as e:
        print(f"[!] Data formatting error in claim submission: {e}")
    except Exception as e:
        print(f"[!] Failed to submit claim transaction: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
