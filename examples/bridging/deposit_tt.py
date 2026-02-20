import os
import sys
import json
import time
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

def main():
    print("=" * 60)
    print(" TRUF.NETWORK - Programmatic Deposit Example (TT)")
    print("=" * 60)

    # 1. Configuration
    # Hoodi RPC URL (public endpoint)
    rpc_url = "https://rpc.hoodi.ethpandaops.io" 
    
    # Contract Addresses (Hoodi Testnet)
    tt_token_address = Web3.to_checksum_address("0x263ce78fef26600e4e428cebc91c2a52484b4fbf")
    bridge_escrow_address = Web3.to_checksum_address("0x878d6aaeb6e746033f50b8dc268d54b4631554e7")
    
    # Bot Wallet
    private_key = "<your_private_key_here>"  # Replace with your bot's private key
    
    # Amount to deposit (2 TRUF)
    amount_to_deposit = 2 * 10**18 

    # 2. Initialize Web3
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    # Inject PoA middleware for Hoodi network
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3.is_connected():
        print("[!] Failed to connect to Hoodi RPC")
        sys.exit(1)

    account = w3.eth.account.from_key(private_key)
    my_address = account.address
    print(f"[*] Bot Address: {my_address}")
    
    # Load ABIs
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(script_dir, "TrufBridge.json")) as f:
            bridge_abi = json.load(f)
        with open(os.path.join(script_dir, "ERC20.json")) as f:
            token_abi = json.load(f)
    except FileNotFoundError:
        print("[!] ABIs not found. Ensure TrufBridge.json and ERC20.json are in this directory.")
        sys.exit(1)

    # Initialize Contracts
    token_contract = w3.eth.contract(address=tt_token_address, abi=token_abi)
    bridge_contract = w3.eth.contract(address=bridge_escrow_address, abi=bridge_abi)

    # 3. Check Balances
    balance_wei = token_contract.functions.balanceOf(my_address).call()
    eth_balance = w3.eth.get_balance(my_address)
    
    print(f"[*] TT Balance:  {balance_wei / 10**18} TT")
    print(f"[*] ETH Balance: {w3.from_wei(eth_balance, 'ether')} ETH")

    if balance_wei < amount_to_deposit:
        print("[!] Insufficient TT balance for deposit")
        sys.exit(1)

    # 4. Approve Tokens
    # Check allowance first
    allowance = token_contract.functions.allowance(my_address, bridge_escrow_address).call()
    if allowance < amount_to_deposit:
        print(f"[*] Approving {amount_to_deposit / 10**18} TT for bridge...")
        
        tx = token_contract.functions.approve(
            bridge_escrow_address, 
            amount_to_deposit
        ).build_transaction({
            'from': my_address,
            'nonce': w3.eth.get_transaction_count(my_address),
            'gasPrice': w3.eth.gas_price,
        })
        
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"[*] Approval TX: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash)
        print("[+] Approval confirmed")
    else:
        print("[*] Allowance sufficient")

    # 5. Execute Deposit
    print(f"[*] Depositing {amount_to_deposit / 10**18} TT to bridge...")
    
    # deposit(amount, recipient)
    tx = bridge_contract.functions.deposit(
        amount_to_deposit,
        my_address  # Recipient on Kwil is same as sender
    ).build_transaction({
        'from': my_address,
        'nonce': w3.eth.get_transaction_count(my_address),
        'gasPrice': w3.eth.gas_price,
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    print(f"[*] Deposit TX: {tx_hash.hex()}")
    print("[*] Waiting for confirmation...")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt['status'] == 1:
        print("[+] Deposit successful! Kwil balance should update shortly.")
    else:
        print("[!] Deposit transaction failed")

if __name__ == "__main__":
    main()
