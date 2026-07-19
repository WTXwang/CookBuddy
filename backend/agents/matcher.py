"""RecipeMatcher Agent —— 候选菜谱语义匹配"""

import json
from typing import List
from langchain_core.language_models import BaseChatModel
from schemas import RecipeRecord, CandidateFeature
from rules.scorer import build_feature
from llm_client import create_chat_llm, chat_json
import config


MATCHER_SYSTEM_PROMPT = """你是一位资深厨师和食材搭配专家。

你的任务：
1. 分析候选菜谱与用户食材的匹配情况
2. 判断每道菜的核心食材覆盖、可选食材缺失
3. 评估口味、时间、难度等偏好约束的符合度
4. 检测过敏原与忌口的硬冲突

输出严格的 JSON 数组：
```json
[
  {
    "recipe_id": "R001",
    "core_ingredients_analysis": {
      "matched": ["番茄", "鸡蛋"],
      "missing": [],
      "can_substitute": []
    },
    "optional_ingredients_analysis": {
      "matched": [],
      "missing": ["葱"],
      "can_omit": ["葱"]
    },
    "flavor_match": 1.0,
    "time_match": 1.0,
    "difficulty_match": 1.0,
    "allergen_conflicts": [],
    "excluded_conflicts": [],
    "notes": "核心食材齐全，完全可以制作"
  }
]
```

规则：
- 不得把核心食材降级为可选食材
- 过敏原冲突、忌口冲突必须明确列出
- 各项 match 值为 0~1
"""

MATCHER_RULE_PROMPT = """基于以下信息，判断每道候选菜谱与用户需求的匹配度。

用户食材: {ingredients}
过敏原: {allergens}
忌口: {excluded}
口味偏好: {flavor}
时间限制: {time_limit}分钟
难度要求: {difficulty}
厨具: {equipment}

候选菜谱:
{candidates_json}

请严格按 JSON 格式输出匹配分析。"""


class RecipeMatcher:
    """基于 LLM 的菜谱匹配器"""

    def __init__(self, model: str = ""):
        self.model = model or config.MATCHER_MODEL
        self.llm = create_chat_llm(self.model)

    async def analyze(self,
                      candidates: List[RecipeRecord],
                      user_ingredients: List[str],
                      user_allergens: List[str],
                      user_excluded: List[str],
                      user_flavor: str,
                      user_time_limit: int,
                      user_equipment: List[str],
                      ) -> List[CandidateFeature]:
        """分析候选菜谱"""
        # LLM 模式
        if self.llm is not None:
            try:
                return await self._llm_analyze(
                    candidates, user_ingredients, user_allergens,
                    user_excluded, user_flavor, user_time_limit, user_equipment
                )
            except Exception as e:
                print(f"[Matcher LLM Error] {e}, 降级为规则模式")

        # 规则兜底
        return self._rule_analyze(
            candidates, user_ingredients, user_allergens,
            user_excluded, user_flavor, user_time_limit, user_equipment
        )

    def _rule_analyze(self, candidates, user_ingredients, user_allergens,
                      user_excluded, user_flavor, user_time_limit, user_equipment):
        """纯规则兜底"""
        return [
            build_feature(c, user_ingredients, user_allergens,
                          user_excluded, user_flavor, user_time_limit, user_equipment)
            for c in candidates
        ]

    async def _llm_analyze(self, candidates, user_ingredients, user_allergens,
                           user_excluded, user_flavor, user_time_limit, user_equipment):
        """LLM 语义分析"""
        candidate_summaries = []
        for c in candidates:
            candidate_summaries.append({
                "recipe_id": c.recipe_id,
                "title": c.title,
                "core_ingredients": c.core_ingredients,
                "optional_ingredients": c.optional_ingredients,
                "tags": c.tags,
                "difficulty": c.difficulty,
                "estimated_time_min": c.estimated_time_min,
                "equipment": c.equipment,
                "allergens": c.allergens,
            })

        prompt = MATCHER_RULE_PROMPT.format(
            ingredients=json.dumps(user_ingredients, ensure_ascii=False),
            allergens=json.dumps(user_allergens, ensure_ascii=False),
            excluded=json.dumps(user_excluded, ensure_ascii=False),
            flavor=user_flavor or "不限",
            time_limit=user_time_limit,
            difficulty=user_flavor or "不限",
            equipment=json.dumps(user_equipment, ensure_ascii=False),
            candidates_json=json.dumps(candidate_summaries, ensure_ascii=False, indent=2),
        )

        llm_result = chat_json(prompt, system=MATCHER_SYSTEM_PROMPT, model=self.model)

        features = []
        for c in candidates:
            feat = build_feature(c, user_ingredients, user_allergens,
                                 user_excluded, user_flavor,
                                 user_time_limit, user_equipment)

            if llm_result:
                llm_item = next(
                    (item for item in llm_result if item.get("recipe_id") == c.recipe_id),
                    None
                )
                if llm_item:
                    # 用 LLM 的偏好分数覆盖
                    pref = float(llm_item.get("flavor_match", llm_item.get("preference_match", feat.preference_score)))
                    tfit = float(llm_item.get("time_match", feat.time_fit))
                    feat.preference_score = pref
                    feat.time_fit = tfit
                    feat.difficulty_fit = float(llm_item.get("difficulty_match", 1.0))

                    # LLM 检测到的额外冲突
                    conflicts = (llm_item.get("allergen_conflicts", []) +
                                 llm_item.get("excluded_conflicts", []))
                    if conflicts:
                        feat.blocked = True
                        for reason in conflicts:
                            if reason not in feat.block_reasons:
                                feat.block_reasons.append(reason)

            features.append(feat)

        return features
