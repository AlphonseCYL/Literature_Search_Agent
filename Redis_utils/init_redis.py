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
REDIS_LIST = os.getenv("REDIS_LIST", "literature_list")

def init_redis_info() -> None:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    if r.ping():  # 测试连接是否成功
        print(f"\n$$$$ SYSTEM CALL $$$$:Redis instance: `{REDIS_HOST}:{REDIS_PORT} DB:{REDIS_DB}` is ready.\n")
    else:
        print(f"\n$$$$ SYSTEM CALL $$$$:Failed to connect to Redis instance\n")