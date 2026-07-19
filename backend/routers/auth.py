"""认证路由 —— 注册 / 登录 / 获取当前用户"""

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import bcrypt
from jose import jwt, JWTError

from database import get_pool
import config

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


# ── 请求 / 响应模型 ──────────────────────────────

class AuthRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

class UserInfo(BaseModel):
    username: str


# ── JWT 工具 ──────────────────────────────────────

def _create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=config.JWT_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire, "iat": datetime.utcnow()}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def _verify_token(token: str) -> str:
    """验证 token，返回 username"""
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")


# ── 依赖注入：从 Bearer 头中获取当前用户 ──────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    return _verify_token(credentials.credentials)


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

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # 检查是否已存在
            await cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if await cur.fetchone():
                raise HTTPException(409, "用户名已存在")

            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            await cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash),
            )

    token = _create_token(username)
    return AuthResponse(access_token=token, username=username)


@router.post("/login", response_model=AuthResponse)
async def login(req: AuthRequest):
    """登录"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT username, password_hash FROM users WHERE username = %s",
                (req.username,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(401, "用户名或密码错误")
            db_user, db_hash = row
            if not bcrypt.checkpw(req.password.encode(), db_hash.encode()):
                raise HTTPException(401, "用户名或密码错误")

    token = _create_token(db_user)
    return AuthResponse(access_token=token, username=db_user)


@router.get("/me", response_model=UserInfo)
async def me(current_user: str = Depends(get_current_user)):
    """获取当前登录用户"""
    return UserInfo(username=current_user)
