"""自然语言解析器 —— 将用户输入 + 按钮约束合并，LLM 提取为 UserRequest"""

import asyncio
import json
from schemas import UserRequest
from llm_client import chat_json_guarded
import config


PARSER_SYSTEM_PROMPT = """你是一个敏锐的厨房助手输入解析器。用户不会总是规规矩矩地列食材——他们可能随口抱怨、分享心情、描述场景。你需要穿透字面意思，识别其真实的需求和限制。

你的任务：从用户输入中提取 8 类信息，输出严格 JSON。

输出格式：
```json
{
  "ingredients": ["鸡蛋", "番茄"],
  "excluded": [],
  "allergens": [],
  "equipment": ["炒锅"],
  "servings": 2,
  "difficulty": "简单",
  "time_limit_min": 20,
  "flavor": "不辣"
}
```

═══════════════════════════════════
字段提取规则
═══════════════════════════════════

【ingredients — 食材】
- 直接提取提到的食材名称："鸡蛋、番茄、土豆" → ["鸡蛋", "番茄", "土豆"]
- 能拆就拆："鸡蛋和番茄" → ["鸡蛋", "番茄"]
- "冰箱里只有XX了"、"家里还有XX" → 提取XX作为食材
- 不要包含数量词（两个、半个、200g、一斤）
- 调料类（盐、酱油、醋）不要放入，它们由系统自动补充
- 如果用户说了具体菜名（如"我想吃番茄炒蛋"），把相关食材拆出来：["番茄", "鸡蛋"]

【excluded — 忌口 / 不吃的】
- 直接表达："不吃猪肉" → ["猪肉"]
- 间接表达（推断）：
  - "最近在减肥" → ["油炸食品", "肥肉", "高热量"]
  - "吃素" → ["肉", "海鲜", "蛋", "奶"]
  - "清真" → ["猪肉"]
  - "最近肠胃不好" → ["辛辣", "生冷"]
  - "上火"、"长痘" → ["辛辣", "油炸"]
  - "孩子不吃XX" → 视为用户不吃XX（代孩子忌口）

【allergens — 过敏原】
- 直接表达："花生过敏" → ["花生"]
- "对XX过敏" → 提取XX
- "吃XX会过敏/起疹子/拉肚子" → 提取XX

【equipment — 厨具】
- 直接表达："只有炒锅" → ["炒锅"]
- "有烤箱" → ["烤箱"]
- "宿舍只有电饭煲" → ["电饭煲"]
- "什么都没有/啥厨具都没有" → []
- 未提则默认 []（表示不限制）

【servings — 人数】
- 直接表达："两个人"、"两人份" → 2
- 间接表达（推断）：
  - "一个人"、"自己吃" → 1
  - "家里来客人了" → 4
  - "一家人"、"全家" → 4
  - "一个人随便吃点" → 1
  - "女朋友/男朋友来" → 2
  - "几个朋友来" → 4
- 未提则默认 2

【difficulty — 难度】
- "简单"：简单、随便、快手、懒人、新手、好做
- "中等"：正常做、家常
- "困难"：复杂、大菜、硬菜、有挑战
- 推断：
  - "第一次下厨"、"不太会做饭"、"手残" → "简单"
  - "想挑战一下"、"做个大菜"、"硬菜" → "困难"
  - "随便弄弄"、"糊弄一顿" → "简单"
- 未提则默认"任意"

【time_limit_min — 时间限制（分钟）】
- 直接表达："20分钟"、"半小时" → 30, "1小时" → 60
- 间接表达（推断）：
  - "下班晚了想快点" → 20
  - "马上要吃"、"赶时间"、"急" → 15
  - "周末慢慢做"、"不赶时间"、"有空" → 120
  - "快手菜" → 20
  - "随便对付一口" → 15
- 所有数字必须转换为纯数字，如"半小时"→30, "一个半小时"→90
- 未提则默认 30

【flavor — 口味偏好】
- 直接表达："不辣"、"清淡"、"重口味"、"酸甜"、"麻辣"
- 间接表达（推断）：
  - "天冷"、"冬天"、"暖暖的" → "热乎的"
  - "夏天"、"热死了"、"不想开火" → "清爽"
  - "没什么胃口" → "开胃"
  - "下饭"、"下酒" → "重口味"
  - "减肥"、"轻食" → "低脂"
  - "宿醉"、"喝完酒"、"醒酒" → "解酒暖胃"
  - "孩子吃"、"老人吃" → "清淡易消化"
  - "来客人了" → "丰盛"
  - "想喝汤" → "汤类"
- 未提则默认""

═══════════════════════════════════
多轮对话：利用 [先前对话] 理解上下文
═══════════════════════════════════
当提示中包含 [先前对话] 时，说明这是与用户的连续对话。上一轮的信息是你理解当前输入的背景参考。

你应该：

1. 理解修正型输入：
   - "换一批"、"换个别的"、"还有吗" → 用户想换菜，保持食材和约束不变
   - "太辣了"、"有没有清淡的" → 调整口味，其余不变
   - "太快了"、"有没有简单点的" → 调整难度，其余不变
   - "太慢了" → 缩短时间，其余不变
   - "再加个青椒" → 继承食材，追加"青椒"
   - "不要鸡蛋了" → 继承食材，在 excluded 中加上"鸡蛋"

2. 自动补全缺失：
   - 用户只说修正意图没说新食材 → 继承上一轮的食材
   - 用户只说了新食材 → 用新食材，但约束（忌口、过敏、口味等）参考上一轮
   - 用户只调整了一个约束 → 其他约束继承上一轮

3. 判断何时不继承：
   - 用户明确说"不用忌口了"、"什么都能吃" → 清空 excluded
   - 用户说了全新的食材和需求（如上一轮是番茄炒蛋，当前说"今天想吃火锅"） → 全新解析
   - [当前输入] 中明确表达的，始终优先于上一轮

关键：用常识判断。你不是机械地复制字段，而是像一个有记忆的助手一样理解用户的连续对话。

═══════════════════════════════════
核心原则
═══════════════════════════════════
1. 用户可能只是在聊天，不是在下指令。你要听懂话外音。
2. 场景比字面重要："好冷啊"四个字蕴含了口味、温度偏好，而不仅仅是 weather report。
3. 推断要合理，不要过度。如果一句话可以有两种解释，选最日常的那种。
4. 输入栏文本中的约束是用户最直接的表达，优先采纳。按钮值仅当输入栏未提及时作为补充。文本与按钮冲突时，以文本为准。
5. 最终 JSON 中每个字段都必须存在，缺信息就用默认值。
"""


async def parse_to_user_request(
    ingredients_text: str,
    servings: int = 2,
    time_limit_min: int = 30,
    difficulty: str = "任意",
    flavor: str = "",
    excluded: list[str] | None = None,
    allergens: list[str] | None = None,
    equipment: list[str] | None = None,
    context: str = "",
) -> UserRequest:
    """将前端输入框 + 按钮值合并，LLM 提取为结构化 UserRequest。
    context 为上一轮对话摘要，供 LLM 参考（非强制继承）。"""

    # 组装完整提示文本 —— 当前输入为主体，先前对话为参考
    parts = []

    if context:
        parts.append(f"[先前对话]\n{context}\n\n[当前输入]")

    parts.append(ingredients_text)

    if servings != 2:
        parts.append(f"{servings}人份")
    if time_limit_min != 30:
        parts.append(f"{time_limit_min}分钟内")
    if difficulty and difficulty != "任意":
        parts.append(f"难度{difficulty}")
    if flavor:
        parts.append(f"口味{flavor}")
    if excluded:
        parts.append(f"不吃{'、'.join(excluded)}")
    if allergens:
        parts.append(f"过敏{'、'.join(allergens)}")
    if equipment:
        parts.append(f"厨具{'、'.join(equipment)}")

    merged_text = "，".join(parts)

    # 调 LLM 解析
    result = await asyncio.to_thread(
        chat_json_guarded,
        prompt=merged_text,
        system=PARSER_SYSTEM_PROMPT,
        model=config.PARSER_MODEL,
    )

    if result:
        return UserRequest(
            ingredients=result.get("ingredients", []),
            excluded=result.get("excluded", []),
            allergens=result.get("allergens", []),
            equipment=result.get("equipment", []),
            servings=result.get("servings", 2),
            difficulty=result.get("difficulty", "任意"),
            time_limit_min=result.get("time_limit_min", 30),
            flavor=result.get("flavor", ""),
        )

    # LLM 不可用时规则兜底：简单分词
    import re
    raw_items = re.split(r'[,，、\s]+', ingredients_text)
    raw_items = [r.strip() for r in raw_items if r.strip()]
    quantity_pattern = re.compile(r'^[\d半个两三四五六七八九十]+[个只条根片块]?$')
    fallback_ingredients = [r for r in raw_items if not quantity_pattern.match(r)]

    return UserRequest(
        ingredients=fallback_ingredients,
        excluded=excluded or [],
        allergens=allergens or [],
        equipment=equipment or [],
        servings=servings,
        difficulty=difficulty,
        time_limit_min=time_limit_min,
        flavor=flavor,
    )
