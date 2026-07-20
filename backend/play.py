"""角色A 交互式沙盒 —— 随便玩

用法:
    python -X utf8 play.py           # stub 模式
    python -X utf8 play.py --ragflow # RAGFlow 模式
"""
import sys
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from schemas import RecommendRequest
from rules.pipeline import run_pipeline
from rules.normalizer import split_ingredients_text
import config


def hr(c="─"):
    print(c * 50)


def show_result(recipes):
    """按 B 接收到的格式输出"""
    if not recipes:
        print("  []\n")
        return

    import json
    for i, r in enumerate(recipes[:5], 1):
        d = r.model_dump()
        print(f"  [{i}] {json.dumps(d, ensure_ascii=False)}")
    print()


def play():
    if "--ragflow" in sys.argv:
        config.RETRIEVAL_BACKEND = "ragflow"

    print(f"""
╔══════════════════════════════════════╗
║  🍳  今晚吃什么 — 角色A 沙盒       ║
║  检索: {config.RETRIEVAL_BACKEND:<25s} ║
╚══════════════════════════════════════╝
命令:
  直接输入食材  →  搜菜
  :过敏 花生    →  设置过敏原
  :忌口 香菜    →  设置忌口
  :厨具 炒锅    →  设置厨具
  :口味 不辣    →  设置口味偏好
  :时间 15      →  设置时间限制(分钟)
  :难度 简单    →  设置难度
  :重置         →  清空所有约束
  :ragflow      →  切换 RAGFlow
  :stub         →  切换 stub
  :exit         →  退出
""")

    # 默认约束
    allergens = []
    excluded = []
    equipment = []
    flavor = ""
    time_limit = 30
    difficulty = "简单"

    while True:
        # 显示当前约束
        constraints = []
        if allergens:
            constraints.append(f"过敏={allergens}")
        if excluded:
            constraints.append(f"忌口={excluded}")
        if equipment:
            constraints.append(f"厨具={equipment}")
        if flavor:
            constraints.append(f"口味={flavor}")
        if time_limit != 30:
            constraints.append(f"时间={time_limit}分钟")
        if difficulty != "简单":
            constraints.append(f"难度={difficulty}")

        tag = " | ".join(constraints) if constraints else "无约束"
        print(f"\n🎯 [{tag}]")

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
        elif cmd == ":reset" or cmd == ":重置":
            allergens, excluded, equipment = [], [], []
            flavor, time_limit, difficulty = "", 30, "简单"
            print("✅ 已重置")
            continue
        elif cmd == ":ragflow":
            config.RETRIEVAL_BACKEND = "ragflow"
            print("✅ 已切换到 RAGFlow")
            continue
        elif cmd == ":stub":
            config.RETRIEVAL_BACKEND = "stub"
            print("✅ 已切换到 stub")
            continue
        elif cmd.startswith(":过敏"):
            v = cmd.replace(":过敏", "").strip()
            if v:
                allergens = [x.strip() for x in v.split()]
                print(f"✅ 过敏原={allergens}")
            else:
                allergens = []
                print("✅ 已清除过敏原")
            continue
        elif cmd.startswith(":忌口"):
            v = cmd.replace(":忌口", "").strip()
            if v:
                excluded = [x.strip() for x in v.split()]
                print(f"✅ 忌口={excluded}")
            else:
                excluded = []
                print("✅ 已清除忌口")
            continue
        elif cmd.startswith(":厨具"):
            v = cmd.replace(":厨具", "").strip()
            if v:
                equipment = [x.strip() for x in v.split()]
                print(f"✅ 厨具={equipment}")
            else:
                equipment = []
                print("✅ 已清除厨具")
            continue
        elif cmd.startswith(":口味"):
            v = cmd.replace(":口味", "").strip()
            flavor = v
            print(f"✅ 口味={flavor or '(不限)'}")
            continue
        elif cmd.startswith(":时间"):
            v = cmd.replace(":时间", "").strip()
            try:
                time_limit = int(v)
                print(f"✅ 时间限制={time_limit}分钟")
            except ValueError:
                print("❌ 请输入数字，如 :时间 15")
            continue
        elif cmd.startswith(":难度"):
            v = cmd.replace(":难度", "").strip()
            if v in ("简单", "中等", "困难", "任意"):
                difficulty = v
                print(f"✅ 难度={difficulty}")
            else:
                print("❌ 请输入: 简单 / 中等 / 困难 / 任意")
            continue

        # ── 搜菜 ──
        req = RecommendRequest(
            ingredients_text=cmd,
            servings=2,
            time_limit_min=time_limit,
            difficulty=difficulty,
            flavor=flavor,
            excluded=excluded,
            allergens=allergens,
            equipment=equipment,
        )

        names = split_ingredients_text(cmd)
        print(f"  食材: {names}")

        recipes = run_pipeline(req, top_n=5)
        show_result(recipes)


if __name__ == "__main__":
    play()
