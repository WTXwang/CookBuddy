"""staples 单元测试"""
import pytest
from rules.staples import get_staples, is_staple, DEFAULT_STAPLES, AROMATICS


class TestDefaultStaples:
    """默认调料白名单"""

    def test_default_count(self):
        """默认至少 12 项"""
        assert len(DEFAULT_STAPLES) >= 12

    def test_aromatics_in_staples(self):
        """葱姜蒜在白名单中"""
        for a in AROMATICS:
            assert a in DEFAULT_STAPLES, f"{a} 应该在默认调料中"

    def test_essential_staples(self):
        """基础调料必须存在"""
        essentials = ["盐", "食用油", "生抽"]
        for e in essentials:
            assert e in DEFAULT_STAPLES, f"{e} 缺失"


class TestGetStaples:
    """获取调料列表"""

    def test_default_all(self):
        """默认返回全部"""
        result = get_staples()
        assert len(result) == len(DEFAULT_STAPLES)

    def test_no_assume(self):
        """assume=False 返回空"""
        result = get_staples(assume=False)
        assert result == []

    def test_exclude_aromatics(self):
        """排除葱姜蒜"""
        result = get_staples(include_aromatics=False)
        for a in AROMATICS:
            assert a not in result
        assert "盐" in result  # 普通调料不受影响

    def test_both_false(self):
        """assume=False 时 aromatics 参数无关"""
        result = get_staples(assume=False, include_aromatics=True)
        assert result == []


class TestIsStaple:
    """判断是否为调料"""

    def test_known_staples(self):
        assert is_staple("盐") is True
        assert is_staple("食用油") is True
        assert is_staple("生抽") is True
        assert is_staple("葱") is True
        assert is_staple("姜") is True
        assert is_staple("蒜") is True

    def test_non_staples(self):
        assert is_staple("番茄") is False
        assert is_staple("鸡蛋") is False
        assert is_staple("牛肉") is False
        assert is_staple("火星石") is False
