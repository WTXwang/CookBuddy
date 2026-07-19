"""LangGraph 主控流程 —— ChefCoordinator

节点顺序（对齐计划书 7.1）：
  Begin → Categorize → Normalize → Retrieve → Match
  → Score → Guide → Safety → Output
"""

import time
import uuid
from typing import Literal

from langgraph.graph import StateGraph, END
from schemas import (
    ChefState, GraphStage, Intent, NormalizedRequest,
    RecommendRequest, RecommendationResponse, Recommendation,
    RequestSummary, CandidateFeature, RecipeRecord,
)
from rules.normalizer import normalize_ingredients
from rules.staples import get_staples
from rules.scorer import build_feature, score_and_rank
from agents.matcher import RecipeMatcher
from agents.cooking_guide import CookingGuide
from agents.safety import FoodSafetyReviewer
from retrieval import create_retriever
import config


# ============================================================
# 初始化模块（每个 Agent 独立指定模型）
# ============================================================
_retrieval = create_retriever()
_matcher = RecipeMatcher(model=config.MATCHER_MODEL)
_guide = CookingGuide(model=config.GUIDE_MODEL)
_safety = FoodSafetyReviewer(model=config.SAFETY_MODEL)


def set_retrieval(r):
    global _retrieval
    _retrieval = r


def set_matcher(m):
    global _matcher
    _matcher = m


def set_guide(g):
    global _guide
    _guide = g


def set_safety(s):
    global _safety
    _safety = s


# ============================================================
# 节点函数
# ============================================================

def _timer(state: ChefState, key: str):
    now = time.time()
    if not hasattr(state, '_timers'):
        object.__setattr__(state, '_timers', {})
    state._timers[key] = now


def _lap(state: ChefState, key: str):
    now = time.time()
    start = getattr(state, '_timers', {}).get(key, now)
    state.stage_durations[key] = round((now - start) * 1000)  # ms


def node_categorize(state: ChefState) -> ChefState:
    """意图分类：推荐 / 查做法 / 找替代 / 其他"""
    _timer(state, 'categorize')
    state.stage = GraphStage.CATEGORIZE

    text = state.raw_input.strip()
    if not text:
        state.intent = Intent.OTHER
        state.error = "未输入食材"
        state.stage = GraphStage.ERROR
        _lap(state, 'categorize')
        return state

    # 简单关键词分类（MVP，后续用 LLM）
    if any(kw in text for kw in ["怎么做", "做法", "步骤", "怎么烧"]):
        state.intent = Intent.LOOKUP
    elif any(kw in text for kw in ["替代", "代替", "换成", "没有"]):
        state.intent = Intent.SUBSTITUTE
    else:
        state.intent = Intent.RECOMMEND

    _lap(state, 'categorize')
    return state


def node_normalize(state: ChefState) -> ChefState:
    """食材标准化：分词、别名映射、去重、基础调料识别"""
    _timer(state, 'normalize')
    state.stage = GraphStage.NORMALIZE

    text = state.raw_input.strip()
    if not text:
        state.error = "请输入食材"
        state.stage = GraphStage.ERROR
        return state

    # 简单分词（按逗号、顿号、空格分割）
    import re
    raw_items = re.split(r'[,，、\s]+', text)
    raw_items = [r.strip() for r in raw_items if r.strip()]

    # 数量词过滤（"半个"、"2个" 等）
    quantity_pattern = re.compile(r'^[\d半个两三四五六七八九十]+[个只条根片块]?$')
    raw_items = [r for r in raw_items if not quantity_pattern.match(r)]

    # 标准化
    normalized = normalize_ingredients(raw_items)
    ing_names = [n.name for n in normalized]

    # 基础调料
    staples = get_staples(assume=True, include_aromatics=True)

    state.request = NormalizedRequest(
        request_id=state.request.request_id if state.request else str(uuid.uuid4()),
        ingredients=normalized,
        servings=state.request.servings if state.request else 2,
        time_limit_min=state.request.time_limit_min if state.request else 30,
        difficulty=state.request.difficulty if state.request else "简单",
        flavor=state.request.flavor if state.request else "",
        excluded_ingredients=state.request.excluded_ingredients if state.request else [],
        allergens=state.request.allergens if state.request else [],
        equipment=state.request.equipment if state.request else [],
        assume_staples=True,
        assumed_staples=staples,
    )

    # 同步约束到 state 顶层
    state.user_allergens = state.request.allergens
    state.user_excluded = state.request.excluded_ingredients
    state.user_equipment = state.request.equipment
    state.user_flavor = state.request.flavor
    state.user_time_limit = state.request.time_limit_min
    state.user_servings = state.request.servings

    _lap(state, 'normalize')
    return state


def node_retrieve(state: ChefState) -> ChefState:
    """知识库检索"""
    _timer(state, 'retrieve')
    state.stage = GraphStage.RETRIEVE

    if not state.request or not state.request.ingredients:
        state.error = "无可检索食材"
        state.stage = GraphStage.ERROR
        return state

    ing_names = [i.name for i in state.request.ingredients]
    state.candidates = _retrieval.search(ing_names, top_n=10)

    if not state.candidates:
        state.error = "未找到匹配菜谱"
        state.stage = GraphStage.ERROR

    _lap(state, 'retrieve')
    return state


def node_match(state: ChefState) -> ChefState:
    """菜谱匹配：分析候选特征"""
    _timer(state, 'match')
    state.stage = GraphStage.MATCH

    if not state.candidates:
        return state

    ing_names = [i.name for i in state.request.ingredients]
    state.features = [
        build_feature(c, ing_names,
                      state.user_allergens, state.user_excluded,
                      state.user_flavor, state.user_time_limit,
                      state.user_equipment)
        for c in state.candidates
    ]

    _lap(state, 'match')
    return state


def node_score(state: ChefState) -> ChefState:
    """评分排序"""
    _timer(state, 'score')
    state.stage = GraphStage.SCORE

    if not state.features:
        return state

    state.features = score_and_rank(state.features)
    _lap(state, 'score')
    return state


def node_guide(state: ChefState) -> ChefState:
    """做法生成：为 Top 3 生成烹饪指导"""
    _timer(state, 'guide')
    state.stage = GraphStage.GUIDE

    if not state.features or not state.candidates:
        return state

    # 取前 3 个未阻塞的候选
    top_features = [f for f in state.features if not f.blocked][:3]

    # 如果不足 3 道，允许最多 1 道缺 1 核心食材的
    if len(top_features) < 3:
        missing_one = [f for f in state.features
                       if not f.blocked and len(f.missing_core) == 1 and f not in top_features]
        top_features.extend(missing_one[:3 - len(top_features)])

    # 生成做法
    recipe_map = {r.recipe_id: r for r in state.candidates}
    recommendations = []

    for feat in top_features:
        recipe = recipe_map.get(feat.recipe_id)
        if not recipe:
            continue

        guide_data = _guide.generate(recipe, feat)

        score = feat.final_score
        match_label = "完美匹配" if score >= 90 else ("推荐" if score >= 70 else "可做")

        recommendations.append(Recommendation(
            recipe_id=recipe.recipe_id,
            title=recipe.title,
            image_url=recipe.image_url,
            match_score=score,
            match_label=match_label,
            estimated_time_min=recipe.estimated_time_min,
            difficulty=recipe.difficulty,
            servings=state.user_servings,
            used_ingredients=feat.core_matched_ingredients if hasattr(feat, 'core_matched_ingredients')
                            else [i.name for i in state.request.ingredients
                                  if i.name in recipe.core_ingredients],
            missing_core=feat.missing_core,
            missing_optional=feat.missing_optional,
            reason=f"核心食材匹配度 {score} 分",
            prep=guide_data.get("prep", []),
            steps=guide_data.get("steps", []),
            heat_tips=guide_data.get("heat_tips", ""),
            substitutions=guide_data.get("substitutions", []),
        ))

    # 构建响应
    ing_names = [i.name for i in state.request.ingredients] if state.request else []
    state.response = RecommendationResponse(
        request_summary=RequestSummary(
            ingredients=ing_names,
            servings=state.user_servings,
            assumed_staples=state.request.assumed_staples if state.request else [],
        ),
        recommendations=recommendations,
        blocked_recipes=[
            {"recipe_id": f.recipe_id, "block_reason": "; ".join(f.block_reasons)}
            for f in state.features if f.blocked
        ],
        trace_id=state.request.request_id if state.request else "",
    )

    _lap(state, 'guide')
    return state


def node_safety(state: ChefState) -> ChefState:
    """安全审查"""
    _timer(state, 'safety')
    state.stage = GraphStage.SAFETY

    if not state.response or not state.response.recommendations:
        _lap(state, 'safety')
        return state

    safe_recs = []
    for rec in state.response.recommendations:
        report = _safety.review(rec, state.user_allergens, state.user_excluded)
        if report.severity == "blocked":
            # 移到 blocked 列表
            state.response.blocked_recipes.append({
                "recipe_id": rec.recipe_id,
                "block_reason": "; ".join(report.issues)
            })
        else:
            # 将安全提醒附加到推荐中
            rec.safety_notes = report.issues
            safe_recs.append(rec)

    state.response.recommendations = safe_recs

    _lap(state, 'safety')
    return state


def node_output(state: ChefState) -> ChefState:
    """最终输出"""
    state.stage = GraphStage.OUTPUT
    return state


def node_error(state: ChefState) -> ChefState:
    """错误处理"""
    state.stage = GraphStage.ERROR
    return state


# ============================================================
# 路由函数（条件边）
# ============================================================

def route_after_categorize(state: ChefState) -> Literal["normalize", "error"]:
    if state.intent == Intent.RECOMMEND:
        return "normalize"
    # 暂不支持 LOOKUP / SUBSTITUTE（MVP 后扩展）
    return "normalize"


def route_after_retrieve(state: ChefState) -> Literal["match", "error"]:
    return "error" if state.stage == GraphStage.ERROR else "match"


def route_after_safety(state: ChefState) -> Literal["output", "error"]:
    return "output"


# ============================================================
# 构建图
# ============================================================

def build_graph() -> StateGraph:
    """构建 LangGraph 工作流"""
    workflow = StateGraph(ChefState)

    # 添加节点
    workflow.add_node("categorize", node_categorize)
    workflow.add_node("normalize", node_normalize)
    workflow.add_node("retrieve", node_retrieve)
    workflow.add_node("match", node_match)
    workflow.add_node("score", node_score)
    workflow.add_node("guide", node_guide)
    workflow.add_node("safety", node_safety)
    workflow.add_node("output", node_output)
    workflow.add_node("error", node_error)

    # 设置入口
    workflow.set_entry_point("categorize")

    # 添加边
    workflow.add_conditional_edges("categorize", route_after_categorize, {
        "normalize": "normalize",
        "error": "error",
    })
    workflow.add_edge("normalize", "retrieve")
    workflow.add_conditional_edges("retrieve", route_after_retrieve, {
        "match": "match",
        "error": "error",
    })
    workflow.add_edge("match", "score")
    workflow.add_edge("score", "guide")
    workflow.add_edge("guide", "safety")
    workflow.add_edge("safety", "output")
    workflow.add_edge("output", END)
    workflow.add_edge("error", END)

    return workflow


# 编译后的 graph（全局单例）
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph().compile()
    return _graph


# ============================================================
# 便捷调用
# ============================================================

async def recommend(req: RecommendRequest) -> ChefState:
    """
    给定前端 RecommendRequest，执行完整流程，返回最终 ChefState。
    """
    state = ChefState(
        raw_input=req.ingredients_text,
        request=NormalizedRequest(
            request_id=str(uuid.uuid4()),
            servings=req.servings,
            time_limit_min=req.time_limit_min,
            difficulty=req.difficulty,
            flavor=req.flavor,
            excluded_ingredients=req.excluded,
            allergens=req.allergens,
            equipment=req.equipment,
        ),
        user_allergens=req.allergens,
        user_excluded=req.excluded,
        user_equipment=req.equipment,
        user_flavor=req.flavor,
        user_time_limit=req.time_limit_min,
        user_servings=req.servings,
    )
    graph = get_graph()
    result = await graph.ainvoke(state)
    # ainvoke 可能返回 dict，统一转为 ChefState
    if isinstance(result, dict):
        return ChefState(**result)
    return result
