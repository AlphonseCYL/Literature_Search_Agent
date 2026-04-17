from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pymysql

from db_utils.init_mysql_db import DB_NAME, TABLE_NAME, get_mysql_server_connection


KEYWORD_SPLIT_PATTERN = re.compile(r"[\s,\uFF0C;\uFF1B\u3001]+")


def tokenize_keywords(keyword: str) -> List[str]:
    """将用户的输入拆分成多个关键词，保留原始输入作为最高优先级的短语匹配。"""
    raw_keyword = str(keyword or "").strip()
    if not raw_keyword:
        return []

    terms: List[str] = []
    seen: set[str] = set()

    # 将原始输入作为一个整体短语优先匹配，同时也拆分成多个关键词进行匹配
    for candidate in [raw_keyword, *KEYWORD_SPLIT_PATTERN.split(raw_keyword)]:
        cleaned = candidate.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            terms.append(cleaned)

    return terms


def _escape_like_value(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", r"\%")
        .replace("_", r"\_")
    )


def search_mysql_literature(
    keyword: str,
    limit: int = 20,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search literature records in MySQL by keyword.

    Relevance is estimated by weighted matches across title, author, snippet,
    and raw_payload, with title matches ranked highest.
    """
    terms = tokenize_keywords(keyword)
    if not terms:
        raise ValueError("keyword must not be empty")

    try:
        safe_limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc

    score_clauses: List[str] = []
    score_params: List[Any] = []
    where_clauses: List[str] = []
    where_params: List[Any] = []

    for index, term in enumerate(terms):
        like_pattern = f"%{_escape_like_value(term)}%"
        phrase_boost = 2 if index == 0 and len(terms) > 1 else 1

        score_clauses.extend(
            [
                f"CASE WHEN COALESCE(title, '') LIKE %s ESCAPE '\\' THEN {10 * phrase_boost} ELSE 0 END",
                f"CASE WHEN COALESCE(author, '') LIKE %s ESCAPE '\\' THEN {6 * phrase_boost} ELSE 0 END",
                f"CASE WHEN COALESCE(snippet, '') LIKE %s ESCAPE '\\' THEN {4 * phrase_boost} ELSE 0 END",
                f"CASE WHEN COALESCE(raw_payload, '') LIKE %s ESCAPE '\\' THEN {2 * phrase_boost} ELSE 0 END",
            ]
        )
        score_params.extend([like_pattern, like_pattern, like_pattern, like_pattern])

        where_clauses.append(
            "("
            "COALESCE(title, '') LIKE %s ESCAPE '\\' OR "
            "COALESCE(author, '') LIKE %s ESCAPE '\\' OR "
            "COALESCE(snippet, '') LIKE %s ESCAPE '\\' OR "
            "COALESCE(raw_payload, '') LIKE %s ESCAPE '\\'"
            ")"
        )
        where_params.extend([like_pattern, like_pattern, like_pattern, like_pattern])

    filter_sql = " OR ".join(where_clauses)
    params: List[Any] = [*score_params, *where_params]

    source_filter_sql = ""
    if source:
        source_filter_sql = " AND source = %s"
        params.append(source)

    params.append(safe_limit)

    search_sql = f"""
    SELECT
        id,
        title,
        author,
        link,
        snippet,
        cited_by,
        source,
        raw_payload,
        created_at,
        updated_at,
        ({' + '.join(score_clauses)}) AS relevance_score
    FROM `{TABLE_NAME}`
    WHERE ({filter_sql}){source_filter_sql}
    ORDER BY relevance_score DESC, cited_by DESC, updated_at DESC, id DESC
    LIMIT %s
    """

    connection = get_mysql_server_connection()
    try:
        connection.select_db(DB_NAME)
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(search_sql, params)
            return list(cursor.fetchall())
    finally:
        connection.close()
