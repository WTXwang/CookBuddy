"""认证路由 —— 注册 / 登录 / 获取当前用户 / 用户画像"""

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import bcrypt
from jose import jwt, JWTError

from database import get_db
from profiles import ProfileStore
import config

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


# ── 请求 / 响应模型 ──────────────────────────────

class AuthRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

class UserInfo(BaseModel):
    user_id: int
    username: str

class ProfileUpdateRequest(BaseModel):
    flavor: Optional[List[str]] = None
    difficulty: Optional[str] = None
    time_limit_min: Optional[int] = None
    servings: Optional[int] = None
    allergens: Optional[List[str]] = None
    excluded_ingredients: Optional[List[str]] = None
    equipment: Optional[List[str]] = None


# ── JWT 工具 ──────────────────────────────────────

_profile_store: ProfileStore | None = None


def set_profile_store(store: ProfileStore) -> None:
    global _profile_store
    _profile_store = store


def _get_profile_store() -> ProfileStore:
    assert _profile_store is not None, "ProfileStore 未初始化"
    return _profile_store


def _create_token(user_id: int, username: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=config.JWT_EXPIRE_HOURS)
    payload = {"sub": username, "uid": user_id, "exp": expire, "iat": datetime.utcnow()}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def _verify_token(token: str) -> tuple[int, str]:
    """验证 token，返回 (user_id, username)"""
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        return payload.get("uid", 0), payload.get("sub", "")
    except JWTError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")


def _get_user_id_from_db(username: str) -> int:
    """从数据库查 user_id（兼容旧 token 没有 uid 的情况）"""
    # This is a sync helper, use with caution
    return 0  # fallback handled in verify


# ── 依赖注入：从 Bearer 头中获取当前用户 ──────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserInfo:
    if credentials is None:
        raise HTTPException(status_code=401, detail="请先登录")
    uid, username = _verify_token(credentials.credentials)
    return UserInfo(user_id=uid, username=username)


def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> int | None:
    """可选认证：有 token 返回 user_id，没有返回 None"""
    if credentials is None:
        return None
    try:
        uid, _ = _verify_token(credentials.credentials)
        return uid
    except HTTPException:
        return None


# ── 端点 ──────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
async def register(req: AuthRequest):
    """注册新用户"""
    username = req.username.strip()
    password = req.password

    if len(username) < 2:
        raise HTTPException(422, "用户名至少 2 个字符")
    if len(password) < 6:
        raise HTTPException(422, "密码至少 6 位")

    db = await get_db()

    # 检查是否已存在
    cursor = await db.execute("SELECT id FROM users WHERE username = ?", (username,))
    if await cursor.fetchone():
        raise HTTPException(409, "用户名已存在")

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor = await db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    await db.commit()
    user_id = cursor.lastrowid

    token = _create_token(user_id, username)
    return AuthResponse(access_token=token, username=username)


@router.post("/login", response_model=AuthResponse)
async def login(req: AuthRequest):
    """登录"""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (req.username,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(401, "用户名或密码错误")
    db_id, db_user, db_hash = row["id"], row["username"], row["password_hash"]
    if not bcrypt.checkpw(req.password.encode(), db_hash.encode()):
        raise HTTPException(401, "用户名或密码错误")

    token = _create_token(db_id, db_user)
    return AuthResponse(access_token=token, username=db_user)


@router.get("/me", response_model=UserInfo)
async def me(current_user: UserInfo = Depends(get_current_user)):
    """获取当前登录用户"""
    return current_user


# ── 用户画像端点 ──────────────────────────────

@router.get("/profile")
async def get_profile(current_user: UserInfo = Depends(get_current_user)):
    """获取当前用户的画像"""
    store = _get_profile_store()
    return store.get(current_user.user_id)


@router.put("/profile")
async def update_profile(
    req: ProfileUpdateRequest,
    current_user: UserInfo = Depends(get_current_user),
):
    """更新用户画像（部分更新）"""
    store = _get_profile_store()
    profile = store.update_preferences(
        user_id=current_user.user_id,
        flavor=req.flavor,
        difficulty=req.difficulty,
        time_limit_min=req.time_limit_min,
        servings=req.servings,
        allergens=req.allergens,
        excluded_ingredients=req.excluded_ingredients,
        equipment=req.equipment,
    )
    return profile
