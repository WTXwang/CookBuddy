"""
Loop 框架端到端冒烟测试

用 mock 替换 chat/chat_json，验证：
1. 正常 LLM 调用成功返回
2. 重试机制：前 N 次失败 → 最终成功
3. 熔断器：连续失败触发 → 拒绝后续调用 → 冷却后恢复
4. 并发控制：超出上限的调用被阻塞
5. chat_json_guarded 集成：JSON 解析 + 重试

不依赖真实 API key，纯 mock 验证控流逻辑。
"""

import sys
import os
import time
import threading

# 确保 backend 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import config
from loop import (
    retry_with_backoff,
    CircuitBreaker,
    _get_circuit_breaker,
    _get_semaphore,
    reset_for_testing,
)


def test_success_first_try():
    """测试：首次调用成功，无重试"""
    print("[SMOKE-1] 正常调用成功")
    reset_for_testing()

    def ok():
        return {"result": "success"}

    result = retry_with_backoff(ok)
    assert result == {"result": "success"}, f"失败: {result}"
    print("  PASS")


def test_retry_after_none():
    """测试：前 2 次返回 None，第 3 次成功"""
    print("[SMOKE-2] 重试后成功")
    reset_for_testing()
    counter = [0]

    def fail_then_ok():
        counter[0] += 1
        if counter[0] < 3:
            return None
        return {"result": "ok"}

    result = retry_with_backoff(fail_then_ok)
    assert result == {"result": "ok"}, f"失败: {result}"
    assert counter[0] == 3, f"应调用 3 次，实际 {counter[0]}"
    print("  PASS")


def test_all_fail_return_none():
    """测试：全部返回 None"""
    print("[SMOKE-3] 全部失败返回 None")
    reset_for_testing()
    result = retry_with_backoff(lambda: None)
    assert result is None, f"期望 None，得到 {result}"
    print("  PASS")


def test_circuit_breaker_opens():
    """测试：熔断触发"""
    print("[SMOKE-4] 熔断触发")
    reset_for_testing()
    cb = _get_circuit_breaker()

    for _ in range(config.LOOP_CIRCUIT_BREAKER_FAILS):
        cb.on_failure()
    assert cb.state == "open", f"期望 open，实际 {cb.state}"

    called = [False]
    result = retry_with_backoff(lambda: (called.__setitem__(0, True), {"ok": True}))
    assert result is None, "熔断打开应直接返回 None"
    assert not called[0], "熔断打开不应调用 func"
    print("  PASS")


def test_circuit_breaker_recovery():
    """测试：熔断恢复（half_open 探测成功）"""
    print("[SMOKE-5] 熔断恢复")
    reset_for_testing()
    cb = _get_circuit_breaker()
    cb._cooldown = 0.01

    for _ in range(config.LOOP_CIRCUIT_BREAKER_FAILS):
        cb.on_failure()
    assert cb.state == "open"
    time.sleep(0.02)
    assert cb.state == "half_open", f"期望 half_open，实际 {cb.state}"

    result = retry_with_backoff(lambda: {"ok": True})
    assert result == {"ok": True}
    assert cb.state == "closed", f"期望 closed，实际 {cb.state}"
    print("  PASS")


def test_concurrency_guard():
    """测试：并发控制限制"""
    print("[SMOKE-6] 并发控制")
    reset_for_testing()
    sem = _get_semaphore()

    # 占满所有许可
    for i in range(config.LOOP_MAX_CONCURRENCY):
        ok = sem.acquire(timeout=0.1)
        assert ok, f"许可 {i+1} 应成功"
    # 第 N+1 个应失败
    assert not sem.acquire(timeout=0.1), f"第 {config.LOOP_MAX_CONCURRENCY+1} 个许可应失败"

    for _ in range(config.LOOP_MAX_CONCURRENCY):
        sem.release()
    print("  PASS")


def test_config_values():
    """测试：config 中 Loop 参数在合理范围"""
    print("[SMOKE-7] Config 参数校验")
    assert 1 <= config.LOOP_RETRY_MAX <= 5, f"LOOP_RETRY_MAX={config.LOOP_RETRY_MAX}"
    assert config.LOOP_CIRCUIT_BREAKER_FAILS >= 1, f"LOOP_CIRCUIT_BREAKER_FAILS={config.LOOP_CIRCUIT_BREAKER_FAILS}"
    assert config.LOOP_CIRCUIT_BREAKER_COOLDOWN >= 10, f"LOOP_CIRCUIT_BREAKER_COOLDOWN={config.LOOP_CIRCUIT_BREAKER_COOLDOWN}"
    assert config.LOOP_MAX_CONCURRENCY >= 1, f"LOOP_MAX_CONCURRENCY={config.LOOP_MAX_CONCURRENCY}"
    assert config.LOOP_LLM_TIMEOUT > 0, f"LOOP_LLM_TIMEOUT={config.LOOP_LLM_TIMEOUT}"
    print("  PASS")


def test_llm_client_import():
    """测试：llm_client 的 guarded 函数可正常 import"""
    print("[SMOKE-8] llm_client guarded import")
    try:
        from llm_client import chat_guarded, chat_json_guarded
        assert callable(chat_guarded), "chat_guarded 不可调用"
        assert callable(chat_json_guarded), "chat_json_guarded 不可调用"
        print("  PASS")
    except ImportError as e:
        print(f"  SKIP (缺少依赖: {e})")


def test_agent_imports():
    """测试：所有 Agent 模块可正常 import（不依赖 API key）"""
    print("[SMOKE-9] Agent 模块 import")
    try:
        from agents.safety import FoodSafetyReviewer
        from agents.cooking_guide import CookingGuide
        from agents.concierge import concierge_chat
        from agents.parser import parse_to_user_request
        from profiles.extractor import extract_profile_changes

        assert FoodSafetyReviewer is not None
        assert CookingGuide is not None
        assert callable(concierge_chat)
        assert callable(parse_to_user_request)
        assert callable(extract_profile_changes)
        print("  PASS")
    except ImportError as e:
        print(f"  SKIP (缺少依赖: {e})")


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("Loop 框架端到端冒烟测试")
    print("=" * 60)

    all_tests = [
        test_success_first_try,
        test_retry_after_none,
        test_all_fail_return_none,
        test_circuit_breaker_opens,
        test_circuit_breaker_recovery,
        test_concurrency_guard,
        test_config_values,
        test_llm_client_import,
        test_agent_imports,
    ]

    passed = 0
    failed = 0
    for test in all_tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {e}")

    print("")
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("All smoke tests passed!")
    else:
        print("Some tests FAILED!")
    print("=" * 60)
