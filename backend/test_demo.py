"""
交互式演示脚本 —— 逐阶段查看 Agent 的输入/输出/运作逻辑
用法: python -X utf8 test_demo.py
      python -X utf8 test_demo.py "鸡蛋、番茄、土豆"
      python -X utf8 test_demo.py --llm "鸡蛋、番茄、花生过敏"
"""
import sys
import json
import time
import uuid
import asyncio
from typing import Optional

from schemas import (
    RecommendRequest, ChefState, GraphStage,
    NormalizedRequest, RecommendationResponse, Recommendation,
    CandidateFeature, RecipeRecord,
)
from rules.normalizer import normalize_ingredients, normalize_name
from rules.staples import get_staples, is_staple
from rules.scorer import build_feature, score_and_rank
from agents.matcher import RecipeMatcher
from agents.cooking_guide import CookingGuide
from agents.safety import FoodSafetyReviewer
from retrieval.stub import RetrievalStub
import config


# ── 工具 ──────────────────────────────────────────
def header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def sub(title: str):
    print(f"\n── {title} ──")

def show_json(obj, max_lines=50):
    """美化打印 JSON"""
    if hasattr(obj, 'model_dump'):
        s = json.dumps(obj.model_dump(), ensure_ascii=False, indent=2)
    elif isinstance(obj, dict):
        s = json.dumps(obj, ensure_ascii=False, indent=2)
    else:
        s = str(obj)
    lines = s.split('\n')
    for line in lines[:max_lines]:
        print(f"  {line}")
    if len(lines) > max_lines:
        print(f"  ... (省略 {len(lines)-max_lines} 行)")

def step_banner(step_num: int, stage_name: str, icon: str):
    print(f"\n{'─'*60}")
    print(f"  Step {step_num} | {icon}  {stage_name}")
    print(f"{'─'*60}")


# ── 主流程 ────────────────────────────────────────
async def run_demo():
    print("""
╔════════════════════════════════════════════════╗
║       🍳  今晚吃什么 — Agent 运作演示         ║
║                                                ║
║  逐阶段展示：输入 → 标准化 → 检索 → 匹配      ║
║  → 评分 → 做法 → 安全审查 → 最终输出          ║
╚════════════════════════════════════════════════╝
""")

    # ─── 解析命令行参数 ───
    use_llm = False
    args = sys.argv[1:]
    if "--llm" in args:
        use_llm = True
        args.remove("--llm")

    if args:
        ingredients_text = " ".join(args)
        print(f"输入: {ingredients_text}")
    else:
        print("输入食材和约束（回车提交）:")
        print("  例: 鸡蛋、番茄、土豆、青菜，两个人，20分钟")
        print("  例: 鸡胸肉、黄瓜、花生，花生过敏，30分钟")
        try:
            ingredients_text = input("\n👉 ").strip()
        except (EOFError, UnicodeDecodeError):
            ingredients_text = ""
    if not ingredients_text:
        ingredients_text = "鸡蛋、番茄、土豆、青菜，两个人，20分钟"
        print(f"  (使用默认: {ingredients_text})")

    req = RecommendRequest(
        ingredients_text=ingredients_text,
        servings=2,
        time_limit_min=20,
        difficulty="简单",
        allergens=["花生"] if "花生过敏" in ingredients_text else [],
        flavor="不辣" if "不辣" in ingredients_text else "",
    )

    # 初始化模块（每个 Agent 独立模型）
    if use_llm:
        matcher = RecipeMatcher(model=config.MATCHER_MODEL)
        guide = CookingGuide(model=config.GUIDE_MODEL)
        safety = FoodSafetyReviewer(model=config.SAFETY_MODEL)
        if matcher.llm is None:
            print("  ⚠ 未配置 API key，降级为纯规则模式")
        else:
            print(f"  🤖 Matcher: {config.MATCHER_MODEL}")
            print(f"  🤖 Guide:   {config.GUIDE_MODEL}")
            print(f"  🤖 Safety:  {config.SAFETY_MODEL}")
    else:
        matcher = RecipeMatcher(model="")  # 空字符串 = 纯规则
        guide = CookingGuide(model="")
        safety = FoodSafetyReviewer(model="")
        print(f"  🔧 纯规则模式 (--llm 切换 LLM, 模型在 config.py 配置)")

    retrieval = RetrievalStub()

    # ─── Step 1: 输入 ───
    step_banner(1, "Categorize 意图分类", "🎯")
    print(f"  原始输入: {req.ingredients_text}")
    intent = "recommend"
    if any(kw in req.ingredients_text for kw in ["怎么做", "做法", "步骤"]):
        intent = "lookup"
    elif any(kw in req.ingredients_text for kw in ["替代", "代替"]):
        intent = "substitute"
    print(f"  识别意图: {intent}")
    print(f"  约束: 人数={req.servings}, 时间≤{req.time_limit_min}分钟, 难度={req.difficulty}")
    if req.allergens:
        print(f"  过敏原: {req.allergens}")

    # ─── Step 2: 标准化 ───
    step_banner(2, "Normalize 食材标准化", "🥚🔪")
    import re
    raw_items = re.split(r'[,，、\s]+', req.ingredients_text)
    raw_items = [r.strip() for r in raw_items if r.strip() and not re.match(r'^[\d半个两]+[个只条根片块]?$', r.strip())]
    normalized = normalize_ingredients(raw_items)
    ing_names = [n.name for n in normalized]
    staples = get_staples(assume=True, include_aromatics=True)

    print(f"  原始分词 ({len(raw_items)}项): {raw_items}")
    print(f"  标准化后 ({len(normalized)}项):")
    for n in normalized:
        alias_hint = f" (别名: {n.raw})" if n.raw != n.name else ""
        print(f"    • {n.name} [{n.category}]{alias_hint}")
    print(f"  基础调料(默认已拥有): {staples}")

    # ─── Step 3: 检索 ───
    step_banner(3, "Retrieve 知识库检索", "📖🔍")
    candidates = retrieval.search(ing_names, top_n=10)
    print(f"  召回候选: {len(candidates)} 道")
    for i, c in enumerate(candidates):
        print(f"    {i+1}. [{c.recipe_id}] {c.title} (检索分:{c.retrieval_score:.2f}) | 核心:{c.core_ingredients}")

    if not candidates:
        print("  ⚠ 未找到匹配菜谱，流程终止")
        return

    # ─── Step 4: 匹配 ───
    step_banner(4, "Match 菜谱匹配 & 特征提取", "🧪✨")
    features = [
        build_feature(c, ing_names, req.allergens, req.excluded,
                      req.flavor, req.time_limit_min, req.equipment)
        for c in candidates
    ]
    print(f"  匹配特征 ({len(features)} 项):")
    for f in features:
        blocked_tag = " ❌阻断" if f.blocked else ""
        miss_tag = f" 缺核心:{f.missing_core}" if f.missing_core else " 核心齐全"
        print(f"    [{f.recipe_id}] 核心:{f.core_matched}/{f.core_total}{miss_tag} | "
              f"偏好:{f.preference_score:.1f} 时间:{f.time_fit:.1f} 厨具:{f.equipment_fit:.1f}{blocked_tag}")
        if f.blocked:
            print(f"      阻断原因: {f.block_reasons}")

    # ─── Step 5: 评分 ───
    step_banner(5, "Score 评分排序", "📊")
    print("  评分公式: Base = 45*core_coverage + 20*retrieval + 15*pref + 10*time + 10*equip")
    print("           Penalty = 25*core_miss_ratio + (10 if overtime)")
    print("           Final = clamp(Base-Penalty, 0, 100)")
    features = score_and_rank(features)
    print(f"\n  排序结果:")
    for i, f in enumerate(features):
        label = "✅" if not f.blocked and not f.missing_core else ("⚠️" if not f.blocked else "❌")
        title = next((c.title for c in candidates if c.recipe_id == f.recipe_id), "?")
        print(f"    {i+1}. {label} [{f.final_score}分] {title} | 缺核心:{f.missing_core} | 阻断:{f.blocked}")

    # ─── Step 6: 做法生成 ───
    step_banner(6, "Guide 烹饪指导生成", "🍳🔥")
    top_features = [f for f in features if not f.blocked][:3]
    recipe_map = {r.recipe_id: r for r in candidates}

    recommendations = []
    for i, feat in enumerate(top_features):
        recipe = recipe_map.get(feat.recipe_id)
        if not recipe:
            continue
        guide_data = guide.generate(recipe, feat)
        score = feat.final_score
        label = "完美匹配" if score >= 90 else ("推荐" if score >= 70 else "可做")

        print(f"\n  ┌─ 推荐 #{i+1} ─────────────────────────────")
        print(f"  │ {recipe.title} [{label} · {score}分]")
        print(f"  │ ⏱{recipe.estimated_time_min}分钟 | 📊{recipe.difficulty} | 👥{recipe.servings}人")
        print(f"  │ ✅ 已用: {[n for n in ing_names if n in recipe.core_ingredients]}")
        print(f"  │ ❌ 缺核心: {feat.missing_core}")
        print(f"  │ ➕ 缺可选: {feat.missing_optional}")
        print(f"  │ 📋 准备: {guide_data['prep']}")
        print(f"  │ 📝 步骤:")
        for j, step in enumerate(guide_data['steps'], 1):
            print(f"  │    {j}. {step}")
        if guide_data['heat_tips']:
            print(f"  │ 🔥 火候: {guide_data['heat_tips']}")
        print(f"  └──────────────────────────────────────")

        rec = Recommendation(
            recipe_id=recipe.recipe_id,
            title=recipe.title,
            image_url=recipe.image_url,
            match_score=score,
            match_label=label,
            estimated_time_min=recipe.estimated_time_min,
            difficulty=recipe.difficulty,
            servings=req.servings,
            used_ingredients=[n for n in ing_names if n in recipe.core_ingredients],
            missing_core=feat.missing_core,
            missing_optional=feat.missing_optional,
            reason=f"核心食材匹配度 {score} 分",
            prep=guide_data.get("prep", []),
            steps=guide_data.get("steps", []),
            heat_tips=guide_data.get("heat_tips", ""),
            substitutions=guide_data.get("substitutions", []),
        )
        recommendations.append(rec)

    # ─── Step 7: 安全审查 ───
    step_banner(7, "Safety 食品安全审查", "🔒✅")
    safe_recs = []
    for rec in recommendations:
        report = safety.review(rec, req.allergens, req.excluded)
        status = "✅ 通过" if report.passed else "❌ 阻断"
        print(f"\n  [{rec.recipe_id}] {rec.title} → {status} (severity={report.severity})")
        if report.issues:
            for issue in report.issues:
                print(f"    ⚠ {issue}")
        if report.passed:
            rec.safety_notes = report.issues
            safe_recs.append(rec)
        else:
            print(f"    🚫 已从推荐中移除")

    recommendations = safe_recs

    # ─── Step 8: 输出 ───
    step_banner(8, "Output 最终推荐 JSON", "🍽️")
    response = RecommendationResponse(
        request_summary={
            "ingredients": ing_names,
            "servings": req.servings,
            "assumed_staples": staples,
        },
        recommendations=recommendations,
        blocked_recipes=[
            {"recipe_id": f.recipe_id, "block_reason": "; ".join(f.block_reasons)}
            for f in features if f.blocked
        ],
        trace_id=str(uuid.uuid4()),
    )
    show_json(response)

    # ─── 耗时统计 ───
    header("📊 流程总结")
    print(f"  输入食材: {ing_names}")
    print(f"  候选菜谱: {len(candidates)} 道")
    print(f"  最终推荐: {len(recommendations)} 道")
    print(f"  阻断菜谱: {len(response.blocked_recipes)} 道")
    print(f"  流程节点: 8 个 (categorize→normalize→retrieve→match→score→guide→safety→output)")
    print(f"  LLM 模式: {'启用' if use_llm and matcher.llm else '纯规则模式'}")
    if use_llm and matcher.llm:
        print(f"  Matcher: {config.MATCHER_MODEL}")
        print(f"  Guide:   {config.GUIDE_MODEL}")
        print(f"  Safety:  {config.SAFETY_MODEL}")


# ── 入口 ──────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(run_demo())
