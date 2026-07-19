"""基础调料白名单策略"""
from typing import List

# 默认基础调料（用户默认拥有的）
DEFAULT_STAPLES: List[str] = [
    "盐", "食用油", "生抽", "老抽", "醋",
    "糖", "料酒", "淀粉", "胡椒粉",
    "葱", "姜", "蒜"
]

# 葱姜蒜可单独控制
AROMATICS = {"葱", "姜", "蒜"}


def get_staples(assume: bool = True,
                include_aromatics: bool = True) -> List[str]:
    """
    返回当前应该视为已有基础调料的列表。
    assume=False 时不假设任何调料。
    include_aromatics=False 时排除葱姜蒜。
    """
    if not assume:
        return []
    staples = list(DEFAULT_STAPLES)
    if not include_aromatics:
        staples = [s for s in staples if s not in AROMATICS]
    return staples


def is_staple(name: str) -> bool:
    """判断食材名是否为基础调料"""
    return name in DEFAULT_STAPLES
