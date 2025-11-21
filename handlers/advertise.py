# handlers/advertise.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters
from services.db import campaigns, users
from datetime import datetime
import json, os

cfg_path = os.getenv("CONFIG_PATH", "config.json")
with open(cfg_path) as f:
    cfg = json.load(f)

CPC_MIN = cfg["CPC_MIN"]
CPC_MAX = cfg["CPC_MAX"]
CAMPAIGN_MIN = cfg["CAMPAIGN_MIN_BUDGET"]
ADMIN_IDS = cfg["ADMIN_IDS"]

CHOOSING, WAIT_TARGET, WAIT_CPC, WAIT_BUDGET, CONFIRM = range(5)

def advertise_menu(update, context):
    kb = [
        [InlineKeyboardButton("📢 Create Campaign", callback_data="create_campaign")],
        [InlineKeyboardButton("📋 My Campaigns", callback_data="my_campaigns")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ]
    update.message.reply_text("Advertise menu:", reply_markup=InlineKeyboardMarkup(kb))

def advertise_cb(update, context):
    q = update.callback_query
    d = q.data
    if d == "create_campaign":
        kb = [
            [InlineKeyboardButton("➕ Join Channel", callback_data="t_join_channel")],
            [InlineKeyboardButton("➕ Join Group", callback_data="t_join_group")],
            [InlineKeyboardButton("🤖 Start Bot", callback_data="t_start_bot")],
            [InlineKeyboardButton("🔗 Visit Link", callback_data="t_visit_link")],
            [InlineKeyboardButton("⬅️ Cancel", callback_data="cancel")]
        ]
        q.edit_message_text("Choose type:", reply_markup=InlineKeyboardMarkup(kb))
        return CHOOSING
    if d == "my_campaigns":
        uid = q.from_user.id
        docs = list(campaigns.find({"owner_id": uid}))
        if not docs:
            q.edit_message_text("No campaigns.")
            return
        out = []
        for c in docs:
            out.append(f"ID:{c['_id']} Type:{c['task_type']} CPC:{c['cpc']} Budget:{c['budget']} Status:{c['status']}")
        q.edit_message_text("\n".join(out))
        return
    q.edit_message_text("Cancelled.")
    return ConversationHandler.END

def type_selected(update, context):
    q = update.callback_query
    mapping = {
        "t_join_channel": "join_channel",
        "t_join_group": "join_group",
        "t_start_bot": "start_bot",
        "t_visit_link": "visit_link"
    }
    context.user_data['cam'] = {"task_type": mapping.get(q.data)}
    q.edit_message_text("Send the target link (t.me or https://):")
    return WAIT_TARGET

def receive_target(update, context):
    text = update.message.text.strip()
    context.user_data['cam']['target'] = text
    update.message.reply_text(f"Got: {text}\nNow enter CPC per completion (TRX). Min {CPC_MIN}, Max {CPC_MAX}")
    return WAIT_CPC

def receive_cpc(update, context):
    try:
        cpc = float(update.message.text.strip())
    except:
        update.message.reply_text("Invalid number.")
        return WAIT_CPC
    if cpc < CPC_MIN or cpc > CPC_MAX:
        update.message.reply_text("CPC out of range.")
        return WAIT_CPC
    context.user_data['cam']['cpc'] = cpc
    update.message.reply_text(f"CPC set to {cpc}. Now enter total budget (TRX), minimum {CAMPAIGN_MIN}")
    return WAIT_BUDGET

def receive_budget(update, context):
    try:
        budget = float(update.message.text.strip())
    except:
        update.message.reply_text("Invalid budget.")
        return WAIT_BUDGET
    if budget < CAMPAIGN_MIN:
        update.message.reply_text("Budget too small.")
        return WAIT_BUDGET
    uid = update.effective_user.id
    doc = users.find_one({"user_id": uid})
    bal = doc.get("balances", {}).get("TRX", 0) if doc else 0
    if budget > bal:
        update.message.reply_text(f"Insufficient balance: {bal}")
        return WAIT_BUDGET
    camp = context.user_data['cam']
    camp['budget'] = budget
    camp['slots'] = int(budget // camp['cpc'])
    camp['owner_id'] = uid
    camp['status'] = 'pending'
    camp['created_at'] = datetime.utcnow()
    summary = f"Summary:\nType:{camp['task_type']}\nTarget:{camp['target']}\nCPC:{camp['cpc']}\nBudget:{camp['budget']}\nSlots:{camp['slots']}\n\nConfirm?"
    kb = [[InlineKeyboardButton("✅ Confirm", callback_data="confirm")], [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(kb))
    return CONFIRM

def confirm_campaign(update, context):
    q = update.callback_query
    uid = q.from_user.id
    camp = context.user_data.get('cam')
    if not camp:
        q.edit_message_text("No campaign data.")
        return ConversationHandler.END
    # debit balance (lock funds)
    users.update_one({"user_id": uid}, {"$inc": {"balances.TRX": -camp['budget']}}, upsert=True)
    campaigns.insert_one(camp)
    # notify admins
    for aid in ADMIN_IDS:
        try:
            context.bot.send_message(aid, f"New campaign pending approval. Owner: {uid} Type: {camp['task_type']} CPC:{camp['cpc']} Budget:{camp['budget']}")
        except:
            pass
    q.edit_message_text("Submitted for admin review.")
    return ConversationHandler.END

def cancel(update, context):
    update.callback_query.edit_message_text("Canceled.")
    return ConversationHandler.END

advertise_cmd = CommandHandler("advertise", advertise_menu)
adv_cb = CallbackQueryHandler(advertise_cb, pattern='^(create_campaign|my_campaigns|back_main)$')
from telegram.ext import ConversationHandler
adv_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(type_selected, pattern='^t_')],
    states={
        WAIT_TARGET: [MessageHandler(Filters.text & ~Filters.command, receive_target)],
        WAIT_CPC: [MessageHandler(Filters.text & ~Filters.command, receive_cpc)],
        WAIT_BUDGET: [MessageHandler(Filters.text & ~Filters.command, receive_budget)],
        CONFIRM: [CallbackQueryHandler(confirm_campaign, pattern='^confirm$'), CallbackQueryHandler(cancel, pattern='^cancel$')]
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern='^cancel$')]
)