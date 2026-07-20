"""角色A 统一入口 —— 接收结构化请求，返回排序后的菜谱列表

数据流:
    RecommendRequest → normalize → retrieve → score → list[RecipeRecord]

这是角色 A 对外暴露的唯一接口。角色 B 只需调用 run_pipeline()。
"""

from schemas import RecommendRequest, RecipeRecord, CandidateFeature
from rules.normalizer import split_ingredients_text, normalize_ingredients
from rules.staples import get_staples
from rules.scorer import build_feature, score_and_rank
from retrieval import create_retriever


def run_pipeline(req: RecommendRequest, top_n: int = 10) -> list[RecipeRecord]:
    """
    角色A 唯一入口。

    输入:
        req: B 分析后的结构化请求
            - ingredients_text: 原始食材文本（如 "西红柿、鸡蛋2个、土豆"）
            - 其他字段已是结构化约束（allergens, equipment, flavor 等）

    输出:
        按 final_score 降序的 RecipeRecord 列表。
        每个 RecipeRecord 的 retrieval_score 已被替换为 final_score，
        body 字段包含菜谱正文（若有）。

    流程:
        1. 从 ingredients_text 分拆食材名
        2. 别名映射 + 去重 + 分类
        3. 知识库检索（stub 或 RAGFlow）
        4. 硬过滤（过敏原/忌口）+ 软约束评分
        5. 排序返回
    """
    # ── Step 1: 解析食材文本 → 食材名列表 ──
    raw_names = split_ingredients_text(req.ingredients_text)
    if not raw_names:
        return []

    # ── Step 2: 标准化 ──
    normalized = normalize_ingredients(raw_names)
    ing_names = [n.name for n in normalized]

    # ── Step 3: 检索 ──
    retriever = create_retriever()
    candidates = retriever.search(ing_names, top_n=top_n)
    if not candidates:
        return []

    # ── Step 4: 特征提取 + 评分排序 ──
    features = [
        build_feature(
            c, ing_names,
            user_allergens=req.allergens,
            user_excluded=req.excluded,
            user_flavor=req.flavor,
            user_time_limit=req.time_limit_min,
            user_equipment=req.equipment,
            user_difficulty=req.difficulty,
        )
        for c in candidates
    ]
    ranked = score_and_rank(features)

    # ── Step 5: 组装结果（分数回填到 RecipeRecord） ──
    recipe_map = {r.recipe_id: r for r in candidates}
    result = []
    for f in ranked:
        recipe = recipe_map.get(f.recipe_id)
        if recipe:
            recipe.retrieval_score = float(f.final_score)
            result.append(recipe)

    return result
