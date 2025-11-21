# main.py
import os, json, threading, time
from telegram.ext import Updater, CallbackQueryHandler
from handlers.start import start_handler
from handlers.wallet import wallet_menu_handler, wallet_cb_handler, wallet_text_handler
from handlers.advertise import advertise_cmd, adv_cb, adv_conv
from handlers.tasks import tasks_handler
from handlers.admin import admin_cmd_handler, admin_cb_handler
from services.db import tx_cache, deposits, users, campaigns
from services.crypto_api import get_trx_transactions, parse_trx_native_amount
from datetime import datetime

cfg_path = os.getenv("CONFIG_PATH", "config.json")
with open(cfg_path) as f:
    cfg = json.load(f)

BOT_TOKEN = cfg["BOT_TOKEN"]
DEPOSIT_POLL_INTERVAL = cfg.get("DEPOSIT_POLL_INTERVAL", 20)
TRX_WALLET = cfg["TRX_WALLET"]

updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher

# register handlers
dp.add_handler(start_handler)
dp.add_handler(wallet_menu_handler)
dp.add_handler(wallet_cb_handler)
dp.add_handler(wallet_text_handler)
dp.add_handler(advertise_cmd)
dp.add_handler(adv_cb)
dp.add_handler(adv_conv)
dp.add_handler(tasks_handler)
dp.add_handler(admin_cmd_handler)
dp.add_handler(admin_cb_handler)

# Deposit poller thread - TRX only here (you can extend for BTC/ETH)
def deposit_poller():
    while True:
        try:
            txs = get_trx_transactions(TRX_WALLET, limit=50)
            for tx in txs:
                # txid may be in different fields depending on RPC format
                txid = tx.get("txID") or tx.get("tx_id") or tx.get("hash") or tx.get("transaction_id") or tx.get("tx_hash")
                if not txid:
                    continue
                if tx_cache.find_one({"txid": txid}):
                    continue
                amt = parse_trx_native_amount(tx)
                if amt and amt >= cfg["DEPOSIT_MIN"]["TRX"]:
                    deposits.insert_one({"user_id": None, "currency":"TRX", "amount": float(amt), "txid": txid, "status":"pending", "created_at": datetime.utcnow()})
                try:
                    tx_cache.insert_one({"txid": txid, "seen_at": datetime.utcnow()})
                except:
                    pass
        except Exception as e:
            print("Deposit poller error:", e)
        time.sleep(DEPOSIT_POLL_INTERVAL)

t = threading.Thread(target=deposit_poller, daemon=True)
t.start()

updater.start_polling()
updater.idle()