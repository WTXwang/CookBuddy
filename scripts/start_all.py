"""一键启动前后端开发服务器"""
import subprocess
import sys
import time
import signal
import os
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPTS_DIR.parent / "backend"
FRONTEND_PORT = 3000

print("=" * 50)
print("  今晚吃什么 — 开发服务器启动")
print("=" * 50)

processes = []

def cleanup():
    print("\n[shutdown] 正在停止所有服务...")
    for name, proc in processes:
        if proc.poll() is None:
            print(f"  停止 {name}...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("[shutdown] 全部已停止")

def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

try:
    # 启动后端
    print("[start] 启动后端 (FastAPI + uvicorn --reload) @ http://localhost:8000")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(BACKEND_DIR),
    )
    processes.append(("backend", backend))
    time.sleep(2)

    if backend.poll() is not None:
        print("[ERROR] 后端启动失败，请检查错误信息")
        cleanup()
        sys.exit(1)

    # 启动前端
    print(f"[start] 启动前端 (http.server) @ http://localhost:{FRONTEND_PORT}")
    frontend = subprocess.Popen(
        [sys.executable, str(SCRIPTS_DIR / "start_frontend.py")],
    )
    processes.append(("frontend", frontend))
    time.sleep(1)

    print()
    print("=" * 50)
    print(f"  后端 API : http://localhost:8000/docs")
    print(f"  前端页面 : http://localhost:{FRONTEND_PORT}")
    print("  按 Ctrl+C 停止全部")
    print("=" * 50)

    # 等待任意子进程结束
    while True:
        for name, proc in processes:
            if proc.poll() is not None:
                print(f"\n[{name}] 进程异常退出 (code={proc.returncode})")
                cleanup()
                sys.exit(1)
        time.sleep(1)

except KeyboardInterrupt:
    pass
finally:
    cleanup()
