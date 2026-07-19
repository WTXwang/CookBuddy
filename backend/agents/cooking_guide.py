"""CookingGuide Agent —— 做法整理与适配"""

from schemas import RecipeRecord, CandidateFeature
from llm_client import create_chat_llm, chat_json
import config


GUIDE_SYSTEM_PROMPT = """你是一位经验丰富的家庭烹饪教练。

任务：基于菜谱信息，生成清晰可执行的烹饪指导。

输出 JSON：
```json
{
  "prep": ["准备工作1", "准备工作2"],
  "steps": ["步骤1", "步骤2", "..."],
  "heat_tips": "火候与成熟判断关键提示",
  "substitutions": ["替代建议"]
}
```

规则：
- 步骤编号清晰，每步一个操作
- 火候提示要具体（中大火/小火、时间判断、成熟标志）
- 不虚构用户没有的食材
- 不改变知识库的核心烹饪逻辑
"""

GUIDE_USER_PROMPT = """请为以下菜谱生成烹饪指导。

菜名: {title}
菜系: {cuisine}
难度: {difficulty}
预计时间: {time_min}分钟
人数: {servings}人

核心食材: {core_ingredients}
调料: {seasonings}
厨具: {equipment}

用户缺失核心食材: {missing_core}
用户缺失可选食材: {missing_optional}

菜谱正文:
{body}

请生成结构化的准备工作和烹饪步骤。"""


class CookingGuide:
    """做法整理 Agent"""

    def __init__(self, model: str = ""):
        self.model = model or config.GUIDE_MODEL
        self.llm = create_chat_llm(self.model)

    def generate(self, recipe: RecipeRecord, feature: CandidateFeature) -> dict:
        """为一首菜生成结构化做法"""
        # 如果有菜谱正文，尝试用 LLM 重写
        if self.llm is not None and recipe.body:
            try:
                return self._llm_generate(recipe, feature)
            except Exception as e:
                print(f"[Guide LLM Error] {e}, 降级为规则解析")

        if recipe.body:
            return self._parse_body(recipe, feature)
        elif self.llm is not None:
            try:
                return self._llm_generate(recipe, feature)
            except Exception:
                pass

        return self._generate_default(recipe, feature)

    def _llm_generate(self, recipe: RecipeRecord, feature: CandidateFeature) -> dict:
        """LLM 生成烹饪指导"""
        prompt = GUIDE_USER_PROMPT.format(
            title=recipe.title,
            cuisine=recipe.cuisine,
            difficulty=recipe.difficulty,
            time_min=recipe.estimated_time_min,
            servings=recipe.servings,
            core_ingredients=", ".join(recipe.core_ingredients),
            seasonings=", ".join(recipe.seasonings),
            equipment=", ".join(recipe.equipment),
            missing_core=", ".join(feature.missing_core) if feature.missing_core else "无",
            missing_optional=", ".join(feature.missing_optional) if feature.missing_optional else "无",
            body=recipe.body or "(无菜谱正文，请根据菜名和食材推断标准做法)",
        )
        result = chat_json(prompt, system=GUIDE_SYSTEM_PROMPT, model=self.model)
        if result:
            return {
                "prep": result.get("prep", []),
                "steps": result.get("steps", []),
                "heat_tips": result.get("heat_tips", ""),
                "substitutions": result.get("substitutions", []),
            }
        raise ValueError("LLM 返回为空")

    def _parse_body(self, recipe, feature) -> dict:
        """解析知识库正文"""
        body = recipe.body
        lines = body.strip().split("\n")
        prep, steps, heat_tips = [], [], ""
        section = "prep"
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("## 准备") or line.startswith("### 准备"):
                section = "prep"; continue
            elif line.startswith("## 步骤") or line.startswith("### 步骤"):
                section = "steps"; continue
            elif line.startswith("## 火候") or line.startswith("### 火候"):
                section = "heat"; continue
            if section == "prep":
                prep.append(line.lstrip("- "))
            elif section == "steps":
                steps.append(line.lstrip("0123456789. "))
            elif section == "heat":
                heat_tips += line + " "
        return {"prep": prep, "steps": steps, "heat_tips": heat_tips.strip(), "substitutions": []}

    def _generate_default(self, recipe, feature) -> dict:
        """无正文且无 LLM 时的兜底"""
        core = ", ".join(recipe.core_ingredients)
        return {
            "prep": [f"{ing}洗净切好" for ing in recipe.core_ingredients],
            "steps": ["热锅倒油", f"放入{core}翻炒", "加盐等调料调味", "翻炒均匀至熟，出锅"],
            "heat_tips": "中火烹饪，注意火候控制",
            "substitutions": [],
        }
