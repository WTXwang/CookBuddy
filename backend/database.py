"""SQLite 数据库连接管理"""

import sys
from pathlib import Path

import aiosqlite
import config

_db: aiosqlite.Connection | None = None


def _ensure_data_dir(db_path: str) -> None:
    """确保数据库文件所在目录存在"""
    parent = Path(db_path).parent
    parent.mkdir(parents=True, exist_ok=True)


async def init_db() -> None:
    """创建 SQLite 连接 + 初始化表结构"""
    global _db

    db_path = config.DATABASE_PATH
    _ensure_data_dir(db_path)

    try:
        _db = await aiosqlite.connect(db_path)
        _db.row_factory = aiosqlite.Row
    except Exception as e:
        print(f"[DB] 打开 SQLite 失败: {e}")
        print(f"[DB] 路径: {db_path}")
        sys.exit(1)

    await _init_tables()


async def _init_tables() -> None:
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _db.commit()


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


async def get_db() -> aiosqlite.Connection:
    assert _db is not None, "数据库未初始化"
    return _db
