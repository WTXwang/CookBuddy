"""
全局配置文件
"""
import os

# ============================================================
# SiliconFlow API
# ============================================================
SILICONFLOW_API_KEY: str = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"

# ============================================================
# 各 Agent 模型（直接写模型全名，可通过环境变量覆盖）
# ============================================================
MATCHER_MODEL: str = os.getenv("CHEF_MATCHER_MODEL", "Qwen/Qwen2.5-72B-Instruct")
GUIDE_MODEL: str = os.getenv("CHEF_GUIDE_MODEL", "Qwen/Qwen2.5-72B-Instruct")
SAFETY_MODEL: str = os.getenv("CHEF_SAFETY_MODEL", "Qwen/Qwen2.5-72B-Instruct")
VISION_MODEL: str = os.getenv("CHEF_VISION_MODEL", "Qwen/Qwen2.5-VL-72B-Instruct")
EMBEDDING_MODEL: str = os.getenv("CHEF_EMBEDDING_MODEL", "BAAI/bge-m3")

# ============================================================
# 推荐流程参数
# ============================================================
MAX_RECOMMENDATIONS: int = 3
RETRIEVAL_TOP_N: int = 10
LLM_TEMPERATURE: float = 0.3
TOTAL_TIMEOUT_SEC: int = 15

# ============================================================
# 检索后端 —— "stub" | "ragflow"
# ============================================================
RETRIEVAL_BACKEND: str = os.getenv("RETRIEVAL_BACKEND", "stub")

# RAGFlow 配置
RAGFLOW_HOST: str = os.getenv("RAGFLOW_HOST", "http://127.0.0.1:9380")
RAGFLOW_API_KEY: str = os.getenv("RAGFLOW_API_KEY", "ragflow-M1btZ5ircgt4Lhn6Y0ogEmvmJ2SIxZmcpEdwN7gIskw")
RAGFLOW_KB_NAME: str = os.getenv("RAGFLOW_KB_NAME", "recipe")

# ============================================================
# 路径
# ============================================================
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_BASE_DIR: str = os.path.join(BASE_DIR, "..", "knowledge-base", "recipes")
DATA_DIR: str = os.path.join(BASE_DIR, "..", "data")

# ============================================================
# MySQL 数据库 —— 修改下面这行，填你的真实密码
# ============================================================
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "mysql://root:specialone27@127.0.0.1:3306/chef"
)

# ============================================================
# JWT
# ============================================================
JWT_SECRET: str = os.getenv("JWT_SECRET", "chef-dev-secret-change-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_HOURS: int = 72
