# 论文检索助手

我是 ALPHONSE，这个项目主要技术栈是 Python。这里记录的是当前仓库最关键的维护信息，方便后续快速接手。

## 项目定位

这是一个论文检索后端，核心链路是：

1. Flask 接收请求。
2. SerpAPI 调 Google Scholar。
3. Pydantic 统一文献字段。
4. Redis 做短期缓存，默认 10 分钟过期。
5. MySQL 做长期保存，并用 `title + link` 去重。
6. Elasticsearch 负责历史文献检索和后续召回。

## 主要入口

- `main.py`：启动 Flask 服务，默认 `0.0.0.0:5001`。
- `server.py`：应用工厂和全部 API 路由。
- `readme.md`：更完整的使用说明和接口示例。
- `docker-compose.yaml`：主要用于启动 Redis。

`main.py` 里虽然保留了 `--query`、`--num`、`--model` 参数，但当前实际只负责启动服务，没有走一次性检索分支。

## API 路由

- `GET /`：服务探活。
- `POST /search_google_scholar/`：调用 Google Scholar 检索。
  - `query_google_scholar` 可传字符串或字典。
  - `lang_num` 必须是 JSON 对象，按语言控制返回数量。
- `POST /save_to_redis/`：把文献列表写入 Redis，并按标准化 JSON 去重。
- `GET /get_from_redis/`：读取 Redis 中当前缓存的文献。
- `POST /save_literature_metadata/`：保存文献到 MySQL。
- `POST /es_search/`：在 Elasticsearch 中检索已沉淀文献。

## 模块职责

- `search_platform/google_scholar.py`：封装 SerpAPI Google Scholar 检索，解析标题、作者、平台、年份、链接、摘要、引用数。
- `schemas/db_template.py`：定义文献元数据模型 `Literature_Metadata_Record` 和 MySQL 保存相关模型。
- `schemas/redis_template.py`：定义 Redis 保存结果返回模型。
- `Redis_utils/init_redis.py`：读取 Redis 配置并检查连接。
- `Redis_utils/redis_func.py`：Redis 写入、去重、读取。
- `db_utils/init_mysql_db.py`：初始化数据库和 `literature_metadata` 表。
- `db_utils/mysql_db_func.py`：把文献批量写入 MySQL，使用 `INSERT IGNORE`。
- `ElasticSearch/ES_conn.py`：ES 连接、建索引、同步 MySQL、关键词检索，代码里也预留了向量字段和混合检索方法。
- `utils/handle_query.py`：清洗查询词，去掉多余引号，空字符串会回落到默认查询。

## 数据约定

统一文献字段：

```python
title, author, platform, year, link, snippet, cited_by, source
```

### MySQL

- 数据库名来自 `MYSQL_DATABASE_NAME`，默认 `literature_db`。
- 表名来自 `MYSQL_TABLE_NAME`，默认 `literature_metadata`。
- 编码为 `utf8mb4`。
- `title(255) + link(255)` 是唯一索引。
- 表含 `created_at` 和 `updated_at`。

### Redis

- 默认列表名来自 `REDIS_LIST_NAME`，默认 `literature_list`。
- 写入前会把每条记录转成排序后的 JSON 字符串。
- 过期时间固定为 600 秒。

### Elasticsearch

- 默认索引来自 `ES_INDEX_NAME` 或 `DEFAULT_ES_INDEX`。
- 当前 `/es_search/` 使用 `multi_match` 在 `title`、`snippet`、`author`、`platform` 上检索。
- 索引映射里已经预留 `dense_vector` 字段，但现有路由主要还是关键词检索。

## 启动注意

- `server.py` 在创建应用时会先初始化 MySQL 和 Redis 连接检查。
- 运行前要确认 Redis、MySQL、Elasticsearch 都可连接。
- MySQL 表会自动创建，ES 索引会在相关逻辑中自动初始化。
- `.env` 里的密钥、密码和连接串不要写进文档或回复里。

## 开发习惯

- 优先保持现有分层：`server.py` 负责路由，`search_platform` 负责外部检索，`Redis_utils` 负责缓存，`db_utils` 负责 MySQL，`ElasticSearch` 负责 ES，`schemas` 负责数据结构。
- 新接口尽量复用 `Literature_Metadata_Record`，避免字段格式分叉。
- 这个仓库里有 `.venv`、`__pycache__`、`result.json`、`test.py` 等辅助文件，维护时优先关注业务代码。
- `test.py` 更像一个连通性小脚本，不是完整测试体系。
