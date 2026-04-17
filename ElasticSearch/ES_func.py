from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

import pymysql
from elasticsearch import Elasticsearch, helpers

from db_utils.init_mysql_db import DB_NAME, TABLE_NAME, get_mysql_server_connection


DEFAULT_ES_INDEX = os.getenv("ES_INDEX_NAME", "literature_metadata_index")
DEFAULT_ES_HOSTS: Sequence[str] = tuple(
    host.strip()
    for host in os.getenv("ELASTICSEARCH_HOSTS", "http://127.0.0.1:9200").split(",")
    if host.strip()
)


def _create_es_client() -> Elasticsearch:
    return Elasticsearch(list(DEFAULT_ES_HOSTS))


def _ensure_index(client: Elasticsearch, index_name: str) -> None:
    if client.indices.exists(index=index_name):
        return

    client.indices.create(
        index=index_name,
        mappings={
            "properties": {
                "mysql_id": {"type": "long"},
                "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "author": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "platform": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "year": {"type": "keyword"},
                "link": {"type": "keyword"},
                "snippet": {"type": "text"},
                "cited_by": {"type": "integer"},
                "source": {"type": "keyword"},
                "raw_payload": {"type": "text"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
            }
        },
    )


def _stream_mysql_rows(source: Optional[str] = None) -> List[Dict[str, Any]]:
    connection = get_mysql_server_connection()
    try:
        connection.select_db(DB_NAME)
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            base_sql = f"""
            SELECT
                id,
                title,
                author,
                platform,
                year,
                link,
                snippet,
                cited_by,
                source,
                raw_payload,
                created_at,
                updated_at
            FROM `{TABLE_NAME}`
            """
            params: List[Any] = []
            if source:
                base_sql += " WHERE source = %s"
                params.append(source)
            cursor.execute(base_sql, params)
            return list(cursor.fetchall())
    finally:
        connection.close()


def _sync_mysql_to_es(
    client: Elasticsearch,
    index_name: str,
    source: Optional[str] = None,
) -> int:
    rows = _stream_mysql_rows(source=source)
    if not rows:
        return 0

    actions = []
    for row in rows:
        mysql_id = row.get("id")
        actions.append(
            {
                "_op_type": "index",
                "_index": index_name,
                "_id": str(mysql_id),
                "_source": {
                    "mysql_id": mysql_id,
                    "title": row.get("title", ""),
                    "author": row.get("author", ""),
                    "platform": row.get("platform", ""),
                    "year": row.get("year", ""),
                    "link": row.get("link", ""),
                    "snippet": row.get("snippet", ""),
                    "cited_by": row.get("cited_by"),
                    "source": row.get("source", ""),
                    "raw_payload": row.get("raw_payload", ""),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                },
            }
        )

    helpers.bulk(client, actions, chunk_size=500, raise_on_error=True)
    client.indices.refresh(index=index_name)
    return len(actions)


def search_mysql_literature_with_es(
    query: str,
    limit: int = 20,
    source: Optional[str] = None,
    index_name: str = DEFAULT_ES_INDEX,
    sync_before_search: bool = True,
) -> Dict[str, Any]:
    cleaned_query = str(query or "").strip()
    if not cleaned_query:
        raise ValueError("query must not be empty")

    try:
        safe_limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc

    client = _create_es_client()
    if not client.ping():
        raise ConnectionError(
            "cannot connect to Elasticsearch. please check ELASTICSEARCH_HOSTS and service status."
        )

    _ensure_index(client, index_name=index_name)

    synced_count = 0
    if sync_before_search:
        synced_count = _sync_mysql_to_es(client, index_name=index_name, source=source)

    filter_clauses: List[Dict[str, Any]] = []
    if source:
        filter_clauses.append({"term": {"source": source}})

    search_body: Dict[str, Any] = {
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": cleaned_query,
                            "fields": [
                                "title^5",
                                "author^3",
                                "platform^2",
                                "snippet^2",
                                "raw_payload",
                            ],
                            "type": "best_fields",
                            "fuzziness": "AUTO",
                        }
                    }
                ],
                "filter": filter_clauses,
            }
        },
        "size": safe_limit,
        "sort": [
            {"_score": {"order": "desc"}},
            {"cited_by": {"order": "desc", "missing": "_last"}},
            {"updated_at": {"order": "desc", "missing": "_last"}},
        ],
    }

    es_resp = client.search(index=index_name, body=search_body)
    hits = es_resp.get("hits", {}).get("hits", [])

    results: List[Dict[str, Any]] = []
    for item in hits:
        source_data = item.get("_source", {})
        results.append(
            {
                "id": source_data.get("mysql_id"),
                "score": item.get("_score"),
                "title": source_data.get("title", ""),
                "author": source_data.get("author", ""),
                "platform": source_data.get("platform", ""),
                "year": source_data.get("year", ""),
                "link": source_data.get("link", ""),
                "snippet": source_data.get("snippet", ""),
                "cited_by": source_data.get("cited_by"),
                "source": source_data.get("source", ""),
                "updated_at": source_data.get("updated_at"),
            }
        )

    total_info = es_resp.get("hits", {}).get("total", {})
    total_value = total_info.get("value", 0) if isinstance(total_info, dict) else 0

    return {
        "query": cleaned_query,
        "index_name": index_name,
        "synced_count": synced_count,
        "returned_count": len(results),
        "total_hits": total_value,
        "results": results,
    }
