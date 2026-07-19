"""RAGFlow 连接探测脚本
用法: python -X utf8 scripts/probe_ragflow.py

自动探测 RAGFlow API 版本和可用端点，帮助确定正确的接口格式。
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import urllib.request
import urllib.error
import config


def api_request(method, path, body=None, host=None, api_key=None):
    """发送请求并打印详细信息"""
    host = (host or config.RAGFLOW_HOST).rstrip('/')
    api_key = api_key or config.RAGFLOW_API_KEY
    url = f"{host}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode('utf-8') if body else None

    print(f"\n{'='*60}")
    print(f"  {method} {path}")
    if body:
        print(f"  Body: {json.dumps(body, ensure_ascii=False)}")
    print(f"{'='*60}")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            print(f"  ✅ HTTP {resp.status}")
            # 截断过长的内容
            result_str = json.dumps(result, ensure_ascii=False, indent=2)
            if len(result_str) > 1500:
                result_str = result_str[:1500] + "\n  ... (截断)"
            print(f"  响应: {result_str}")
            return result
    except urllib.error.HTTPError as e:
        body_text = e.read().decode('utf-8', errors='replace')[:300] if e.fp else '(empty)'
        print(f"  ❌ HTTP {e.code}: {body_text}")
        return None
    except urllib.error.URLError as e:
        print(f"  ❌ 连接失败: {e.reason}")
        return None


def main():
    print("""
╔══════════════════════════════════════════════╗
║   RAGFlow API 探测工具                      ║
║   自动发现可用的 API 端点和数据格式         ║
╚══════════════════════════════════════════════╝
""")
    host = config.RAGFLOW_HOST
    api_key = config.RAGFLOW_API_KEY
    kb_name = config.RAGFLOW_KB_NAME

    print(f"配置:")
    print(f"  Host:     {host or '(未设置)'}")
    print(f"  API Key:  {api_key[:12] + '***' if len(api_key) > 12 else '(未设置)'}")
    print(f"  KB Name:  {kb_name}")

    if not host or not api_key:
        print("\n⚠️  请先在 config.py 中设置 RAGFLOW_HOST 和 RAGFLOW_API_KEY")
        print("   RAGFLOW_HOST: RAGFlow 地址（如 http://localhost:9380）")
        print("   RAGFLOW_API_KEY: 从 RAGFlow Web UI 右上角 → API 获取")
        return

    # ── Step 1: 测试连通性 ──
    print("\n\n📡 Step 1: 测试连通性")
    result = api_request("GET", "/api/v1/healthz") or api_request("GET", "/health")

    # ── Step 2: 列出知识库 ──
    print("\n\n📚 Step 2: 查找知识库")
    datasets = (
        api_request("GET", "/api/v1/datasets") or
        api_request("GET", "/api/datasets")
    )
    dataset_id = None
    if datasets and datasets.get("code") == 0:
        for ds in datasets.get("data", []):
            ds_name = ds.get("name", "?")
            ds_id = ds.get("id", "?")
            print(f"    知识库: {ds_name} (id={ds_id})")
            if ds_name == kb_name:
                dataset_id = ds_id
                print(f"    ✅ 匹配到目标知识库 '{kb_name}'")
    if not dataset_id:
        print(f"    ⚠ 未找到名为 '{kb_name}' 的知识库，将用名称代替 ID")

    # ── Step 3: 尝试检索 ──
    print(f"\n\n🔍 Step 3: 尝试检索（用 '{kb_name}' 知识库）")
    ds_id = dataset_id or kb_name
    query = "番茄 鸡蛋 土豆"

    # 尝试多个可能的端点
    endpoints = [
        ("POST", "/api/v1/retrieval", {
            "question": query,
            "dataset_ids": [ds_id],
            "page": 1, "page_size": 3,
            "similarity_threshold": 0.1,
            "vector_similarity_weight": 0.5,
        }),
        ("POST", f"/api/v1/datasets/{ds_id}/retrieve", {
            "question": query,
            "page": 1, "page_size": 3,
        }),
        ("POST", "/api/v1/chat/completions", {
            "question": query,
            "dataset_ids": [ds_id],
            "stream": False,
            "page_size": 3,
        }),
    ]

    for method, path, body in endpoints:
        result = api_request(method, path, body)
        if result and result.get("code") == 0:
            chunks = (
                result.get("data", {}).get("chunks", []) or
                result.get("data", {}).get("reference", {}).get("chunks", [])
            )
            print(f"\n    📊 检索到 {len(chunks)} 个 chunks")
            for i, chunk in enumerate(chunks[:3]):
                doc = chunk.get("doc_name", "?")
                sim = chunk.get("similarity", chunk.get("vector_similarity", "?"))
                content_preview = (chunk.get("content", "") or chunk.get("content_with_weight", ""))[:100]
                print(f"    [{i+1}] {doc} (相似度={sim})")
                print(f"        内容预览: {content_preview}...")
            print(f"\n    ✅ 可用端点: {method} {path}")
            break
    else:
        print("\n    ❌ 所有端点均失败，请检查 RAGFlow 版本和配置")

    # ── Step 4: 建议 ──
    print(f"""
{'='*60}
📋 下一步

根据上面成功的端点，在 config.py 中确认以下配置:

    RAGFLOW_HOST = "{host}"
    RAGFLOW_API_KEY = "{api_key[:12]}..."
    RAGFLOW_KB_NAME = "{kb_name}"
    RETRIEVAL_BACKEND = "ragflow"

然后测试检索:
    python -X utf8 -c "from retrieval import create_retriever; \\
        r = create_retriever(); \\
        print([c.title for c in r.search(['番茄','鸡蛋'], 5)])"

如果一切正常，应返回知识库中的菜谱列表。
{'='*60}
""")


if __name__ == "__main__":
    main()
