"""食材标准化 —— 别名映射、去重、分类、数量解析、自然语言输入解析"""

import re
from typing import List, Dict, Tuple, Optional
from schemas import RawIngredient


# ============================================================
# 同义词表（100+ 组别名）
# ============================================================

SYNONYM_MAP: Dict[str, str] = {
    # ── 蔬菜 ──
    "西红柿": "番茄", "蕃茄": "番茄",
    "马铃薯": "土豆", "洋芋": "土豆", "山药蛋": "土豆",
    "包菜": "卷心菜", "圆白菜": "卷心菜", "甘蓝": "卷心菜", "包心菜": "卷心菜",
    "青菜": "青菜", "小白菜": "青菜", "上海青": "青菜", "油菜": "青菜",
    "青椒": "青椒", "柿子椒": "青椒", "菜椒": "青椒", "甜椒": "青椒",
    "胡萝卜": "胡萝卜", "红萝卜": "胡萝卜",
    "洋葱": "洋葱", "葱头": "洋葱", "圆葱": "洋葱",
    "黄瓜": "黄瓜", "青瓜": "黄瓜",
    "茄子": "茄子", "矮瓜": "茄子",
    "西葫芦": "西葫芦", "角瓜": "西葫芦",
    "花菜": "花菜", "花椰菜": "花菜", "菜花": "花菜",
    "西兰花": "西兰花", "青花菜": "西兰花",
    "白菜": "白菜", "大白菜": "白菜",
    "生菜": "生菜",
    "菠菜": "菠菜",
    "芹菜": "芹菜",
    "韭菜": "韭菜",
    "豆芽": "豆芽", "绿豆芽": "豆芽", "黄豆芽": "豆芽",
    "冬瓜": "冬瓜",
    "南瓜": "南瓜",
    "丝瓜": "丝瓜",
    "苦瓜": "苦瓜",
    "莲藕": "莲藕", "藕": "莲藕",
    "山药": "山药",
    "莴笋": "莴笋",
    "空心菜": "空心菜", "蕹菜": "空心菜",

    # ── 蛋类 / 豆制品 ──
    "鸡蛋": "鸡蛋", "鸡子儿": "鸡蛋", "鸡卵": "鸡蛋",
    "豆腐": "豆腐",
    "豆干": "豆干", "豆腐干": "豆干", "香干": "豆干",
    "豆皮": "豆皮", "千张": "豆皮", "百叶": "豆皮",
    "腐竹": "腐竹",

    # ── 肉类 ──
    "鸡胸肉": "鸡胸肉", "鸡胸": "鸡胸肉",
    "鸡腿": "鸡腿", "鸡腿肉": "鸡腿",
    "鸡翅": "鸡翅", "鸡翅膀": "鸡翅",
    "猪肉": "猪肉", "猪瘦肉": "猪肉", "瘦肉": "猪肉",
    "五花肉": "五花肉", "三层肉": "五花肉",
    "排骨": "排骨", "猪排骨": "排骨", "肋排": "排骨",
    "牛肉": "牛肉",
    "牛腩": "牛腩",
    "牛腱": "牛腱", "牛腱子": "牛腱",
    "羊肉": "羊肉",
    "培根": "培根",
    "火腿": "火腿",
    "香肠": "香肠", "腊肠": "香肠",

    # ── 水产 ──
    "虾": "虾", "虾仁": "虾", "大虾": "虾", "对虾": "虾", "鲜虾": "虾",
    "鱼": "鱼", "鱼肉": "鱼",
    "鲈鱼": "鲈鱼",
    "鲤鱼": "鲤鱼",
    "带鱼": "带鱼",
    "三文鱼": "三文鱼",
    "鱿鱼": "鱿鱼",
    "螃蟹": "螃蟹", "蟹": "螃蟹",
    "蛤蜊": "蛤蜊", "花蛤": "蛤蜊",

    # ── 菌菇类 ──
    "香菇": "香菇", "冬菇": "香菇",
    "蘑菇": "蘑菇", "口蘑": "蘑菇",
    "金针菇": "金针菇",
    "木耳": "木耳", "黑木耳": "木耳",

    # ── 主食 ──
    "米饭": "米饭", "大米": "米饭", "白饭": "米饭",
    "面条": "面条", "挂面": "面条",
    "面粉": "面粉",
    "馒头": "馒头",
    "粉丝": "粉丝", "粉条": "粉丝",
    "年糕": "年糕",

    # ── 调料 ──
    "酱油": "生抽",
    "油": "食用油", "菜油": "食用油", "花生油": "食用油", "色拉油": "食用油",
    "辣椒": "辣椒", "干辣椒": "辣椒", "红辣椒": "辣椒",
    "花椒": "花椒",
    "八角": "八角", "大料": "八角",
    "豆瓣酱": "豆瓣酱",
    "番茄酱": "番茄酱",
    "蚝油": "蚝油",
    "鸡精": "鸡精", "味精": "鸡精",
    "香油": "香油", "芝麻油": "香油",
    "醋": "醋", "陈醋": "醋", "白醋": "醋",
    "料酒": "料酒", "黄酒": "料酒",
    "胡椒粉": "胡椒粉", "胡椒": "胡椒粉",
}


# ============================================================
# 分类规则
# ============================================================

CATEGORY_RULES: Dict[str, str] = {
    # 蔬菜
    "番茄": "蔬菜", "土豆": "蔬菜", "卷心菜": "蔬菜", "青菜": "蔬菜",
    "青椒": "蔬菜", "胡萝卜": "蔬菜", "洋葱": "蔬菜", "黄瓜": "蔬菜",
    "茄子": "蔬菜", "西葫芦": "蔬菜", "花菜": "蔬菜", "西兰花": "蔬菜",
    "白菜": "蔬菜", "生菜": "蔬菜", "菠菜": "蔬菜", "芹菜": "蔬菜",
    "韭菜": "蔬菜", "豆芽": "蔬菜", "冬瓜": "蔬菜", "南瓜": "蔬菜",
    "丝瓜": "蔬菜", "苦瓜": "蔬菜", "莲藕": "蔬菜", "山药": "蔬菜",
    "莴笋": "蔬菜", "空心菜": "蔬菜",

    # 菌菇
    "香菇": "菌菇", "蘑菇": "菌菇", "金针菇": "菌菇", "木耳": "菌菇",

    # 蛋类
    "鸡蛋": "蛋类",

    # 豆制品
    "豆腐": "豆制品", "豆干": "豆制品", "豆皮": "豆制品", "腐竹": "豆制品",

    # 肉类
    "鸡胸肉": "鸡肉", "鸡腿": "鸡肉", "鸡翅": "鸡肉",
    "猪肉": "猪肉", "五花肉": "猪肉", "排骨": "猪肉",
    "牛肉": "牛肉", "牛腩": "牛肉", "牛腱": "牛肉",
    "羊肉": "羊肉",
    "培根": "肉类", "火腿": "肉类", "香肠": "肉类",

    # 水产
    "虾": "水产", "鱼": "水产", "鲈鱼": "水产", "鲤鱼": "水产",
    "带鱼": "水产", "三文鱼": "水产", "鱿鱼": "水产",
    "螃蟹": "水产", "蛤蜊": "水产",

    # 主食
    "米饭": "主食", "面条": "主食",
}


# ============================================================
# 数量解析
# ============================================================

# 数量 + 单位模式
QUANTITY_PATTERN = re.compile(
    r'^(.*?)'                         # 食材名（捕获）
    r'('
    r'\d+\s*(?:个|只|条|根|片|块|斤|两|克|g|kg|碗|份|勺|把|颗|粒)|'  # 数字 + 单位
    r'半\s*(?:个|只|条|根|片|块|斤|两|碗|份|勺|把)|'                # 半 + 单位
    r'[一二三四五六七八九十]\s*(?:个|只|条|根|片|块|斤|两)|'          # 中文数字 + 单位
    r'少许|适量|若干|一把|一小把|一撮'                                 # 模糊量词
    r')$'
)

# 纯数量词（应过滤掉，不是食材）
PURE_QUANTITY = re.compile(
    r'^[\d半两一二三四五六七八九十]+[个只条根片块斤两克碗份勺把颗粒]?$'
)


def parse_quantity(raw: str) -> Tuple[str, str]:
    """
    从食材字符串中分离名称和数量。

    Examples:
        "鸡蛋2个"  → ("鸡蛋", "2个")
        "番茄一个" → ("番茄", "一个")
        "盐少许"   → ("盐", "少许")
        "番茄"     → ("番茄", "")
    """
    raw = raw.strip()
    m = QUANTITY_PATTERN.match(raw)
    if m:
        name = m.group(1).strip()
        quantity = m.group(2).strip()
        if name:
            return (name, quantity)
    return (raw, "")


# ============================================================
# 公共函数
# ============================================================

def normalize_name(raw: str) -> str:
    """查同义词表，返回标准名称；若不在表中则返回原词"""
    return SYNONYM_MAP.get(raw.strip(), raw.strip())


def classify_ingredient(name: str) -> str:
    """根据标准名返回类别"""
    return CATEGORY_RULES.get(name, "其他")


def normalize_ingredients(raw_list: List[str]) -> List[RawIngredient]:
    """
    输入用户原始食材字符串列表，输出标准化后的 RawIngredient 列表。
    包含：数量解析、去重、别名映射、分类。
    """
    seen = set()
    result: List[RawIngredient] = []
    for item in raw_list:
        item = item.strip()
        if not item:
            continue
        # 分离数量
        name_part, quantity = parse_quantity(item)
        if not name_part:
            continue
        # 过滤纯数量词
        if PURE_QUANTITY.match(name_part) and not quantity:
            continue
        # 别名映射
        std_name = normalize_name(name_part)
        if std_name in seen:
            continue
        seen.add(std_name)
        result.append(RawIngredient(
            raw=item,
            name=std_name,
            quantity=quantity,
            category=classify_ingredient(std_name)
        ))
    return result


# ============================================================
# 自然语言输入解析
# ============================================================

# 时间约束模式
TIME_PATTERNS = [
    (re.compile(r'(\d+)\s*分钟'), lambda m: int(m.group(1))),
    (re.compile(r'半小时'), lambda m: 30),
    (re.compile(r'([一二三四五])\s*小时'), lambda m: {'一': 60, '二': 120, '三': 180, '四': 240, '五': 300}[m.group(1)]),
    (re.compile(r'(\d+)\s*小时'), lambda m: int(m.group(1)) * 60),
]

# 人数模式
SERVINGS_PATTERNS = [
    (re.compile(r'(\d+)\s*人份?'), lambda m: int(m.group(1))),
    (re.compile(r'([两三四五六七八九])\s*人份?'), lambda m: {'两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}[m.group(1)]),
    (re.compile(r'([一二三四五六七八九])\s*人份?'), lambda m: {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}[m.group(1)]),
]

# 难度模式
DIFFICULTY_KEYWORDS = {
    "简单": ["简单", "新手", "快手", "方便", "容易", "不难"],
    "中等": ["中等", "一般"],
    "困难": ["困难", "复杂", "硬菜", "大菜"],
}

# 口味模式 —— 注意：否定式必须排在肯定式前面，避免 "不要辣" 先被 "辣" 匹配
FLAVOR_KEYWORDS = {
    "不辣": ["不辣", "不要辣", "别辣", "免辣", "不吃辣", "不能吃辣"],
    "辣": ["辣的", "微辣", "麻辣", "香辣", "带辣", "辣味"],
    "不酸": ["不酸", "不要酸", "别酸"],
    "酸": ["酸的", "酸辣", "酸味"],
    "不甜": ["不甜", "不要甜"],
    "甜": ["甜的", "甜味"],
    "清淡": ["清淡", "不油腻", "爽口", "无油"],
}

# 约束残留词（口味/约束干掉后剩下的副词）
CONSTRAINT_LEFTOVERS = {
    '不要', '别', '免', '不能', '不吃', '不带', '无', '非',
    '口味', '偏好', '做法',
}

# 厨具关键词
EQUIPMENT_KEYWORDS = {
    "炒锅": ["炒锅", "炒菜锅", "铁锅", "不粘锅", "中式炒锅"],
    "蒸锅": ["蒸锅", "蒸笼", "蒸屉"],
    "汤锅": ["汤锅", "煮锅", "奶锅"],
    "炖锅": ["炖锅", "砂锅", "煲", "高压锅", "压力锅", "电炖锅"],
    "烤箱": ["烤箱", "烤炉"],
    "微波炉": ["微波炉"],
    "空气炸锅": ["空气炸锅", "空气锅"],
    "电饭煲": ["电饭煲", "电饭锅"],
    "平底锅": ["平底锅", "煎锅", "平底煎锅"],
}

# 厨具名标准化（从 EQUIPMENT_KEYWORDS 反向构建）
_EQUIP_NORMALIZE: Dict[str, str] = {}
for _std_name, _aliases in EQUIPMENT_KEYWORDS.items():
    for _a in _aliases:
        _EQUIP_NORMALIZE[_a] = _std_name


def normalize_equipment(name: str) -> str:
    """将厨具别名映射为标准名，如 '不粘锅' → '炒锅'"""
    return _EQUIP_NORMALIZE.get(name.strip(), name.strip())


# 过敏原关键词
ALLERGEN_KEYWORDS = {
    "花生": ["花生过敏", "不能吃花生", "花生不耐受"],
    "鸡蛋": ["鸡蛋过敏", "不能吃鸡蛋", "蛋过敏"],
    "牛奶": ["牛奶过敏", "乳糖不耐", "不能喝奶"],
    "海鲜": ["海鲜过敏", "不能吃海鲜", "虾过敏", "鱼过敏"],
    "坚果": ["坚果过敏", "不能吃坚果"],
    "麦麸": ["麦麸过敏", "麸质过敏"],
}


def split_ingredients_text(text: str) -> List[str]:
    """
    从食材文本中只提取食材名，不做约束解析。
    用于角色 A 接收 RecommendRequest 后的第一步——
    约束已由角色 B 提取好了，这里只需分拆食材名称。

    Examples:
        "西红柿、鸡蛋2个、土豆" → ["西红柿", "鸡蛋2个", "土豆"]
        "鸡蛋、番茄，不要辣"   → ["鸡蛋", "番茄"]  (约束词被过滤)
    """
    text = text.strip()
    if not text:
        return []

    # 先清掉常见约束词和连接词
    noise = {'不要', '不能', '不吃', '别', '免', '无', '非',
             '口味', '偏好', '做法', '简单', '快手', '容易',
             '中等', '困难', '复杂', '清淡', '不油腻',
             '辣', '不辣', '微辣', '麻辣', '酸', '甜',
             '过敏', '不耐受'}

    # 先清掉时间/数量模式的子串
    text = re.sub(r'\d+\s*分钟', '', text)
    text = re.sub(r'半小时', '', text)
    text = re.sub(r'\d+\s*小时', '', text)
    text = re.sub(r'\d+\s*人份?', '', text)
    text = re.sub(r'[两三四五六七八九]人份?', '', text)
    text = re.sub(r'一人份?', '', text)

    for w in noise:
        text = text.replace(w, '')

    # 按标点分割
    items = re.split(r'[,，、;\s]+', text)
    result = []
    for item in items:
        item = item.strip().strip('，,、;； ')
        if not item:
            continue
        # 过滤纯数量词
        if PURE_QUANTITY.match(item):
            continue
        # 过滤残留单字
        if item in ('个', '只', '条', '份', '人', '道', '盘', '碗', '勺'):
            continue
        result.append(item)
    return result


def parse_ingredients_text(text: str) -> Dict:
    """
    解析用户自然语言输入，分离食材和约束。

    Args:
        text: 用户输入，如 "鸡蛋、番茄、土豆，两人，20分钟，不要辣"

    Returns:
        dict:
        {
            "ingredient_items": ["鸡蛋", "番茄", "土豆"],   # 食材（未标准化）
            "servings": 2,                                  # 人数，None=未指定
            "time_limit_min": 20,                           # 时间限制（分钟），None=未指定
            "difficulty": "简单",                            # 难度偏好，None=未指定
            "flavor": "不辣",                                # 口味偏好，""=未指定
            "allergens": ["花生"],                           # 检测到的过敏原
            "excluded": [],                                 # 忌口
            "equipment": ["炒锅"],                           # 用户可用厨具
            "raw_text": text,                               # 保留原文
        }
    """
    text = text.strip()
    result = {
        "ingredient_items": [],
        "servings": None,
        "time_limit_min": None,
        "difficulty": None,
        "flavor": "",
        "allergens": [],
        "excluded": [],
        "equipment": [],       # 用户拥有的厨具
        "raw_text": text,
    }

    # ── 1. 提取时间约束 ──
    for pattern, extractor in TIME_PATTERNS:
        m = pattern.search(text)
        if m:
            result["time_limit_min"] = extractor(m)
            text = pattern.sub('', text)  # 移除已匹配的时间
            break

    # ── 2. 提取人数 ──
    for pattern, extractor in SERVINGS_PATTERNS:
        m = pattern.search(text)
        if m:
            result["servings"] = extractor(m)
            text = pattern.sub('', text)
            break

    # ── 3. 提取过敏原 ──
    for allergen, keywords in ALLERGEN_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                result["allergens"].append(allergen)
                text = text.replace(kw, '')
                break

    # ── 3.5 提取用户厨具 ──
    for equip, keywords in EQUIPMENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                result["equipment"].append(equip)
                text = text.replace(kw, '')
                break
    # 处理 "只有炒锅" / "没有微波炉" 模式
    only_match = re.search(r'只有\s*([一-鿿]+锅[一-鿿]*)', text)
    if only_match:
        only_equip = only_match.group(1)
        # 尝试匹配已知厨具
        for equip, keywords in EQUIPMENT_KEYWORDS.items():
            if only_equip in keywords or only_equip == equip:
                if equip not in result["equipment"]:
                    result["equipment"].append(equip)
                break
        text = text.replace(only_match.group(0), '')

    # ── 4. 提取口味偏好 ──
    for flavor, keywords in FLAVOR_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                result["flavor"] = flavor
                # 清除该口味类别的所有关键词
                for k in keywords:
                    text = text.replace(k, '')
                break
        if result["flavor"]:
            break

    # ── 5. 提取难度偏好 ──
    for difficulty, keywords in DIFFICULTY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                result["difficulty"] = difficulty
                # 清除该难度类别的所有关键词
                for k in keywords:
                    text = text.replace(k, '')
                break
        if result["difficulty"]:
            break

    # ── 6. 分割剩余为食材列表 ──
    # 先清掉约束残留词
    for leftover in CONSTRAINT_LEFTOVERS:
        text = re.sub(rf'(?:^|[，,、;\s]){re.escape(leftover)}(?:$|[，,、;\s])', ' ', text)

    # 按标点/空格分割
    cleaned = re.sub(r'[,，、;\s]+', ' ', text).strip()
    raw_items = [item.strip() for item in cleaned.split() if item.strip()]

    # 过滤纯数量词和约束残留
    for item in raw_items:
        item = item.strip('，,、;； ')
        if not item:
            continue
        if PURE_QUANTITY.match(item):
            continue
        if item in CONSTRAINT_LEFTOVERS:
            continue
        # 过滤单字非食材
        if item in ('个', '只', '条', '份', '人', '道', '盘', '碗', '勺'):
            continue
        result["ingredient_items"].append(item)

    return result
