"""菜谱结构化提取器 —— LLM 从 markdown 全文提取元数据

独立模块，通过 RecipeMetaStore 构造函数注入使用:
    meta = RecipeMetaStore(db_path="...", llm_extractor=llm_extract_recipe)
"""

import json
import re
from typing import Optional


EXTRACT_SYSTEM_PROMPT = """你是一个菜谱数据提取器。你的唯一任务是：从给定的菜谱全文（markdown 格式）中提取结构化信息，输出严格的 JSON。

规则：
1. 只输出 JSON，不要任何解释、markdown 包裹或额外文本
2. core_ingredients: 做这道菜必须有的主要食材（不包括调料）
3. seasonings: 调料、香料、调味品
4. optional_ingredients: 可选/可替代的食材
5. equipment: 所需厨具
6. allergens: 过敏原（鸡蛋、牛奶、花生、海鲜、坚果等）
7. difficulty: "简单" | "中等" | "困难"
8. estimated_time_min: 预估时间（分钟），整数
9. 所有列表字段如果无法确定，返回空数组 []
10. 字段值如果无法确定，使用合理的默认值

输出 JSON 格式:
{
  "title": "菜名",
  "cuisine": "菜系",
  "tags": ["标签1", "标签2"],
  "difficulty": "简单|中等|困难",
  "estimated_time_min": 30,
  "servings": 2,
  "core_ingredients": ["食材1", "食材2"],
  "seasonings": ["调料1", "调料2"],
  "optional_ingredients": ["可选食材1"],
  "equipment": ["厨具1"],
  "allergens": ["过敏原1"]
}
"""

EXTRACT_USER_PROMPT = """请从以下菜谱全文提取结构化信息：

{text}"""


def llm_extract_recipe(text: str, model: str | None = None) -> dict | None:
    """
    从菜谱 markdown 全文提取结构化元数据。

    Args:
        text: 菜谱 markdown 全文
        model: LLM 模型名，默认用 config.EXTRACTOR_MODEL

    Returns:
        符合 RecipeMetaStore._meta_to_record() 格式的 dict，失败返回 None
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # ── 尝试调 LLM ──
    llm_result = _call_llm(text, model)
    if llm_result:
        return _validate_and_fix(llm_result, text)

    # ── LLM 不可用时的规则兜底 ──
    return _rule_fallback(text)


def _call_llm(text: str, model: str | None = None) -> dict | None:
    """调 LLM 提取。优先用 llm_client，不可用时直接用 urllib 调 SiliconFlow"""
    import config

    m = model or getattr(config, 'EXTRACTOR_MODEL', None)
    if not m:
        m = getattr(config, 'MATCHER_MODEL', 'Qwen/Qwen2.5-7B-Instruct')

    prompt = EXTRACT_USER_PROMPT.format(text=text[:8000])

    # 方式1: llm_client（需要 langchain_core）
    try:
        from llm_client import chat_json
        result = chat_json(prompt, system=EXTRACT_SYSTEM_PROMPT, model=m)
        if isinstance(result, dict):
            return result
    except ImportError:
        pass
    except Exception as e:
        print(f"[Extractor] llm_client 失败: {e}")

    # 方式2: 直接用 urllib 调 SiliconFlow API（零额外依赖）
    try:
        return _call_siliconflow(prompt, m)
    except Exception as e:
        print(f"[Extractor] SiliconFlow 直调失败: {e}")
        return None


def _call_siliconflow(prompt: str, model: str) -> dict | None:
    """用 urllib 直接调 SiliconFlow OpenAI 兼容 API"""
    import json
    import urllib.request
    import urllib.error
    import config

    api_key = getattr(config, 'SILICONFLOW_API_KEY', '')
    base_url = getattr(config, 'SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')

    if not api_key:
        print("[Extractor] 未配置 SILICONFLOW_API_KEY")
        return None

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }).encode('utf-8')

    url = f"{base_url}/chat/completions"
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            content = data["choices"][0]["message"]["content"]
            return _parse_json(content)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:300]
        print(f"[Extractor] HTTP {e.code}: {body}")
        return None


def _parse_json(raw: str) -> dict | None:
    """解析 LLM 返回的 JSON，处理常见格式问题"""
    # print(raw)
    import re

    # 尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取 { ... } 最外层
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    print(f"[Extractor] JSON 解析失败，原始内容前200字: {raw[:200]}")
    return None


def _validate_and_fix(data: dict, full_text: str) -> dict | None:
    """校验并修复 LLM 输出"""
    if not isinstance(data, dict):
        return None

    # 确保必填字段存在
    result = {
        "title": str(data.get("title", "")).strip(),
        "cuisine": str(data.get("cuisine", "家常菜")).strip(),
        "tags": _ensure_list(data.get("tags")),
        "difficulty": _normalize_difficulty(data.get("difficulty", "中等")),
        "estimated_time_min": _ensure_int(data.get("estimated_time_min"), 30),
        "servings": _ensure_int(data.get("servings"), 2),
        "core_ingredients": _ensure_list(data.get("core_ingredients")),
        "seasonings": _ensure_list(data.get("seasonings")),
        "optional_ingredients": _ensure_list(data.get("optional_ingredients")),
        "equipment": _ensure_list(data.get("equipment")),
        "allergens": _ensure_list(data.get("allergens")),
    }

    if not result["title"]:
        result["title"] = _extract_title_from_text(full_text)

    return result


def _rule_fallback(text: str) -> dict | None:
    """纯规则兜底（无 LLM 时）"""
    title = _extract_title_from_text(text)

    # 从正文提取食材行（- XXX 格式）
    ingredients = []
    for m in re.finditer(r'^[-*]\s+(.+?)(?:\s+\d|$)', text, re.MULTILINE):
        name = m.group(1).strip()
        name = re.sub(r'[（(].*?[）)]', '', name).strip()
        if name and len(name) < 30 and not name.startswith('#'):
            ingredients.append(name)

    return {
        "title": title,
        "cuisine": "家常菜",
        "tags": [],
        "difficulty": "中等",
        "estimated_time_min": 30,
        "servings": 2,
        "core_ingredients": ingredients[:8] if ingredients else [],
        "seasonings": [],
        "optional_ingredients": [],
        "equipment": [],
        "allergens": [],
    }


def _extract_title_from_text(text: str) -> str:
    m = re.search(r'^#\s+(.+?)(?:的做法|$)', text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(r'^#\s+(.+)', text, re.MULTILINE)
    return m.group(1).strip() if m else "未知菜谱"


def _ensure_list(val) -> list:
    if isinstance(val, list):
        return [str(v).strip() for v in val if v]
    if isinstance(val, str) and val:
        return [v.strip() for v in val.split(',') if v.strip()]
    return []


def _ensure_int(val, default: int) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _normalize_difficulty(val) -> str:
    v = str(val).strip()
    if "简单" in v or "easy" in v.lower():
        return "简单"
    if "困难" in v or "hard" in v.lower():
        return "困难"
    return "中等"
