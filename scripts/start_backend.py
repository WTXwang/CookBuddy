"""启动 FastAPI 后端（带热重载）"""
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"

if not BACKEND_DIR.exists():
    print(f"[ERROR] 后端目录不存在：{BACKEND_DIR}")
    sys.exit(1)

print(f"[backend] 启动 FastAPI @ http://localhost:8000")
subprocess.run(
    [sys.executable, "-m", "uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
    cwd=str(BACKEND_DIR),
)
