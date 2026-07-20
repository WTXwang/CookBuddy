"""检索抽象基类 —— 所有检索实现必须遵守的接口契约"""

from abc import ABC, abstractmethod
from typing import List, Optional
from schemas import RecipeRecord


class BaseRetriever(ABC):
    """
    检索抽象基类。
    stub / RAGFlow / LanceDB 都实现这个接口，
    上层代码（normalizer, scorer, graph）只依赖这个接口，不关心实现。
    """

    @abstractmethod
    def search(self, ingredients: List[str], top_n: int = 10) -> List[RecipeRecord]:
        """
        输入标准化食材名列表，返回候选菜谱（按检索分降序）。

        Args:
            ingredients: 标准化后的食材名，如 ["番茄", "鸡蛋"]
            top_n: 最多返回多少道候选

        Returns:
            按 retrieval_score 降序排列的 RecipeRecord 列表
        """
        ...

    @abstractmethod
    def search_ids(self, ingredients: List[str], top_n: int = 10) -> List[tuple[str, float]]:
        """
        输入食材名列表，返回候选菜谱 ID + 检索分。

        Returns:
            [(recipe_id, score), ...] 按 score 降序
        """
        ...

    def get_full_text(self, recipe_id: str) -> str | None:
        """获取菜谱全文。默认返回 None（stub 不支持）"""
        return None

    @abstractmethod
    def get_by_id(self, recipe_id: str) -> Optional[RecipeRecord]:
        """
        按 recipe_id 查单道菜谱。

        Returns:
            找到返回 RecipeRecord，否则 None
        """
        ...
