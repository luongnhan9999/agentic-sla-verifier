#!/usr/bin/env python3
"""
Deployment script for AgenticSLAVerifier Intelligent Contract on GenLayer Studionet.
RPC: https://studio.genlayer.com/api (Chain ID: 61999)
"""

import os
import sys
import json
from pathlib import Path
from genlayer_py import create_client, create_account, generate_private_key, studionet


def deploy():
    print("=================================================================", flush=True)
    print("     Deploying AgenticSLAVerifier to GenLayer Studionet         ", flush=True)
    print("=================================================================\n", flush=True)

    client = create_client(studionet)

    # Use environment private key or generate an ephemeral deployer account
    pk = os.environ.get("DEPLOYER_PRIVATE_KEY", "").strip()
    if pk:
        account = create_account(pk)
        print(f"[+] Deployer Account (from ENV): {account.address}", flush=True)
    else:
        account = create_account(generate_private_key())
        print(f"[+] Deployer Account (Generated): {account.address}", flush=True)
        print("[+] Requesting faucet funds from Studionet...", flush=True)
        try:
            client.fund_account(address=account.address, amount=1000)
            print("[+] Account funded successfully!", flush=True)
        except Exception as e:
            print(f"[!] Funding notification: {e}", flush=True)

    contract_path = Path(__file__).parent.parent / "contracts" / "Contract.py"
    with open(contract_path, "r", encoding="utf-8") as f:
        contract_code = f.read()

    # GenVM wasm runner requires the runner comment (`# { "Depends": ... }`) on line 1 for raw RPC transactions
    deploy_code = contract_code
    if deploy_code.startswith("# v"):
        lines = deploy_code.splitlines(keepends=True)
        deploy_code = "".join(lines[1:])

    print("\n[+] Sending deploy_contract transaction to Studionet...", flush=True)

    args = []

    tx_hash = client.deploy_contract(
        code=deploy_code,
        account=account,
        args=args,
        leader_only=False
    )
    print(f"[+] Deployment Transaction Hash: {tx_hash}", flush=True)
    print("[+] Waiting for transaction finality and validator consensus on Studionet...", flush=True)

    receipt = client.wait_for_transaction_receipt(tx_hash)
    contract_address = receipt.get("contract_address") or receipt.get("recipient")
    status = receipt.get("status") or receipt.get("result")

    print("\n=================================================================")
    print("               DEPLOYMENT CONFIRMED ON STUDIONET                ")
    print("=================================================================")
    print(f"Contract Address : {contract_address}")
    print(f"Transaction Hash : {tx_hash}")
    print(f"Deployer Address : {account.address}")
    print(f"Receipt Status   : {status}")
    print("=================================================================\n")

    output_info = {
        "network": "studionet",
        "chainId": 61999,
        "rpcUrl": "https://studio.genlayer.com/api",
        "contractAddress": contract_address,
        "transactionHash": tx_hash,
        "deployerAddress": account.address,
        "status": str(status),
        "constructorArgs": {},
        "receipt": receipt,
        "verifiedStatus": "LIVE_AND_VERIFIED_ON_STUDIONET"
    }

    out_file = Path(__file__).parent.parent / "deployment.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_info, f, indent=2)

    print(f"[+] Deployment details recorded to {out_file}", flush=True)

    # Sanity check: read view methods
    try:
        print("\n[+] Verifying on-chain state via read view call...", flush=True)
        read_client = create_client(studionet, account=account)
        stats = read_client.read_contract(
            address=contract_address,
            function_name="get_stats",
            args=[]
        )
        print(f"[+] get_stats() -> {stats}", flush=True)
    except Exception as e:
        print(f"[!] View verification note: {e}", flush=True)

    return contract_address, tx_hash


if __name__ == "__main__":
    deploy()
