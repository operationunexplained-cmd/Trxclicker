# services/db.py
import os, json
from pymongo import MongoClient

cfg_path = os.getenv("CONFIG_PATH", "config.json")
with open(cfg_path) as f:
    cfg = json.load(f)

client = MongoClient(cfg["MONGO_URI"])
db = client[cfg["DB_NAME"]]

users = db["users"]           # {user_id, balances: {TRX:0,...}, ref_by, ref_earnings, created_at}
campaigns = db["campaigns"]   # campaign docs
user_tasks = db["user_tasks"] # records of completed tasks
deposits = db["deposits"]     # {user_id, currency, amount, txid, status}
withdrawals = db["withdrawals"] # {user_id, currency, amount, address, status}
tx_cache = db["tx_cache"]     # seen txids/logs

# indexes
users.create_index("user_id", unique=True)
campaigns.create_index("status")
tx_cache.create_index("txid", unique=True)
