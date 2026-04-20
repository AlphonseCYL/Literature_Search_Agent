import redis
import json
import os
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379)) # os.getenv返回字符串，需要转换为整数
REDIS_DB = int(os.getenv("REDIS_DB", 0))

def init_redis_info() -> None:
    print(f"\n$$$$ SYSTEM CALL $$$$:Redis instance: `{REDIS_HOST}:{REDIS_PORT} DB:{REDIS_DB}` is ready.\n")