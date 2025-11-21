# handlers/wallet.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from services.db import users, deposits, withdrawals
import json, os

cfg_path = os.getenv("CONFIG_PATH", "config.json")
with open(cfg_path) as f:
    cfg = json.load(f)

TRX_WALLET = cfg["TRX_WALLET"]
DEPOSIT_MIN_TRX = cfg["DEPOSIT_MIN"]["TRX"]
WITHDRAW_MIN_TRX = cfg["WITHDRAW_MIN"]["TRX"]

def wallet_menu(update, context):
    kb = [
        [InlineKeyboardButton("💰 Deposit", callback_data="deposit")],
        [InlineKeyboardButton("💸 Withdrawal", callback_data="withdraw")],
        [InlineKeyboardButton("👛 Balance", callback_data="balance")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ]
    update.message.reply_text("Wallet menu:", reply_markup=InlineKeyboardMarkup(kb))

def wallet_button(update, context):
    q = update.callback_query
    data = q.data
    uid = q.from_user.id
    if data == "deposit":
        text = (f"💰 Deposit\n\nSend TRX (or TRC20 USDT) to:\n`{TRX_WALLET}`\n\nMinimum: {DEPOSIT_MIN_TRX} TRX\nAfter sending, reply here with the TXID (recommended).")
        q.edit_message_text(text, parse_mode="Markdown")
    elif data == "withdraw":
        q.edit_message_text(f"💸 Withdrawal\n\nMinimum: {WITHDRAW_MIN_TRX} TRX\nReply with: `TRX AMOUNT ADDRESS` (example: TRX 250 TCu8...)")
    elif data == "balance":
        doc = users.find_one({"user_id": uid})
        balances = doc.get("balances", {}) if doc else {}
        lines = ["Your balances:"]
        if not balances:
            lines.append("No balances yet.")
        for cur, val in balances.items():
            lines.append(f"{cur}: {val}")
        q.edit_message_text("\n".join(lines))
    else:
        q.edit_message_text("Back to main.")

def handle_text(update, context):
    text = update.message.text.strip()
    uid = update.effective_user.id
    # Check for declared deposit (amount only)
    if text.replace('.', '', 1).isdigit():
        amt = float(text)
        if amt < DEPOSIT_MIN_TRX:
            update.message.reply_text(f"Minimum deposit is {DEPOSIT_MIN_TRX} TRX.")
            return
        deposits.insert_one({"user_id": uid, "currency": "TRX", "amount": amt, "txid": None, "status": "user_declaration"})
        update.message.reply_text("Deposit declared. Reply with TXID if available.")
        return
    # Withdrawal format: CUR AMOUNT ADDRESS
    parts = text.split()
    if len(parts) >= 3:
        cur = parts[0].upper()
        try:
            amount = float(parts[1])
            address = parts[2]
        except:
            update.message.reply_text("Bad format. Use: CUR AMOUNT ADDRESS")
            return
        # check min
        min_map = cfg["WITHDRAW_MIN"].get(cur, None)
        if min_map and amount < min_map:
            update.message.reply_text(f"Minimum withdrawal for {cur} is {min_map}")
            return
        # check balance
        doc = users.find_one({"user_id": uid})
        bal = doc.get("balances", {}).get(cur, 0) if doc else 0
        if amount > bal:
            update.message.reply_text("Insufficient balance.")
            return
        # create withdrawal pending
        withdrawals.insert_one({"user_id": uid, "currency": cur, "amount": amount, "address": address, "status": "pending"})
        users.update_one({"user_id": uid}, {"$inc": {f"balances.{cur}": -amount}})
        update.message.reply_text("Withdrawal request submitted for admin approval.")
        return
    update.message.reply_text("I did not understand. Use the wallet menu.")

wallet_menu_handler = CommandHandler("wallet", wallet_menu)
wallet_cb_handler = CallbackQueryHandler(wallet_button)
wallet_text_handler = MessageHandler(Filters.text & ~Filters.command, handle_text)