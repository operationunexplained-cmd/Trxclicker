# handlers/tasks.py
from telegram.ext import CommandHandler
from services.db import campaigns, user_tasks, users
from services.task_checker import check_join_channel

def tasks_list(update, context):
    uid = update.effective_user.id
    active = list(campaigns.find({"status": "active"}))
    if not active:
        update.message.reply_text("No tasks available.")
        return
    lines = []
    for c in active:
        lines.append(f"ID: {c['_id']} | Type: {c['task_type']} | Reward: {c['cpc']} TRX")
    update.message.reply_text("\n".join(lines))

tasks_handler = CommandHandler("tasks", tasks_list)
