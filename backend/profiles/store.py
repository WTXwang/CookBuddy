"""用户画像存储 —— 每个用户一个 JSON 文件"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from schemas import UserProfile, UserPreferences, UserStats


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        """部分更新偏好字段"""
        profile = self.get(user_id)

        if flavor is not None:
            profile.preferences.flavor = flavor
        if difficulty is not None:
            profile.preferences.difficulty = difficulty
        if time_limit_min is not None:
            profile.preferences.time_limit_min = time_limit_min
        if servings is not None:
            profile.preferences.servings = servings
        if allergens is not None:
            profile.allergens = allergens
        if excluded_ingredients is not None:
            profile.excluded_ingredients = excluded_ingredients
        if equipment is not None:
            profile.equipment = equipment

        self.save(profile)
        return profile

    # ── 更新统计 ──────────────────────────────────────

    def update_stats(
        self,
        user_id: int,
        cuisines: List[str] | None = None,
        ingredients: List[str] | None = None,
    ) -> None:
        """每次推荐后更新历史统计"""
        profile = self.get(user_id)
        stats = profile.stats

        stats.total_recommendations += 1
        stats.last_updated = _now_iso()

        for c in (cuisines or []):
            stats.favorite_cuisines[c] = stats.favorite_cuisines.get(c, 0) + 1

        for ing in (ingredients or []):
            stats.frequent_ingredients[ing] = stats.frequent_ingredients.get(ing, 0) + 1

        profile.stats = stats
        self.save(profile)
