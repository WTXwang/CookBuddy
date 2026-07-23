"""LangGraph 主控流程 —— Concierge 总控，三条分支

  Concierge ─┬─ chat ──────────────────────────→ Output
              ├─ recommend → Parser → Normalize → Retrieve → Match → Score → Guide → Safety → Output
              └─ lookup ──────────────────────→ Retrieve → Match → Score → Guide → Safety → Output
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
from agents.cooking_guide import CookingGuide
from agents.safety import FoodSafetyReviewer
from agents.concierge import concierge_chat
from agents.parser import parse_to_user_request
from retrieval import create_retriever
import config


# ============================================================
# 初始化模块（每个 Agent 独立指定模型）
# ============================================================
_retrieval = create_retriever()
_guide = CookingGuide(model=config.GUIDE_MODEL)
_safety = FoodSafetyReviewer(model=config.SAFETY_MODEL)


def set_retrieval(r):
    global _retrieval
    _retrieval = r


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


async def node_concierge(state: ChefState) -> ChefState:
    """对话门面 + 意图路由（只分类，不提取字段）"""
    _timer(state, 'concierge')
    state.stage = GraphStage.CONCIERGE

    text = state.raw_input.strip()
    if not text:
        state.intent = Intent.OTHER
        state.chat_reply = "你好像还没说话呢～告诉我你有什么食材，我帮你搭配！"
        state.stage = GraphStage.ERROR
        _lap(state, 'concierge')
        return state

    result = await concierge_chat(user_text=text, context=state.conversation_context)
    state.intent = result.intent
    state.chat_reply = result.reply
    state.dish_name = result.dish_name

    # 更新上下文，供下一轮对话使用
    state.conversation_context = f"用户说：{text}\n助手回复：{result.reply}"

    _lap(state, 'concierge')
    return state


async def node_parser(state: ChefState) -> ChefState:
    """Parser：LLM 提取 8 字段 → UserRequest"""
    _timer(state, 'parser')
    state.stage = GraphStage.CONCIERGE

    req = state.request
    user_req = await parse_to_user_request(
        ingredients_text=state.raw_input,
        servings=req.servings if req else 2,
        time_limit_min=req.time_limit_min if req else 30,
        difficulty=req.difficulty if req else "任意",
        flavor=req.flavor if req else "",
        excluded=req.excluded_ingredients if req else [],
        allergens=req.allergens if req else [],
        equipment=req.equipment if req else [],
    )

    state.raw_ingredients = user_req.ingredients
    state.user_allergens = user_req.allergens
    state.user_excluded = user_req.excluded
    state.user_equipment = user_req.equipment
    state.user_servings = user_req.servings
    state.user_flavor = user_req.flavor
    state.user_time_limit = user_req.time_limit_min

    _lap(state, 'parser')
    return state


def node_lookup(state: ChefState) -> ChefState:
    """教学线：Concierge 已提取菜名，直接设置 raw_ingredients 供检索使用"""
    _timer(state, 'lookup')
    state.stage = GraphStage.LOOKUP

    dish_name = state.dish_name or state.raw_input.strip()
    state.raw_ingredients = [dish_name]
    state.intent = Intent.LOOKUP

    _lap(state, 'lookup')
    return state


def node_normalize(state: ChefState) -> ChefState:
    """食材标准化 + 基础调料识别（A 的 normalizer）"""
    _timer(state, 'normalize')
    state.stage = GraphStage.NORMALIZE

    # 标准化（交给 A）—— 空食材时跳过，靠 retrieve 兜底
    if state.raw_ingredients:
        normalized = normalize_ingredients(state.raw_ingredients)
    else:
        normalized = []

    # 基础调料
    staples = get_staples(assume=True, include_aromatics=True)

    state.request = NormalizedRequest(
        request_id=state.request.request_id if state.request else str(uuid.uuid4()),
        ingredients=normalized,
        servings=state.user_servings,
        time_limit_min=state.user_time_limit,
        difficulty=state.request.difficulty if state.request else "任意",
        flavor=state.user_flavor,
        excluded_ingredients=state.user_excluded,
        allergens=state.user_allergens,
        equipment=state.user_equipment,
        assume_staples=True,
        assumed_staples=staples,
    )

    _lap(state, 'normalize')
    return state


def node_retrieve(state: ChefState) -> ChefState:
    """知识库检索 —— 按意图分流：lookup 走菜名检索，recommend 走食材检索"""
    _timer(state, 'retrieve')
    state.stage = GraphStage.RETRIEVE

    # ── Lookup 路径：用户已知菜名，查做法 ──
    if state.intent == Intent.LOOKUP:
        dish_name = state.raw_ingredients[0] if state.raw_ingredients else state.raw_input.strip()
        if not dish_name:
            state.error = "未能识别菜名"
            state.stage = GraphStage.ERROR
            _lap(state, 'retrieve')
            return state
        state.candidates = _retrieval.search_by_name(dish_name, top_n=1)
        if not state.candidates:
            state.error = f"未找到「{dish_name}」的做法"
            state.stage = GraphStage.ERROR
        _lap(state, 'retrieve')
        return state

    # ── Recommend 路径：按标准化食材检索 ──
    if not state.request or not state.request.ingredients:
        # 无食材：兜底推荐
        state.candidates = _retrieval.get_suggestions(top_n=5)
        if not state.candidates:
            state.error = "无可检索食材"
            state.stage = GraphStage.ERROR
        _lap(state, 'retrieve')
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


async def node_guide(state: ChefState) -> ChefState:
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

        guide_data = await _guide.generate(recipe, feat)

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


async def node_safety(state: ChefState) -> ChefState:
    """安全审查"""
    _timer(state, 'safety')
    state.stage = GraphStage.SAFETY

    if not state.response or not state.response.recommendations:
        _lap(state, 'safety')
        return state

    safe_recs = []
    for rec in state.response.recommendations:
        report = await _safety.review(rec, state.user_allergens, state.user_excluded)
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
    if state.response:
        state.response.conversation_context = state.conversation_context
    return state


def node_error(state: ChefState) -> ChefState:
    """错误处理"""
    state.stage = GraphStage.ERROR
    return state


# ============================================================
# 路由函数（条件边）
# ============================================================

def route_after_concierge(state: ChefState) -> Literal["parser", "lookup", "output", "error"]:
    if state.stage == GraphStage.ERROR:
        return "error"
    if state.intent == Intent.CHAT:
        return "output"
    if state.intent == Intent.LOOKUP:
        return "lookup"
    return "parser"


def route_after_parser(state: ChefState) -> Literal["normalize", "error"]:
    return "error" if state.stage == GraphStage.ERROR else "normalize"


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
    workflow.add_node("concierge", node_concierge)
    workflow.add_node("parser", node_parser)
    workflow.add_node("lookup", node_lookup)
    workflow.add_node("normalize", node_normalize)
    workflow.add_node("retrieve", node_retrieve)
    workflow.add_node("match", node_match)
    workflow.add_node("score", node_score)
    workflow.add_node("guide", node_guide)
    workflow.add_node("safety", node_safety)
    workflow.add_node("output", node_output)
    workflow.add_node("error", node_error)

    # 入口：Concierge 统一对话门面
    workflow.set_entry_point("concierge")

    # ── 三条分支 ──
    workflow.add_conditional_edges("concierge", route_after_concierge, {
        "parser": "parser",         # recommend → Parser 提取 8 字段
        "lookup": "lookup",         # lookup → 教学线，传菜名给 A 检索
        "output": "output",         # chat → 直接输出对话
        "error": "error",
    })
    # 菜谱线：parser → normalize → retrieve → match → score → guide → safety
    workflow.add_conditional_edges("parser", route_after_parser, {
        "normalize": "normalize",
        "error": "error",
    })
    workflow.add_edge("normalize", "retrieve")
    # 教学线：lookup → retrieve（A 负责用菜名精确查找）
    workflow.add_edge("lookup", "retrieve")
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
        conversation_context=req.conversation_context,
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
