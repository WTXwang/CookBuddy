"""菜谱元数据管理器 —— SQLite 缓存 + LLM 提取 + normalize

独立模块，不绑死 RAGFlow、不绑死 pipeline。
LLM 提取能力通过构造函数注入，文本由调用方提供。
"""

import json
import sqlite3
import os
from typing import Callable, List, Optional

from schemas import RecipeRecord
from rules.normalizer import normalize_name, normalize_equipment


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS recipe_meta (
    recipe_id   TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    cuisine     TEXT DEFAULT '家常菜',
    tags        TEXT DEFAULT '[]',
    difficulty  TEXT DEFAULT '中等',
    time_min    INTEGER DEFAULT 30,
    servings    INTEGER DEFAULT 2,
    core_ingredients    TEXT DEFAULT '[]',
    seasonings          TEXT DEFAULT '[]',
    optional_ingredients TEXT DEFAULT '[]',
    equipment   TEXT DEFAULT '[]',
    allergens   TEXT DEFAULT '[]',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _to_json(val) -> str:
    return json.dumps(val, ensure_ascii=False)


def _from_json(val: str) -> list:
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


class RecipeMetaStore:
    """
    菜谱元数据管理器。

    工作逻辑:
        get_or_create(recipe_id, full_text):
            1. 用 recipe_id 查 SQLite → 命中返回
            2. 未命中 + 有 full_text → llm_extractor 提取 → normalize → 写库 → 返回
            3. 未命中 + 无 full_text → 返回 None
    """

    def __init__(self,
                 db_path: str,
                 llm_extractor: Callable[[str], dict | None] | None = None):
        """
        Args:
            db_path: SQLite 数据库路径，":memory:" = 纯内存
            llm_extractor: (full_text) -> 结构化字段 dict | None
                {
                    "title": "番茄炒蛋",
                    "core_ingredients": ["番茄", "鸡蛋"],
                    "seasonings": ["食用油", "盐"],
                    "optional_ingredients": ["葱"],
                    "equipment": ["炒锅"],
                    "allergens": ["鸡蛋"],
                    "difficulty": "简单",
                    "estimated_time_min": 15,
                    "cuisine": "家常菜",
                    "tags": ["快手菜"],
                    "servings": 2,
                    "body": "做法正文..."
                }
        """
        self.llm_extractor = llm_extractor
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    # ── 公开接口 ──────────────────────────────────────

    def get_or_create(self, recipe_id: str, full_text: str = "") -> RecipeRecord | None:
        """
        1. 查 SQLite → 命中返回
        2. 未命中 + 有 full_text + 有 llm_extractor → 提取 → 入库 → 返回
        3. 否则 → 返回 None
        """
        recipe_id = recipe_id.strip()
        if not recipe_id:
            return None

        cached = self._query(recipe_id)
        if cached:
            return cached

        if full_text and self.llm_extractor:
            meta = self.llm_extractor(full_text)
            if meta:
                record = self._meta_to_record(recipe_id, meta)
                self._insert(record)
                return record

        return None

    def batch_get_or_create(self, items: List[tuple[str, str]]) -> List[RecipeRecord]:
        """
        批量获取/创建。

        Args:
            items: [(recipe_id, full_text), ...]
                   已缓存的 id 可以不传 full_text ("")。
        """
        result = []
        for recipe_id, full_text in items:
            r = self.get_or_create(recipe_id, full_text)
            if r:
                result.append(r)
        return result

    def get(self, recipe_id: str) -> RecipeRecord | None:
        """纯查缓存（不触发提取）"""
        return self.get_or_create(recipe_id, "")

    def put(self, recipe_id: str, data: RecipeRecord) -> None:
        """手动写入/更新（自动 normalize 食材名 + 厨具名）"""
        data.core_ingredients = [normalize_name(i) for i in data.core_ingredients]
        data.seasonings = [normalize_name(i) for i in data.seasonings]
        data.optional_ingredients = [normalize_name(i) for i in data.optional_ingredients]
        data.allergens = [normalize_name(i) for i in data.allergens]
        data.equipment = [normalize_equipment(e) for e in data.equipment]
        self._insert(data)

    def has(self, recipe_id: str) -> bool:
        """检查是否已缓存"""
        row = self._conn.execute(
            "SELECT 1 FROM recipe_meta WHERE recipe_id = ?",
            (recipe_id.strip(),)
        ).fetchone()
        return row is not None

    # ── 内部方法 ──────────────────────────────────────

    def _query(self, recipe_id: str) -> RecipeRecord | None:
        row = self._conn.execute(
            "SELECT * FROM recipe_meta WHERE recipe_id = ?",
            (recipe_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def _insert(self, record: RecipeRecord) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO recipe_meta
               (recipe_id, title, cuisine, tags, difficulty, time_min, servings,
                core_ingredients, seasonings, optional_ingredients,
                equipment, allergens, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)""",
            (
                record.recipe_id, record.title, record.cuisine,
                _to_json(record.tags), record.difficulty,
                record.estimated_time_min, record.servings,
                _to_json(record.core_ingredients),
                _to_json(record.seasonings),
                _to_json(record.optional_ingredients),
                _to_json(record.equipment),
                _to_json(record.allergens),
            )
        )
        self._conn.commit()

    def _row_to_record(self, row) -> RecipeRecord:
        cols = [
            "recipe_id", "title", "cuisine", "tags", "difficulty",
            "time_min", "servings", "core_ingredients", "seasonings",
            "optional_ingredients", "equipment", "allergens",
            "created_at", "updated_at",
        ]
        d = dict(zip(cols, row))
        return RecipeRecord(
            recipe_id=d["recipe_id"],
            title=d["title"],
            cuisine=d.get("cuisine", "家常菜"),
            tags=_from_json(d.get("tags", "[]")),
            difficulty=d.get("difficulty", "中等"),
            estimated_time_min=d.get("time_min", 30),
            servings=d.get("servings", 2),
            core_ingredients=_from_json(d.get("core_ingredients", "[]")),
            seasonings=_from_json(d.get("seasonings", "[]")),
            optional_ingredients=_from_json(d.get("optional_ingredients", "[]")),
            equipment=_from_json(d.get("equipment", "[]")),
            allergens=_from_json(d.get("allergens", "[]")),
        )

    def _meta_to_record(self, recipe_id: str, meta: dict) -> RecipeRecord:
        """LLM 提取的 dict → RecipeRecord，食材名全部 normalize"""
        return RecipeRecord(
            recipe_id=recipe_id,
            title=meta.get("title", recipe_id),
            cuisine=meta.get("cuisine", "家常菜"),
            tags=meta.get("tags", []),
            difficulty=meta.get("difficulty", "中等"),
            estimated_time_min=meta.get("estimated_time_min", 30),
            servings=meta.get("servings", 2),
            core_ingredients=[normalize_name(i) for i in meta.get("core_ingredients", [])],
            seasonings=[normalize_name(i) for i in meta.get("seasonings", [])],
            optional_ingredients=[normalize_name(i) for i in meta.get("optional_ingredients", [])],
            equipment=[normalize_equipment(e) for e in meta.get("equipment", [])],
            allergens=[normalize_name(i) for i in meta.get("allergens", [])],
        )
