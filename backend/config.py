"""
全局配置文件
"""
import os

# ============================================================
# SiliconFlow API
# ============================================================
SILICONFLOW_API_KEY: str = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL: str = "https://api.deepseek.com"
# ============================================================
# 各 Agent 模型（直接写模型全名，可通过环境变量覆盖）
# ============================================================
GUIDE_MODEL: str = os.getenv("CHEF_GUIDE_MODEL", "deepseek-v4-flash")
SAFETY_MODEL: str = os.getenv("CHEF_SAFETY_MODEL", "deepseek-v4-flash")
PARSER_MODEL: str = os.getenv("CHEF_PARSER_MODEL", "deepseek-v4-flash")
CONCIERGE_MODEL: str = os.getenv("CHEF_CONCIERGE_MODEL", "deepseek-v4-flash")
VISION_MODEL: str = os.getenv("CHEF_VISION_MODEL", "deepseek-v4-flash")
EMBEDDING_MODEL: str = os.getenv("CHEF_EMBEDDING_MODEL", "deepseek-v4-flash")
EXTRACTOR_MODEL: str = os.getenv("CHEF_EXTRACTOR_MODEL", "deepseek-v4-flash")

# ============================================================
# 推荐流程参数
# ============================================================
MAX_RECOMMENDATIONS: int = 3
RETRIEVAL_TOP_N: int = 10
LLM_TEMPERATURE: float = 0.3
TOTAL_TIMEOUT_SEC: int = 60  # 4×LLM(各~30s内部超时) + RAGFlow(10s)，60s 留足余量

# ============================================================
# Loop 运行时控流参数（可通过环境变量覆盖）
# ============================================================
LOOP_RETRY_MAX: int = int(os.getenv("LOOP_RETRY_MAX", "3"))                    # 最大重试次数 (1~5)
LOOP_RETRY_BACKOFF_BASE: float = float(os.getenv("LOOP_RETRY_BACKOFF_BASE", "1.5"))  # 退避底数
LOOP_RETRY_BACKOFF_MIN: float = float(os.getenv("LOOP_RETRY_BACKOFF_MIN", "0.5"))    # 最小退避间隔(秒)
LOOP_RETRY_BACKOFF_MAX: float = float(os.getenv("LOOP_RETRY_BACKOFF_MAX", "8.0"))    # 最大退避间隔(秒)
LOOP_CIRCUIT_BREAKER_FAILS: int = int(os.getenv("LOOP_CIRCUIT_BREAKER_FAILS", "5"))  # 连续失败触发熔断
LOOP_CIRCUIT_BREAKER_COOLDOWN: int = int(os.getenv("LOOP_CIRCUIT_BREAKER_COOLDOWN", "60"))  # 熔断冷却(秒)
LOOP_MAX_CONCURRENCY: int = int(os.getenv("LOOP_MAX_CONCURRENCY", "3"))        # 最大并发 LLM 调用
LOOP_LLM_TIMEOUT: float = float(os.getenv("LOOP_LLM_TIMEOUT", "30.0"))         # 单次 LLM HTTP 超时(秒)
LOOP_TOTAL_TIMEOUT: int = int(os.getenv("LOOP_TOTAL_TIMEOUT", "90"))           # /api/recommend 总超时

# ============================================================
# 检索后端 —— "stub" | "ragflow"
# ============================================================
RETRIEVAL_BACKEND: str = os.getenv("RETRIEVAL_BACKEND", "ragflow")

# RAGFlow 配置
RAGFLOW_HOST: str = os.getenv("RAGFLOW_HOST", "https://macbook-air.tail448e24.ts.net")
RAGFLOW_API_KEY: str = os.getenv("RAGFLOW_API_KEY", "ragflow-A3SjhQBw50wJObe3BIdL1TyHbUxGBQaCvEC7RsFiFik")
RAGFLOW_KB_NAME: str = os.getenv("RAGFLOW_KB_NAME", "recipe")

# ============================================================
# 路径
# ============================================================
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_BASE_DIR: str = os.path.join(BASE_DIR, "..", "knowledge-base", "recipes")
DATA_DIR: str = os.path.join(BASE_DIR, "..", "data")

# ============================================================
# SQLite 数据库路径
# ============================================================
DATABASE_PATH: str = os.getenv(
    "DATABASE_PATH",
    str(os.path.join(BASE_DIR, "data", "users.db"))
)

# 用户画像 JSON 目录
PROFILES_DIR: str = os.getenv(
    "PROFILES_DIR",
    str(os.path.join(BASE_DIR, "data", "profiles"))
)

# ============================================================
# JWT
# ============================================================
JWT_SECRET: str = os.getenv("JWT_SECRET", "chef-dev-secret-change-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_HOURS: int = 72
