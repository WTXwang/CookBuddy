"""语法和 import 检查 —— 遍历所有 .py 文件"""
import subprocess
import sys
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
SCRIPTS = ROOT / "scripts"

print("=" * 50)
print("  Python 语法检查")
print("=" * 50)

errors = []
checked = 0

def check_file(filepath: Path):
    global checked
    checked += 1
    try:
        py_compile.compile(str(filepath), doraise=True)
        print(f"  OK  {filepath.relative_to(ROOT)}")
    except py_compile.PyCompileError as e:
        print(f"  FAIL  {filepath.relative_to(ROOT)}")
        print(f"        {e}")
        errors.append((filepath, str(e)))

# 扫描 backend 目录
for py_file in sorted(BACKEND.rglob("*.py")):
    if "__pycache__" in str(py_file):
        continue
    check_file(py_file)

# 扫描 scripts 目录
for py_file in sorted(SCRIPTS.rglob("*.py")):
    if "__pycache__" in str(py_file):
        continue
    check_file(py_file)

print()
print(f"检查完成：{checked} 个文件，{len(errors)} 个错误")

if errors:
    print("\n错误详情：")
    for fpath, err in errors:
        print(f"  {fpath.relative_to(ROOT)}: {err}")
    sys.exit(1)
else:
    print("全部通过！")
