"""Harness PostToolUse hook: 检查 Python 文件语法"""
import sys
import json
import py_compile
from pathlib import Path

try:
    data = json.load(sys.stdin)
    f = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
except (json.JSONDecodeError, KeyError):
    sys.exit(0)

if not f:
    sys.exit(0)

p = Path(f)
if p.suffix != ".py":
    sys.exit(0)

try:
    py_compile.compile(str(p), doraise=True)
    print(f"[harness] OK  {p.name}")
except py_compile.PyCompileError as e:
    print(f"[harness] SYNTAX ERROR  {p.name}: {e}", file=sys.stderr)
    sys.exit(1)
