# 角色A 工作报告

## 职责

后端规则管线：纯 Python 逻辑，不调 LLM。

```
B(LLM分析) → RecommendRequest → A.run_pipeline() → list[RecipeRecord] → B(继续)
```

---

## 输入

**角色B 传来 `RecommendRequest`：**

```json
{
  "ingredients_text": "西红柿、鸡蛋2个",
  "servings": 2,
  "time_limit_min": 20,
  "difficulty": "简单",
  "flavor": "不辣",
  "allergens": ["花生"],
  "excluded": [],
  "equipment": ["炒锅"]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `ingredients_text` | `str` | 原始食材文本，A 负责从中提取食材名并标准化 |
| `servings` | `int` | 用餐人数 |
| `time_limit_min` | `int` | 时间限制（分钟） |
| `difficulty` | `str` | 难度偏好：简单 / 中等 / 困难 / 任意 |
| `flavor` | `str` | 口味偏好：辣 / 不辣 / 酸 / 甜 / 清淡 / "" |
| `allergens` | `list[str]` | 过敏原，命中则硬阻断 |
| `excluded` | `list[str]` | 忌口食材，命中则硬阻断 |
| `equipment` | `list[str]` | 用户可用厨具 |

---

## 输出

**返回 `list[RecipeRecord]` 给角色B：**

```json
[
  {
    "recipe_id": "R001",
    "title": "番茄炒蛋",
    "cuisine": "家常菜",
    "tags": ["快手菜", "下饭菜", "鸡蛋类"],
    "difficulty": "简单",
    "estimated_time_min": 15,
    "servings": 2,
    "core_ingredients": ["番茄", "鸡蛋"],
    "seasonings": ["食用油", "盐", "糖"],
    "optional_ingredients": ["葱"],
    "equipment": ["炒锅"],
    "allergens": ["鸡蛋"],
    "body": "",
    "retrieval_score": 94.0
  }
]
```

| 字段 | 说明 |
|---|---|
| `recipe_id`, `title` | 菜谱标识和名称 |
| `core_ingredients` | 核心食材（缺了做不了） |
| `optional_ingredients` | 可选食材（缺了也能做） |
| `seasonings` | 所需调料 |
| `equipment` | 所需厨具 |
| `allergens` | 过敏原 |
| `difficulty`, `estimated_time_min` | 难度和预计时间 |
| `body` | 菜谱做法正文（RAGFlow 时填充，stub 时为空） |
| `retrieval_score` | 最终评分（0-100），已排序 |

- 过敏原/忌口冲突的菜 **不返回**（硬阻断）
- 缺核心食材越少越靠前
- 厨具匹配的优先

---

## 内部流程

```
RecommendRequest
  │
  ├─ split_ingredients_text()    解析食材文本 → 食材名列表
  ├─ normalize_ingredients()     别名映射 + 去重 + 分类
  ├─ retriever.search()         关键词精确匹配（stub）或向量检索（RAGFlow）
  ├─ build_feature()            硬过滤 + 软约束评分
  ├─ score_and_rank()           公式打分 + 排序
  │
  └─ list[RecipeRecord]
```

**评分公式：**
```
Base   = 45×核心覆盖率 + 15×检索分 + 10×口味 + 10×时间 + 5×难度 + 15×厨具比例
Penalty = 25×核心缺失比例 + (超时+10)
Final   = clamp(Base-Penalty, 0, 100)
```

**排序规则：** 缺核心少优先 → 厨具匹配优先 → 分高优先 → 检索分高优先

**硬阻断：** 过敏原冲突 / 忌口冲突 → 直接从结果中移除

---

## 文件清单

### 新建文件

| 文件 | 说明 |
|---|---|
| `rules/pipeline.py` | A 线统一入口 `run_pipeline()` |
| `retrieval/base.py` | `BaseRetriever` 抽象接口 |
| `retrieval/ragflow.py` | RAGFlow 向量检索，未就绪时自动降级 stub |
| `retrieval/__init__.py` | `create_retriever()` 工厂函数 |
| `tests/__init__.py` | 测试包 |
| `tests/test_normalizer.py` | 32 项 |
| `tests/test_staples.py` | 11 项 |
| `tests/test_scorer.py` | 25 项 |
| `tests/test_retrieval.py` | 14 项 |
| `test_a.py` | 角色A 独立交互测试脚本 |
| `test_batch.py` | 16 场景批量测试 |
| `play.py` | 交互式沙盒（输出 B 接收格式） |
| `scripts/probe_ragflow.py` | RAGFlow API 探测工具 |

### 修改文件

| 文件 | 改动 |
|---|---|
| `rules/normalizer.py` | 新增 `parse_ingredients_text()`、`split_ingredients_text()`、数量解析、别名扩充至 144 条 |
| `rules/scorer.py` | 新增 `difficulty_fit`、过敏/忌口硬阻断、厨具优先级、设备比例评分 |
| `retrieval/stub.py` | 实现 `BaseRetriever`、修复子串匹配 bug、精确匹配 |
| `schemas.py` | `CandidateFeature` 新增 `difficulty_fit` |
| `config.py` | 新增 `RETRIEVAL_BACKEND` + RAGFlow 配置项 |
| `graph.py` | `RetrievalStub()` → `create_retriever()` |
| `test_demo.py` | 同上 |
| `app.py` | 同上 |

---

## 测试

```bash
# 自动化（82 项）
python -X utf8 -m pytest tests/ -v

# 批量场景（16 个）
python -X utf8 test_batch.py

# 交互沙盒
python -X utf8 play.py

# B 调用方式
python -X utf8 -c "from schemas import RecommendRequest; from rules.pipeline import run_pipeline; ..."
```
