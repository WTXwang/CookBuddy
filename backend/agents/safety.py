"""FoodSafetyReviewer Agent —— 食品安全审查"""

import asyncio
from typing import List, Optional
from schemas import SafetyReport, Recommendation
from llm_client import create_chat_llm, chat_json_guarded
from rules.normalizer import classify_ingredient
import config


SAFETY_SYSTEM_PROMPT = """你是一位食品安全专家。

任务：审查推荐菜谱的安全性，检测过敏原、忌口、生熟交叉污染等问题。

输出 JSON：
```json
{
  "passed": true,
  "severity": "warning",
  "issues": ["鸡蛋应充分加热至凝固"],
  "revision_suggestions": []
}
```

审查要点：
- 过敏原冲突 → severity="blocked", passed=false
- 忌口冲突 → severity="blocked", passed=false
- 生肉/蛋/海鲜需充分加热提醒 → severity="warning", passed=true
- 高风险人群（孕妇、婴幼儿）通用提示
- 不提供疾病治疗或医学营养建议
"""

SAFETY_USER_PROMPT = """请审查以下推荐菜谱的安全性：

菜名: {title}
使用食材: {used_ingredients}
缺失核心食材: {missing_core}
缺失可选食材: {missing_optional}
步骤: {steps}

用户过敏原: {allergens}
用户忌口: {excluded}

检查是否有过敏原冲突、忌口冲突，以及必要的加热/安全提醒。"""


# 规则兜底：风险食材表
RISK_INGREDIENTS = {
    "鸡蛋": "鸡蛋应充分加热至凝固，避免沙门氏菌风险",
    "鸡胸肉": "鸡肉务必炒至完全变白熟透，中心温度达到74°C",
    "鸡腿": "鸡肉务必炒至完全变白熟透",
    "猪肉": "猪肉应充分加热至无粉红色",
    "牛肉": "牛肉如非全熟需注明食用风险",
    "牛腩": "牛腩需炖煮至软烂，确保内部熟透",
    "虾": "虾应加热至完全变红、肉质不透明",
    "鱼": "鱼应加热至鱼肉不透明、易剥落",
}


class FoodSafetyReviewer:
    """食品安全审查"""

    def __init__(self, model: str = ""):
        self.model = model or config.SAFETY_MODEL
        self.llm = create_chat_llm(self.model)

    async def review(self,
               recommendation: Recommendation,
               user_allergens: List[str],
               user_excluded: List[str]) -> SafetyReport:
        """审查一道推荐菜的安全性"""
        # 先用规则做硬检查（不可跳过）
        rule_report = self._rule_review(recommendation, user_allergens, user_excluded)
        if rule_report.severity == "blocked":
            return rule_report

        # LLM 增强审查
        if self.llm is not None:
            try:
                llm_report = await self._llm_review(recommendation, user_allergens, user_excluded)
                if llm_report:
                    all_issues = list(set(rule_report.issues + llm_report.issues))
                    all_suggestions = list(set(rule_report.revision_suggestions + llm_report.revision_suggestions))
                    return SafetyReport(
                        passed=rule_report.passed and llm_report.passed,
                        severity="blocked" if not llm_report.passed else rule_report.severity,
                        issues=all_issues,
                        revision_suggestions=all_suggestions,
                    )
            except Exception as e:
                print(f"[Safety LLM Error] {e}")

        return rule_report

    def _rule_review(self, rec, user_allergens, user_excluded) -> SafetyReport:
        """规则硬检查"""
        issues = []
        suggestions = []
        all_ings = set(rec.used_ingredients + rec.missing_core + rec.missing_optional)

        # 过敏原
        for allergen in user_allergens:
            if allergen in all_ings:
                issues.append(f"过敏原冲突：含{allergen}")
            for step in rec.steps:
                if allergen in step:
                    issues.append(f"步骤中含过敏原：{allergen}")

        # 忌口（分类感知：忌口牛肉 → 匹配牛腩/牛腱等子类食材）
        for ex in user_excluded:
            ex_category = classify_ingredient(ex)
            for ing in all_ings:
                if ing == ex or classify_ingredient(ing) == ex_category:
                    issues.append(f"忌口冲突：含{ex}（{ing}）")
                    break

        # 生食风险
        for ing in rec.used_ingredients:
            if ing in RISK_INGREDIENTS:
                issues.append(RISK_INGREDIENTS[ing])

        has_blocked = any("过敏原" in i or "忌口" in i for i in issues)
        return SafetyReport(
            passed=not has_blocked,
            severity="blocked" if has_blocked else ("warning" if issues else "none"),
            issues=issues,
            revision_suggestions=suggestions,
        )

    async def _llm_review(self, rec, user_allergens, user_excluded) -> Optional[SafetyReport]:
        """LLM 增强审查"""
        prompt = SAFETY_USER_PROMPT.format(
            title=rec.title,
            used_ingredients=", ".join(rec.used_ingredients),
            missing_core=", ".join(rec.missing_core),
            missing_optional=", ".join(rec.missing_optional),
            steps="\n".join(f"{i+1}. {s}" for i, s in enumerate(rec.steps)),
            allergens=", ".join(user_allergens) if user_allergens else "无",
            excluded=", ".join(user_excluded) if user_excluded else "无",
        )
        result = await asyncio.to_thread(
            chat_json_guarded, prompt, system=SAFETY_SYSTEM_PROMPT, model=self.model
        )
        if result:
            return SafetyReport(
                passed=result.get("passed", True),
                severity=result.get("severity", "none"),
                issues=result.get("issues", []),
                revision_suggestions=result.get("revision_suggestions", []),
            )
        return None
