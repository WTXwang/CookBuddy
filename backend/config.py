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
# 路径
# ============================================================
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_BASE_DIR: str = os.path.join(BASE_DIR, "..", "knowledge-base", "recipes")
DATA_DIR: str = os.path.join(BASE_DIR, "..", "data")
