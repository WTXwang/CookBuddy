"""候选评分与排序 —— 确定性规则模块"""

from typing import List
from schemas import CandidateFeature, Recommendation, RecipeRecord
from rules.staples import is_staple


def build_feature(recipe: RecipeRecord,
                  user_ingredients: List[str],
                  user_allergens: List[str],
                  user_excluded: List[str],
                  user_flavor: str,
                  user_time_limit: int,
                  user_equipment: List[str]) -> CandidateFeature:
    """
    对一道候选菜谱计算匹配特征。
    不依赖 LLM —— 纯规则计算。
    """
    core = set(recipe.core_ingredients)
    optional = set(recipe.optional_ingredients)
    user_set = set(user_ingredients)

    # 核心食材匹配
    core_matched = core & user_set
    missing_core = list(core - user_set)

    # 可选食材匹配（仅用于展示，不影响硬过滤）
    missing_optional = list(optional - user_set)

    # ---- 硬过滤 ----
    blocked = False
    block_reasons = []

    # 过敏原冲突
    for allergen in user_allergens:
        if allergen in recipe.allergens:
            blocked = True
            block_reasons.append(f"含过敏原：{allergen}")

    # 忌口冲突
    for ex in user_excluded:
        if ex in recipe.core_ingredients or ex in recipe.optional_ingredients:
            blocked = True
            block_reasons.append(f"含忌口食材：{ex}")

    # 厨具不匹配（硬约束：缺少必需厨具且无替代）
    if user_equipment:
        recipe_equip = set(recipe.equipment)
        user_equip = set(user_equipment)
        if recipe_equip and not (recipe_equip & user_equip):
            # 如果菜谱需要厨具而用户一样都没有，标记但不硬阻断（可提示）
            pass  # MVP 阶段不硬阻断，仅降低 equipment_fit

    # ---- 软约束评分因子 ----
    # 偏好符合度
    preference_score = 1.0
    if user_flavor and user_flavor != "不限":
        tags_lower = [t.lower() for t in recipe.tags]
        flavor_lower = user_flavor.lower()
        if "辣" in flavor_lower and "辣" not in "".join(tags_lower):
            preference_score = 0.5
        if "不辣" == flavor_lower and any("辣" in t for t in tags_lower):
            preference_score = 0.3

    # 时间符合度
    time_fit = min(1.0, user_time_limit / max(recipe.estimated_time_min, 1))
    if recipe.estimated_time_min <= user_time_limit:
        time_fit = 1.0

    # 厨具符合度
    equipment_fit = 1.0
    if user_equipment and recipe.equipment:
        matching = set(user_equipment) & set(recipe.equipment)
        equipment_fit = len(matching) / len(set(recipe.equipment)) if recipe.equipment else 1.0

    return CandidateFeature(
        recipe_id=recipe.recipe_id,
        retrieval_score=recipe.retrieval_score,
        core_total=len(core),
        core_matched=len(core_matched),
        missing_core=missing_core,
        missing_optional=missing_optional,
        preference_score=preference_score,
        time_fit=time_fit,
        equipment_fit=equipment_fit,
        blocked=blocked,
        block_reasons=block_reasons,
    )


def score_and_rank(features: List[CandidateFeature]) -> List[CandidateFeature]:
    """
    按计划书 11.2 评分公式：
      Base = 45*core_coverage + 20*retrieval + 15*preference + 10*time_fit + 10*equip_fit
      Penalty = 25*core_miss_ratio + (10 if time over limit)
      FinalScore = clamp(Base-Penalty, 0, 100)

    排序：blocked → missing_core_count → FinalScore DESC → estimated_time
    """
    for f in features:
        core_coverage = f.core_matched / max(f.core_total, 1)
        retrieval_norm = f.retrieval_score  # 假设已在检索阶段归一化

        base = (45 * core_coverage
                + 20 * retrieval_norm
                + 15 * f.preference_score
                + 10 * f.time_fit
                + 10 * f.equipment_fit)

        core_miss_ratio = len(f.missing_core) / max(f.core_total, 1)
        penalty = 25 * core_miss_ratio
        if f.time_fit < 1.0:
            penalty += 10

        final_score = max(0, min(100, round(base - penalty)))
        f.final_score = final_score

    def sort_key(f: CandidateFeature):
        return (
            f.blocked,           # blocked=True 排最后
            len(f.missing_core), # 缺失核心食材多的排后面
            -f.final_score,      # 分高排前
            f.retrieval_score    # 同分按检索分
        )

    ranked = sorted(features, key=sort_key)
    return ranked


"""评分样例验证（开发计划 11.4）"""
# 番茄炒蛋: 核心覆盖100%, 检索0.90, pref=1, time=1, equip=1
# Base=45*1+20*0.9+15*1+10*1+10*1=45+18+15+10+10=98, Penalty=0 → 98
# 青菜鸡蛋汤: 核心覆盖100%, 检索0.72, pref=1, time=1, equip=1
# Base=45+14.4+15+10+10=94.4, Penalty=0 → 94
# 番茄牛腩: 核心覆盖50%, 检索0.80, pref=1, time=0(超时), equip=1
# Base=45*0.5+20*0.8+15+10*0+10=22.5+16+15+0+10=63.5, Penalty=25*0.5+10=22.5 → 41
