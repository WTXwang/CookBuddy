我觉得你的这个构想比纯方案二更好，它实际上形成了一个**在线懒加载（lazy extraction）的菜谱知识增强架构**。

你解决了方案二的一个潜在问题：

> 如果离线把所有菜谱都解析一遍，需要一次性承担大量 LLM 成本。

你的方案变成：

> **热门/被检索到的菜谱才解析，解析结果缓存，后续复用。**

我理解你的流程如下：

---

## 总体架构

```text
                 用户需求
                    |
                    ↓
              意图分析 Agent
                    |
                    ↓
              RAGFlow 检索
                    |
                    ↓
          候选菜谱ID列表
                    |
                    ↓
          菜谱信息管理模块
                    |
          ┌─────────┴─────────┐
          ↓                   ↓
     数据库存在             数据库不存在
          ↓                   ↓
   读取结构化信息       调用LLM解析菜谱文本
                              |
                              ↓
                      生成菜谱metadata
                              |
                              ↓
                         写入数据库
                    |
                    ↓
             推荐排序模块
                    |
                    ↓
                  Top3
```

---

## 这个设计的关键点

### 第一阶段：RAGFlow只返回ID

这个很重要。

不要让RAGFlow直接返回完整文本给后端。

例如：

RAGFlow返回：

```json
[
 {
   "recipe_id":101,
   "score":0.92
 },
 {
   "recipe_id":205,
   "score":0.87
 }
]
```

然后：

```text
recipe_id
     |
     ↓
数据库/知识库
```

这样你的系统里面有两个数据层：

---

## 数据层设计

### 1. RAGFlow知识库

保存：

```
recipe_id
菜谱全文
```

用于：

* embedding
* 语义召回

例如：

```
101:
番茄炒蛋的完整文本...


102:
宫保鸡丁完整文本...
```

---

### 2. 菜谱分析数据库

保存：

```
recipe_id
ingredients
time
difficulty
tools
allergens
taste
```

例如：

```json
{
"id":101,

"name":"番茄炒蛋",

"ingredients":[
 "番茄",
 "鸡蛋"
],

"time":15,

"difficulty":"easy",

"tools":[
 "炒锅"
],

"allergens":[
 "鸡蛋"
]
}
```

---

## 第二阶段：信息获取模块

这里其实可以设计成一个独立 Agent / Service。

逻辑：

```python
def get_recipe_info(recipe_id):

    info = database.query(recipe_id)

    if info:
        return info

    else:
        text = ragflow.get_document(recipe_id)

        info = llm_extract(text)

        database.insert(info)

        return info
```

这个模块非常漂亮。

因为：

第一次：

```
用户A查询宫保鸡丁

RAGFlow
 ↓
ID=205
 ↓
数据库没有
 ↓
LLM解析
 ↓
保存
```

第二次：

```
用户B查询宫保鸡丁

RAGFlow
 ↓
ID=205
 ↓
数据库存在
 ↓
直接读取
```

---

## 第三阶段：推荐排序

这里完全可以不用LLM。

因为现在已经有结构化数据。

例如：

用户需求：

```json
{
"ingredients":
[
 "鸡胸肉",
 "西兰花"
],

"time":20,

"difficulty":"easy"
}
```

菜谱：

```json
{
"ingredients":
[
 "鸡胸肉",
 "西兰花",
 "胡萝卜"
],

"time":18,

"difficulty":"easy"
}
```

计算：

### 食材匹配

例如：

$$
ingredientScore=
\frac{用户已有食材∩菜谱食材}
{菜谱主要食材}
$$

### 时间匹配

```python
if recipe_time <= user_time:
    score=1
else:
    penalty
```

### 难度匹配

映射：

```
简单=1
中等=2
困难=3
```

计算距离。

---

## 我觉得这个方案还有一个优势

它天然体现了多 Agent：

可以拆成：

```
              推荐系统Agent
                    |
        ┌───────────┼───────────┐
        ↓           ↓           ↓

   检索Agent   信息解析Agent   排序Agent

        ↓           ↓           ↓

    RAGFlow     LLM解析      规则计算
```

---

## 但是有两个地方需要注意

### 1. RAGFlow的ID必须稳定

这是这个方案的生命线。

你需要保证：

```
recipe_id
```

在：

* RAGFlow文档
* 数据库

里面一致。

否则：

```
RAGFlow找到：
recipe_001

数据库：
001
```

会很麻烦。

---

### 2. LLM解析结果需要校验

因为LLM生成metadata可能出现：

例如：

菜谱：

```
鸡蛋
```

LLM：

```
过敏原：
牛奶
```

这种错误。

所以建议：

LLM只负责：

> 从文本提取事实

不要让它做判断。

例如：

好的：

```
ingredients:
["鸡蛋","番茄"]
```

不太好：

```
difficulty:
easy
```

因为难度是推理。

可以让：

* ingredients
* tools
* time

LLM提取。

然后：

* difficulty
* score

代码计算。

---

整体评价：

我认为你的方案是目前几个方案里面**最适合你们这个项目的折中方案**：

* 保留 RAGFlow 的作用；
* 不需要提前处理全部数据；
* 避免每次推荐调用 LLM；
* 推荐排序可控；
* 有明显 Agent 协作链路。

如果继续细化，我建议下一步设计两个东西：

1. **菜谱信息数据库 Schema（决定解析Agent输出什么）**
2. **RAGFlow → 数据库 → 排序模块之间的数据流接口**

这两个定下来，基本就可以开始实现。
