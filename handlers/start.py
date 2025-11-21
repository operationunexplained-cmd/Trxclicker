# handlers/start.py
from telegram.ext import CommandHandler
from services.db import users
from datetime import datetime

def start(update, context):
    user = update.effective_user
    args = context.args or []
    if users.find_one({"user_id": user.id}) is None:
        users.insert_one({"user_id": user.id, "balances": {}, "ref_by": None, "ref_earnings": 0.0, "created_at": datetime.utcnow()})
    # referral param format: ref<user_id>
    if args:
        token = args[0]
        if token.startswith("ref"):
            try:
                ref_id = int(token[3:])
                if ref_id != user.id:
                    doc = users.find_one({"user_id": user.id})
                    if doc and not doc.get("ref_by"):
                        users.update_one({"user_id": user.id}, {"$set": {"ref_by": ref_id}})
                        users.update_one({"user_id": ref_id}, {"$inc": {"ref_earnings": 0.25}})
                        users.update_one({"user_id": ref_id}, {"$inc": {"balances.TRX": 0.25}})
                        update.message.reply_text("Referral linked. Referrer awarded 0.25 TRX.")
            except:
                pass
    update.message.reply_text("Welcome. Use /wallet to manage funds, /tasks to see tasks, /advertise to create campaigns.")

start_handler = CommandHandler("start", start)