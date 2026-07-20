"""检索桩 —— 模拟知识库检索，后续由 RAGFlow 替代"""

from typing import List, Optional
from schemas import RecipeRecord
from .base import BaseRetriever


# ============================================================
# 内置种子菜谱（MVP 阶段 mock 用，后续由真实知识库替代）
# ============================================================

SEED_RECIPES: List[RecipeRecord] = [
    RecipeRecord(
        recipe_id="R001", title="番茄炒蛋", cuisine="家常菜",
        tags=["快手菜", "下饭菜", "鸡蛋类"],
        difficulty="简单", estimated_time_min=15, servings=2,
        core_ingredients=["番茄", "鸡蛋"],
        seasonings=["食用油", "盐", "糖"],
        optional_ingredients=["葱"],
        equipment=["炒锅"],
        allergens=["鸡蛋"],
    ),
    RecipeRecord(
        recipe_id="R002", title="青菜鸡蛋汤", cuisine="家常菜",
        tags=["快手菜", "汤羹", "清淡"],
        difficulty="简单", estimated_time_min=10, servings=2,
        core_ingredients=["青菜", "鸡蛋"],
        seasonings=["盐", "食用油", "胡椒粉"],
        optional_ingredients=["豆腐", "姜"],
        equipment=["汤锅"],
        allergens=["鸡蛋"],
    ),
    RecipeRecord(
        recipe_id="R003", title="番茄土豆汤", cuisine="家常菜",
        tags=["汤羹", "开胃", "素食"],
        difficulty="简单", estimated_time_min=20, servings=2,
        core_ingredients=["番茄", "土豆"],
        seasonings=["盐", "食用油", "胡椒粉"],
        optional_ingredients=["洋葱"],
        equipment=["汤锅"],
        allergens=[],
    ),
    RecipeRecord(
        recipe_id="R004", title="葱花煎蛋", cuisine="家常菜",
        tags=["快手菜", "鸡蛋类"],
        difficulty="简单", estimated_time_min=8, servings=2,
        core_ingredients=["鸡蛋"],
        seasonings=["食用油", "盐"],
        optional_ingredients=["葱"],
        equipment=["炒锅"],
        allergens=["鸡蛋"],
    ),
    RecipeRecord(
        recipe_id="R005", title="蒸水蛋", cuisine="家常菜",
        tags=["快手菜", "鸡蛋类", "清淡"],
        difficulty="简单", estimated_time_min=15, servings=2,
        core_ingredients=["鸡蛋"],
        seasonings=["盐", "生抽", "香油"],
        optional_ingredients=["葱"],
        equipment=["蒸锅"],
        allergens=["鸡蛋"],
    ),
    RecipeRecord(
        recipe_id="R006", title="宫保鸡丁", cuisine="川菜",
        tags=["下饭菜", "辣", "鸡肉类"],
        difficulty="中等", estimated_time_min=25, servings=2,
        core_ingredients=["鸡胸肉", "花生", "黄瓜", "胡萝卜"],
        seasonings=["食用油", "盐", "生抽", "醋", "糖", "淀粉", "料酒", "干辣椒"],
        optional_ingredients=["葱", "姜", "蒜"],
        equipment=["炒锅"],
        allergens=["花生"],
    ),
    RecipeRecord(
        recipe_id="R007", title="黄瓜炒鸡片", cuisine="家常菜",
        tags=["快手菜", "清淡", "鸡肉类"],
        difficulty="简单", estimated_time_min=15, servings=2,
        core_ingredients=["鸡胸肉", "黄瓜", "胡萝卜"],
        seasonings=["盐", "食用油", "生抽", "料酒", "淀粉"],
        optional_ingredients=[],
        equipment=["炒锅"],
        allergens=[],
    ),
    RecipeRecord(
        recipe_id="R008", title="酸辣土豆丝", cuisine="家常菜",
        tags=["快手菜", "下饭菜", "辣", "素食"],
        difficulty="简单", estimated_time_min=12, servings=2,
        core_ingredients=["土豆", "青椒"],
        seasonings=["盐", "食用油", "醋", "干辣椒"],
        optional_ingredients=["葱", "蒜"],
        equipment=["炒锅"],
        allergens=[],
    ),
    RecipeRecord(
        recipe_id="R009", title="青椒炒蛋", cuisine="家常菜",
        tags=["快手菜", "鸡蛋类"],
        difficulty="简单", estimated_time_min=10, servings=2,
        core_ingredients=["青椒", "鸡蛋"],
        seasonings=["食用油", "盐"],
        optional_ingredients=[],
        equipment=["炒锅"],
        allergens=["鸡蛋"],
    ),
    RecipeRecord(
        recipe_id="R010", title="番茄牛腩", cuisine="家常菜",
        tags=["硬菜", "炖菜"],
        difficulty="中等", estimated_time_min=90, servings=3,
        core_ingredients=["番茄", "牛腩"],
        seasonings=["盐", "食用油", "生抽", "料酒", "姜"],
        optional_ingredients=["葱", "洋葱"],
        equipment=["炖锅"],
        allergens=[],
    ),
    RecipeRecord(
        recipe_id="R011", title="土豆炖牛肉", cuisine="家常菜",
        tags=["硬菜", "炖菜"],
        difficulty="中等", estimated_time_min=60, servings=3,
        core_ingredients=["土豆", "牛肉", "胡萝卜"],
        seasonings=["盐", "食用油", "生抽", "老抽", "料酒", "姜"],
        optional_ingredients=["洋葱", "葱"],
        equipment=["炖锅"],
        allergens=[],
    ),
    RecipeRecord(
        recipe_id="R012", title="清炒时蔬", cuisine="家常菜",
        tags=["快手菜", "清淡", "素食"],
        difficulty="简单", estimated_time_min=8, servings=2,
        core_ingredients=["青菜"],
        seasonings=["盐", "食用油", "蒜"],
        optional_ingredients=[],
        equipment=["炒锅"],
        allergens=[],
    ),
]


class RetrievalStub(BaseRetriever):
    """
    基于关键词匹配的模拟检索。

    策略（精确匹配，不做子串匹配避免误匹配）：
    - 核心食材命中：+3 分
    - 可选食材命中：+1 分
    - 调料命中：+0.5 分
    - 标题关键词命中：+2 分

    得分归一化到 0~1，按检索分降序返回 top_n。
    """

    def __init__(self, recipes: List[RecipeRecord] | None = None):
        self.recipes = recipes or list(SEED_RECIPES)  # list() 避免共享引用

    # ── BaseRetriever 接口实现 ──────────────────────────

    def search(self, ingredients: List[str], top_n: int = 10) -> List[RecipeRecord]:
        """精确关键词匹配召回候选菜谱"""
        ing_set = set(ingredients)
        scored = []

        for r in self.recipes:
            core = set(r.core_ingredients)
            optional = set(r.optional_ingredients)
            seasons = set(r.seasonings)
            title_words = set(r.title)

            score = 0.0

            for ing in ing_set:
                # 核心食材精确命中
                if ing in core:
                    score += 3.0
                # 可选食材精确命中
                elif ing in optional:
                    score += 1.0
                # 调料精确命中
                elif ing in seasons:
                    score += 0.5
                # 标题关键词命中（单字不算，避免误匹配）
                elif len(ing) >= 2 and ing in title_words:
                    score += 2.0

            if score > 0:
                r.retrieval_score = min(1.0, score / 10.0)  # 归一化到 0~1
                scored.append(r)

        scored.sort(key=lambda r: r.retrieval_score, reverse=True)
        return scored[:top_n]

    def search_ids(self, ingredients: List[str], top_n: int = 10) -> List[tuple[str, float]]:
        """返回 [(recipe_id, score), ...]"""
        candidates = self.search(ingredients, top_n)
        return [(r.recipe_id, r.retrieval_score) for r in candidates]

    def get_by_id(self, recipe_id: str) -> Optional[RecipeRecord]:
        """按 ID 查单道菜谱"""
        for r in self.recipes:
            if r.recipe_id == recipe_id:
                return r
        return None
