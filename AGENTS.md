我叫 ALPHONSE，主要技术栈是 Python。遇到 Java 等我不熟悉的语言时，请多解释语法和运行方式。

## 项目概览

本项目是一个 Python 论文检索助手后端。核心目标是把一次 Google Scholar 检索变成结构化文献数据，并支持临时缓存、长期保存和后续召回。

整体链路：
1. Flask 接收前端或智能体请求。
2. SerpAPI 调用 Google Scholar 获取论文结果。
3. Pydantic 将结果统一成文献元数据结构。
4. Redis 保存短期检索结果，默认 10 分钟过期。
5. MySQL 保存长期文献元数据，并用 `title + link` 唯一索引去重。
6. Elasticsearch 从 MySQL 同步文献后，用于历史文献检索和智能体记忆召回。

## 主要入口

- `main.py`：启动 Flask 服务，默认监听 `0.0.0.0:5001`。
- `server.py`：Flask 应用工厂和所有 API 路由。
- `readme.md`：项目说明文档，包含接口示例、架构说明和运行步骤。
- `docker-compose.yaml`：当前主要用于启动 Redis 容器，挂载了本机 Redis 配置文件。

常用启动命令：

```powershell
python main.py --host 0.0.0.0 --port 5001
```

## API 路由

- `GET /`：服务探活和基础说明。
- `POST /search_google_scholar/`：调用 Google Scholar 检索论文。请求字段包含 `query_google_scholar` 和 `lang_num`，支持按语言分别检索。
- `POST /save_to_redis/`：把文献列表写入 Redis 列表，并按标准化 JSON 去重。
- `GET /get_from_redis/`：从 Redis 读取当前缓存的文献列表。
- `POST /save_literature_metadata/`：把文献元数据保存到 MySQL。
- `POST /es_search/`：从 Elasticsearch 检索已经沉淀的文献，输入 `query` 和可选 `literature_num`。

## 模块职责

- `search_platform/google_scholar.py`：封装 SerpAPI Google Scholar 检索，解析作者、平台、年份、引用次数等字段。
- `schemas/db_template.py`：定义核心文献模型 `Literature_Metadata_Record`，字段包括 `title`、`author`、`platform`、`year`、`link`、`snippet`、`cited_by`、`source`。
- `schemas/redis_template.py`：定义 Redis 保存结果返回模型。
- `Redis_utils/init_redis.py`：读取 Redis 环境变量并检查连接。
- `Redis_utils/redis_func.py`：Redis 写入、去重、读取逻辑。
- `db_utils/init_mysql_db.py`：初始化 MySQL 数据库和 `literature_metadata` 表。
- `db_utils/mysql_db_func.py`：保存文献到 MySQL，使用 `INSERT IGNORE` 避免重复中断流程。
- `ElasticSearch/ES_conn.py`：连接 ES、初始化索引、从 MySQL 批量同步、关键词检索；代码中预留了向量字段和 `hybrid_search`。
- `utils/handle_query.py`：简单清洗查询词，去掉多余引号并避免空查询。

## 数据模型和存储约定

标准文献字段统一使用：

```python
title, author, platform, year, link, snippet, cited_by, source
```

MySQL 表默认配置：

- 数据库名来自 `MYSQL_DATABASE_NAME`，默认 `literature_db`。
- 表名来自 `MYSQL_TABLE_NAME`，默认 `literature_metadata`。
- 表使用 `utf8mb4`，适合保存中英文和特殊字符。
- `id` 是自增主键。
- `title(255) + link(255)` 是唯一索引，用于长期去重。

Redis 默认列表名来自 `REDIS_LIST_NAME`，默认 `literature_list`。写入时会把每条文献序列化为排序后的 JSON 字符串，用于判断重复。

Elasticsearch 默认索引来自 `ES_INDEX_NAME` 或 `DEFAULT_ES_INDEX`，默认 `literature_metadata`。当前 `/es_search/` 使用 `multi_match` 关键词检索。

## 环境变量

项目依赖 `.env`，但不要把真实密钥写入文档或提交记录。常见配置项：

- `SERPAPI_API_KEY`
- `DASHSCOPE_URL`
- `DASHSCOPE_API_KEY`
- `MYSQL_DATABASE_NAME`
- `MYSQL_TABLE_NAME`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `REDIS_LIST_NAME`
- `ELASTICSEARCH_HOSTS`
- `ES_USERNAME`
- `ES_PASSWORD`
- `DEFAULT_ES_INDEX` 或 `ES_INDEX_NAME`

## 开发注意事项

- 这是 Python 项目，依赖见 `requirements.txt`。
- 优先保持现有分层：路由放 `server.py`，外部平台放 `search_platform`，缓存放 `Redis_utils`，数据库放 `db_utils`，ES 放 `ElasticSearch`，数据结构放 `schemas`。
- 新增接口时尽量复用 `Literature_Metadata_Record`，避免各模块字段格式不一致。
- 涉及中文内容时注意文件编码，当前仓库已有部分文件在 PowerShell 中显示为乱码，修改文档建议统一保存为 UTF-8。
- 运行服务前需要确认 Redis、MySQL、Elasticsearch 可连接；MySQL 表会在 Flask 应用启动时自动初始化，ES 索引会在调用相关逻辑时初始化。
- 不要在回答或文档中泄露 `.env` 里的 API Key、数据库密码或 ES 密钥。
