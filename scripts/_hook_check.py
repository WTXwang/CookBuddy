"""Harness PostToolUse hook: 根据被修改的文件，检查对应的"不能坏"的规则

检查矩阵：
  graph.py   → safety 节点存在 + safety→output 边存在
  ragflow.py → stub 降级分支完整
  config.py  → 无硬编码 API key
  所有 .py   → 语法编译
"""

import sys
import json
import ast
import re
import py_compile
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# 检查函数
# ═══════════════════════════════════════════════════════════════

def _check_graph(tree: ast.AST) -> list[str]:
    """graph.py：验证 safety 节点和 safety→output 边存在"""
    issues = []

    # 找到 build_graph 函数体
    func_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_graph":
            func_node = node
            break

    if func_node is None:
        return issues  # 不是 graph 构建文件，跳过

    nodes: set[str] = set()
    edges: list[tuple[str, str]] = []

    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue

        match node:
            case ast.Call(
                func=ast.Attribute(attr="add_node"),
                args=[ast.Constant(value=str(name)), *_],
            ):
                nodes.add(name)

            case ast.Call(
                func=ast.Attribute(attr="add_edge"),
                args=[ast.Constant(value=str(a)), ast.Constant(value=str(b)), *_],
            ):
                edges.append((a, b))

            case ast.Call(
                func=ast.Attribute(attr="add_conditional_edges"),
                args=[ast.Constant(value=str(src)), _, mapping, *_],
            ) if isinstance(mapping, ast.Dict):
                for val in mapping.values:
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        edges.append((src, val.value))

    # 检查
    if "safety" not in nodes:
        issues.append("缺失 safety 节点 — 过敏原/忌口检查可能被绕过")
    elif ("safety", "output") not in edges:
        issues.append("缺失 safety→output 边 — 安全审查结果未传递到输出")

    return issues


def _check_ragflow(source: str) -> list[str]:
    """ragflow.py：验证 RAGFlow 失败时有 stub 降级"""
    issues = []

    # search_ids 方法里 except 块是否调用 self._stub
    if "self._stub" not in source:
        issues.append("缺失 self._stub 引用 — RAGFlow 失败时无降级")
    if "降级到 stub" not in source:
        issues.append("缺失降级标记 — fallback 逻辑可能已被删除")

    return issues


def _check_config(source: str) -> list[str]:
    """config.py：检查安全隐患"""
    issues = []

    # 检查 RAGFLOW_API_KEY 是否有硬编码默认值
    m = re.search(r'RAGFLOW_API_KEY.*?"(ragflow-[^"]+)"', source)
    if m:
        issues.append(
            f"RAGFLOW_API_KEY 有硬编码默认值，存在泄露风险，"
            f"建议改为 os.getenv(\"RAGFLOW_API_KEY\", \"\")"
        )

    # 检查 TOTAL_TIMEOUT_SEC 是否被引用（跨文件，只提示）
    # 这里只做标记检查，实际接线由开发者保证

    return issues


def _check_config_loop(source: str) -> list[str]:
    """config.py：验证 Loop 运行时控流参数在合理范围"""
    issues = []

    # LOOP_RETRY_MAX 在 1-5 范围
    m = re.search(r"LOOP_RETRY_MAX.*?int\(.*?,\s*\"(\d+)\"\)", source)
    if m:
        val = int(m.group(1))
        if not (1 <= val <= 5):
            issues.append(f"LOOP_RETRY_MAX={val} 不在合理范围 (1-5)")
    else:
        issues.append("LOOP_RETRY_MAX 未找到，Loop 重试次数未配置")

    # LOOP_CIRCUIT_BREAKER_FAILS >= 1
    m = re.search(r"LOOP_CIRCUIT_BREAKER_FAILS.*?int\(.*?,\s*\"(\d+)\"\)", source)
    if m:
        val = int(m.group(1))
        if val < 1:
            issues.append(f"LOOP_CIRCUIT_BREAKER_FAILS={val} 必须 >= 1（不允许无限重试）")
    else:
        issues.append("LOOP_CIRCUIT_BREAKER_FAILS 未找到，熔断阈值未配置")

    # LOOP_CIRCUIT_BREAKER_COOLDOWN >= 10
    m = re.search(r"LOOP_CIRCUIT_BREAKER_COOLDOWN.*?int\(.*?,\s*\"(\d+)\"\)", source)
    if m:
        val = int(m.group(1))
        if val < 10:
            issues.append(f"LOOP_CIRCUIT_BREAKER_COOLDOWN={val}s 冷却时间过短（建议 >= 10s）")
    else:
        issues.append("LOOP_CIRCUIT_BREAKER_COOLDOWN 未找到，熔断冷却时间未配置")

    # LOOP_MAX_CONCURRENCY >= 1
    m = re.search(r"LOOP_MAX_CONCURRENCY.*?int\(.*?,\s*\"(\d+)\"\)", source)
    if m:
        val = int(m.group(1))
        if val < 1:
            issues.append(f"LOOP_MAX_CONCURRENCY={val} 必须 >= 1")
    else:
        issues.append("LOOP_MAX_CONCURRENCY 未找到，并发控制未配置")

    return issues


def _check_schemas(tree: ast.AST) -> list[str]:
    """schemas.py：验证前端依赖的关键字段未被删除"""
    # 前端 renderer.js 直接访问的所有字段
    CRITICAL: dict[str, list[str]] = {
        "RecommendationResponse": [
            "request_summary", "recommendations", "follow_up_question",
            "blocked_recipes", "trace_id",
        ],
        "Recommendation": [
            "recipe_id", "title", "image_url", "match_score", "match_label",
            "estimated_time_min", "difficulty", "servings",
            "used_ingredients", "missing_core", "missing_optional",
            "reason", "prep", "steps", "heat_tips", "substitutions",
            "safety_notes",
        ],
        "RequestSummary": [
            "ingredients",
        ],
    }

    issues: list[str] = []

    # 从 AST 提取所有 BaseModel 类及其字段
    models: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [
            b.id if isinstance(b, ast.Name) else b.attr
            for b in node.bases
            if isinstance(b, (ast.Name, ast.Attribute))
        ]
        if "BaseModel" not in bases:
            continue

        fields: set[str] = set()
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.add(item.target.id)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        fields.add(target.id)
        models[node.name] = fields

    for model_name, required_fields in CRITICAL.items():
        if model_name not in models:
            issues.append(f"模型 {model_name} 未找到 — 前端依赖此模型")
            continue
        missing = [f for f in required_fields if f not in models[model_name]]
        if missing:
            fields_str = ", ".join(missing)
            issues.append(f"{model_name} 缺失字段: {fields_str} — 前端 renderer.js 依赖这些字段")

    return issues


# ═══════════════════════════════════════════════════════════════
# 按文件名分发
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 通用检查（所有 .py 文件）
# ═══════════════════════════════════════════════════════════════

def _check_to_thread_coverage(source: str, filepath: str) -> list[str]:
    """检查 chat_json_guarded / chat_guarded 调用是否被 asyncio.to_thread 包裹"""
    issues = []
    lines = source.split("\n")

    for i, line in enumerate(lines):
        # 只检查实际函数调用（排除 import、def、注释）
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("from ") or stripped.startswith("import "):
            continue
        if stripped.startswith("def chat_guarded") or stripped.startswith("def chat_json_guarded"):
            continue
        if "chat_json_guarded" not in line and "chat_guarded" not in line:
            continue

        # 检查前后 2 行上下文是否包含 asyncio.to_thread
        context = "\n".join(lines[max(0, i - 2):i + 1])
        if "asyncio.to_thread" not in context:
            issues.append(
                f"LLM 调用缺 asyncio.to_thread: {filepath}:{i+1}: {stripped[:80]}"
            )

    return issues


def _check_llm_bypass(source: str, filepath: str) -> list[str]:
    """检查是否有代码绕过 llm_client 直接调 SiliconFlow API"""
    issues = []

    # 已知例外：recipes/extractor.py 有自带 fallback 的直接 HTTP 路径
    if filepath.replace("\\", "/").endswith("recipes/extractor.py"):
        return issues

    for lineno, line in enumerate(source.split("\n"), 1):
        stripped = line.strip()
        # 跳过注释
        if stripped.startswith("#"):
            continue
        # 检测直接 urlopen 调 API
        if "urlopen" in stripped and (
            "siliconflow" in stripped.lower()
            or "api.siliconflow" in stripped.lower()
        ):
            issues.append(
                f"LLM 调用绕过 llm_client: {filepath}:{lineno}: urlopen 直接调 SiliconFlow"
            )
        # 检测 requests 直接调 API
        if ("requests.post" in stripped or "requests.get" in stripped) and (
            "siliconflow" in stripped.lower()
            or "api.siliconflow" in stripped.lower()
        ):
            issues.append(
                f"LLM 调用绕过 llm_client: {filepath}:{lineno}: requests 直接调 SiliconFlow"
            )

    return issues


CHECKS = {
    "graph.py":   [lambda src, tree: _check_graph(tree)],
    "ragflow.py": [lambda src, _:  _check_ragflow(src)],
    "config.py":  [lambda src, _:  _check_config(src),
                   lambda src, _:  _check_config_loop(src)],
    "schemas.py": [lambda _, tree: _check_schemas(tree)],
}


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    try:
        data = json.load(sys.stdin)
        f = data.get("tool_input", {}).get("file_path", "")
    except (json.JSONDecodeError, KeyError):
        sys.exit(0)

    if not f:
        sys.exit(0)

    p = Path(f)
    if p.suffix != ".py":
        sys.exit(0)

    # ── 1. 语法编译（所有 .py 都跑） ──
    try:
        py_compile.compile(str(p), doraise=True)
    except py_compile.PyCompileError as e:
        print(f"[harness] SYNTAX ERROR {p.name}: {e}", file=sys.stderr)
        sys.exit(1)

    source = p.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        sys.exit(1)  # py_compile 已经报过了

    all_issues: list[str] = []

    # ── 2. 通用检查（所有 .py 都跑） ──
    # to_thread 覆盖：仅检查 backend/ 下的文件
    if "backend" in str(p):
        all_issues.extend(_check_to_thread_coverage(source, str(p)))
        all_issues.extend(_check_llm_bypass(source, str(p)))

    # ── 3. 按文件名匹配专项检查 ──
    for check_fn in CHECKS.get(p.name, []):
        result = check_fn(source, tree)
        if result:
            all_issues.extend(result)

    if all_issues:
        for issue in all_issues:
            print(f"[harness] ⚠ {p.name}: {issue}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"[harness] OK {p.name}")


if __name__ == "__main__":
    main()
