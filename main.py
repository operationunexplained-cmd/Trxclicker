import os
import json
import threading
import time
from datetime import datetime
from pymongo import MongoClient
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ------------------------
# Load config
# ------------------------
cfg_path = os.getenv("CONFIG_PATH", "config.json")
with open(cfg_path) as f:
    cfg = json.load(f)

API_TOKEN = cfg["BOT_TOKEN"]
DEPOSIT_POLL_INTERVAL = cfg.get("DEPOSIT_POLL_INTERVAL", 20)
TRX_WALLET = cfg["TRX_WALLET"]
DEPOSIT_MIN = cfg["DEPOSIT_MIN"]["TRX"]

# ------------------------
# MongoDB Setup
# ------------------------
mongo_uri = cfg.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(mongo_uri)
db = client["trxclicker"]
users_col = db["users"]
deposits_col = db["deposits"]
tx_cache_col = db["tx_cache"]

# ------------------------
# Initialize bot
# ------------------------
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ------------------------
# Inline Keyboard
# ------------------------
main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="💻 Visit website", callback_data="visit"),
        InlineKeyboardButton(text="🤖 Message", callback_data="message"),
    ],
    [
        InlineKeyboardButton(text="📢 Join channel", callback_data="join"),
        InlineKeyboardButton(text="😅 More", callback_data="more"),
    ],
    [
        InlineKeyboardButton(text="💰 Balance", callback_data="balance"),
        InlineKeyboardButton(text="👥 Referral", callback_data="referral"),
    ],
    [
        InlineKeyboardButton(text="📊 Advertise", callback_data="advertise"),
    ]
])

# ------------------------
# Start command
# ------------------------
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({
            "user_id": user_id,
            "balance": 0.0,
            "created_at": datetime.utcnow()
        })
    await message.answer("Welcome to TRX Clicker Bot! Choose an option:", reply_markup=main_menu)

# ------------------------
# Callback handler
# ------------------------
@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if data == "visit":
        await bot.send_message(user_id, "Visit our website: https://example.com")
    elif data == "message":
        await bot.send_message(user_id, "Send your message here.")
    elif data == "join":
        await bot.send_message(user_id, "Join our channel: t.me/YourChannel")
    elif data == "more":
        await bot.send_message(user_id, "More options coming soon!")
    elif data == "balance":
        user = users_col.find_one({"user_id": user_id})
        balance = user.get("balance", 0) if user else 0
        await bot.send_message(user_id, f"Your balance is: {balance} TRX")
    elif data == "referral":
        referral_link = f"https://t.me/YourBot?start={user_id}"
        await bot.send_message(user_id, f"Your referral link: {referral_link}")
    elif data == "advertise":
        await bot.send_message(user_id, "Advertise with us! Contact admin.")

    await callback_query.answer()

# ------------------------
# TRX Deposit Poller
# ------------------------
def get_trx_transactions(wallet_address, limit=50):
    """
    Placeholder for TRX API call.
    Replace this with actual API that returns a list of dicts like:
    [{"txID": "...", "amount": 1000000, "from": "...", "memo": user_id}]
    """
    return []

def parse_trx_native_amount(tx):
    """
    Convert TRX amount from SUN to TRX
    """
    amt_sun = tx.get("amount", 0)
    return amt_sun / 1_000_000

def deposit_poller():
    while True:
        try:
            txs = get_trx_transactions(TRX_WALLET, limit=50)
            for tx in txs:
                txid = tx.get("txID") or tx.get("tx_id") or tx.get("hash") or tx.get("transaction_id") or tx.get("tx_hash")
                if not txid:
                    continue
                if tx_cache_col.find_one({"txid": txid}):
                    continue

                amt = parse_trx_native_amount(tx)
                if amt >= DEPOSIT_MIN:
                    # Extract user_id from memo or other method
                    user_id = tx.get("memo")  # You need to instruct users to send their user_id in memo
                    if user_id and users_col.find_one({"user_id": int(user_id)}):
                        users_col.update_one({"user_id": int(user_id)}, {"$inc": {"balance": amt}})
                        deposits_col.insert_one({
                            "user_id": int(user_id),
                            "amount": amt,
                            "txid": txid,
                            "status": "completed",
                            "created_at": datetime.utcnow()
                        })
                        print(f"Credited {amt} TRX to user {user_id}, txid: {txid}")
                    else:
                        deposits_col.insert_one({
                            "user_id": None,
                            "amount": amt,
                            "txid": txid,
                            "status": "pending",
                            "created_at": datetime.utcnow()
                        })
                        print(f"Deposit detected with unknown user, txid: {txid}, amount: {amt} TRX")

                tx_cache_col.insert_one({"txid": txid, "seen_at": datetime.utcnow()})
        except Exception as e:
            print("Deposit poller error:", e)
        time.sleep(DEPOSIT_POLL_INTERVAL)

# Start poller thread
t = threading.Thread(target=deposit_poller, daemon=True)
t.start()

# ------------------------
# Run bot
# ------------------------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
