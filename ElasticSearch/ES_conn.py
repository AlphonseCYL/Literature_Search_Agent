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

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


if load_dotenv:
    load_dotenv()

DEFAULT_ES_INDEX = os.getenv("ES_INDEX_NAME") or os.getenv("DEFAULT_ES_INDEX", "literature_metadata")
DEFAULT_ES_HOSTS: Sequence[str] = tuple(
    host.strip()
    for host in os.getenv("ELASTICSEARCH_HOSTS", "http://127.0.0.1:9200").split(",")
    if host.strip()
)
ES_USERNAME = (os.getenv("ES_USERNAME") or "elastic").strip()
ES_PASSWORD = os.getenv("ES_PASSWORD", "0000")
EMBEDDING_DIMS = 768

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

        # 构建Elasticsearch客户端连接参数
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
                    "title": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type":"keyword",
                                "ignore_above" : 256
                            }
                        }
                        },
                    "title_embedding": {
                        "type": "dense_vector",
                        "dims": EMBEDDING_DIMS,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "author": {"type": "keyword"},
                    "platform": {"type": "keyword"},
                    "year": {"type": "keyword"},
                    "link": {"type": "keyword"},
                    "snippet": {"type": "keyword"},
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
            existing_properties = self.es.indices.get_mapping(index=index_name)[index_name]["mappings"].get("properties", {})
            print(f"$$$$ SYSTEM CALL $$$$: FROM ESConnection init_index:")
            print(f"$$$$ SYSTEM CALL $$$$: Elasticsearch index '{index_name}' already exists, existing mappings: {existing_properties}")
        
    
    # 插入文档到Elasticsearch，要求每个文档必须包含'id'字段作为唯一标识符
    def insert(self, document: list[Literature_Metadata_DB], index_name: str = DEFAULT_ES_INDEX):
        operations = []
        document_dicts = [doc.model_dump() for doc in document]
        for i, doc in enumerate(document_dicts):
            assert "id" in doc, f"doc[{i + 1}] must contain field 'id'"
            assert "_id" not in doc, f"doc[{i + 1}] cannot contain reserved field '_id'"

            doc_copy = copy.deepcopy(doc)
            meta_id = doc_copy.pop("id")
            # doc_copy.update(embed_literature_fields(doc_copy.get("title"), doc_copy.get("snippet")))
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

    # 搜索函数，支持基于任意Elasticsearch查询DSL的搜索，并返回搜索结果和相关信息
    # size参数用于控制返回结果的数量，默认为3条
    def ES_query_search(self, index_name: str, search_query: str, size: int = 3) -> List[Literature_Metadata_Record]:
        try:
            # 构建Elasticsearch查询DSL，使用multi_match查询在指定的文本字段中搜索用户输入的查询字符串，并根据相关性得分返回最相关的结果
            query = {"query": {"multi_match": {"query": search_query, "fields": ["title", "snippet", "author", "platform"]}}}
            print(f"\nFROM ESConnection.ES_query_search:")
            print(f"Executing Elasticsearch query search with query: \n{query}\n and size: \n{size}\n")

            response = self.es.search(index=index_name, body=query, size=size, timeout="60s")
            print(f"Received Elasticsearch query search response:\n {response}\n")

            hits = response.get("hits", {}).get("hits", [])
            ret = []
            for hit in hits:
                source_data = hit.get("_source", {}) or {}
                ret.append(
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
            return ret
        except Exception as e:
            print(f"Error from ESConnection.ES_query_search: {e}")
            return []
    

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


        search_query = {
            "query": {
                "script_score": {
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": list(text_fields),
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
