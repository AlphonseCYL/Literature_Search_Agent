from db_utils.init_mysql_db import DB_NAME, TABLE_NAME, get_mysql_server_connection, init_mysql_database
from typing import Dict, Any, List, Optional
import re
import json
from schemas.db_template import (
    Literature_Metadata_DB,
    Literature_Metadata_Record,
    Save_Mysql_Info,
)


############################# 标准化元数据记录格式 ########################
def _normalize_metadata_record(record: Dict[str, Any], index: int) -> Literature_Metadata_Record:
    title = record.get("title", "")
    if not title:
        record["title"] = f"Untitled record #{index}"

    return Literature_Metadata_Record(**record)


########################### 存储文献元数据到MySQL数据库的函数同步双写到ES #########################
def save_literature_metadata(payload: List[Any]) -> Save_Mysql_Info:
    # payload是一个包含文献记录的列表
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):# 保险处理
        records = payload.get("literature_search_results")
    else:
        records = None
    if not isinstance(records, list):
        raise ValueError(
            "payload must be a list or contain a list field named 'literature_search_results'"
        )

    normalized_records: List[Literature_Metadata_Record] = []
    for index, record in enumerate(records, start=1):
        if isinstance(record, Literature_Metadata_Record):
            normalized_records.append(record)
        elif isinstance(record, dict):
            normalized_records.append(_normalize_metadata_record(record, index))

    if not normalized_records:
        return Save_Mysql_Info(
            saved_count=0,
            received_count=0,
            duplicate_count=0,
            message="no valid literature records to save",
        )

    connection = get_mysql_server_connection()
    saved_count = 0
    try:
        connection.select_db(DB_NAME)
        with connection.cursor() as cursor:
            insert_sql_cmd = f"""
            INSERT IGNORE INTO `{TABLE_NAME}`
            (title, author, platform, year, link, snippet, cited_by, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            for record in normalized_records:
                cursor.execute(
                    insert_sql_cmd,
                    (
                        record.title,
                        record.author,
                        record.platform,
                        record.year,
                        record.link,
                        record.snippet,
                        record.cited_by,
                        record.source,
                    ),
                )
                if cursor.rowcount == 1:
                    saved_count += 1

        connection.commit()

    finally:
        connection.close()

    return Save_Mysql_Info(
        saved_count=saved_count,
        received_count=len(normalized_records),
        duplicate_count=len(normalized_records) - saved_count,
        message="literature metadata saved to mysql database",
    )
