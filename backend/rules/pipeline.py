"""角色A 统一入口 —— 接收结构化请求，返回排序后的菜谱列表

数据流:
    RecommendRequest → normalize → search_ids → meta.get → score → list[RecipeRecord]

这是角色 A 对外暴露的唯一接口。角色 B 只需调用 run_pipeline()。
"""

from schemas import RecommendRequest, RecipeRecord, CandidateFeature
from rules.normalizer import split_ingredients_text, normalize_ingredients
from rules.staples import get_staples
from rules.scorer import build_feature, score_and_rank
from retrieval import create_retriever
from recipes.meta import RecipeMetaStore


# ── 全局 meta store（懒加载） ────────────────────────

_meta_store: RecipeMetaStore | None = None


def set_meta_store(store: RecipeMetaStore) -> None:
    """注入 RecipeMetaStore 实例（由外部配置 text_fetcher / llm_extractor）"""
    global _meta_store
    _meta_store = store


def _get_meta() -> RecipeMetaStore:
    """获取或创建 meta store（自动注入 extractor）"""
    global _meta_store
    if _meta_store is None:
        import os
        from recipes.extractor import llm_extract_recipe
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "recipes.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _meta_store = RecipeMetaStore(db_path=db_path, llm_extractor=llm_extract_recipe)
    return _meta_store


# ── 主入口 ────────────────────────────────────────────

def run_pipeline(req: RecommendRequest, top_n: int = 10) -> list[RecipeRecord]:
    """
    角色A 唯一入口。

    输入:
        req: B 分析后的结构化请求
    输出:
        按 final_score 降序的 RecipeRecord 列表。
        retrieval_score 已被替换为 final_score。

    流程:
        1. 从 ingredients_text 分拆食材名
        2. 别名映射 + 去重 + 分类
        3. 检索 → [(recipe_id, score)]
        4. 元数据获取 → meta.get(rid) 优先，兜底 retriever.get_by_id(rid)
        5. 硬过滤 + 软约束评分
        6. 排序返回
    """
    # ── Step 1: 解析食材文本 → 食材名列表 ──
    raw_names = split_ingredients_text(req.ingredients_text)
    if not raw_names:
        return []

    # ── Step 2: 标准化 ──
    normalized = normalize_ingredients(raw_names)
    ing_names = [n.name for n in normalized]

    # ── Step 3: 检索 → [(recipe_id, score)] ──
    retriever = create_retriever()
    id_scores = retriever.search_ids(ing_names, top_n=top_n)
    if not id_scores:
        return []

    # ── Step 4: 元数据获取 ──
    # meta 缓存 → 命中返回
    # 未命中 → retriever 取全文 → extractor 提取 → 入库
    # 仍未命中 → retriever.get_by_id() 兜底
    # 全文暂存，供 Step 6 填充 body
    meta = _get_meta()
    candidates = []
    body_cache: dict[str, str] = {}
    for rid, score in id_scores:
        recipe = meta.get(rid)
        if not recipe:
            full_text = retriever.get_full_text(rid)
            if full_text:
                body_cache[rid] = full_text
                recipe = meta.get_or_create(rid, full_text)
        if not recipe:
            recipe = retriever.get_by_id(rid)
        if recipe:
            recipe.retrieval_score = score
            candidates.append(recipe)

    if not candidates:
        return []

    # ── Step 5: 特征提取 + 评分排序 ──
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

    # ── Step 6: 组装结果 + 补全 body ──
    recipe_map = {r.recipe_id: r for r in candidates}
    result = []
    for f in ranked:
        recipe = recipe_map.get(f.recipe_id)
        if recipe:
            recipe.retrieval_score = float(f.final_score)
            if not recipe.body:
                recipe.body = body_cache.get(recipe.recipe_id) or retriever.get_full_text(recipe.recipe_id) or ""
            result.append(recipe)

    return result
