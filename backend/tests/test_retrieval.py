"""retrieval 单元测试 —— 对 stub 和抽象接口通用测试"""
import pytest
from schemas import RecipeRecord
from retrieval.base import BaseRetriever
from retrieval.stub import RetrievalStub, SEED_RECIPES
from retrieval import create_retriever


class TestBaseRetriever:
    """接口契约测试"""

    def test_cannot_instantiate_abstract(self):
        """不能直接实例化抽象基类"""
        with pytest.raises(TypeError):
            BaseRetriever()


class TestRetrievalStub:
    """stub 检索实现测试"""

    @pytest.fixture
    def stub(self):
        return RetrievalStub()

    def test_implements_base(self):
        """实现 BaseRetriever 接口"""
        stub = RetrievalStub()
        assert isinstance(stub, BaseRetriever)

    # ── search ──

    def test_exact_match_returns_result(self, stub):
        """精确食材匹配返回结果"""
        candidates = stub.search(["番茄", "鸡蛋"], top_n=5)
        assert len(candidates) > 0
        titles = [c.title for c in candidates]
        assert "番茄炒蛋" in titles

    def test_top_result_highest_score(self, stub):
        """第一条结果得分最高"""
        candidates = stub.search(["番茄", "鸡蛋"], top_n=5)
        if len(candidates) >= 2:
            assert candidates[0].retrieval_score >= candidates[1].retrieval_score

    def test_no_match_returns_empty(self, stub):
        """无匹配返回空列表"""
        candidates = stub.search(["火星陨石"], top_n=5)
        assert candidates == []

    def test_single_char_no_false_match(self, stub):
        """单字不应误匹配（子串匹配 bug 修复）"""
        candidates = stub.search(["牛"], top_n=10)
        # "牛" 不在任何核心食材列表中 —— 只有 "牛肉"、"牛腩" 是食材
        # 所以应该返回空
        assert candidates == []

    def test_empty_ingredients(self, stub):
        """空食材列表"""
        candidates = stub.search([], top_n=5)
        assert candidates == []

    def test_respects_top_n(self, stub):
        """top_n 限制生效"""
        candidates = stub.search(["鸡蛋"], top_n=3)
        assert len(candidates) <= 3

    def test_scores_are_normalized(self, stub):
        """检索分归一化到 0~1"""
        candidates = stub.search(["番茄", "鸡蛋"], top_n=10)
        for c in candidates:
            assert 0.0 <= c.retrieval_score <= 1.0

    def test_seasoning_match_lower_than_core(self, stub):
        """调料匹配得分低于核心食材匹配"""
        # 仅命中调料
        cand_seasoning = stub.search(["食用油"], top_n=10)
        # 命中核心食材
        cand_core = stub.search(["鸡蛋"], top_n=10)

        if cand_seasoning and cand_core:
            max_seasoning = max(c.retrieval_score for c in cand_seasoning)
            max_core = max(c.retrieval_score for c in cand_core)
            assert max_core >= max_seasoning, \
                f"核心匹配({max_core})应 ≥ 调料匹配({max_seasoning})"

    def test_custom_recipes(self):
        """自定义菜谱列表"""
        custom = [
            RecipeRecord(
                recipe_id="C001", title="自定义菜",
                core_ingredients=["火星石", "木星尘"],
                seasonings=[], optional_ingredients=[],
                equipment=[], allergens=[],
            )
        ]
        stub = RetrievalStub(recipes=custom)
        assert len(stub.search(["火星石"])) == 1
        assert stub.search(["番茄"]) == []

    # ── get_by_id ──

    def test_get_existing_recipe(self, stub):
        """按 ID 查存在的菜谱"""
        r = stub.get_by_id("R001")
        assert r is not None
        assert r.title == "番茄炒蛋"

    def test_get_nonexistent_recipe(self, stub):
        """查不存在的 ID"""
        r = stub.get_by_id("R999")
        assert r is None

    def test_seed_recipes_count(self):
        """种子菜谱数量"""
        assert len(SEED_RECIPES) == 12

    def test_seed_recipes_have_required_fields(self):
        """种子菜谱必要字段不为空"""
        for r in SEED_RECIPES:
            assert r.recipe_id, f"{r.title} 缺少 recipe_id"
            assert r.title, "缺少 title"
            assert r.core_ingredients, f"{r.title} 缺少 core_ingredients"


class TestCreateRetriever:
    """工厂函数测试"""

    def test_returns_base_retriever(self):
        """返回 BaseRetriever 实例"""
        r = create_retriever()
        assert isinstance(r, BaseRetriever)

    def test_default_is_stub(self):
        """默认返回 stub"""
        r = create_retriever()
        assert isinstance(r, RetrievalStub)
