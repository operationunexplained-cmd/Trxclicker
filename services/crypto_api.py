# services/crypto_api.py
import json, requests, time
from decimal import Decimal
import os

cfg_path = os.getenv("CONFIG_PATH", "config.json")
with open(cfg_path) as f:
    cfg = json.load(f)

GETBLOCK_RPC = cfg["GETBLOCK_TRON_RPC"]
TRX_WALLET = cfg["TRX_WALLET"]
USDT_CONTRACT = cfg.get("USDT_TRC20_CONTRACT")

# Helper: generic JSON-RPC POST to GetBlock (Tron)
def rpc_call(method, params=None):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": int(time.time())
    }
    try:
        r = requests.post(GETBLOCK_RPC, json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        # network or parse errors
        # print("rpc error", e)
        return None

# This retrieves recent transactions for the account using `getaccount`/`gettransactionsrelated` alternative approaches.
# Tron nodes / GetBlock support `trx_getTransactionsRelated` or `eth_getTransactionByHash` like methods — GetBlock maps many.
# Simpler approach: use Tron fullnode HTTP endpoints via GetBlock: method "tron_getTransactionsToAddress" is often supported.
def get_trx_transactions(address, limit=50):
    # Try method name used by some GetBlock Tron endpoints
    res = rpc_call("tron_getTransactionsToAddress", [address, limit])
    if res and "result" in res:
        return res["result"]
    # fallback: try 'getaccount' family - if not supported returns None
    return []

def parse_trx_native_amount(tx):
    # tx likely contains raw_data.contract.parameter.value.amount in sun (1e6)
    try:
        raw = tx.get("raw_data", {})
        for c in raw.get("contract", []):
            value = c.get("parameter", {}).get("value", {})
            if "amount" in value:
                return Decimal(value["amount"]) / Decimal(1_000_000)
    except Exception:
        return None
    return None

# TRC20 detection requires scanning 'log' / 'ret' fields for Transfer events.
def parse_trc20_transfer_amount(tx, contract_address=None):
    # naive: look into 'log' entries or 'raw_data' 'contract' with token transfers; complex in practice
    # This is a skeleton: you must adapt based on actual RPC response structure from GetBlock.
    try:
        logs = tx.get("log", []) or []
        for log in logs:
            # check token transfer topics or contract address
            if contract_address and log.get("address","").lower() == contract_address.lower():
                # parse data field (hex) — value usually last 32 bytes
                data = log.get("data", "")
                if data and len(data) >= 64:
                    val_hex = data[-64:]
                    val = int(val_hex, 16)
                    # token decimals must be considered (USDT on TRON: 6 decimals)
                    return Decimal(val) / Decimal(10**6)
    except Exception:
        return None
    return None