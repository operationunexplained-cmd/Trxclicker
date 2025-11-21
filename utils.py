# utils.py
import uuid
def gen_id(prefix="id"):
    return f"{prefix}_{uuid.uuid4().hex}"