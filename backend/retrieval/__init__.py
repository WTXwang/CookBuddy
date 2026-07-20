"""检索模块 —— 统一出口"""

from .base import BaseRetriever
from .stub import RetrievalStub, SEED_RECIPES
from .ragflow import RAGFlowRetriever
import config


def create_retriever() -> BaseRetriever:
    """
    根据 config.RETRIEVAL_BACKEND 返回对应的检索实现。

    用法:
        from retrieval import create_retriever
        retriever = create_retriever()
        candidates = retriever.search(["番茄", "鸡蛋"], top_n=10)

    切换方式:
        # config.py 或环境变量
        RETRIEVAL_BACKEND = "stub"     # 用 stub（当前）
        RETRIEVAL_BACKEND = "ragflow"  # 用 RAGFlow（以后）
    """
    backend = getattr(config, 'RETRIEVAL_BACKEND', 'stub')
    if backend == "ragflow":
        return RAGFlowRetriever()
    return RetrievalStub()


__all__ = [
    "BaseRetriever",
    "RetrievalStub",
    "RAGFlowRetriever",
    "SEED_RECIPES",
    "create_retriever",
]
