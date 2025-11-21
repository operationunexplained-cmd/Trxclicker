# handlers/admin.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler
from services.db import campaigns, withdrawals, users
from datetime import datetime
import json, os

cfg_path = os.getenv("CONFIG_PATH", "config.json")
with open(cfg_path) as f:
    cfg = json.load(f)
ADMIN_IDS = cfg["ADMIN_IDS"]

def is_admin(uid):
    return uid in ADMIN_IDS

def admin_cmd(update, context):
    uid = update.effective_user.id
    if not is_admin(uid):
        update.message.reply_text("Not authorized.")
        return
    kb = [
        [InlineKeyboardButton("Pending Campaigns", callback_data="adm_campaigns")],
        [InlineKeyboardButton("Pending Withdrawals", callback_data="adm_withdrawals")],
        [InlineKeyboardButton("Users (sample)", callback_data="adm_users")]
    ]
    update.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(kb))

def admin_router(update, context):
    q = update.callback_query
    data = q.data
    uid = q.from_user.id
    q.answer()
    if not is_admin(uid):
        return q.edit_message_text("Unauthorized")
    if data == "adm_campaigns":
        pend = list(campaigns.find({"status":"pending"}))
        if not pend:
            return q.edit_message_text("No pending campaigns.")
        out = []
        for p in pend[:10]:
            out.append(f"ID:{p['_id']} Owner:{p['owner_id']} Type:{p['task_type']} CPC:{p['cpc']} Budget:{p['budget']}")
        return q.edit_message_text("\n".join(out))
    if data.startswith("approve_camp::"):
        cid = data.split("::")[1]
        campaigns.update_one({"_id": cid}, {"$set": {"status":"active", "approved_at": datetime.utcnow()}})
        return q.edit_message_text("Approved.")
    if data == "adm_withdrawals":
        pend = list(withdrawals.find({"status":"pending"}))
        if not pend:
            return q.edit_message_text("No pending withdrawals.")
        w = pend[0]
        text = f"Withdraw ID:{w['_id']} User:{w['user_id']} {w['amount']} {w['currency']} Address:{w['address']}"
        kb = [[InlineKeyboardButton("Approve", callback_data=f"wd_ok::{w['_id']}")], [InlineKeyboardButton("Reject", callback_data=f"wd_no::{w['_id']}")]]
        return q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    if data.startswith("wd_ok::"):
        wid = data.split("::")[1]
        withdrawals.update_one({"_id": wid}, {"$set": {"status":"approved", "approved_at": datetime.utcnow()}})
        return q.edit_message_text("Withdrawal approved. Send funds manually from hot wallet.")
    if data == "adm_users":
        docs = list(users.find().limit(20))
        out = []
        for u in docs:
            out.append(f"{u['user_id']} Balances:{u.get('balances')}")
        return q.edit_message_text("\n".join(out))

admin_cmd_handler = CommandHandler("admin", admin_cmd)
admin_cb_handler = CallbackQueryHandler(admin_router, pattern='^adm_')