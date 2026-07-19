"""normalizer 单元测试"""
import pytest
from rules.normalizer import (
    normalize_name, classify_ingredient, normalize_ingredients,
    parse_quantity, parse_ingredients_text, SYNONYM_MAP,
)


class TestSynonymMap:
    """别名映射测试"""

    def test_size(self):
        """别名表至少 100 条"""
        assert len(SYNONYM_MAP) >= 100, f"别名仅 {len(SYNONYM_MAP)} 条"

    def test_vegetable_aliases(self):
        """蔬菜别名"""
        assert normalize_name("西红柿") == "番茄"
        assert normalize_name("蕃茄") == "番茄"
        assert normalize_name("马铃薯") == "土豆"
        assert normalize_name("洋芋") == "土豆"
        assert normalize_name("包菜") == "卷心菜"
        assert normalize_name("圆白菜") == "卷心菜"

    def test_meat_aliases(self):
        """肉类别名"""
        assert normalize_name("鸡胸") == "鸡胸肉"
        assert normalize_name("瘦肉") == "猪肉"

    def test_seafood_aliases(self):
        """水产别名"""
        assert normalize_name("虾仁") == "虾"
        assert normalize_name("大虾") == "虾"

    def test_unknown_word_returns_itself(self):
        """未知词返回自身"""
        assert normalize_name("龙肉") == "龙肉"
        assert normalize_name("") == ""


class TestClassify:
    """分类测试"""

    def test_vegetable(self):
        assert classify_ingredient("番茄") == "蔬菜"
        assert classify_ingredient("土豆") == "蔬菜"

    def test_egg(self):
        assert classify_ingredient("鸡蛋") == "蛋类"

    def test_tofu(self):
        assert classify_ingredient("豆腐") == "豆制品"

    def test_meat(self):
        assert classify_ingredient("鸡胸肉") == "鸡肉"
        assert classify_ingredient("猪肉") == "猪肉"
        assert classify_ingredient("牛肉") == "牛肉"

    def test_seafood(self):
        assert classify_ingredient("虾") == "水产"

    def test_unknown(self):
        assert classify_ingredient("火星石") == "其他"


class TestParseQuantity:
    """数量解析测试"""

    def test_digit_with_unit(self):
        assert parse_quantity("鸡蛋2个") == ("鸡蛋", "2个")
        assert parse_quantity("土豆3个") == ("土豆", "3个")

    def test_chinese_number(self):
        assert parse_quantity("番茄一个") == ("番茄", "一个")

    def test_vague_quantity(self):
        assert parse_quantity("盐少许") == ("盐", "少许")
        assert parse_quantity("糖适量") == ("糖", "适量")

    def test_no_quantity(self):
        assert parse_quantity("牛肉") == ("牛肉", "")
        assert parse_quantity("番茄") == ("番茄", "")

    def test_half(self):
        assert parse_quantity("白菜半个") == ("白菜", "半个")


class TestNormalizeIngredients:
    """标准化列表测试"""

    def test_alias_and_dedup(self):
        """别名映射 + 去重"""
        result = normalize_ingredients(["西红柿", "番茄", "马铃薯"])
        names = [r.name for r in result]
        assert len(result) == 2  # 西红柿、番茄 → 都映射为番茄，去重
        assert "番茄" in names
        assert "土豆" in names

    def test_quantity_preserved(self):
        """数量信息保留"""
        result = normalize_ingredients(["鸡蛋2个", "番茄"])
        egg = next(r for r in result if r.name == "鸡蛋")
        assert egg.quantity == "2个"
        assert egg.raw == "鸡蛋2个"

    def test_category_assigned(self):
        """分类正确"""
        result = normalize_ingredients(["鸡蛋", "番茄", "虾"])
        cats = {r.name: r.category for r in result}
        assert cats["鸡蛋"] == "蛋类"
        assert cats["番茄"] == "蔬菜"
        assert cats["虾"] == "水产"

    def test_empty_list(self):
        assert normalize_ingredients([]) == []

    def test_whitespace_only(self):
        assert normalize_ingredients(["  ", "\t"]) == []


class TestParseIngredientsText:
    """自然语言输入解析测试"""

    def test_basic_ingredients(self):
        """基本食材解析"""
        parsed = parse_ingredients_text("鸡蛋、番茄、土豆")
        assert "鸡蛋" in parsed["ingredient_items"]
        assert "番茄" in parsed["ingredient_items"]
        assert "土豆" in parsed["ingredient_items"]

    def test_servings_extraction(self):
        """人数提取"""
        assert parse_ingredients_text("鸡蛋、番茄，两人")["servings"] == 2
        assert parse_ingredients_text("鸡蛋，三人份")["servings"] == 3
        assert parse_ingredients_text("鸡蛋，2人份")["servings"] == 2

    def test_time_extraction(self):
        """时间提取"""
        assert parse_ingredients_text("鸡蛋，20分钟")["time_limit_min"] == 20
        assert parse_ingredients_text("鸡蛋，半小时")["time_limit_min"] == 30

    def test_flavor_no_spicy(self):
        """口味：不辣"""
        parsed = parse_ingredients_text("鸡蛋、番茄，不要辣")
        assert parsed["flavor"] == "不辣"
        assert "不要" not in parsed["ingredient_items"]

    def test_flavor_spicy(self):
        """口味：辣"""
        parsed = parse_ingredients_text("鸡胸肉，麻辣")
        assert parsed["flavor"] == "辣"

    def test_flavor_light(self):
        """口味：清淡"""
        parsed = parse_ingredients_text("豆腐、青菜，清淡")
        assert parsed["flavor"] == "清淡"

    def test_allergen_peanut(self):
        """花生过敏检测"""
        parsed = parse_ingredients_text("鸡胸肉、花生，花生过敏")
        assert "花生" in parsed["allergens"]

    def test_allergen_egg(self):
        """鸡蛋过敏检测"""
        parsed = parse_ingredients_text("鸡蛋、番茄，鸡蛋过敏")
        assert "鸡蛋" in parsed["allergens"]

    def test_difficulty_simple(self):
        """难度：简单"""
        parsed = parse_ingredients_text("鸡蛋，简单快手")
        assert parsed["difficulty"] == "简单"
        assert "快手" not in parsed["ingredient_items"]

    def test_complex_input(self):
        """复合输入"""
        parsed = parse_ingredients_text(
            "鸡胸肉、黄瓜、花生，两人，30分钟，花生过敏，不辣"
        )
        assert "鸡胸肉" in parsed["ingredient_items"]
        assert parsed["servings"] == 2
        assert parsed["time_limit_min"] == 30
        assert "花生" in parsed["allergens"]
        assert parsed["flavor"] == "不辣"

    def test_empty_input(self):
        parsed = parse_ingredients_text("")
        assert parsed["ingredient_items"] == []
        assert parsed["servings"] is None
