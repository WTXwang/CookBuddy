"""启动前端静态文件服务（端口 3000）"""
import http.server
import socketserver
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
PORT = 3000

if not FRONTEND_DIR.exists():
    print(f"[ERROR] 前端目录不存在：{FRONTEND_DIR}")
    sys.exit(1)

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def log_message(self, format, *args):
        print(f"[frontend:{PORT}] {args[0]}")

print(f"[frontend] 启动静态服务 @ http://localhost:{PORT}")
print(f"[frontend] 按 Ctrl+C 停止")

with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[frontend] 已停止")
