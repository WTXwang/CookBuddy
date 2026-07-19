"""MySQL 数据库连接管理"""

import sys
from urllib.parse import urlparse

import aiomysql
import config

_pool: aiomysql.Pool | None = None


def _parse_db_url(url: str) -> dict:
    """解析 DATABASE_URL → aiomysql 所需参数"""
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "db": parsed.path.lstrip("/") or "chef",
    }


async def init_pool() -> None:
    """创建连接池 + 初始化表结构"""
    global _pool
    params = _parse_db_url(config.DATABASE_URL)

    try:
        _pool = await aiomysql.create_pool(
            **params,
            autocommit=True,
            minsize=1,
            maxsize=10,
        )
    except Exception as e:
        print(f"[DB] 连接 MySQL 失败: {e}")
        print(f"[DB] 请确认 MySQL 已启动，且 config.py 中 DATABASE_URL 正确")
        print(f"[DB] 当前 URL: {config.DATABASE_URL}")
        print(f"[DB] 提示：首次使用需先创建数据库：")
        print(f"[DB]   CREATE DATABASE IF NOT EXISTS {params['db']} CHARACTER SET utf8mb4;")
        sys.exit(1)

    await _init_tables()


async def _init_tables() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql)


async def close_pool() -> None:
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


async def get_pool() -> aiomysql.Pool:
    assert _pool is not None, "数据库连接池未初始化"
    return _pool
