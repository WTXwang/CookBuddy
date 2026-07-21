"""用户画像存储 —— 每个用户一个 JSON 文件

约束规则：
  - 口味：固定词汇表，不能自创
  - 过敏原 / 忌口：每项 ≤10 字，数量有上限
  - 厨具：固定词汇表
  - 统计：自动淘汰低频项，防止野蛮生长
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from schemas import UserProfile, UserPreferences, UserStats


# ═══════════════════════════════════════════════════════
# 固定词汇表
# ═══════════════════════════════════════════════════════

VALID_FLAVORS = {"辣", "不辣", "酸甜", "清淡", "重口味", "咸香", "麻", "蒜香", "酱香", "酸辣"}

VALID_EQUIPMENT = {"炒锅", "蒸锅", "烤箱", "汤锅", "空气炸锅", "微波炉", "电饭煲", "压力锅", "平底锅", "炖锅"}

VALID_DIFFICULTY = {"任意", "简单", "中等", "困难"}

# 数量上限
MAX_ALLERGENS = 15          # 过敏原最多 15 项
MAX_EXCLUDED = 20           # 忌口最多 20 项
MAX_FLAVOR = 5              # 口味最多选 5 个
MAX_ITEM_CHARS = 10         # 单项过敏原/忌口最多 10 字
MAX_STAT_CUISINES = 20      # 菜系统计最多保留 20 项
MAX_STAT_INGREDIENTS = 30   # 食材统计最多保留 30 项


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _top_keys(d: dict, n: int) -> dict:
    """保留计数最高的 n 个 key"""
    return dict(sorted(d.items(), key=lambda x: x[1], reverse=True)[:n])


class ProfileStore:
    """用户画像 JSON 文件存储"""

    def __init__(self, profiles_dir: str):
        self._dir = Path(profiles_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _file(self, user_id: int) -> Path:
        return self._dir / f"{user_id}.json"

    # ── 读取 ──────────────────────────────────────────

    def get(self, user_id: int) -> UserProfile:
        """获取画像，文件不存在返回空画像"""
        path = self._file(user_id)
        if not path.exists():
            return UserProfile(user_id=user_id)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return UserProfile(**data)
        except (json.JSONDecodeError, TypeError):
            return UserProfile(user_id=user_id)

    # ── 写入 ──────────────────────────────────────────

    def save(self, profile: UserProfile) -> None:
        """完整写入画像（覆盖）"""
        path = self._file(profile.user_id)
        path.write_text(
            profile.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── 校验 ──────────────────────────────────────────

    @staticmethod
    def _validate_flavor(flavor: List[str]) -> List[str]:
        """只保留合法口味，去重，限制数量"""
        valid = [f for f in flavor if f in VALID_FLAVORS]
        seen = set()
        result = []
        for f in valid:
            if f not in seen:
                seen.add(f)
                result.append(f)
        return result[:MAX_FLAVOR]

    @staticmethod
    def _validate_items(items: List[str], max_items: int) -> List[str]:
        """每项 ≤10 字，去重，限制数量"""
        result = []
        seen = set()
        for item in items:
            item = item.strip()
            if not item or item in seen:
                continue
            if len(item) > MAX_ITEM_CHARS:
                item = item[:MAX_ITEM_CHARS]
            seen.add(item)
            result.append(item)
            if len(result) >= max_items:
                break
        return result

    @staticmethod
    def _validate_equipment(equipment: List[str]) -> List[str]:
        """只保留合法厨具，去重"""
        seen = set()
        result = []
        for e in equipment:
            if e in VALID_EQUIPMENT and e not in seen:
                seen.add(e)
                result.append(e)
        return result

    # ── 更新偏好 ──────────────────────────────────────

    def update_preferences(
        self,
        user_id: int,
        flavor: List[str] | None = None,
        difficulty: str | None = None,
        time_limit_min: int | None = None,
        servings: int | None = None,
        allergens: List[str] | None = None,
        excluded_ingredients: List[str] | None = None,
        equipment: List[str] | None = None,
    ) -> UserProfile:
        """部分更新偏好字段（自动校验 + 截断）"""
        profile = self.get(user_id)

        if flavor is not None:
            profile.preferences.flavor = self._validate_flavor(flavor)
        if difficulty is not None and difficulty in VALID_DIFFICULTY:
            profile.preferences.difficulty = difficulty
        if time_limit_min is not None:
            profile.preferences.time_limit_min = max(1, min(480, time_limit_min))
        if servings is not None:
            profile.preferences.servings = max(1, min(20, servings))
        if allergens is not None:
            profile.allergens = self._validate_items(allergens, MAX_ALLERGENS)
        if excluded_ingredients is not None:
            profile.excluded_ingredients = self._validate_items(excluded_ingredients, MAX_EXCLUDED)
        if equipment is not None:
            profile.equipment = self._validate_equipment(equipment)

        self.save(profile)
        return profile

    # ── 更新统计 ──────────────────────────────────────

    def update_stats(
        self,
        user_id: int,
        cuisines: List[str] | None = None,
        ingredients: List[str] | None = None,
    ) -> None:
        """每次推荐后更新历史统计，自动淘汰低频项"""
        profile = self.get(user_id)
        stats = profile.stats

        stats.total_recommendations += 1
        stats.last_updated = _now_iso()

        for c in (cuisines or []):
            stats.favorite_cuisines[c] = stats.favorite_cuisines.get(c, 0) + 1
        for ing in (ingredients or []):
            stats.frequent_ingredients[ing] = stats.frequent_ingredients.get(ing, 0) + 1

        # 每 10 次推荐清理一次低频项
        if stats.total_recommendations % 10 == 0:
            stats.favorite_cuisines = _top_keys(stats.favorite_cuisines, MAX_STAT_CUISINES)
            stats.frequent_ingredients = _top_keys(stats.frequent_ingredients, MAX_STAT_INGREDIENTS)

        profile.stats = stats
        self.save(profile)
