from db_utils.init_mysql_db import DB_NAME, TABLE_NAME, get_mysql_server_connection, init_mysql_database
from typing import Dict, Any, List, Optional
import re
import json
from template.db_template import (
    Literature_Metadata_Record,
    Save_Mysql_Info,
)


def _extract_cited_by_total(value: Any) -> Optional[int]:
    try:
        return Literature_Metadata_Record.model_validate({"cited_by": value}).cited_by
    except Exception:
        return None


def safe_parse_summary(summary: Any) -> tuple[str, str, str]:
    if not isinstance(summary, str) or not summary.strip():
        return "Unknown Author", "Unknown Platform", "Unknown Year"

    text = summary.strip()
    parts = [part.strip() for part in text.split(" - ", 2)]

    if len(parts) >= 2:
        author = parts[0] or "Unknown Author"
        platform_year = parts[1]
    else:
        author = text or "Unknown Author"
        platform_year = ""

    year_match = re.search(r"\b(19|20)\d{2}\b", platform_year)
    year = year_match.group(0) if year_match else "Unknown Year"

    if "," in platform_year:
        platform = platform_year.rsplit(",", 1)[0].strip()
    else:
        platform = platform_year.strip()

    if not platform:
        platform = "Unknown Platform"

    return author, platform, year


############################# 标准化元数据记录格式 ########################
def _normalize_metadata_record(record: Dict[str, Any], index: int) -> Literature_Metadata_Record:
    title = str(record.get("title", "") or "").strip()
    if not title:
        title = f"Untitled record #{index}"

    author, platform, year = safe_parse_summary(record.get("summary", ""))

    return Literature_Metadata_Record(
        title=title,
        author=author,
        platform=platform,
        year=year,
        link=record.get("link", ""),
        snippet=record.get("snippet", ""),
        cited_by=_extract_cited_by_total(record.get("cited_by")),
        source=record.get("source", "hiagent"),
        raw_payload=json.dumps(record, ensure_ascii=False),
    )


########################### 存储文献元数据到MySQL数据库的函数 #########################
def save_literature_metadata(payload: Any) -> Save_Mysql_Info:
    # payload可以是一个包含文献记录的列表，或者一个包含字段'literature_search_results'的字典，该字段是一个文献记录列表
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = payload.get("literature_search_results")
    else:
        records = None

    if not isinstance(records, list):
        raise ValueError(
            "payload must be a list or contain a list field named 'literature_search_results'"
        )

    normalized_records: List[Literature_Metadata_Record] = []
    for index, record in enumerate(records, start=1):
        if isinstance(record, dict):
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
            (title, author, platform, year, link, snippet, cited_by, source, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        record.raw_payload,
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
