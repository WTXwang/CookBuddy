"""scorer 单元测试"""
import pytest
from schemas import RecipeRecord, CandidateFeature
from rules.scorer import build_feature, score_and_rank


# ── 测试用菜谱 ──

def make_recipe(recipe_id="T001", title="测试菜", core=None, optional=None,
                allergens=None, equipment=None, difficulty="简单",
                estimated_time_min=15, retrieval_score=0.8):
    return RecipeRecord(
        recipe_id=recipe_id, title=title,
        core_ingredients=core or ["鸡蛋", "番茄"],
        optional_ingredients=optional or ["葱"],
        seasonings=["食用油", "盐"],
        equipment=equipment or ["炒锅"],
        allergens=allergens or [],
        difficulty=difficulty,
        estimated_time_min=estimated_time_min,
        retrieval_score=retrieval_score,
    )


class TestBuildFeature:
    """特征提取测试"""

    def test_perfect_match(self):
        """完美匹配：所有核心食材都有"""
        recipe = make_recipe()
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], [], "", 20, ["炒锅"])
        assert f.core_total == 2
        assert f.core_matched == 2
        assert f.missing_core == []
        assert not f.blocked
        assert f.equipment_fit == 1.0

    def test_missing_core(self):
        """缺失核心食材"""
        recipe = make_recipe(core=["鸡蛋", "番茄", "土豆"])
        f = build_feature(recipe, ["鸡蛋"], [], [], "", 20, ["炒锅"])
        assert f.core_matched == 1
        assert f.core_total == 3
        assert "番茄" in f.missing_core
        assert "土豆" in f.missing_core

    def test_missing_optional(self):
        """缺失可选食材"""
        recipe = make_recipe(optional=["葱", "姜"])
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], [], "", 20, ["炒锅"])
        assert "葱" in f.missing_optional
        assert "姜" in f.missing_optional

    def test_allergen_block(self):
        """过敏原硬阻断"""
        recipe = make_recipe(allergens=["花生", "鸡蛋"])
        f = build_feature(recipe, ["鸡蛋", "番茄"], ["花生"], [], "", 20, ["炒锅"])
        assert f.blocked
        assert any("花生" in r for r in f.block_reasons)

    def test_allergen_in_core_ingredient(self):
        """过敏原在核心食材中——即使 allergens 字段已声明也阻断"""
        recipe = make_recipe(allergens=["鸡蛋"])
        f = build_feature(recipe, ["鸡蛋", "番茄"], ["鸡蛋"], [], "", 20, ["炒锅"])
        assert f.blocked

    def test_excluded_block(self):
        """忌口硬阻断"""
        recipe = make_recipe(core=["鸡蛋", "番茄", "香菜"])
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], ["香菜"], "", 20, ["炒锅"])
        assert f.blocked

    def test_no_allergen_no_block(self):
        """没有过敏原则不应该阻断"""
        recipe = make_recipe(allergens=["鸡蛋"])
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], [], "", 20, ["炒锅"])
        assert not f.blocked

    def test_empty_allergens(self):
        """空过敏原不应阻断"""
        recipe = make_recipe(allergens=["鸡蛋"])
        f = build_feature(recipe, ["鸡蛋"], [""], [], "", 20, ["炒锅"])
        assert not f.blocked

    # ── 软约束 ──

    def test_time_fit_within_limit(self):
        """时间在限制内 → time_fit=1"""
        recipe = make_recipe(estimated_time_min=15)
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], [], "", 30, ["炒锅"])
        assert f.time_fit == 1.0

    def test_time_fit_over_limit(self):
        """超时 → time_fit < 1"""
        recipe = make_recipe(estimated_time_min=90)
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], [], "", 20, ["炒锅"])
        assert f.time_fit < 1.0

    def test_time_fit_zero_time(self):
        """时间为 0 的边界情况"""
        recipe = make_recipe(estimated_time_min=0)
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], [], "", 20, ["炒锅"])
        assert f.time_fit == 1.0

    def test_difficulty_fit_exact(self):
        """难度完全匹配"""
        recipe = make_recipe(difficulty="简单")
        f = build_feature(recipe, ["鸡蛋"], [], [], "", 20, [], user_difficulty="简单")
        assert f.difficulty_fit == 1.0

    def test_difficulty_fit_one_level_off(self):
        """难度差一级"""
        recipe = make_recipe(difficulty="中等")
        f = build_feature(recipe, ["鸡蛋"], [], [], "", 20, [], user_difficulty="简单")
        assert f.difficulty_fit == 0.6

    def test_difficulty_fit_two_levels_off(self):
        """难度差两级"""
        recipe = make_recipe(difficulty="困难")
        f = build_feature(recipe, ["鸡蛋"], [], [], "", 20, [], user_difficulty="简单")
        assert f.difficulty_fit == 0.3

    def test_difficulty_any(self):
        """不限难度"""
        recipe = make_recipe(difficulty="困难")
        f = build_feature(recipe, ["鸡蛋"], [], [], "", 20, [], user_difficulty="任意")
        assert f.difficulty_fit == 1.0

    def test_flavor_spicy_preference(self):
        """偏好辣但菜谱不辣"""
        recipe = make_recipe()  # tags=[] by default
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], [], "辣", 20, ["炒锅"])
        assert f.preference_score < 1.0

    def test_equipment_partial_match(self):
        """厨具部分匹配"""
        recipe = make_recipe(equipment=["炒锅", "蒸锅"])
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], [], "", 20, ["炒锅"])
        assert f.equipment_fit == 0.5  # 1/2

    def test_no_equipment_needed(self):
        """不需要特殊厨具"""
        recipe = make_recipe(equipment=[])
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], [], "", 20, [])
        assert f.equipment_fit == 1.0


class TestScoreAndRank:
    """评分排序测试"""

    def test_ranking_blocked_last(self):
        """blocked 的直接被移除"""
        r1 = make_recipe("R001", "正常菜")
        r2 = make_recipe("R002", "过敏菜", allergens=["花生"])
        f1 = build_feature(r1, ["鸡蛋", "番茄"], [], [], "", 20, ["炒锅"])
        f2 = build_feature(r2, ["鸡蛋", "番茄"], ["花生"], [], "", 20, ["炒锅"])

        ranked = score_and_rank([f1, f2])
        # blocked 被移除，只剩正常菜
        assert len(ranked) == 1
        assert ranked[0].recipe_id == "R001"

    def test_ranking_fewer_missing_core_first(self):
        """缺失核心少的排前面"""
        r1 = make_recipe("R001", "全匹配", core=["鸡蛋"])
        r2 = make_recipe("R002", "缺一个", core=["鸡蛋", "番茄"])
        f1 = build_feature(r1, ["鸡蛋"], [], [], "", 20, [])
        f2 = build_feature(r2, ["鸡蛋"], [], [], "", 20, [])

        ranked = score_and_rank([f1, f2])
        assert ranked[0].recipe_id == "R001"

    def test_score_range(self):
        """评分在 0-100 范围"""
        recipe = make_recipe()
        f = build_feature(recipe, ["鸡蛋", "番茄"], [], [], "", 20, ["炒锅"])
        ranked = score_and_rank([f])
        assert 0 <= ranked[0].final_score <= 100

    def test_empty_list(self):
        """空列表返回空"""
        assert score_and_rank([]) == []

    def test_single_candidate(self):
        """单候选"""
        recipe = make_recipe()
        f = build_feature(recipe, ["鸡蛋"], [], [], "", 20, [])
        ranked = score_and_rank([f])
        assert len(ranked) == 1
        assert ranked[0].final_score >= 0

    def test_all_blocked(self):
        """全部被阻断——返回空列表"""
        r1 = make_recipe("R001", allergens=["鸡蛋"])
        r2 = make_recipe("R002", allergens=["花生"])
        f1 = build_feature(r1, ["鸡蛋"], ["鸡蛋"], [], "", 20, [])
        f2 = build_feature(r2, ["鸡蛋"], ["花生"], [], "", 20, [])

        ranked = score_and_rank([f1, f2])
        assert len(ranked) == 0  # 全部阻断，空列表
