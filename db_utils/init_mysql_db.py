import os
import re
from typing import Any, Dict

import pymysql

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

DB_NAME = os.getenv("MYSQL_DATABASE_NAME", "literature_db")
TABLE_NAME = os.getenv("MYSQL_TABLE_NAME", "literature_metadata")

MYSQL_SERVER_CONFIG: Dict[str, Any] = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "0000"),
    "charset": "utf8mb4",
    "autocommit": True,
}



def get_mysql_server_connection() -> pymysql.connections.Connection:
    return pymysql.connect(**MYSQL_SERVER_CONFIG) # 字典解包


############### 初始化MySQL数据库和表的函数 ###############
def init_mysql_database() -> None:

    create_database_sql = f"""
    CREATE DATABASE IF NOT EXISTS `{DB_NAME}`
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci
    """

    # 设置主键id为自增，title和link字段设置唯一索引，
    # source和created_at字段设置普通索引，以优化查询性能
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS `{DB_NAME}`.`{TABLE_NAME}` (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        title VARCHAR(512) NOT NULL,
        author VARCHAR(512) DEFAULT NULL,
        platform VARCHAR(512) DEFAULT NULL,
        year VARCHAR(16) DEFAULT NULL,
        link VARCHAR(1024) DEFAULT NULL,
        snippet TEXT,
        cited_by INT DEFAULT NULL,
        source VARCHAR(128) NOT NULL DEFAULT 'hiagent',
        raw_payload LONGTEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uq_literature_title_link (title(255), link(255)),
        KEY idx_literature_source (source),
        KEY idx_literature_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """

    connection = get_mysql_server_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(create_database_sql)
            cursor.execute(create_table_sql)
    finally:
        connection.close()

    print(f"\n$$$$ SYSTEM CALL $$$$:MySQL database: `{DB_NAME}` is ready.\n")
    print(f"$$$$ SYSTEM CALL $$$$:Table: `{DB_NAME}.{TABLE_NAME}` is ready.\n")


if __name__ == "__main__":
    init_mysql_database()
