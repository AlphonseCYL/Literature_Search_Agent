from flask import Flask, jsonify, request
from typing import Any, Dict, List

from ElasticSearch import search_mysql_literature_with_es
from db_utils.init_mysql_db import init_mysql_database
from db_utils.mysql_db_func import save_literature_metadata
from search_platform.google_scholar import serpapi_google_scholar
from utils.handle_query import handle_query


def create_app() -> Flask:
    app = Flask(__name__)

    # initialize mysql database and table
    init_mysql_database()

    # 涓婚〉route
    @app.route("/")
    def navigator() -> Dict[str, str]:
        return {
            "hello": "this is CYL's literature navigator server",
            "role": "navigator",
            "data": "literature_searched",
        }

    ####################### Google Scholar 搜索route ########################
    @app.route("/search_google_scholar/", methods=["POST"])
    def google_scholar_search():
        received_dict = request.get_json(silent=True) or {}
        query_google_scholar = received_dict.get("query_google_scholar")
        lang_num = received_dict.get("lang_num") or {}

        if not isinstance(lang_num, dict):
            return jsonify(
                {
                    "success": False,
                    "message": "field 'lang_num' must be a JSON object",
                }
            ), 400

        if isinstance(query_google_scholar, str):
            query_google_scholar = {"default": query_google_scholar}
        elif query_google_scholar is None:
            return jsonify(
                {
                    "success": False,
                    "message": "field 'query_google_scholar' is required",
                }
            ), 400
        elif not isinstance(query_google_scholar, dict):
            return jsonify(
                {
                    "success": False,
                    "message": "field 'query_google_scholar' must be a string or a JSON object",
                }
            ), 400

        cleaned_query: Dict[str, str] = {}
        for lang, query in query_google_scholar.items():
            cleaned_query[lang] = handle_query(str(query or ""))

        literal_list: List[Dict[str, Any]] = []
        for lang, query in cleaned_query.items():
            literal_result = serpapi_google_scholar(
                query=query,
                num=lang_num.get(lang, 0),
                lang=lang,
            )
            literal_list.extend(literal_result)

        result_json = {"literature_search_results": []}
        for item in literal_list:
            publication_info = item.get("publication_info") or {}
            inline_links = item.get("inline_links") or {}
            result_json["literature_search_results"].append(
                {
                    "title": item.get("title", ""),
                    "summary": publication_info.get("summary", "Unknown"),
                    "link": item.get("link", "閾炬帴鏆傜己"),
                    "snippet": item.get("snippet", ""),
                    "cite_format_link": inline_links.get("serpapi_cite_link"),
                    "cited_by": inline_links.get("cited_by"),
                    "related_pages_link": item.get("serpapi_related_pages_link"),
                }
            )

        return jsonify(result_json)

    ############################## 存储到MySQL数据库route ################################
    @app.route("/save_literature_metadata/", methods=["POST"])
    def save_literature_metadata_route():
        received_dict = request.get_json(silent=True) or {}
        print(f"\n$$$$ SYSTEM CALL $$$$: FROM SAVE_LITERATURE_METADATA:")
        print(f"$$$$ SYSTEM CALL $$$$: successfully received request with payload:\n")
        print(f"{received_dict}\n")

        try:
            save_result = save_literature_metadata(received_dict)
            print(f"save_result: \n{save_result}")
            return jsonify({"success": True, **save_result.model_dump()}), 200
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400
        except Exception as exc:
            return jsonify(
                {
                    "success": False,
                    "message": f"failed to save literature metadata: {exc}",
                }
            ), 500

    ############################## MySQL + Elasticsearch检索本地数据库route ################################
    @app.route("/search_db_es/", methods=["POST"])
    def search_db_es_route():
        received_dict = request.get_json(silent=True) or {}
        print(f"\n$$$$ SYSTEM CALL $$$$: FROM SEARCH_DB_ES:")
        print(f"$$$$ SYSTEM CALL $$$$: successfully received request with payload:\n")
        print(f"{received_dict}\n")
        # 提取参数,hiagent端定义的参数
        query = received_dict.get("query")
        limit = received_dict.get("limit", 20)
        source = received_dict.get("source")
        sync_before_search = received_dict.get("sync_before_search", True)

        if not isinstance(query, str) or not query.strip():
            return jsonify(
                {
                    "success": False,
                    "message": "field 'query' is required and must be a non-empty string",
                }
            ), 400

        try:
            result = search_mysql_literature_with_es(
                query=query,
                limit=limit,
                source=source,
                sync_before_search=bool(sync_before_search),
            )
            return jsonify({"success": True, **result}), 200
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400
        except ConnectionError as exc:
            return jsonify({"success": False, "message": str(exc)}), 503
        except Exception as exc:
            return jsonify(
                {
                    "success": False,
                    "message": f"failed to search literature by elasticsearch: {exc}",
                }
            ), 500

    return app
