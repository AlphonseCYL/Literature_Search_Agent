from __future__ import annotations

import copy
import os
import re
import time
from typing import Any, Optional, Sequence, List

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
from schemas.db_template import Literature_Metadata_DB, Literature_Metadata_Record
from utils import handle_query, singleton
from db_utils.init_mysql_db import DB_NAME, TABLE_NAME, get_mysql_server_connection
from ElasticSearch.embedding_service import EMBEDDING_DIMS, embed_literature_fields, embed_text

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


if load_dotenv:
    load_dotenv()

DEFAULT_ES_INDEX = os.getenv("ES_INDEX_NAME") or os.getenv("DEFAULT_ES_INDEX", "literature_metadata_index")
DEFAULT_ES_HOSTS: Sequence[str] = tuple(
    host.strip()
    for host in os.getenv("ELASTICSEARCH_HOSTS", "http://127.0.0.1:9200").split(",")
    if host.strip()
)
ES_USERNAME = (os.getenv("ES_USERNAME") or "elastic").strip()
ES_PASSWORD = os.getenv("ES_PASSWORD", "0000")

LITERATURE_METADATA_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "author",
    "platform",
    "year",
    "link",
    "snippet",
    "cited_by",
    "source",
)

DEFAULT_TEXT_FIELDS: tuple[str, ...] = (
    "title^5",
    "author^3",
    "platform^2",
    "snippet^4",
    "raw_payload",
)
VECTOR_FIELD_PREFERENCES: tuple[str, ...] = (
    "title_embedding",
    "snippet_embedding",
)


@singleton # 唯一实例装饰器，确保ESConnection类只有一个实例被创建
class ESConnection:
    # 构造器，建立与Elasticsearch服务器的连接，并检查连接是否成功
    def __init__(self):
        client_kwargs: dict[str, Any] = {"request_timeout": 60}
        if ES_PASSWORD:
            client_kwargs["basic_auth"] = (ES_USERNAME, ES_PASSWORD)
        self.es = Elasticsearch(hosts=list(DEFAULT_ES_HOSTS), **client_kwargs)
        print(f"\n$$$$ SYSTEM CALL $$$$: FROM ESConnection __init__:")
        print(f"$$$$ SYSTEM CALL $$$$: Connected to Elasticsearch at {DEFAULT_ES_HOSTS} with username '{ES_USERNAME}'")

    def init_index(self, index_name: str = DEFAULT_ES_INDEX):
        # 索引不存在时创建索引，并定义映射（mapping）以指定字段类型和属性
        if not self.es.indices.exists(index=index_name):
            mapping = {
                "properties": {
                    "title": {"type": "text"},
                    "title_embedding": {
                        "type": "dense_vector",
                        "dims": EMBEDDING_DIMS,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "author": {"type": "text"},
                    "platform": {"type": "text"},
                    "year": {"type": "keyword"},
                    "link": {"type": "keyword"},
                    "snippet": {"type": "text"},
                    "snippet_embedding": {
                        "type": "dense_vector",
                        "dims": EMBEDDING_DIMS,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "cited_by": {"type": "integer"},
                    "source": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                }
            }
            self.es.indices.create(index=index_name, mappings=mapping)
            print(f"\n$$$$ SYSTEM CALL $$$$: FROM ESConnection init_index:")
            print(f"$$$$ SYSTEM CALL $$$$: Created Elasticsearch index '{index_name}' with mappings: {mapping}")
        else:
            print(f"$$$$ SYSTEM CALL $$$$: FROM ESConnection init_index:")
            print(f"$$$$ SYSTEM CALL $$$$: Elasticsearch index '{index_name}' already exists")

            existing_properties = self.es.indices.get_mapping(index=index_name)[index_name]["mappings"].get("properties", {})
            new_properties: dict[str, Any] = {}
            for field_name in ("title_embedding", "snippet_embedding"):
                field_mapping = existing_properties.get(field_name)
                if field_mapping is None:
                    new_properties[field_name] = {
                        "type": "dense_vector",
                        "dims": EMBEDDING_DIMS,
                        "index": True,
                        "similarity": "cosine",
                    }
                elif field_mapping.get("type") != "dense_vector":
                    raise ValueError(
                        f"Field '{field_name}' already exists as type "
                        f"'{field_mapping.get('type')}', cannot change it to dense_vector in-place. "
                        "Create a new index with the correct mapping and reindex the data."
                    )

            if new_properties:
                self.es.indices.put_mapping(
                    index=index_name,
                    properties=new_properties,
                )
                print(f"$$$$ SYSTEM CALL $$$$: Added vector fields to '{index_name}': {list(new_properties)}")
        
    
    # 插入文档到Elasticsearch，要求每个文档必须包含'id'字段作为唯一标识符
    def insert(self, document: list[Literature_Metadata_DB], index_name: str = DEFAULT_ES_INDEX):
        operations = []
        document_dicts = [doc.model_dump() for doc in document]
        for i, doc in enumerate(document_dicts):
            assert "id" in doc, f"doc[{i + 1}] must contain field 'id'"
            assert "_id" not in doc, f"doc[{i + 1}] cannot contain reserved field '_id'"

            doc_copy = copy.deepcopy(doc)
            meta_id = doc_copy.pop("id")
            doc_copy.update(embed_literature_fields(doc_copy.get("title"), doc_copy.get("snippet")))
            operations.append({"index": {"_index": index_name, "_id": meta_id}})
            operations.append(doc_copy)

        for _ in range(3):# 最多重试3次
            try:
                res = []
                result_bulk = self.es.bulk(index=index_name, operations=operations, timeout="60s")
                if re.search(r"False", str(result_bulk["errors"]), re.IGNORECASE):
                    return res

                for item in result_bulk["items"]:
                    for action in ["create", "delete", "index", "update"]:
                        if action in item and "error" in item[action]:
                            res.append(str(item[action]["_id"]) + ":" + str(item[action]["error"]))

                return res
            except Exception as e:
                print(f"Error inserting documents into Elasticsearch: {e}")
                if re.search(r"(Timeout|time out)", str(e), re.IGNORECASE):
                    res.append(str(e))
                    time.sleep(3)
                    continue
        return res
    

    # 删除函数，支持基于文档ID或其他条件删除符合条件的文档
    def delete(self, index_name: str, doc_id: Optional[str] = None) -> dict[str, Any]:
        """
        删除符合条件的文档
        
        Args:
            condition: 删除条件
            indexName: 索引名称
            knowledgebaseId: 知识库ID
            
        Returns:
            删除的文档数量
        """
        # 构建删除查询
        delete_query = {
            "query": {
                "bool": {
                    "must": []
                }
            }
        }

        if doc_id:
            delete_query["query"]["bool"]["must"].append({
                "match": {
                    "_id": doc_id
                }
            })
    
        # 执行删除操作
        try:
            response = self.es.delete_by_query(
                index=index_name,
                body=delete_query
            )
            deleted_count = response.get('deleted', 0)
            return {
                "deleted_count": deleted_count,
                "status": "success",
                "message": f"Deleted {deleted_count} documents from index '{index_name}'"
            }
        except Exception as e:
            return {
                "deleted_count": 0,
                "status": "error",
                "message": f"Error deleting documents: {str(e)}"
            }

    # 同步MySQL数据库中的文献元数据到Elasticsearch索引中，供搜索使用
    def sync_literature_metadata_from_mysql(
            self,
            index_name: str, 
            db_name: str = DB_NAME, 
            table_name: str = TABLE_NAME
            ) -> dict[str, Any]:

        mysql_conn = get_mysql_server_connection()
        # 从MySQL数据库中查询所有文献元数据记录
        try:
            self.init_index(index_name)
            cmd = f"SELECT {', '.join(LITERATURE_METADATA_FIELDS)} FROM `{table_name}`"
            mysql_conn.select_db(db_name)
            with mysql_conn.cursor() as cursor:
                cursor.execute(cmd)
                records = cursor.fetchall()
                print(f"\n$$$$ SYSTEM CALL $$$$: FROM ESConnection sync_literature_metadata_from_mysql:")
                print(f"$$$$ SYSTEM CALL $$$$: 正在从MySQL数据库'{db_name}'的表'{table_name}'中获取所有待同步数据，请稍候......")
                print(f"Successfully fetched {len(records)} records from MySQL database '{db_name}', table '{table_name}'")
                print(f"record 第一个记录为：\n{records[0]}")
        except Exception as exc:
            return {
                "success": False,
                "message": f"Failed to fetch records from MySQL: {exc}",
            }
        finally:
            mysql_conn.close()

        # 如果没有记录需要同步，直接返回成功响应
        if not records:
            return {
                "success": True,
                "synced_count": 0,
                "failed_count": 0,
                "errors": [],
                "message": f"No literature metadata records found in MySQL table '{db_name}.{table_name}'",
            }

        # 成功获取到记录后，读取Elasticsearch索引的mapping，确定哪些字段是可写的（即非semantic_text类型），并构建批量插入操作
        try:
            mapping_response = self.es.indices.get_mapping(index=index_name)
            index_mapping = mapping_response[index_name]["mappings"].get("properties", {})
            writable_fields = set(index_mapping)
        except Exception as exc:
            return {
                "success": False,
                "message": f"Failed to read Elasticsearch mapping for index '{index_name}': {exc}",
            }

        # 构建批量插入操作列表ES_operations
        ES_operations: list[dict[str, Any]] = []
        for record in records:
            # 将MySQL查询结果中的每条记录转换为字典格式（字段名: 字段值）
            record_dict = dict(zip(LITERATURE_METADATA_FIELDS, record))
            doc_id = str(record_dict.pop("id"))
            # 构建要插入Elasticsearch的文档，字段名和值都必须符合Elasticsearch索引的mapping定义，且只能包含可写字段
            document = {
                field_name: record_dict.get(field_name)
                for field_name in LITERATURE_METADATA_FIELDS
                if field_name != "id" and field_name in writable_fields
            }
            # 对于year和cited_by字段，确保它们的类型与Elasticsearch索引的mapping定义一致‘
            # （year作为字符串，cited_by作为整数）
            if "year" in document and document["year"] is not None:
                document["year"] = str(document["year"])
            if "cited_by" in document and document["cited_by"] is not None:
                document["cited_by"] = int(document["cited_by"])
            document.update(embed_literature_fields(document.get("title"), document.get("snippet")))

            ES_operations.append({"index": {"_index": index_name, "_id": doc_id}})
            ES_operations.append(document)
        print(f"\n$$$$ SYSTEM CALL $$$$: FROM ESConnection sync_literature_metadata_from_mysql:")
        print(f"$$$$ SYSTEM CALL $$$$: 成功构建批量插入操作列表")
        print(f"操作列表前两条为：\n{ES_operations[:4]}\n")# 每条记录对应两条操作命令（index和文档数据），因此显示前4条操作命令

        # 执行批量插入操作，并统计成功和失败的记录数量，以及失败的错误信息
        errors: list[str] = []
        batch_size = 500
        synced_count = 0

        for start in range(0, len(ES_operations), batch_size * 2):# 每2行操作命令为一次有效操作，因此 * 2
            batch_operations = ES_operations[start:start + batch_size * 2]
            for attempt in range(3):
                try:
                    bulk_result = self.es.bulk(operations=batch_operations, timeout="300s", refresh=True)
                    for item in bulk_result.get("items", []):# 获取每一条操作的结果，len(items)就是批量操作的数量
                        index_result = item.get("index", {}) # ????????????????????????没有这个字段
                        # 根据Elasticsearch的bulk API响应格式，检查每条操作的结果状态码，统计成功和失败的记录数量，并收集失败的错误信息
                        status = int(index_result.get("status", 0))
                        if 200 <= status < 300:
                            synced_count += 1
                        else:
                            errors.append(f"{index_result.get('_id')}: {index_result.get('error', index_result)}")
                    break
                except Exception as exc:
                    if attempt < 2 and re.search(r"(Timeout|time out)", str(exc), re.IGNORECASE):
                        time.sleep(3)
                        continue
                    errors.append(str(exc))
                    break

        failed_count = len(errors)
        return {
            "success": failed_count == 0,
            "synced_count": synced_count,
            "failed_count": failed_count,
            "errors": errors,
            "message": (
                f"Successfully synchronized {synced_count} literature metadata records "
                f"from MySQL to Elasticsearch index '{index_name}'"
                if failed_count == 0
                else f"Synchronized {synced_count} records with {failed_count} failures"
            ),
        }

    def backfill_missing_embeddings(
        self,
        index_name: str = DEFAULT_ES_INDEX,
        batch_size: int = 100,
    ) -> dict[str, Any]:
        self.init_index(index_name)

        query = {
            "query": {
                "bool": {
                    "should": [
                        {"bool": {"must_not": {"exists": {"field": "title_embedding"}}}},
                        {"bool": {"must_not": {"exists": {"field": "snippet_embedding"}}}},
                    ],
                    "minimum_should_match": 1,
                }
            },
            "_source": ["title", "snippet"],
        }

        operations: list[dict[str, Any]] = []
        updated_count = 0
        errors: list[str] = []
        safe_batch_size = max(1, int(batch_size))

        def flush_batch() -> None:
            nonlocal operations, updated_count
            if not operations:
                return

            bulk_result = self.es.bulk(
                operations=operations,
                timeout="300s",
                refresh=True,
            )
            for item in bulk_result.get("items", []):
                update_result = item.get("update", {})
                status = int(update_result.get("status", 0))
                if 200 <= status < 300:
                    updated_count += 1
                else:
                    errors.append(f"{update_result.get('_id')}: {update_result.get('error', update_result)}")
            operations = []

        try:
            for hit in scan(
                self.es,
                index=index_name,
                query=query,
                size=safe_batch_size,
                scroll="5m",
            ):
                source_data = hit.get("_source", {}) or {}
                operations.append({"update": {"_index": index_name, "_id": hit["_id"]}})
                operations.append(
                    {
                        "doc": embed_literature_fields(
                            source_data.get("title"),
                            source_data.get("snippet"),
                        )
                    }
                )

                if len(operations) >= safe_batch_size * 2:
                    flush_batch()

            flush_batch()
        except Exception as exc:
            errors.append(str(exc))

        return {
            "success": len(errors) == 0,
            "updated_count": updated_count,
            "failed_count": len(errors),
            "errors": errors,
        }
    
    # Elasticsearch搜索函数，支持基于文本查询和向量查询的混合搜索
    def hybrid_search(
        self,
        query: str,
        index_name: str = DEFAULT_ES_INDEX,
        text_fields: Sequence[str] = DEFAULT_TEXT_FIELDS,
        top_k: int = 3,                 # 返回最相关的top_k条结果，默认为3条
    ) -> List[Literature_Metadata_Record]:
        query = handle_query(str(query or "")).strip()
        if not query:
            raise ValueError("query must not be empty")

        safe_top_k = max(1, min(int(top_k), 100))
        candidate_size = max(safe_top_k * 2, safe_top_k)

        query_vector = embed_text(query)

        search_query = {
            "query": {
                "script_score": {
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": list(text_fields),
                        }
                    },
                    "script": {
                        "source": """
                            double titleScore = doc['title_embedding'].size() == 0
                                ? 0.0
                                : cosineSimilarity(params.query_vector, 'title_embedding');
                            double snippetScore = doc['snippet_embedding'].size() == 0
                                ? 0.0
                                : cosineSimilarity(params.query_vector, 'snippet_embedding');
                            return _score + 2.0 + (titleScore * 2.0) + snippetScore;
                        """,
                        "params": {
                            "query_vector": query_vector
                        }
                    }
                }
            }
        }

        response = self.es.search(
            index=index_name,
            body=search_query,
            size=candidate_size,
            timeout="60s"
        )

        hits = response.get("hits", {}).get("hits", [])
        records: List[Literature_Metadata_Record] = []
        for hit in hits[:safe_top_k]:
            source_data = hit.get("_source", {}) or {}
            records.append(
                Literature_Metadata_Record(
                    title=source_data.get("title", ""),
                    author=source_data.get("author", ""),
                    platform=source_data.get("platform", ""),
                    year=source_data.get("year", ""),
                    link=source_data.get("link", ""),
                    snippet=source_data.get("snippet", ""),
                    cited_by=source_data.get("cited_by"),
                    source=source_data.get("source", ""),
                )
            )
        return records
