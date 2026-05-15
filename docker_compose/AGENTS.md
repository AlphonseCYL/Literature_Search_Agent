# 项目说明

我是 Alphonse。这个项目用于学习和维护 Docker Compose 容器编排，目标是启动多个容器，并让容器之间能互相通信、读写数据。

## 重要安全规则

- 禁止批量删除文件或目录。
- 禁止使用：`del /s`、`rd /s`、`rmdir /s`、`Remove-Item -Recurse`、`rm -rf`。
- 需要删除文件时，只能一次删除一个明确路径的文件，例如：`Remove-Item "C:\path\to\file.txt"`。
- 如果需要批量删除文件，应停止操作，并让用户手动删除。

## 技术背景

- 用户主要技术栈是 Python。
- 涉及其他语言或配置语法时，需要多解释语法含义和用途。
- 本项目主要由 Docker Compose、Redis、Elasticsearch、Kibana、Logstash 配置组成。

## 项目文件

- `docker-compose.yaml`：核心编排文件，定义 Redis、Elasticsearch、Kibana、Logstash 服务。
- `.env`：环境变量文件，保存 ES/Kibana 用户名、密码、内存限制、时区、ES 容器访问地址等。
- `redis.conf`：Redis 配置文件，会挂载到 Redis 容器内 `/etc/redis/redis.conf`。
- `kibana.yml`：Kibana 示例配置文件，目前没有在 `docker-compose.yaml` 中挂载。
- `logstash.conf`：Logstash pipeline 配置，会挂载到容器内 `/usr/share/logstash/pipeline/logstash.conf`。
- `data/`：本地数据目录，操作时要谨慎，不要批量删除。

## Docker Compose 服务

- `redis`
  - 镜像：`redis:7-alpine`
  - 容器名：`redis_CYL`
  - 宿主机端口：`6379`
  - 数据卷：`redis_cyl_data:/data`
  - 配置挂载：本机 `redis.conf` 到容器 `/etc/redis/redis.conf`
  - 启动命令：`redis-server /etc/redis/redis.conf`
  - 注意：当前未加入 `CYL_network`，默认使用 Compose 自动网络。

- `es`
  - 镜像：`elasticsearch:9.4.1`
  - 容器名：`es_CYL`
  - 宿主机端口：`9201` 映射到容器 `9200`
  - 内部容器访问地址：`http://es_CYL:9200`
  - 单节点模式：`discovery.type=single-node`
  - 开启安全认证：`xpack.security.enabled=true`
  - 关闭 HTTP/transport SSL，适合本地学习环境。
  - 数据卷：`es_data_cyl:/usr/share/elasticsearch/data`
  - 网络：`CYL_network`

- `kibana`
  - 镜像：`kibana:9.4.1`
  - 容器名：`kibana_CYL`
  - 宿主机端口：`5601`
  - 通过环境变量连接 Elasticsearch：`ELASTICSEARCH_HOSTS=${ES_DOCKER_HOST}`
  - 依赖 `es` 服务启动。
  - 数据卷：`kibana_data_cyl:/usr/share/kibana/data`
  - 网络：`CYL_network`

- `logstash`
  - 镜像：`logstash:9.4.1`
  - 容器名：`logstash_CYL`
  - 宿主机端口：`5044`
  - 挂载 `./logstash.conf` 到 pipeline 配置目录。
  - 依赖 `es` 服务启动。
  - 数据卷：`logstash_data_cyl:/usr/share/logstash/data`
  - 网络：`CYL_network`

## 网络与访问

- Compose 中定义了自定义桥接网络 `CYL_network`。
- `es`、`kibana`、`logstash` 在同一网络内，可用容器名互相访问。
- 宿主机访问 Elasticsearch 使用：`http://localhost:9201`。
- 容器内访问 Elasticsearch 使用：`http://es_CYL:9200`。
- 宿主机访问 Kibana 使用：`http://localhost:5601`。
- 宿主机访问 Redis 使用：`localhost:6379`。

## 环境变量注意事项

- `.env` 中 `ELASTIC_PASSWORD=000000` 是 Elasticsearch `elastic` 用户密码。
- `.env` 中 `ELASTICSEARCH_USERNAME=kibana_system`、`ELASTICSEARCH_PASSWORD=123456` 用于 Kibana/Logstash 环境变量。
- 注意当前 ES 密码和 Kibana/Logstash 密码不一致，若服务认证失败，优先检查这里。
- `ES_DOCKER_HOST=http://es_CYL:9200` 适合容器之间通信，不适合宿主机直接访问。
- `STACK_VERSION=8.11.3` 当前没有被 `docker-compose.yaml` 使用；实际镜像版本写死为 `9.4.1`。
- `TIMEZONE='Asia/Shanghai'` 用于容器时区。

## Logstash 配置注意事项

- `logstash.conf` 同时包含 `stdin` 和 `jdbc` input。
- JDBC 当前连接：`jdbc:mysql://localhost:3306/literature_db?...`
- 如果 Logstash 在容器中运行，`localhost` 指的是 Logstash 容器本身，不是宿主机；连接宿主机 MySQL 时需要改为合适的宿主机地址。
- JDBC 驱动路径当前是 Windows 本机路径：`E:\Program Files\Logstash\...`，容器内通常无法访问；容器运行时需要把驱动 jar 挂载进容器，并改成容器内路径。
- output 当前写到 `127.0.0.1:9200`，容器内通常应改为 `es_CYL:9200` 或使用环境变量中的 ES 地址。
- 索引名：`literature_metadata`。
- 文档 ID：使用 MySQL 查询结果中的 `id` 字段。

## Redis 配置注意事项

- `redis.conf` 设置 `bind 0.0.0.0`，允许远程连接。
- `protected-mode yes` 已开启保护模式。
- Redis 数据库数量设置为 `12`。
- 禁用了危险命令：`FLUSHDB` 和 `CONFIG`。
- Redis 密码：`requirepass 0000`。

## 常用命令

- 启动全部服务：`docker compose up -d`
- 查看服务状态：`docker compose ps`
- 查看日志：`docker compose logs -f`
- 停止服务：`docker compose down`
- 只重启某个服务：`docker compose restart <service>`

## 维护原则

- 修改配置前先确认服务是在宿主机运行，还是在容器内运行；两者的 `localhost` 含义不同。
- 修改端口、密码、容器名、网络名后，要同步检查 `.env`、`docker-compose.yaml`、`logstash.conf`、`kibana.yml`。
- 不要轻易删除 Docker volume，因为其中保存 Redis、Elasticsearch、Kibana、Logstash 的持久化数据。
- 本项目是学习型配置，安全性适合本地环境；如果部署到生产环境，需要重新设计密码、证书、网络暴露和权限控制。
