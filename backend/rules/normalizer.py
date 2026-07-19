"""食材标准化 —— 别名映射、去重、分类"""

from typing import List, Dict, Optional
from schemas import RawIngredient

# 同义词表（MVP：50+ 组别名）
SYNONYM_MAP: Dict[str, str] = {
    # 蔬菜
    "西红柿": "番茄", "蕃茄": "番茄",
    "马铃薯": "土豆", "洋芋": "土豆", "山药蛋": "土豆",
    "包菜": "卷心菜", "圆白菜": "卷心菜", "甘蓝": "卷心菜",
    "青菜": "青菜", "小白菜": "青菜", "上海青": "青菜",
    "青椒": "青椒", "柿子椒": "青椒", "菜椒": "青椒",
    "胡萝卜": "胡萝卜", "红萝卜": "胡萝卜",
    "洋葱": "洋葱", "葱头": "洋葱",
    "黄瓜": "黄瓜", "青瓜": "黄瓜",
    "茄子": "茄子", "矮瓜": "茄子",
    "西葫芦": "西葫芦", "角瓜": "西葫芦",
    "花菜": "花菜", "花椰菜": "花菜", "菜花": "花菜",
    "西兰花": "西兰花", "青花菜": "西兰花",

    # 蛋类 / 豆制品
    "鸡蛋": "鸡蛋", "鸡子儿": "鸡蛋",
    "豆腐": "豆腐",
    "豆干": "豆干", "豆腐干": "豆干",

    # 肉类
    "鸡胸肉": "鸡胸肉", "鸡胸": "鸡胸肉",
    "鸡腿": "鸡腿", "鸡腿肉": "鸡腿",
    "猪肉": "猪肉", "猪瘦肉": "猪肉",
    "牛肉": "牛肉",
    "牛腩": "牛腩",

    # 水产
    "虾": "虾", "虾仁": "虾", "大虾": "虾", "对虾": "虾",
    "鱼": "鱼", "鱼肉": "鱼",

    # 主食
    "米饭": "米饭", "大米": "米饭",
    "面条": "面条", "挂面": "面条",
    "面粉": "面粉",

    # 调料（部分常见）
    "酱油": "生抽",
    "油": "食用油", "菜油": "食用油", "花生油": "食用油",
}

# 简易分类
CATEGORY_RULES = {
    "番茄": "蔬菜", "土豆": "蔬菜", "卷心菜": "蔬菜", "青菜": "蔬菜",
    "青椒": "蔬菜", "胡萝卜": "蔬菜", "洋葱": "蔬菜", "黄瓜": "蔬菜",
    "茄子": "蔬菜", "西葫芦": "蔬菜", "花菜": "蔬菜", "西兰花": "蔬菜",
    "鸡蛋": "蛋类",
    "豆腐": "豆制品", "豆干": "豆制品",
    "鸡胸肉": "鸡肉", "鸡腿": "鸡肉",
    "猪肉": "猪肉", "牛肉": "牛肉", "牛腩": "牛肉",
    "虾": "水产", "鱼": "水产",
    "米饭": "主食", "面条": "主食",
}


def normalize_name(raw: str) -> str:
    """查同义词表，返回标准名称；若不在表中则返回原词"""
    return SYNONYM_MAP.get(raw.strip(), raw.strip())


def classify_ingredient(name: str) -> str:
    """根据标准名返回类别"""
    return CATEGORY_RULES.get(name, "其他")


def normalize_ingredients(raw_list: List[str]) -> List[RawIngredient]:
    """
    输入用户原始食材字符串列表，输出标准化后的 RawIngredient 列表。
    包含：去重、别名映射、分类。
    """
    seen = set()
    result: List[RawIngredient] = []
    for item in raw_list:
        item = item.strip()
        if not item:
            continue
        std_name = normalize_name(item)
        if std_name in seen:
            continue
        seen.add(std_name)
        result.append(RawIngredient(
            raw=item,
            name=std_name,
            category=classify_ingredient(std_name)
        ))
    return result
