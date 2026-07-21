"""停止所有开发服务器进程"""
import subprocess
import sys

print("[stop] 查找并停止开发服务器进程...")

# Windows: 用 taskkill 停止 uvicorn 和 http.server
commands = [
    # 停止 uvicorn 进程（后端）
    'taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" 2>nul',
    # 也可以按端口杀
    'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :8000 ^| findstr LISTENING\') do taskkill /F /PID %a 2>nul',
    'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :3000 ^| findstr LISTENING\') do taskkill /F /PID %a 2>nul',
]

# 简单方案：用 Python 查找并终止
import os
import signal

killed = 0
try:
    result = subprocess.run(
        ['tasklist', '/FO', 'CSV', '/NH'],
        capture_output=True, text=True, shell=True
    )
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.replace('"', '').split(',')
        if len(parts) >= 2:
            image = parts[0].strip()
            pid = parts[1].strip()
            if image in ('python.exe', 'python3.exe'):
                # 不杀自己
                if pid != str(os.getpid()):
                    try:
                        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True, shell=True)
                        killed += 1
                    except Exception:
                        pass
except Exception as e:
    print(f"  [warn] {e}")

print(f"[stop] 已停止 {killed} 个 Python 进程")
print("[stop] 注意：这停止了所有 python.exe 进程（除自身外）")
