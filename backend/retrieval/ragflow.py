"""RAGFlow 真实检索 —— 通过 REST API 调用本地 RAGFlow 实例

RAGFlow 知识库中的菜谱是纯 markdown 格式（无 YAML 头部），
chunk 只包含正文段落。检索策略：
  1. 调 RAGFlow /api/v1/retrieval 获取相关 chunks
  2. 按文档分组，取最高相似度作为检索分
  3. 从 chunk 内容提取标题和食材信息构建 RecipeRecord
  4. 如果菜谱在 stub 种子数据中存在，用 stub 的结构化元数据
"""

import re
import json
import urllib.request
import urllib.error
from typing import List, Optional, Dict, Any
from collections import defaultdict

from schemas import RecipeRecord
from .base import BaseRetriever
from .stub import RetrievalStub, SEED_RECIPES
import config


# ============================================================
# 从 chunk/文档名提取 RecipeRecord
# ============================================================

def _extract_title_from_chunk(content: str, doc_name: str) -> str:
    """从 chunk 内容提取菜谱标题"""
    # 尝试匹配 "# XXX的做法" 或 "# XXX"
    m = re.search(r'^#\s+(.+?)(?:的做法|$)', content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # Fallback: 从文件名提取
    name = doc_name.rsplit('.', 1)[0].replace('_', ' ').strip() if '.' in doc_name else doc_name.strip()
    return name if name else '未知菜谱'


def _extract_ingredients_from_chunk(content: str) -> List[str]:
    """从 chunk 内容粗略提取食材名（- XXX 格式的行）"""
    ingredients = []
    # 匹配 "- 食材名 数量" 格式
    for m in re.finditer(r'^-\s+(.+?)(?:\s+\d|$)', content, re.MULTILINE):
        name = m.group(1).strip()
        # 过滤非食材行
        if name and len(name) < 30 and not name.startswith('#'):
            # 去掉括号里的说明
            name = re.sub(r'[（(].*?[）)]', '', name).strip()
            if name:
                ingredients.append(name)
    return ingredients


def _chunks_to_recipes(chunks: List[dict]) -> List[RecipeRecord]:
    """
    将 RAGFlow 返回的 chunks 转换为 RecipeRecord 列表。
    按文档分组，每组生成一个 RecipeRecord。
    """
    # 按 document_keyword 分组
    doc_groups: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "chunks": [],
        "max_similarity": 0.0,
        "doc_name": "",
        "content_parts": [],
    })

    for chunk in chunks:
        doc_key = chunk.get("document_keyword", chunk.get("docnm_kwd", ""))
        if not doc_key:
            doc_key = chunk.get("document_id", "unknown")

        group = doc_groups[doc_key]
        group["doc_name"] = doc_key
        group["chunks"].append(chunk)
        group["content_parts"].append(chunk.get("content", ""))

        # 取最高相似度
        sim = chunk.get("similarity", chunk.get("vector_similarity", 0.0))
        if sim > group["max_similarity"]:
            group["max_similarity"] = sim

    # 查找 stub 中的菜谱（用于补充结构化元数据）
    stub_map: Dict[str, RecipeRecord] = {}
    for r in SEED_RECIPES:
        # 尝试多种匹配方式
        stub_map[r.title] = r
        stub_map[r.recipe_id] = r

    recipes = []
    for doc_key, group in doc_groups.items():
        # 合并所有 chunk 内容作为 body
        full_body = "\n\n".join(group["content_parts"])
        doc_name = group["doc_name"]

        # 提取标题
        title = _extract_title_from_chunk(full_body, doc_name)

        # 尝试在 stub 中找匹配的菜谱
        stub_match = stub_map.get(title) or stub_map.get(doc_key)
        # 也尝试在 SEED_RECIPES 中做标题模糊匹配
        if not stub_match:
            for r in SEED_RECIPES:
                if r.title in title or title in r.title:
                    stub_match = r
                    break

        if stub_match:
            # 有结构化数据：用 stub 的元数据 + RAGFlow 的检索分和 body
            recipe = RecipeRecord(
                recipe_id=stub_match.recipe_id,
                title=stub_match.title,
                cuisine=stub_match.cuisine,
                tags=list(stub_match.tags),
                difficulty=stub_match.difficulty,
                estimated_time_min=stub_match.estimated_time_min,
                servings=stub_match.servings,
                core_ingredients=list(stub_match.core_ingredients),
                seasonings=list(stub_match.seasonings),
                optional_ingredients=list(stub_match.optional_ingredients),
                equipment=list(stub_match.equipment),
                allergens=list(stub_match.allergens),
                body=full_body or stub_match.body,
                retrieval_score=min(1.0, group["max_similarity"]),
            )
        else:
            # 无结构化数据：从 chunk 内容尽力提取
            ingredients = _extract_ingredients_from_chunk(full_body)
            recipe = RecipeRecord(
                recipe_id=doc_name.rsplit('.', 1)[0] if '.' in doc_name else doc_name,
                title=title,
                cuisine="家常菜",
                tags=[],
                difficulty="中等",
                estimated_time_min=30,
                servings=2,
                core_ingredients=ingredients[:8],  # 前8个食材作为核心食材（粗略）
                seasonings=[],
                optional_ingredients=[],
                equipment=[],
                allergens=[],
                body=full_body,
                retrieval_score=min(1.0, group["max_similarity"]),
            )

        recipes.append(recipe)

    return recipes


# ============================================================
# RAGFlow Retriever
# ============================================================

class RAGFlowRetriever(BaseRetriever):
    """
    通过 RAGFlow REST API 做向量检索。

    配置（config.py）:
        RAGFLOW_HOST = "http://127.0.0.1:9380"
        RAGFLOW_API_KEY = "ragflow-xxx..."
        RAGFLOW_KB_NAME = "recipe"
        RETRIEVAL_BACKEND = "ragflow"
    """

    def __init__(self,
                 host: str | None = None,
                 api_key: str | None = None,
                 kb_name: str | None = None):
        self.host = (host or getattr(config, 'RAGFLOW_HOST', '')).rstrip('/')
        self.api_key = api_key or getattr(config, 'RAGFLOW_API_KEY', '')
        self.kb_name = kb_name or getattr(config, 'RAGFLOW_KB_NAME', 'recipe')
        self._stub = RetrievalStub()
        self._dataset_id: str | None = None

    # ── 内部方法 ──────────────────────────────────────────

    @property
    def _available(self) -> bool:
        return bool(self.host and self.api_key)

    def _api(self, method: str, path: str, body: dict | None = None) -> dict | None:
        """发送 RAGFlow API 请求"""
        url = f"{self.host}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = json.dumps(body).encode('utf-8') if body else None

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            body_text = e.read().decode('utf-8', errors='replace')[:200] if e.fp else ''
            print(f"[RAGFlow] HTTP {e.code} on {method} {path}: {body_text}")
            return None
        except urllib.error.URLError as e:
            print(f"[RAGFlow] 连接失败 {method} {path}: {e.reason}")
            return None
        except Exception as e:
            print(f"[RAGFlow] 异常 {method} {path}: {e}")
            return None

    def _get_dataset_id(self) -> str | None:
        """懒加载：根据知识库名称查找 dataset_id"""
        if self._dataset_id is not None:
            return self._dataset_id

        result = self._api("GET", "/api/v1/datasets")
        if result and result.get("code") == 0:
            for ds in result.get("data", []):
                if ds.get("name") == self.kb_name:
                    self._dataset_id = ds["id"]
                    print(f"[RAGFlow] 知识库 '{self.kb_name}' → id={self._dataset_id[:16]}...")
                    return self._dataset_id

        print(f"[RAGFlow] ⚠ 未找到知识库 '{self.kb_name}'")
        self._dataset_id = ""
        return None

    def _retrieve(self, query: str, top_n: int) -> List[dict]:
        """调用 RAGFlow 检索"""
        ds_id = self._get_dataset_id()
        if not ds_id:
            return []

        body = {
            "question": query,
            "dataset_ids": [ds_id],
            "page": 1,
            "page_size": max(top_n, 10),
            "similarity_threshold": 0.1,
            "vector_similarity_weight": 0.5,
        }
        result = self._api("POST", "/api/v1/retrieval", body)
        if result and result.get("code") == 0:
            return result.get("data", {}).get("chunks", [])
        return []

    # ── BaseRetriever 接口 ────────────────────────────────

    def search_ids(self, ingredients: List[str], top_n: int = 10) -> List[tuple[str, float]]:
        """
        返回 [(recipe_id, score), ...]，不解析完整 RecipeRecord。
        recipe_id = document_keyword 去掉后缀。
        同时缓存 chunk content，供 get_full_text() 使用。
        """
        if not self._available:
            return self._stub.search_ids(ingredients, top_n)

        query = " ".join(ingredients)
        try:
            chunks = self._retrieve(query, top_n)
        except Exception as e:
            print(f"[RAGFlow] 检索异常: {e}，降级到 stub")
            return self._stub.search_ids(ingredients, top_n)

        if not chunks:
            print(f"[RAGFlow] 无结果，降级到 stub")
            return self._stub.search_ids(ingredients, top_n)

        # 按文档分组，取最高相似度，同时缓存 content
        doc_scores: dict[str, float] = {}
        if not hasattr(self, '_content_cache'):
            self._content_cache: dict[str, str] = {}
        for chunk in chunks:
            doc_key = chunk.get("document_keyword", chunk.get("docnm_kwd", ""))
            if not doc_key:
                continue
            # 去掉文件后缀（.md / .txt / 无后缀均可）
            rid = doc_key.rsplit(".", 1)[0] if "." in doc_key else doc_key
            rid = rid.strip()
            if not rid:
                continue
            sim = chunk.get("similarity", chunk.get("vector_similarity", 0.0))
            doc_scores[rid] = max(doc_scores.get(rid, 0.0), float(sim))
            # 缓存 content（一个食谱一个块，content 即全文）
            content = chunk.get("content", "")
            if content and rid not in self._content_cache:
                self._content_cache[rid] = content

        result = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        print(f"[RAGFlow] '{query}' → {len(result)} 个文档: "
              f"{[(r[0], round(r[1], 2)) for r in result[:5]]}")
        return result[:top_n]

    def search(self, ingredients: List[str], top_n: int = 10) -> List[RecipeRecord]:
        if not self._available:
            return self._stub.search(ingredients, top_n)

        query = " ".join(ingredients)
        try:
            chunks = self._retrieve(query, top_n)
        except Exception as e:
            print(f"[RAGFlow] 检索异常: {e}，降级到 stub")
            return self._stub.search(ingredients, top_n)

        if not chunks:
            print(f"[RAGFlow] 无结果，降级到 stub")
            return self._stub.search(ingredients, top_n)

        # chunks → RecipeRecord 列表
        recipes = _chunks_to_recipes(chunks)

        if not recipes:
            return self._stub.search(ingredients, top_n)

        # 按检索分降序
        recipes.sort(key=lambda r: r.retrieval_score, reverse=True)
        result = recipes[:top_n]

        print(f"[RAGFlow] '{query}' → {len(result)} 道菜: "
              f"{[(r.title, round(r.retrieval_score, 2)) for r in result[:5]]}")
        return result

    def get_full_text(self, recipe_id: str) -> str | None:
        """从 RAGFlow 获取菜谱全文（优先 search_ids 缓存，兜底检索拼接）"""
        # 缓存命中（一个食谱一个块，content 即全文）
        cache = getattr(self, '_content_cache', {})
        if recipe_id in cache:
            return cache[recipe_id]

        # 兜底：检索拼接
        chunks = self._retrieve(recipe_id, top_n=30)
        if not chunks:
            return None
        return "\n".join(c.get("content", "") for c in chunks if c.get("content"))

    def get_by_id(self, recipe_id: str) -> Optional[RecipeRecord]:
        if not self._available:
            return self._stub.get_by_id(recipe_id)

        # 先用 stub 查
        result = self._stub.get_by_id(recipe_id)
        if result:
            return result

        # 用 recipe_id 做检索
        chunks = self._retrieve(recipe_id, top_n=5)
        if chunks:
            recipes = _chunks_to_recipes(chunks)
            for r in recipes:
                if r.recipe_id == recipe_id or r.title == recipe_id:
                    return r
        return None
