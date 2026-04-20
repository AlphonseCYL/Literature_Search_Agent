import redis
import json
from typing import cast
from template.db_template import Literature_Metadata_Record


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

# 获取要操作的Redis实例
def get_redis_connection() -> redis.Redis:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    return r

def save_literature_metadata_to_redis(key: str, metadata: Literature_Metadata_Record) -> None:
    r = get_redis_connection()
    metadata_dict = metadata.model_dump()  # 将Pydantic模型转换为字典，否则redis无法转为JSON格式用于存储Pydantic对象
    r.set(key, json.dumps(metadata_dict, ensure_ascii=False))

def get_literature_metadata_from_redis(key: str) -> Literature_Metadata_Record | None:
    r = get_redis_connection()
    metadata_json = r.get(key)
    if metadata_json is None:
        return None
    try:
        metadata_json = cast(str, metadata_json)# 打上类型注解，告诉MyPy这个值是字符串类型
        metadata_dict = json.loads(metadata_json)
        return Literature_Metadata_Record.model_validate(metadata_dict)
    except json.JSONDecodeError:
        print(f"Error decoding JSON from Redis for key: {key}")
        return None