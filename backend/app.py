"""FastAPI 入口 —— 今晚吃什么 推荐服务"""

import asyncio
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from schemas import RecommendRequest, RecommendationResponse
from graph import recommend as run_recommend
from routers.auth import router as auth_router, get_optional_user_id, set_profile_store
from profiles import ProfileStore, extract_profile_changes, apply_changes
import database
import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭钩子"""
    # 预编译 graph
    from graph import get_graph
    get_graph()
    await database.init_db()

    # 初始化用户画像存储
    profile_store = ProfileStore(config.PROFILES_DIR)
    set_profile_store(profile_store)

    yield
    await database.close_db()


app = FastAPI(
    title="今晚吃什么 API",
    description="基于 LangGraph 的多 Agent 食材推荐菜肴服务",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS（前端开发用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(auth_router)


# ============================================================
# 接口
# ============================================================

@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "今晚吃什么"}


async def _background_profile_update(user_id: int, raw_input: str, conversation_context: str):
    """异步后台：LLM 分析对话，微调画像"""
    try:
        from routers.auth import _get_profile_store
        store = _get_profile_store()
        profile = store.get(user_id)
        profile_json = profile.model_dump_json(indent=2, ensure_ascii=False)

        changes = await asyncio.wait_for(
            extract_profile_changes(profile_json, raw_input, conversation_context),
            timeout=25,  # 比 extractor 内部 20s 多 5s 缓冲
        )
        if not changes:
            return

        if apply_changes(profile, changes):
            store.save(profile)
            print(f"[Profile] user_id={user_id} 画像已微调: {changes}")
    except asyncio.TimeoutError:
        print(f"[Profile] user_id={user_id} 画像更新超时，跳过")
    except Exception:
        traceback.print_exc()


@app.post("/api/recommend")
async def api_recommend(
    req: RecommendRequest,
    background_tasks: BackgroundTasks,
    user_id: int | None = Depends(get_optional_user_id),
):
    """
    统一入口 —— 闲聊或推荐。Concierge 判断意图后路由。
    登录用户始终融合画像约束，缩小 RAGFlow 检索范围。
    """
    if not req.ingredients_text.strip():
        raise HTTPException(status_code=422, detail="请至少提供一种现有食材")

    # ── 画像融合：始终叠加用户画像到请求中 ──
    if user_id is not None:
        from routers.auth import _get_profile_store
        profile = _get_profile_store().get(user_id)

        # 过敏原 = 画像 + 请求（并集，双向缩小）
        req.allergens = list(set(profile.allergens + req.allergens))

        # 忌口 = 画像 + 请求（并集）
        req.excluded = list(set(profile.excluded_ingredients + req.excluded))

        # 厨具 = 始终用画像（用户厨房不变）
        if profile.equipment:
            req.equipment = profile.equipment

        # 口味：请求优先，没填用画像
        if not req.flavor and profile.preferences.flavor:
            req.flavor = ",".join(profile.preferences.flavor)

        # 难度、时间、份数：请求优先，没填用画像
        if req.difficulty == "简单" and profile.preferences.difficulty != "任意":
            req.difficulty = profile.preferences.difficulty
        if req.time_limit_min == 20 and profile.preferences.time_limit_min != 30:
            req.time_limit_min = profile.preferences.time_limit_min
        if req.servings == 2 and profile.preferences.servings != 2:
            req.servings = profile.preferences.servings

    try:
        state = await asyncio.wait_for(
            run_recommend(req),
            timeout=config.LOOP_TOTAL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"推荐流程超时（{config.LOOP_TOTAL_TIMEOUT}s），请稍后重试或减少食材数量",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐流程异常: {str(e)}")

    # ── 更新画像统计（登录用户） ──
    if user_id is not None and state.response and state.response.recommendations:
        try:
            from routers.auth import _get_profile_store
            cuisines = [
                r.title for r in state.response.recommendations[:3]
            ]
            ingredients = state.response.request_summary.ingredients if state.response.request_summary else []
            _get_profile_store().update_stats(user_id, cuisines=cuisines, ingredients=ingredients)
        except Exception:
            pass  # 统计更新失败不影响主流程

    # ── 异步后台：LLM 微调画像（不阻塞响应） ──
    if user_id is not None:
        background_tasks.add_task(
            _background_profile_update,
            user_id,
            req.ingredients_text,
            req.conversation_context,
        )

    # 闲聊模式：直接返回对话回复
    if state.intent == "chat" and state.chat_reply:
        return {"reply": state.chat_reply, "intent": "chat", "conversation_context": state.conversation_context}

    if state.error and not state.response:
        raise HTTPException(status_code=422, detail=state.error)

    if not state.response or not state.response.recommendations:
        return RecommendationResponse(
            request_summary=state.response.request_summary if state.response else None,
            recommendations=[],
            follow_up_question=state.chat_reply or "没有找到完全匹配的菜谱，试试放宽条件或补充食材？",
            trace_id=state.request.request_id if state.request else "",
        )

    # 推荐成功时也带上 Concierge 的口头回复
    if state.chat_reply:
        state.response.follow_up_question = state.chat_reply

    return state.response


@app.get("/api/recipes/{recipe_id}")
async def api_get_recipe(recipe_id: str):
    """查看某道菜的完整信息（P1 MVP 后续）"""
    # 从检索桩中查找
    from retrieval import SEED_RECIPES
    for r in SEED_RECIPES:
        if r.recipe_id == recipe_id:
            return r.model_dump()
    raise HTTPException(status_code=404, detail="菜谱不存在")


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
