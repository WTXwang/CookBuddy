"""A+B 全链路交互沙盒 —— 人工联调工具

用法:
    cd backend && python -X utf8 play_full.py

与 play.py 的区别：
    play.py       → 只跑 A 线（规则管线），不调 LLM，秒出结果
    play_full.py  → 跑完整 A+B 链路（8 节点 LangGraph），会调 LLM
"""

import sys
import os
import asyncio

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from schemas import RecommendRequest
import config

# ── 阶段名称映射（GraphStage → 中文） ──
STAGE_LABELS = {
    "concierge": "Concierge 意图分类",
    "parser":    "Parser 字段提取",
    "lookup":    "Lookup 菜名检索",
    "normalize": "Normalize 标准化",
    "retrieve":  "Retrieve 检索",
    "match":     "Match 特征匹配",
    "score":     "Score 评分排序",
    "guide":     "Guide 做法生成",
    "safety":    "Safety 安全审查",
    "output":    "Output 输出",
    "error":     "Error 错误",
}


def hr(c="─", width=56):
    print(c * width)


async def run_recommend(text, constraints):
    """调用完整 A+B 管线"""
    from graph import recommend

    req = RecommendRequest(
        ingredients_text=text,
        servings=constraints["servings"],
        time_limit_min=constraints["time_limit"],
        difficulty=constraints["difficulty"],
        flavor=constraints["flavor"],
        excluded=constraints["excluded"],
        allergens=constraints["allergens"],
        equipment=constraints["equipment"],
    )
    return await recommend(req)


def show_stages(state):
    """打印各阶段耗时"""
    if not state.stage_durations:
        return
    print()
    print("  ⏱ 阶段耗时:")
    for key, label in STAGE_LABELS.items():
        ms = state.stage_durations.get(key)
        if ms is not None:
            bar = "█" * max(1, min(20, ms // 200))
            print(f"    {label:<18s} {ms:>5d}ms  {bar}")


def show_result(state, constraints):
    """打印推荐结果"""

    # ── 闲聊模式 ──
    if state.intent and state.intent.value == "chat":
        if state.chat_reply:
            print(f"\n  💬 {state.chat_reply}")
        show_stages(state)
        return

    # ── 错误 ──
    if state.error:
        print(f"\n  ❌ {state.error}")
        show_stages(state)
        return

    if not state.response or not state.response.recommendations:
        print(f"\n  📭 没有找到匹配的菜谱")
        if state.chat_reply:
            print(f"  💬 {state.chat_reply}")
        show_stages(state)
        return

    # ── 菜谱列表 ──
    recs = state.response.recommendations
    print(f"\n  📋 推荐 {len(recs)} 道菜：")

    EMOJI_MAP = {"完美匹配": "⭐", "推荐": "👍", "可做": "👌"}

    for i, r in enumerate(recs, 1):
        emoji = EMOJI_MAP.get(r.match_label, "🍳")
        print(f"\n  ┌─ {emoji} [{r.match_label}] {r.title}")
        print(f"  │   评分: {r.match_score}/100  |  {r.estimated_time_min}分钟  |  {r.difficulty}")
        print(f"  │   用到: {', '.join(r.used_ingredients) if r.used_ingredients else '(无)'}")
        if r.missing_core:
            print(f"  │   缺核心: {', '.join(r.missing_core)}")
        if r.missing_optional:
            print(f"  │   缺可选: {', '.join(r.missing_optional)}")

        # 做法预览（前 2 步）
        if r.steps:
            print(f"  │   步骤({len(r.steps)}步):")
            for s in r.steps[:2]:
                print(f"  │     · {s}")
            if len(r.steps) > 2:
                print(f"  │     … 还有 {len(r.steps) - 2} 步")

        # 安全提醒
        if r.safety_notes:
            print(f"  │   ⚠️  安全提醒({len(r.safety_notes)}条):")
            for note in r.safety_notes[:2]:
                print(f"  │     · {note}")

        print(f"  └{'─' * 42}")

    # ── 被阻断的菜谱 ──
    blocked = state.response.blocked_recipes
    if blocked:
        print(f"\n  🚫 被阻断 {len(blocked)} 道:")
        for b in blocked:
            print(f"    · {b.get('recipe_id', '?')}: {b.get('block_reason', '?')}")

    print()
    show_stages(state)


async def main():
    # ── 编译 graph（提前预热） ──
    from graph import get_graph
    print("⏳ 正在编译 LangGraph 工作流...")
    get_graph()
    print("✅ 就绪")

    print(f"""
╔══════════════════════════════════════════════╗
║  🍳  今晚吃什么 — A+B 全链路沙盒          ║
║  后端: {config.RETRIEVAL_BACKEND:<34s} ║
║  模型: {config.CONCIERGE_MODEL:<34s} ║
╚══════════════════════════════════════════════╝
命令:
  直接输入食材  →  全链路推荐（8 节点）
  :过敏 花生    →  设置过敏原
  :忌口 香菜    →  设置忌口
  :厨具 炒锅    →  设置厨具
  :口味 不辣    →  设置口味偏好
  :时间 15      →  设置时间限制(分钟)
  :难度 简单    →  设置难度
  :重置         →  清空所有约束
  :exit         →  退出
""")

    # 默认约束
    constraints = {
        "allergens": [],
        "excluded": [],
        "equipment": [],
        "flavor": "",
        "time_limit": 30,
        "difficulty": "简单",
        "servings": 2,
    }

    while True:
        # ── 显示当前约束 ──
        tags = []
        if constraints["allergens"]:
            tags.append(f"过敏={'+'.join(constraints['allergens'])}")
        if constraints["excluded"]:
            tags.append(f"忌口={'+'.join(constraints['excluded'])}")
        if constraints["equipment"]:
            tags.append(f"厨具={'+'.join(constraints['equipment'])}")
        if constraints["flavor"]:
            tags.append(f"口味={constraints['flavor']}")
        if constraints["time_limit"] != 30:
            tags.append(f"{constraints['time_limit']}分钟")
        if constraints["difficulty"] != "简单":
            tags.append(f"难度={constraints['difficulty']}")

        tag_str = " | ".join(tags) if tags else "无约束"
        print(f"\n🎯 [{tag_str}]")

        try:
            cmd = input("👉 ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见!")
            break

        if not cmd:
            continue

        # ── 命令处理 ──
        if cmd == ":exit":
            print("👋 再见!")
            break
        elif cmd in (":reset", ":重置"):
            constraints.update({
                "allergens": [], "excluded": [], "equipment": [],
                "flavor": "", "time_limit": 30, "difficulty": "简单",
            })
            print("✅ 已重置所有约束")
            continue
        elif cmd.startswith(":过敏"):
            v = cmd.replace(":过敏", "").strip()
            constraints["allergens"] = [x.strip() for x in v.replace("，", ",").split(",") if x.strip()] if v else []
            print(f"✅ 过敏原={constraints['allergens'] or '(无)'}")
            continue
        elif cmd.startswith(":忌口"):
            v = cmd.replace(":忌口", "").strip()
            constraints["excluded"] = [x.strip() for x in v.replace("，", ",").split(",") if x.strip()] if v else []
            print(f"✅ 忌口={constraints['excluded'] or '(无)'}")
            continue
        elif cmd.startswith(":厨具"):
            v = cmd.replace(":厨具", "").strip()
            constraints["equipment"] = [x.strip() for x in v.replace("，", ",").split(",") if x.strip()] if v else []
            print(f"✅ 厨具={constraints['equipment'] or '(无)'}")
            continue
        elif cmd.startswith(":口味"):
            v = cmd.replace(":口味", "").strip()
            constraints["flavor"] = v
            print(f"✅ 口味={v or '(不限)'}")
            continue
        elif cmd.startswith(":时间"):
            v = cmd.replace(":时间", "").strip()
            try:
                constraints["time_limit"] = int(v)
                print(f"✅ 时间限制={v}分钟")
            except ValueError:
                print("❌ 请输入数字，如 :时间 15")
            continue
        elif cmd.startswith(":难度"):
            v = cmd.replace(":难度", "").strip()
            if v in ("简单", "中等", "困难", "任意"):
                constraints["difficulty"] = v
                print(f"✅ 难度={v}")
            else:
                print("❌ 请输入: 简单 / 中等 / 困难 / 任意")
            continue

        # ── 全链路推荐 ──
        hr()
        try:
            state = await asyncio.wait_for(
                run_recommend(cmd, constraints),
                timeout=config.LOOP_TOTAL_TIMEOUT,
            )
            show_result(state, constraints)
        except asyncio.TimeoutError:
            print(f"\n  ⏰ 超时（{config.LOOP_TOTAL_TIMEOUT}s），LLM 响应较慢，请重试")
        except Exception as e:
            print(f"\n  ❌ 异常: {e}")
        hr()


if __name__ == "__main__":
    asyncio.run(main())
