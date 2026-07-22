"""
Loop 运行时控流模块

- CircuitBreaker: 熔断器，连续失败 N 次后进入 OPEN 状态暂停服务
- retry_with_backoff: 重试 + 指数退避 + 熔断 + 并发控制
- ConcurrencyLimitError: 并发超限异常

所有参数从 config.py 读取，可通过环境变量覆盖。
"""

import time
import threading
import logging
from typing import Optional, Callable, Any

logger = logging.getLogger("loop")


# ═══════════════════════════════════════════════════════════════
# 全局单例（惰性初始化）
# ═══════════════════════════════════════════════════════════════

_circuit_breaker: Optional["CircuitBreaker"] = None
_semaphore: Optional[threading.BoundedSemaphore] = None


class CircuitBreakerOpenError(Exception):
    """熔断器打开——请求被拒绝。仅用于需要区分"熔断拒绝"和"返回空"的场景。"""
    pass


class ConcurrencyLimitError(Exception):
    """并发许可获取超时。"""
    pass


# ═══════════════════════════════════════════════════════════════
# 熔断器
# ═══════════════════════════════════════════════════════════════

class CircuitBreaker:
    """熔断器状态机：closed → open → half_open → closed

    状态转换：
    - closed: 正常，记录失败
    - open: 连续失败达阈值，拒绝请求；冷却结束后自动进入 half_open
    - half_open: 允许一次探测调用；成功→closed，失败→open
    """

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 60.0):
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "closed"

    @property
    def state(self) -> str:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time >= self._cooldown:
                self._state = "half_open"
                logger.info("[CircuitBreaker] open → half_open（冷却结束，进入探测）")
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def before_call(self) -> bool:
        """调用前检查。返回 False 表示熔断打开，应拒绝调用。"""
        if self.state == "open":
            remaining = self._cooldown - (time.monotonic() - self._last_failure_time)
            logger.warning(
                f"[CircuitBreaker] 熔断中，剩余冷却 {remaining:.0f}s "
                f"（{self._failure_count} 次连续失败）"
            )
            return False
        return True

    def on_success(self) -> None:
        """调用成功——重置熔断器。"""
        prev = self._state
        self._failure_count = 0
        self._state = "closed"
        if prev == "half_open":
            logger.info("[CircuitBreaker] half_open → closed（探测成功，熔断解除）")

    def on_failure(self) -> None:
        """调用失败——记录。达到阈值则打开熔断。"""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._threshold and self._state != "open":
            self._state = "open"
            logger.warning(
                f"[CircuitBreaker] closed → open（连续 {self._failure_count} 次失败，"
                f"冷却 {self._cooldown}s）"
            )


def _get_circuit_breaker() -> CircuitBreaker:
    """获取全局熔断器单例"""
    global _circuit_breaker
    if _circuit_breaker is None:
        import config
        _circuit_breaker = CircuitBreaker(
            failure_threshold=config.LOOP_CIRCUIT_BREAKER_FAILS,
            cooldown_seconds=config.LOOP_CIRCUIT_BREAKER_COOLDOWN,
        )
    return _circuit_breaker


# ═══════════════════════════════════════════════════════════════
# 并发控制（threading.Semaphore，同步/异步均可使用）
# ═══════════════════════════════════════════════════════════════

def _get_semaphore() -> threading.BoundedSemaphore:
    """获取全局信号量单例"""
    global _semaphore
    if _semaphore is None:
        import config
        _semaphore = threading.BoundedSemaphore(config.LOOP_MAX_CONCURRENCY)
    return _semaphore


# ═══════════════════════════════════════════════════════════════
# 重试 + 退避
# ═══════════════════════════════════════════════════════════════

def _backoff_delay(attempt: int, base: float, min_s: float, max_s: float) -> float:
    """计算第 attempt 次重试的退避延迟（0-indexed）。"""
    return min(max_s, min_s * (base ** attempt))


def _is_retryable_error(exception: Exception) -> bool:
    """判断 API 异常是否可重试。

    可重试：网络/超时/限流/服务端错误 (5xx / 429)
    不可重试：认证/鉴权/参数错误 (401/403/400)
    """
    try:
        import openai
        if isinstance(exception, (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError,
            openai.RateLimitError,
        )):
            return True
        if isinstance(exception, (
            openai.AuthenticationError,
            openai.BadRequestError,
            openai.PermissionDeniedError,
        )):
            return False
    except ImportError:
        pass

    # 回退：字符串匹配
    msg = str(exception).lower()
    non_retryable = {"401", "403", "404", "invalid api key", "permission denied", "bad request"}
    if any(kw in msg for kw in non_retryable):
        return False
    retryable = {"timeout", "connection", "rate limit", "internal server error",
                 "503", "502", "500", "429", "timed out", "connection reset"}
    if any(kw in msg for kw in retryable):
        return True
    # 对未知异常默认不重试（安全侧）
    return False


def retry_with_backoff(func: Callable, *args, **kwargs) -> Any:
    """用重试 + 指数退避 + 熔断 + 并发控制包装同步调用。

    行为：
    - func 返回非 None → 成功，熔断器 on_success
    - func 返回 None → 视为失败，指数退避后重试
    - func 抛出异常 → 仅可重试异常会触发重试；不可重试异常立即传播
    - 全部重试耗尽且均返回 None → 返回 None
    - 全部重试耗尽且最后抛出异常 → 重新抛出
    - 熔断打开 → 立即返回 None（不进入 func）
    - 并发许可获取超时 → 返回 None

    Config（从 config.py 读取）:
        LOOP_RETRY_MAX, LOOP_RETRY_BACKOFF_BASE/MIN/MAX,
        LOOP_CIRCUIT_BREAKER_FAILS/COOLDOWN, LOOP_MAX_CONCURRENCY, LOOP_LLM_TIMEOUT
    """
    import config

    max_retries = config.LOOP_RETRY_MAX
    backoff_base = config.LOOP_RETRY_BACKOFF_BASE
    backoff_min = config.LOOP_RETRY_BACKOFF_MIN
    backoff_max = config.LOOP_RETRY_BACKOFF_MAX

    cb = _get_circuit_breaker()
    sem = _get_semaphore()

    # 1. 熔断检查
    if not cb.before_call():
        return None

    # 2. 并发许可
    timeout_for_slot = config.LOOP_LLM_TIMEOUT + 15
    acquired = sem.acquire(timeout=timeout_for_slot)
    if not acquired:
        logger.error(
            f"[Loop] 并发许可等待超时（max={config.LOOP_MAX_CONCURRENCY}，"
            f"等了 {timeout_for_slot}s）"
        )
        return None

    last_exception: Optional[Exception] = None

    try:
        for attempt in range(max_retries + 1):          # 1 次初始 + N 次重试
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                last_exception = exc
                if not _is_retryable_error(exc):
                    cb.on_failure()
                    logger.warning(f"[Loop] 不可重试异常，立即传播: {exc}")
                    raise

                if attempt < max_retries:
                    delay = _backoff_delay(attempt, backoff_base, backoff_min, backoff_max)
                    logger.warning(
                        f"[Loop] 第{attempt+1}/{max_retries+1}次异常，"
                        f"{delay:.1f}s 后重试: {exc}"
                    )
                    time.sleep(delay)
                    continue

                # 最后一次也异常
                cb.on_failure()
                logger.error(f"[Loop] {max_retries+1} 次全部异常，最后: {exc}")
                raise

            # ── 正常返回（无异常）──
            if result is not None:
                cb.on_success()
                if attempt > 0:
                    logger.info(f"[Loop] 第{attempt+1}次尝试成功（共 {attempt} 次重试）")
                return result

            # result is None ── 视为失败
            if attempt < max_retries:
                delay = _backoff_delay(attempt, backoff_base, backoff_min, backoff_max)
                logger.warning(
                    f"[Loop] 第{attempt+1}/{max_retries+1}次返回空，"
                    f"{delay:.1f}s 后重试"
                )
                time.sleep(delay)

        # 全部重试耗尽，均返回 None
        cb.on_failure()
        logger.error(f"[Loop] {max_retries+1} 次尝试全部返回空")
        return None

    finally:
        sem.release()


# ═══════════════════════════════════════════════════════════════
# 测试辅助
# ═══════════════════════════════════════════════════════════════

def reset_for_testing() -> None:
    """重置全局单例（仅测试用）。"""
    global _circuit_breaker, _semaphore
    _circuit_breaker = None
    _semaphore = None


# ═══════════════════════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import config

    # 配置日志：自测时显示 INFO 及以上
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-5s %(name)s: %(message)s",
    )

    print("=" * 60)
    print("Loop 模块自测")
    print(f"  LOOP_RETRY_MAX           = {config.LOOP_RETRY_MAX}")
    print(f"  LOOP_CIRCUIT_BREAKER_FAILS = {config.LOOP_CIRCUIT_BREAKER_FAILS}")
    print(f"  LOOP_CIRCUIT_BREAKER_COOLDOWN = {config.LOOP_CIRCUIT_BREAKER_COOLDOWN}")
    print(f"  LOOP_MAX_CONCURRENCY     = {config.LOOP_MAX_CONCURRENCY}")
    print(f"  LOOP_LLM_TIMEOUT         = {config.LOOP_LLM_TIMEOUT}")
    print("=" * 60)

    # ── 测试 1：正常调用（首次成功，无重试）─────────────────
    print("\n[测试1] 正常调用（首次成功）")
    reset_for_testing()

    def ok():
        return {"status": "ok"}

    result = retry_with_backoff(ok)
    assert result == {"status": "ok"}, f"失败: {result}"
    print("  [PASS]")

    # ── 测试 2：前 N 次 None，最后一次成功 ─────────────────
    print("\n[测试2] 前2次None → 第3次成功")
    reset_for_testing()
    counter = [0]

    def ok_after_2():
        counter[0] += 1
        if counter[0] < 3:
            return None
        return {"status": "ok"}

    result = retry_with_backoff(ok_after_2)
    assert result == {"status": "ok"}, f"失败: {result}"
    assert counter[0] == 3, f"应调用3次，实际 {counter[0]}"
    print("  [PASS]")

    # ── 测试 3：全部返回 None ────────────────────────────
    print("\n[测试3] 全部None → 最终返回None")
    reset_for_testing()
    result = retry_with_backoff(lambda: None)
    assert result is None, f"期望 None，得到 {result}"
    print("  [PASS]")

    # ── 测试 4：熔断触发 ────────────────────────────────
    print("\n[测试4] 连续失败触发熔断")
    reset_for_testing()
    cb = _get_circuit_breaker()
    # 手动注入失败至阈值
    for i in range(config.LOOP_CIRCUIT_BREAKER_FAILS):
        cb.on_failure()
    assert cb.state == "open", f"期望 open，实际 {cb.state}"
    # 熔断打开后调用应直接返回 None
    called = [False]
    result = retry_with_backoff(lambda: called.__setitem__(0, True) or {"ok": True})
    assert result is None, "熔断打开应返回 None"
    assert not called[0], "熔断打开不应进入 func"
    print("  [PASS]")

    # ── 测试 5：熔断恢复（模拟冷却后探测成功）────────────
    print("\n[测试5] 熔断恢复（half_open 探测成功 → closed）")
    reset_for_testing()
    cb = _get_circuit_breaker()
    # 使用极短冷却时间模拟
    cb._cooldown = 0.01
    for _ in range(config.LOOP_CIRCUIT_BREAKER_FAILS):
        cb.on_failure()
    assert cb.state == "open"
    time.sleep(0.02)  # 等冷却结束
    assert cb.state == "half_open", f"期望 half_open，实际 {cb.state}"
    # 一次成功即可恢复
    result = retry_with_backoff(lambda: {"ok": True})
    assert result == {"ok": True}
    assert cb.state == "closed", f"期望 closed，实际 {cb.state}"
    print("  [PASS]")

    # ── 测试 6：并发控制 ────────────────────────────────
    print("\n[测试6] 并发控制（max=3）")
    reset_for_testing()
    sem = _get_semaphore()
    assert sem.acquire(timeout=0.1), "许可1"
    assert sem.acquire(timeout=0.1), "许可2"
    assert sem.acquire(timeout=0.1), "许可3"
    assert not sem.acquire(timeout=0.1), "许可4应失败"
    sem.release(); sem.release(); sem.release()
    print("  [PASS]")

    # ── 测试 7：不重试错误分类（字符串回退）────────────
    print("\n[测试7] is_retryable_error 分类（字符串匹配）")
    assert _is_retryable_error(Exception("Connection timed out")), "timeout 应可重试"
    assert _is_retryable_error(RuntimeError("503 Service Unavailable")), "503 应可重试"
    assert _is_retryable_error(IOError("connection reset by peer")), "connection reset 应可重试"
    assert not _is_retryable_error(ValueError("401 Unauthorized")), "401 不应重试"
    assert not _is_retryable_error(Exception("invalid api key")), "invalid api key 不应重试"
    # 未知错误默认不重试
    assert not _is_retryable_error(RuntimeError("something weird happened")), "未知错误默认不重试"
    print("  [PASS]")

    print("\n" + "=" * 60)
    print("All self-tests passed.")
    print("=" * 60)
