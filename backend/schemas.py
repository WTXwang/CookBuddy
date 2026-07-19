"""
所有 Pydantic 数据模型 —— 前端 ↔ 后端 数据契约
对齐 开发计划.md 第九章 核心数据结构
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ============================================================
# Request
# ============================================================

class RawIngredient(BaseModel):
    raw: str = Field(description="用户原始输入，如'西红柿'")
    name: str = Field(description="标准化名称，如'番茄'")
    quantity: str = Field(default="", description="数量描述，如'2个'")
    category: str = Field(default="", description="类别：蔬菜/肉类/蛋类/豆制品/水产/调料/主食/其他")


class NormalizedRequest(BaseModel):
    """标准化请求 —— normalizer 输出 / coordinator 输入"""
    request_id: str
    ingredients: list[RawIngredient] = Field(default_factory=list)
    servings: int = Field(default=2, ge=1, le=20)
    time_limit_min: int = Field(default=30, ge=1, le=480)
    difficulty: str = Field(default="任意")
    flavor: str = Field(default="")
    excluded_ingredients: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    assume_staples: bool = Field(default=True, description="是否假设用户有基础调料")
    assumed_staples: list[str] = Field(default_factory=list, description="实际可用的基础调料列表")


class RecommendRequest(BaseModel):
    """前端 POST /api/recommend 的原始请求"""
    ingredients_text: str = Field(default="", description="用户自然语言食材输入")
    servings: int = Field(default=2)
    time_limit_min: int = Field(default=20)
    difficulty: str = Field(default="简单")
    flavor: str = Field(default="")
    excluded: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)


class UserRequest(BaseModel):
    """B → A 统一数据契约 —— 8 字段，B 只拆词，A 负责标准化和匹配"""
    ingredients: list[str] = Field(default_factory=list, description="食材名称列表（B只分词不标准化，A负责别名映射）")
    excluded: list[str] = Field(default_factory=list, description="忌口食材")
    allergens: list[str] = Field(default_factory=list, description="过敏原")
    equipment: list[str] = Field(default_factory=list, description="可用厨具")
    servings: int = Field(default=2, ge=1, le=20, description="用餐人数")
    difficulty: str = Field(default="任意", description="难度要求：任意/简单/中等/困难")
    time_limit_min: int = Field(default=30, ge=1, le=480, description="时间限制（分钟）")
    flavor: str = Field(default="", description="口味偏好，如：不辣、清淡、重口味")


# ============================================================
# Knowledge Base / Recipe
# ============================================================

class RecipeRecord(BaseModel):
    """知识库中的一道菜谱（对应 .md 文件 YAML 头部）"""
    recipe_id: str
    title: str
    cuisine: str = Field(default="家常菜")
    tags: list[str] = Field(default_factory=list)
    difficulty: str = "简单"
    estimated_time_min: int = 30
    servings: int = 2
    core_ingredients: list[str] = Field(default_factory=list)
    seasonings: list[str] = Field(default_factory=list)
    optional_ingredients: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    image_url: str = ""
    version: str = "1.0"

    # 正文内容（检索召回时填充）
    body: str = Field(default="", description="菜谱正文：用量、准备、步骤、替代、注意事项")
    retrieval_score: float = Field(default=0.0)


# ============================================================
# Intermediate (graph internal)
# ============================================================

class CandidateFeature(BaseModel):
    """匹配 Agent 输出的候选特征 —— 用于评分排序"""
    recipe_id: str
    retrieval_score: float = 0.0
    core_total: int = 0
    core_matched: int = 0
    missing_core: list[str] = Field(default_factory=list)
    missing_optional: list[str] = Field(default_factory=list)
    preference_score: float = 0.0      # 0~1 口味匹配度
    time_fit: float = 0.0              # 0~1 时间符合度
    difficulty_fit: float = 0.0        # 0~1 难度符合度
    equipment_fit: float = 0.0         # 0~1 厨具符合度
    blocked: bool = False
    block_reasons: list[str] = Field(default_factory=list)
    final_score: int = 0               # 最终评分（scorer 填充）


class SafetyReport(BaseModel):
    """安全审查 Agent 输出"""
    passed: bool
    severity: str = "none"   # none / warning / blocked
    issues: list[str] = Field(default_factory=list)
    revision_suggestions: list[str] = Field(default_factory=list)


# ============================================================
# Response
# ============================================================

class Recommendation(BaseModel):
    """单道推荐菜"""
    recipe_id: str
    title: str
    image_url: str = ""
    match_score: int = 0
    match_label: str = ""
    estimated_time_min: int = 30
    difficulty: str = "简单"
    servings: int = 2
    used_ingredients: list[str] = Field(default_factory=list)
    missing_core: list[str] = Field(default_factory=list)
    missing_optional: list[str] = Field(default_factory=list)
    reason: str = ""
    prep: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    heat_tips: str = ""
    substitutions: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class RequestSummary(BaseModel):
    ingredients: list[str] = Field(default_factory=list, description="标准化后的食材名称列表")
    servings: int = 2
    assumed_staples: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    request_summary: RequestSummary = Field(default_factory=RequestSummary)
    recommendations: list[Recommendation] = Field(default_factory=list)
    blocked_recipes: list[dict] = Field(default_factory=list)
    follow_up_question: Optional[str] = None
    trace_id: str = ""


# ============================================================
# LangGraph State
# ============================================================

class Intent(str, Enum):
    RECOMMEND = "recommend"
    LOOKUP = "lookup"          # 按菜名查做法
    SUBSTITUTE = "substitute"  # 找替代食材
    OTHER = "other"            # 超出能力范围


class GraphStage(str, Enum):
    """工作流各阶段"""
    INIT = "init"
    NORMALIZE = "normalize"
    CATEGORIZE = "categorize"
    RETRIEVE = "retrieve"
    MATCH = "match"
    SCORE = "score"
    GUIDE = "guide"
    SAFETY = "safety"
    OUTPUT = "output"
    ERROR = "error"


class ChefState(BaseModel):
    """LangGraph 全局状态"""
    # 输入
    raw_input: str = ""
    request: Optional[NormalizedRequest] = None

    # 意图
    intent: Intent = Intent.RECOMMEND

    # 中间结果
    candidates: list[RecipeRecord] = Field(default_factory=list)
    features: list[CandidateFeature] = Field(default_factory=list)

    # 输出
    response: Optional[RecommendationResponse] = None

    # 流程控制
    stage: GraphStage = GraphStage.INIT
    error: str = ""
    revision_count: int = 0
    stage_durations: dict = Field(default_factory=dict)

    # 用户约束（从 request 展开供各节点使用）
    user_allergens: list[str] = Field(default_factory=list)
    user_excluded: list[str] = Field(default_factory=list)
    user_equipment: list[str] = Field(default_factory=list)
    user_flavor: str = ""
    user_time_limit: int = 30
    user_servings: int = 2
