"""提交前检查：对 git diff --cached 中的 .py 文件做语法检查"""
import subprocess
import sys
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

print("=" * 50)
print("  Pre-commit 检查")
print("=" * 50)

# 获取暂存区中变更的 .py 文件
result = subprocess.run(
    ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
    capture_output=True, text=True, cwd=str(ROOT)
)

if result.returncode != 0:
    print("[ERROR] git diff 失败")
    print(result.stderr)
    sys.exit(1)

staged = [line.strip() for line in result.stdout.strip().split("\n") if line.strip().endswith(".py")]

if not staged:
    print("没有暂存的 Python 文件变更，跳过检查。")
    sys.exit(0)

print(f"检查 {len(staged)} 个暂存文件：")

errors = []
for rel_path in staged:
    filepath = ROOT / rel_path
    if not filepath.exists():
        print(f"  SKIP  {rel_path} (已删除)")
        continue

    try:
        py_compile.compile(str(filepath), doraise=True)
        print(f"  OK  {rel_path}")
    except py_compile.PyCompileError as e:
        print(f"  FAIL  {rel_path}")
        print(f"        {e}")
        errors.append((rel_path, str(e)))

print()
if errors:
    print(f"[BLOCKED] {len(errors)} 个文件有语法错误，提交已阻止。")
    sys.exit(1)
else:
    print("[PASS] 全部通过，可以提交。")
