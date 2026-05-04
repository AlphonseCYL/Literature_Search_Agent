import json
import os
from typing import Any, List, cast

import redis
from schemas.db_template import Literature_Metadata_Record
from schemas.redis_template import Save_To_Redis_Info

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))  # os.getenv返回字符串，需要转换为整数
REDIS_DB = int(os.getenv("REDIS_DB", 0))


# 获取要操作的Redis实例
def get_redis_connection() -> redis.Redis:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    return r


# 存储文献数据到redis列表中，存储格式为JSON字符串
def save_literature_to_redis(list_key: str, metadata_list: list[Any]) -> dict[str, Any]:
    r = get_redis_connection()
    received_cnt = 0
    saved_cnt = 0
    duplicate_cnt = 0

    # 返回列表中所有元素，JSON字符串为元素的列表
    existing_items = r.lrange(list_key, 0, -1)
    existing_set = set()
    for raw_item in existing_items:
        try:
            normalized_item = json.dumps(
                json.loads(raw_item), ensure_ascii=False, sort_keys=True
            )
        except json.JSONDecodeError:
            normalized_item = raw_item
        existing_set.add(normalized_item)

    for item in metadata_list:
        received_cnt += 1

        if isinstance(item, Literature_Metadata_Record):
            item_dict = item.model_dump()
        else:
            # 兼容字典和JSON字符串输入
            if isinstance(item, str):
                item = json.loads(item)
            item_dict = Literature_Metadata_Record.model_validate(item).model_dump()

        item_json = json.dumps(item_dict, ensure_ascii=False, sort_keys=True)

        # 重复数据不存入
        if item_json in existing_set:
            duplicate_cnt += 1
            continue

        r.rpush(list_key, item_json)
        existing_set.add(item_json)
        saved_cnt += 1
    
    # 当当前查询结果全部存入Redis后，后续若其他查询结果也存入列表，则会重置列表
    r.expire(list_key, 600)  # 设置过期时间为600秒（10分钟）

    return Save_To_Redis_Info(
        received_cnt=received_cnt,
        saved_cnt=saved_cnt,
        duplicate_cnt=duplicate_cnt,
        message="literature metadata saved to redis"
    ).model_dump()


# 从redis取得文献元数据
def get_literature_metadata_from_redis(list_key: str) -> List[dict]:
    r = get_redis_connection()
    items_json = r.lrange(list_key, 0, -1)
    # 待返回的文献列表，格式为List[dict]，每个dict符合Literature_Metadata_Record的字段要求
    literature_list = []
    for item_json in items_json:
        try:
            item_dict = json.loads(item_json)
            literature_list.append(Literature_Metadata_Record.model_validate(item_dict).model_dump())
        except json.JSONDecodeError:
            continue
    return literature_list
