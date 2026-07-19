"""FastAPI 入口 —— 今晚吃什么 推荐服务"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from schemas import RecommendRequest, RecommendationResponse
from graph import recommend as run_recommend
from routers.auth import router as auth_router
import database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭钩子"""
    # 启动时预编译 graph
    from graph import get_graph
    get_graph()
    await database.init_pool()
    yield
    await database.close_pool()


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


@app.post("/api/recommend")
async def api_recommend(req: RecommendRequest):
    """
    推荐接口 —— 用户提供食材文本和约束，返回菜谱推荐。

    响应结构见 schemas.RecommendationResponse。
    """
    if not req.ingredients_text.strip():
        raise HTTPException(status_code=422, detail="请至少提供一种现有食材")

    try:
        state = await run_recommend(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐流程异常: {str(e)}")

    if state.error and not state.response:
        raise HTTPException(status_code=422, detail=state.error)

    if not state.response or not state.response.recommendations:
        return RecommendationResponse(
            request_summary=state.response.request_summary if state.response else None,
            recommendations=[],
            follow_up_question="没有找到完全匹配的菜谱，试试放宽条件或补充食材？",
            trace_id=state.request.request_id if state.request else "",
        )

    return state.response


@app.get("/api/recipes/{recipe_id}")
async def api_get_recipe(recipe_id: str):
    """查看某道菜的完整信息（P1 MVP 后续）"""
    # 从检索桩中查找
    from retrieval.stub import SEED_RECIPES
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
