"""候选评分与排序 —— 确定性规则模块"""

from typing import List
from schemas import CandidateFeature, RecipeRecord


# 难度权重（用于比较）
DIFFICULTY_ORDER = {"简单": 1, "中等": 2, "困难": 3}


def build_feature(recipe: RecipeRecord,
                  user_ingredients: List[str],
                  user_allergens: List[str],
                  user_excluded: List[str],
                  user_flavor: str,
                  user_time_limit: int,
                  user_equipment: List[str],
                  user_difficulty: str = "任意") -> CandidateFeature:
    """
    对一道候选菜谱计算匹配特征。纯规则计算，不依赖 LLM。

    Args:
        recipe: 候选菜谱
        user_ingredients: 用户标准化后的食材名列表
        user_allergens: 用户过敏原列表
        user_excluded: 用户忌口列表
        user_flavor: 口味偏好 ("" = 不限)
        user_time_limit: 时间限制（分钟）
        user_equipment: 用户可用厨具列表
        user_difficulty: 难度偏好 ("任意" = 不限)

    Returns:
        CandidateFeature: 包含所有匹配指标的特征对象
    """
    core = set(recipe.core_ingredients)
    optional = set(recipe.optional_ingredients)
    user_set = set(user_ingredients)

    # ── 核心食材匹配 ──
    core_matched = core & user_set
    missing_core = list(core - user_set)

    # ── 可选食材缺失 ──
    missing_optional = list(optional - user_set)

    # ── 硬过滤 ──
    blocked = False
    block_reasons = []

    # 过敏原冲突（硬阻断）
    for allergen in user_allergens:
        if not allergen:
            continue
        if allergen in recipe.allergens:
            blocked = True
            block_reasons.append(f"含过敏原：{allergen}")
        # 同时检查核心食材名中是否含过敏原（处理 "鸡蛋" 过敏但 allergens 为空的情况）
        for ci in recipe.core_ingredients:
            if allergen in ci or ci in allergen:
                blocked = True
                block_reasons.append(f"核心食材含过敏原：{allergen}（{ci}）")

    # 忌口冲突（硬阻断）
    for ex in user_excluded:
        if not ex:
            continue
        if ex in recipe.core_ingredients or ex in recipe.optional_ingredients:
            blocked = True
            block_reasons.append(f"含忌口食材：{ex}")

    # ── 软约束评分 ──

    # 1) 口味偏好
    preference_score = 1.0
    if user_flavor and user_flavor not in ("不限", "任意", ""):
        tags_lower = [t.lower() for t in recipe.tags]
        flavor_lower = user_flavor.lower()
        if "辣" in flavor_lower and "辣" not in "".join(tags_lower):
            preference_score = 0.5
        if "不辣" in flavor_lower and any("辣" in t for t in tags_lower):
            preference_score = 0.3
        if "清淡" in flavor_lower and any("辣" in t or "重" in t for t in tags_lower):
            preference_score = 0.4
        if "酸" in flavor_lower and "酸" not in "".join(tags_lower):
            preference_score = 0.5
        if "甜" in flavor_lower and "甜" not in "".join(tags_lower):
            preference_score = 0.5

    # 2) 时间符合度
    if recipe.estimated_time_min <= 0:
        time_fit = 1.0
    elif recipe.estimated_time_min <= user_time_limit:
        time_fit = 1.0
    else:
        time_fit = max(0.0, min(1.0, user_time_limit / recipe.estimated_time_min))

    # 3) 难度符合度
    difficulty_fit = 1.0
    if user_difficulty and user_difficulty not in ("任意", "不限", ""):
        recipe_level = DIFFICULTY_ORDER.get(recipe.difficulty, 2)
        user_level = DIFFICULTY_ORDER.get(user_difficulty, 2)
        if recipe_level <= user_level:
            difficulty_fit = 1.0
        elif recipe_level - user_level == 1:
            difficulty_fit = 0.6  # 差一级，还行
        else:
            difficulty_fit = 0.3  # 差两级，不太合适

    # 4) 厨具符合度
    equipment_fit = 1.0
    if user_equipment and recipe.equipment:
        matching = set(user_equipment) & set(recipe.equipment)
        equipment_fit = len(matching) / len(set(recipe.equipment)) if recipe.equipment else 1.0
    elif not recipe.equipment:
        equipment_fit = 1.0  # 不需要特殊厨具 = 完美匹配
    # 如果用户指定了厨具但菜谱什么都不需要 → 完美匹配
    # 如果用户没指定厨具 → equipment_fit=1.0（不惩罚）

    return CandidateFeature(
        recipe_id=recipe.recipe_id,
        retrieval_score=recipe.retrieval_score,
        core_total=len(core),
        core_matched=len(core_matched),
        missing_core=missing_core,
        missing_optional=missing_optional,
        preference_score=preference_score,
        time_fit=time_fit,
        difficulty_fit=difficulty_fit,
        equipment_fit=equipment_fit,
        blocked=blocked,
        block_reasons=block_reasons,
    )


def score_and_rank(features: List[CandidateFeature]) -> List[CandidateFeature]:
    """
    对非阻断菜谱打分并排序。阻断的菜直接丢弃，不返回。

    公式:
      Base = 30*core_coverage + 30*retrieval + 10*preference
           + 10*time + 5*difficulty + 15*equip
      Penalty = 25*core_miss_ratio
              + (10 if overtime)
      Final = clamp(Base - Penalty, 0, 100)

    排序: 缺失核心少的排前 → 检索分高排前 → 分高排前
    """
    if not features:
        return features

    # 分离阻断和非阻断
    blocked = [f for f in features if f.blocked]
    active = [f for f in features if not f.blocked]

    if blocked:
        names = [f.recipe_id for f in blocked]
        print(f"[Scorer] 硬阻断 {len(blocked)} 道: {names}")

    if not active:
        return []

    for f in active:
        core_coverage = f.core_matched / max(f.core_total, 1)
        retrieval_norm = max(0.0, min(1.0, f.retrieval_score))

        base = (30 * core_coverage
                + 30 * retrieval_norm
                + 10 * f.preference_score
                + 10 * f.time_fit
                + 5 * f.difficulty_fit
                + 15 * f.equipment_fit)

        core_miss_ratio = len(f.missing_core) / max(f.core_total, 1)
        penalty = 25 * core_miss_ratio

        if f.time_fit < 1.0:
            penalty += 10

        f.final_score = max(0, min(100, round(base - penalty)))

    active.sort(key=lambda f: (
        len(f.missing_core) / max(f.core_total, 1),  # 缺失比例，而非绝对数
        -f.retrieval_score,    # RAGFlow 向量相关度优先
        -f.final_score,
    ))
    return active


# ============================================================
# 评分样例验证（与 开发计划.md 对齐）
# ============================================================
"""
番茄炒蛋: core=2/2(100%), retrieval=0.90, pref=1, time=1, diff=1, equip=1
  Base = 45*1 + 15*0.9 + 10*1 + 10*1 + 5*1 + 15*1 = 45+13.5+10+10+5+15 = 98.5
  Penalty = 0 → Final = 99

青菜鸡蛋汤: core=2/2(100%), retrieval=0.72, pref=1, time=1, diff=1, equip=1
  Base = 45+10.8+10+10+5+15 = 95.8 → 96

番茄牛腩(超时): core=1/2(50%), retrieval=0.80, pref=1, time=0.22, diff=0.6, equip=1
  Base = 45*0.5 + 15*0.8 + 10*1 + 10*0.22 + 5*0.6 + 15*1
       = 22.5 + 12 + 10 + 2.2 + 3 + 15 = 64.7
  Penalty = 25*0.5 + 10 = 22.5
  Final = 64.7 - 22.5 = 42.2 → 42
"""
