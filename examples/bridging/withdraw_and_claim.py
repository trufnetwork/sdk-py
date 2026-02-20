import os
import sys
import json
import time
import base64
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
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
            
            # Extract r, s, v
            r = "0x" + sig_bytes[:32].hex()
            s = "0x" + sig_bytes[32:64].hex()
            v = sig_bytes[64]
            
            # Adjust v for Ethereum (27/28) if needed, though usually standard 0/1 for some bridges
            # The frontend logic uses raw v, r, s. Let's stick to standard EVM recovery id if needed.
            # Kwil usually returns standard 65-byte signatures.
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
    private_key = "<your_private_key_here>"  # Replace with your bot's private key
    
    # Amount to withdraw (1 TRUF)
    amount_to_withdraw = 1 * 10**18
    amount_str = str(amount_to_withdraw)

    # 2. Initialize Clients
    # Note: TNClient expects private key without 0x prefix
    kwil_key = private_key[2:] if private_key.startswith("0x") else private_key
    tn_client = TNClient(kwil_endpoint, kwil_key)
    
    w3 = Web3(Web3.HTTPProvider(hoodi_rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    account = w3.eth.account.from_key(private_key)
    my_address = account.address
    print(f"[*] Bot Address: {my_address}")

    # Load Bridge ABI
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(script_dir, "TrufBridge.json")) as f:
            bridge_abi = json.load(f)
    except FileNotFoundError:
        print("[!] TrufBridge.json not found.")
        sys.exit(1)
        
    bridge_contract = w3.eth.contract(address=bridge_escrow_address, abi=bridge_abi)

    # 3. Check Kwil Balance
    # Note: get_wallet_balance returns a string (wei)
    try:
        kwil_balance = tn_client.get_wallet_balance(bridge_id, my_address)
        print(f"[*] Kwil TT Balance: {int(kwil_balance) / 10**18} TT")
        
        if int(kwil_balance) < amount_to_withdraw:
            print("[!] Insufficient Kwil balance for withdrawal")
            sys.exit(1)
    except Exception as e:
        print(f"[!] Failed to get Kwil balance: {e}")
        sys.exit(1)

    # 4. Initiate Withdrawal on Kwil (Burn)
    print(f"\n[*] Initiating withdrawal of {amount_to_withdraw / 10**18} TT...")
    try:
        burn_tx = tn_client.withdraw(bridge_id, amount_str, my_address)
        print(f"[+] Burn TX Hash: {burn_tx}")
    except Exception as e:
        print(f"[!] Withdrawal failed: {e}")
        sys.exit(1)

    # 5. Wait for Proof (Polling)
    print("\n[*] Waiting for epoch finalization and proof generation...")
    print("    This typically takes 10-15 minutes on Testnet.")
    
    proof = None
    max_retries = 30 # 30 * 30s = 15 minutes
    
    for i in range(max_retries):
        print(f"    Polling attempt {i+1}/{max_retries}...", end="\r")
        try:
            # Check history to see status
            history = tn_client.get_history(bridge_id, my_address, 5, 0)
            # Find our withdrawal (most recent matching amount)
            target_tx = None
            for tx in history:
                # Basic matching logic: Same amount, status logic
                if tx['amount'] == amount_str and tx['type'] == 'withdrawal':
                    target_tx = tx
                    break
            
            if target_tx:
                status = target_tx['status']
                if status == 'completed': # Ready to claim
                    print(f"\n[+] Withdrawal ready! Fetching proof...")
                    
                    # Fetch the actual proof data
                    # get_withdrawal_proof returns an ARRAY of proofs for all unclaimed withdrawals
                    proofs = tn_client.get_withdrawal_proof(bridge_id, my_address)
                    
                    if proofs and len(proofs) > 0:
                        # Find the specific proof matching our amount/time if needed
                        # For simplicity, we grab the first one (LIFO/FIFO depends on implementation)
                        proof = proofs[0] 
                        break
                elif status == 'claimed':
                    print(f"\n[!] This withdrawal is already claimed.")
                    return
            
        except Exception as e:
            pass # Ignore transient errors during polling
            
        time.sleep(30) # Poll every 30 seconds

    if not proof:
        print("[!] Timeout waiting for proof. Check back later.")
        sys.exit(1)

    # 6. Parse and Submit Claim to EVM
    print(f"\n[*] Proof received. Submitting claim to Hoodi...")
    parsed_proof = parse_withdrawal_proof(proof)
    
    try:
        # Contract function: withdraw(recipient, amount, blockHash, root, proofs, signatures)
        # Note: 'proofs' arg is for merkle siblings, often empty for this bridge implementation
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
            'gasPrice': w3.eth.gas_price,
        })
        
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"[*] Claim TX: {tx_hash.hex()}")
        print("[*] Waiting for confirmation...")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt['status'] == 1:
            print("[+] Withdrawal claimed successfully on Hoodi!")
        else:
            print("[!] Claim transaction failed on-chain.")
            
    except Exception as e:
        print(f"[!] Failed to submit claim transaction: {e}")

if __name__ == "__main__":
    main()
