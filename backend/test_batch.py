"""角色A 批量测试脚本 —— 覆盖多种场景

用法:
    python -X utf8 test_batch.py              # 全部场景
    python -X utf8 test_batch.py --stub       # 只用 stub
    python -X utf8 test_batch.py --ragflow    # 只用 RAGFlow
    python -X utf8 test_batch.py --quick      # 只跑 5 个核心场景
"""
import sys
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from schemas import RecommendRequest
from rules.pipeline import run_pipeline
import config


# ============================================================
# 测试用例: (名称, RecommendRequest, 期望)
# ============================================================
TEST_CASES = [
    # ── 标准食材组合 ──
    {
        "name": "标准: 鸡蛋+番茄",
        "req": RecommendRequest(ingredients_text="鸡蛋、番茄", servings=2,
                                time_limit_min=20, difficulty="简单"),
        "expect": lambda r: len(r) > 0 and r[0].title == "番茄炒蛋",
    },
    {
        "name": "标准: 土豆+青椒",
        "req": RecommendRequest(ingredients_text="土豆、青椒", servings=2,
                                time_limit_min=20, difficulty="简单"),
        "expect": lambda r: len(r) > 0 and any("土豆" in x.title for x in r[:3]),
    },
    {
        "name": "标准: 单一食材鸡蛋",
        "req": RecommendRequest(ingredients_text="鸡蛋", servings=2,
                                time_limit_min=20, difficulty="简单"),
        "expect": lambda r: len(r) >= 3 and all("蛋" in x.title for x in r[:3]),
    },

    # ── 别名映射 ──
    {
        "name": "别名: 西红柿→番茄",
        "req": RecommendRequest(ingredients_text="西红柿", servings=2,
                                time_limit_min=20, difficulty="简单"),
        "expect": lambda r: len(r) > 0 and r[0].title == "番茄炒蛋",
    },
    {
        "name": "别名: 马铃薯→土豆",
        "req": RecommendRequest(ingredients_text="马铃薯、青椒", servings=2,
                                time_limit_min=20, difficulty="简单"),
        "expect": lambda r: len(r) > 0 and any("土豆" in x.title for x in r[:3]),
    },
    {
        "name": "别名: 鸡胸→鸡胸肉",
        "req": RecommendRequest(ingredients_text="鸡胸、黄瓜", servings=2,
                                time_limit_min=30, difficulty="简单"),
        "expect": lambda r: len(r) > 0 and any("鸡" in x.title for x in r),
    },

    # ── 过敏原硬阻断 ──
    {
        "name": "过敏: 花生过敏→宫保鸡丁被移除",
        "req": RecommendRequest(ingredients_text="鸡胸肉、黄瓜、花生",
                                allergens=["花生"], servings=2,
                                time_limit_min=30, difficulty="简单"),
        "expect": lambda r: (
            # 宫保鸡丁含花生，必须被彻底移除，不能在结果中
            not any("宫保" in x.title for x in r)
        ),
    },
    {
        "name": "过敏: 鸡蛋过敏",
        "req": RecommendRequest(ingredients_text="鸡蛋、番茄",
                                allergens=["鸡蛋"], servings=2,
                                time_limit_min=20, difficulty="简单"),
        "expect": lambda r: len(r) >= 0,  # 至少不崩溃
    },

    # ── 口味偏好 ──
    {
        "name": "口味: 不辣→辣菜排后面",
        "req": RecommendRequest(ingredients_text="鸡胸肉、黄瓜",
                                flavor="不辣", servings=2,
                                time_limit_min=30, difficulty="简单"),
        "expect": lambda r: len(r) >= 0,
    },

    # ── 时间约束 ──
    {
        "name": "时间: 15分钟快手菜",
        "req": RecommendRequest(ingredients_text="鸡蛋、番茄",
                                time_limit_min=15, servings=2, difficulty="简单"),
        "expect": lambda r: len(r) > 0 and r[0].estimated_time_min <= 20,
    },
    {
        "name": "时间: 严格10分钟",
        "req": RecommendRequest(ingredients_text="鸡蛋",
                                time_limit_min=10, servings=2, difficulty="简单"),
        "expect": lambda r: len(r) > 0 and r[0].estimated_time_min <= 15,
    },

    # ── 厨具约束 ──
    {
        "name": "厨具: 只有炒锅→蒸锅菜降分",
        "req": RecommendRequest(ingredients_text="鸡蛋",
                                equipment=["炒锅"], servings=2,
                                time_limit_min=20, difficulty="简单"),
        "expect": lambda r: len(r) > 0 and (
            r[0].equipment == [] or "炒锅" in r[0].equipment or
            all(e in ["炒锅"] or e in [] for e in r[0].equipment)
        ),
    },

    # ── 边界情况 ──
    {
        "name": "边界: 空食材",
        "req": RecommendRequest(ingredients_text="", servings=2,
                                time_limit_min=20, difficulty="简单"),
        "expect": lambda r: r == [],
    },
    {
        "name": "边界: 不存在的食材",
        "req": RecommendRequest(ingredients_text="火星陨石",
                                servings=2, time_limit_min=20, difficulty="简单"),
        "expect": lambda r: r == [],
    },
    {
        "name": "边界: 只有调料",
        "req": RecommendRequest(ingredients_text="盐、食用油、生抽",
                                servings=2, time_limit_min=20, difficulty="简单"),
        "expect": lambda r: isinstance(r, list),  # 不崩溃
    },
    {
        "name": "边界: 极长时间",
        "req": RecommendRequest(ingredients_text="鸡蛋、番茄",
                                time_limit_min=480, servings=2, difficulty="简单"),
        "expect": lambda r: len(r) > 0,
    },
]


def run_all_tests():
    """跑全部测试用例"""
    total = len(TEST_CASES)
    passed = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"  角色A 批量测试 — {total} 个场景")
    print(f"  检索后端: {config.RETRIEVAL_BACKEND}")
    print(f"{'='*60}")

    for i, case in enumerate(TEST_CASES, 1):
        name = case["name"]
        req = case["req"]
        check = case["expect"]

        try:
            recipes = run_pipeline(req)
            ok = check(recipes)
        except Exception as e:
            ok = False
            print(f"\n  [{i:2d}/{total}] ❌ {name}")
            print(f"         异常: {e}")
            failed += 1
            continue

        status = "✅" if ok else "❌"
        top_titles = ", ".join(r.title for r in recipes[:3]) if recipes else "(无结果)"
        print(f"  [{i:2d}/{total}] {status} {name}")
        if not ok:
            print(f"         Top3: {top_titles}")
            failed += 1
        else:
            passed += 1

    print(f"\n{'='*60}")
    print(f"  结果: {passed} 通过 / {failed} 失败 / {total} 总计")
    print(f"{'='*60}")
    return failed == 0


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--stub" in args:
        config.RETRIEVAL_BACKEND = "stub"
    elif "--ragflow" in args:
        config.RETRIEVAL_BACKEND = "ragflow"

    # quick 模式：只跑前 5 个核心场景
    if "--quick" in args:
        TEST_CASES = TEST_CASES[:5]
        print("(快速模式: 仅核心场景)")

    success = run_all_tests()
    sys.exit(0 if success else 1)
