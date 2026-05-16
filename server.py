from flask import Flask, jsonify, request
from typing import Any, Dict, List

from ElasticSearch import ESConnection, DEFAULT_ES_HOSTS, DEFAULT_ES_INDEX
from db_utils import init_mysql_database, save_literature_metadata, DB_NAME, TABLE_NAME
from search_platform.google_scholar import serpapi_google_scholar
from utils import handle_query
from Redis_utils import init_redis_info, save_literature_to_redis, get_literature_metadata_from_redis, REDIS_LIST_NAME
from llm import filter_literature_records, QwenFilterError

from schemas.redis_template import Save_To_Redis_Info
from schemas.db_template import Save_Mysql_Info, Literature_Metadata_Record

def create_app() -> Flask:
    app = Flask(__name__)

    # 初始化MySQL数据库和输出Redis信息
    init_mysql_database()
    init_redis_info()

    # route
    @app.route("/")
    def navigator() -> Dict[str, str]:
        return {
            "hello": "this is CYL's literature navigator server",
            "role": "navigator",
            "data": "literature_searched",
        }

    ############################### Google Scholar 搜索route #################################
    #    前端输入：{"query_google_scholar": "xxx", "lang_num": {"zh-CN": 5, "en": 5}}
    #    后端输出：{"literature_search_results": [Literature_Metadata_Record,...]}
    #
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

        literal_list: List[Literature_Metadata_Record] = []
        # 根据不同语言的查询分别调用Google Scholar搜索，并将结果合并到一个列表中
        for lang, query in cleaned_query.items():
            literal_result = serpapi_google_scholar(
                query=query,
                num=lang_num.get(lang, 0),
                lang=lang,
            )
            literal_list.extend(literal_result)

        result_json = {"literature_search_results": []}
        for item in literal_list:
            result_json["literature_search_results"].append(item.model_dump())

        return jsonify(result_json)

    ############################## 存储到MySQL数据库 ################################
    #    前端输入：List[dict]，每个dict符合Literature_Metadata_Record的字段要求
    #    后端输出：dict格式的Save_Mysql_Info的model_dump结果，包含存储结果信息
    @app.route("/save_literature_metadata/", methods=["POST"])
    def save_literature_metadata_route():
        received_list = request.get_json(silent=True) or []
        print(f"\n$$$$ ROUTER CALL $$$$: FROM save_to_mysql:")
        print(f"$$$$ ROUTER CALL $$$$: successfully received {len(received_list)} literature metadata to save")
        print("正在存入MySQL数据库......")

        try:
            # 确保MySQL数据库和表已经初始化，避免因数据库或表不存在而导致的存储失败
            init_mysql_database()
            save_result = save_literature_metadata(received_list)
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

    ################################ 数据存入redis ###################################
    #   功能：将前端搜索文献得到的文献信息存入Redis列表中，存入时会去重，避免重复数据存入Redis
    #   前端输入：[Literature_Metadata_Record,...]
    #   后端返回：存储结果给前端
    @app.route("/save_to_redis/", methods=["POST"])
    def save_to_redis_route():
        # 获取前端的返回数据，默认为空列表，以避免get_json返回None时导致后续代码出错
        received_list = request.get_json(silent=True) or []
        print(f"\n$$$$ ROUTER CALL $$$$: FROM SAVE_TO_REDIS:")
        print(f"$$$$ ROUTER CALL $$$$: successfully received request with payload:\n")
        print(f"{len(received_list)} items received\n")
        print("Redis正在存入数据......")

        # 将每条文献信息存入Redis列表中，返回dict给前端展示存储结果
        save_result: dict[str, Any] = save_literature_to_redis(REDIS_LIST_NAME, received_list)
        return jsonify(save_result), 200


    ############################## 从redis筛选并读取 ################################
    #   前端输入：query
    #   后端返回：{"literature_search_results": List[dict]}JSON格式
    @app.route("/get_from_redis/", methods=["POST"])
    def get_from_redis_route():
        # 从Redis列表中获取所有文献信息
        literature_list = get_literature_metadata_from_redis(REDIS_LIST_NAME)
        print(f"\n$$$$ ROUTER CALL $$$$: FROM get_from_redis:")
        print(f"$$$$ ROUTER CALL $$$$: successfully retrieved literature metadata from Redis, count: {len(literature_list)}\n")

        # 获取前端回传参数
        received_dict = request.get_json(silent=True) or {}
        query = received_dict.get("query")
        if not isinstance(query, str) or not query.strip():
            return jsonify(
                {
                    "success": False,
                    "message": "field 'query' is required and must be a non-empty string",
                }
            ), 400
        model = received_dict.get("model")
        max_selected = received_dict.get("max_selected")
        
        # 进行文献筛选，并返回给前端，中间遇到任何问题都会返回给前端报错
        try:
            literature_filtered_schemas_list = filter_literature_records(
                literature_list,
                query=query,
                model=model if isinstance(model, str) and model.strip() else None,
                max_selected=max_selected if isinstance(max_selected, int) else None,
            )
            literature_filtered_list = [record.model_dump() for record in literature_filtered_schemas_list]
            return jsonify(
                {
                    "success": True,
                    "redis_count": len(literature_list),
                    "literature_search_results": literature_list,
                    "filtered_count": len(literature_filtered_list),
                    "literature_filtered_results": literature_filtered_list,
                }
            ), 200
        except QwenFilterError as exc:
            return jsonify({"success": False, "message": str(exc)}), 502
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400
        except ConnectionError as exc:
            return jsonify({"success": False, "message": str(exc)}), 503
        except Exception as exc:
            return jsonify(
                {
                    "success": False,
                    "message": f"failed to filter redis literature with qwen: {exc}",
                }
            ), 500



    ############################## Elasticsearch检索MySQL数据库 ################################
    @app.route("/es_search/", methods=["POST"])
    def es_search_route():
        received_dict = request.get_json(silent=True) or {}
        print(f"\n$$$$ ROUTER CALL $$$$: FROM es_search:")
        print(f"$$$$ ROUTER CALL $$$$: successfully received request with payload:\n")
        print(f"{received_dict}\n")

        # 提取参数,hiagent端定义的参数
        query = received_dict.get("query")
        literature_num = received_dict.get("literature_num", 3)# 默认为3条结果,hiagent端会传入需要的结果数量

        if not isinstance(query, str) or not query.strip():
            return jsonify(
                {
                    "success": False,
                    "message": "field 'query' is required and must be a non-empty string",
                }
            ), 400

        try:
            # 初始化Elasticsearch连接并确保索引已创建
            es_conn = ESConnection()
            es_conn.init_index(DEFAULT_ES_INDEX)
            # 调用Elasticsearch搜索函数，作为检索用户记忆
            print(f"\n$$$$ ROUTER CALL $$$$: FROM es_search:")
            print(f"$$$$ ROUTER CALL $$$$：正在执行query检索......\n")
            result = es_conn.ES_query_search(
                index_name=DEFAULT_ES_INDEX,
                search_query=query,
                size=literature_num,
            )
            # 将搜索结果pydantic结构数据转化为dict格式
            serialized_results = [item.model_dump() for item in result]
            print(f"$$$$ ROUTER CALL $$$$：query检索结果已序列化，共 {len(serialized_results)} 条\n")

            return jsonify(
                {
                    "success": True,
                    "returned_count": len(serialized_results),
                    "literature_metadata": serialized_results
                }
            ), 200
            
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
