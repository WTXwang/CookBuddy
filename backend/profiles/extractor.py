"""LLM 画像微调 —— 异步后台，从对话中提取画像变更"""

import asyncio
import json
from typing import Optional

from llm_client import chat_json
import config


SYSTEM_PROMPT = """你是用户画像维护助手。根据用户当前的对话，判断是否需要微调其饮食画像。

核心原则：**只做微小、有根据的调整，不猜测，不臆断。**

规则：
1. 只在用户**明确表达**时才 ADD（如「我花生过敏」→ 过敏原加"花生"）
2. 只在用户**明确纠正**时才 REMOVE（如「我现在能吃辣了」→ 忌口删"辣"）
3. 没有提到的字段，不要改动
4. 不要因为推荐结果去改画像，只根据用户说的话
5. 不确定时，返回空变更（changes: []）

口味只能从以下选择：辣、不辣、酸甜、清淡、重口味、咸香、麻、蒜香、酱香、酸辣
厨具只能从以下选择：炒锅、蒸锅、烤箱、汤锅、空气炸锅、微波炉、电饭煲、压力锅、平底锅、炖锅
难度只能从以下选择：任意、简单、中等、困难
过敏原/忌口每项不超过 10 个字。

返回 JSON：
{
  "reasoning": "简要说明推理过程（不超过 30 字）",
  "changes": [
    {"field": "allergens", "action": "add", "value": "花生"},
    {"field": "excluded_ingredients", "action": "remove", "value": "香菜"},
    {"field": "flavor", "action": "add", "value": "清淡"},
    {"field": "equipment", "action": "add", "value": "烤箱"},
    {"field": "difficulty", "action": "set", "value": "简单"}
  ]
}
field 可选值：flavor, difficulty, allergens, excluded_ingredients, equipment
action 可选值：add, remove, set
"""


def _build_prompt(profile_json: str, user_input: str, conversation_context: str) -> str:
    return f"""当前画像：
{profile_json}

用户本轮说的话：
{user_input}

对话上下文：
{conversation_context or "（无）"}

请判断是否需要微调画像，返回 JSON。"""


async def extract_profile_changes(
    profile_json: str,
    user_input: str,
    conversation_context: str = "",
) -> list[dict]:
    """
    调用 LLM 分析对话，返回画像变更列表。

    Returns:
        [{"field": "allergens", "action": "add", "value": "花生"}, ...]
        失败或无需变更时返回空列表
    """
    try:
        result = await asyncio.to_thread(
            chat_json,
            prompt=_build_prompt(profile_json, user_input, conversation_context),
            system=SYSTEM_PROMPT,
            model=config.EXTRACTOR_MODEL,
        )
    except Exception:
        return []

    if not result:
        return []

    changes = result.get("changes", [])
    if not isinstance(changes, list):
        return []

    # 基本校验：每条变更必须有 field, action, value
    valid = []
    for c in changes:
        if not isinstance(c, dict):
            continue
        field = c.get("field", "")
        action = c.get("action", "")
        value = c.get("value", "")
        if field in ("flavor", "difficulty", "allergens", "excluded_ingredients", "equipment") \
           and action in ("add", "remove", "set") \
           and value:
            valid.append({"field": field, "action": action, "value": str(value)})

    return valid


def apply_changes(profile, changes: list[dict]) -> bool:
    """
    将变更应用到画像对象上（原地修改）。

    Returns:
        True 如果有任何变更被应用
    """
    from profiles.store import ProfileStore as _Store

    updated = False

    for c in changes:
        field = c["field"]
        action = c["action"]
        value = c["value"]

        if field == "flavor":
            current = list(profile.preferences.flavor)
            if action == "add" and value not in current:
                current.append(value)
                profile.preferences.flavor = _Store._validate_flavor(current)
                updated = True
            elif action == "remove" and value in current:
                current.remove(value)
                profile.preferences.flavor = _Store._validate_flavor(current)
                updated = True
            elif action == "set":
                profile.preferences.flavor = _Store._validate_flavor([value])
                updated = True

        elif field == "difficulty":
            if action in ("set", "add"):
                from profiles.store import VALID_DIFFICULTY
                if value in VALID_DIFFICULTY:
                    profile.preferences.difficulty = value
                    updated = True

        elif field == "allergens":
            current = list(profile.allergens)
            if action == "add" and value not in current:
                current.append(value)
                profile.allergens = _Store._validate_items(current, 15)
                updated = True
            elif action == "remove" and value in current:
                current.remove(value)
                profile.allergens = current
                updated = True

        elif field == "excluded_ingredients":
            current = list(profile.excluded_ingredients)
            if action == "add" and value not in current:
                current.append(value)
                profile.excluded_ingredients = _Store._validate_items(current, 20)
                updated = True
            elif action == "remove" and value in current:
                current.remove(value)
                profile.excluded_ingredients = current
                updated = True

        elif field == "equipment":
            current = list(profile.equipment)
            if action == "add" and value not in current:
                current.append(value)
                profile.equipment = _Store._validate_equipment(current)
                updated = True
            elif action == "remove" and value in current:
                current.remove(value)
                profile.equipment = current
                updated = True

    return updated
