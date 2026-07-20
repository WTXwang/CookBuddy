"""角色A 独立测试脚本 —— 不依赖任何 LLM / LangChain / FastAPI

用法:
    python -X utf8 test_a.py                        # 交互式输入
    python -X utf8 test_a.py "鸡蛋、番茄、土豆"      # 命令行传参
    python -X utf8 test_a.py "鸡蛋、番茄，不要辣"    # 带口味约束
    python -X utf8 test_a.py "鸡胸肉、花生，花生过敏" # 带过敏原
    python -X utf8 test_a.py --stub "鸡蛋、番茄"     # 强制用 stub
    python -X utf8 test_a.py --ragflow "土豆、洋葱"  # 强制用 RAGFlow
"""
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from schemas import RecommendRequest
from rules.pipeline import run_pipeline
from rules.normalizer import split_ingredients_text
import config


def banner(title: str):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


def show_candidates(recipes):
    """打印菜谱列表"""
    for i, r in enumerate(recipes, 1):
        equip_hint = f" 🔧需要{r.equipment}" if r.equipment else ""
        print(f"  {i}. [{int(r.retrieval_score)}分] {r.title}")
        print(f"     ⏱{r.estimated_time_min}分钟 | {r.difficulty} | {r.cuisine}{equip_hint}")
        print(f"     核心: {', '.join(r.core_ingredients)}")
        if r.optional_ingredients:
            print(f"     可选: {', '.join(r.optional_ingredients)}")
        if r.allergens:
            print(f"     ⚠ 过敏原: {', '.join(r.allergens)}")
        if r.body:
            body_preview = r.body[:150].replace('\n', ' ').strip()
            print(f"     📖 {body_preview}...")


def main():
    args = sys.argv[1:]
    override_backend = None

    if "--stub" in args:
        override_backend = "stub"
        args.remove("--stub")
    elif "--ragflow" in args:
        override_backend = "ragflow"
        args.remove("--ragflow")

    if args:
        text = " ".join(args)
    else:
        print("\n🍳 角色A 管线测试 —— RecommendRequest → 菜谱列表")
        print("─" * 55)
        print("输入示例:")
        print("  鸡蛋、番茄、土豆，两人，20分钟")
        print("  鸡胸肉、黄瓜、花生，花生过敏，不辣")
        print("  西红柿、鸡蛋2个、马铃薯（测试别名+数量）")
        try:
            text = input("\n👉 请输入食材: ").strip()
        except (EOFError, UnicodeDecodeError):
            text = ""
        if not text:
            text = "鸡蛋、番茄、土豆，两人，20分钟"
            print(f"  (默认: {text})")

    if override_backend:
        config.RETRIEVAL_BACKEND = override_backend

    # ── 模拟 B 角色传来的 RecommendRequest ──
    # 用 split_ingredients_text 做简单食材提取
    # 真正的约束值在真实场景中由 B 的 LLM 填好，这里从文本中粗提取做演示
    raw_names = split_ingredients_text(text)
    req = RecommendRequest(
        ingredients_text=text,
        servings=2,
        time_limit_min=20,
        difficulty="简单",
        flavor="",
        excluded=[],
        allergens=[],
        equipment=[],
    )

    # 简单从文本提取约束（模拟 B 的工作，正常由 B 的 LLM 完成）
    if "花生过敏" in text:
        req.allergens.append("花生")
    if "不辣" in text or "不要辣" in text:
        req.flavor = "不辣"
    elif "辣" in text or "麻辣" in text:
        req.flavor = "辣"
    if "半小时" in text:
        req.time_limit_min = 30
    if "两人" in text or "2人" in text:
        req.servings = 2
    if "炒锅" in text:
        req.equipment.append("炒锅")
    if "蒸锅" in text:
        req.equipment.append("蒸锅")
    if "微波炉" in text:
        req.equipment.append("微波炉")

    print(f"\n🔧 检索后端: {config.RETRIEVAL_BACKEND}")

    banner(f"输入: RecommendRequest")
    print(f"  ingredients_text: \"{req.ingredients_text}\"")
    print(f"  servings={req.servings}, time={req.time_limit_min}min, difficulty={req.difficulty}")
    print(f"  flavor=\"{req.flavor}\", allergens={req.allergens}, equipment={req.equipment}")
    print(f"  excluded={req.excluded}")
    print(f"  提取食材名: {raw_names}")

    banner("执行 pipeline.run_pipeline()")
    recipes = run_pipeline(req, top_n=10)

    if not recipes:
        print("\n  ❌ 未找到匹配菜谱")
        return

    banner(f"结果: {len(recipes)} 道菜谱（按评分降序）")
    show_candidates(recipes)

    banner("📊 汇总")
    print(f"  输入: {raw_names}")
    print(f"  返回: {len(recipes)} 道")
    top3 = recipes[:3]
    for i, r in enumerate(top3, 1):
        print(f"  {i}. [{int(r.retrieval_score)}分] {r.title}  ⏱{r.estimated_time_min}分钟")


if __name__ == "__main__":
    main()
