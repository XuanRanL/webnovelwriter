# Webnovel Writer Story System Pro Max 架构改造 Spec

> 日期：2026-04-12
> 状态：草案 v1
> 目标：在不破坏现有 `reference_search.py` 与 CSV 检索契约的前提下，为 Webnovel Writer 增加“题材推理 + 多表聚合 + Master/Chapter 持久化覆盖”能力。

---

## 1. 文档定位

### 1.1 与既有 spec 的关系

本 spec 是以下文档的补充，不替代它们：

- `2026-04-02-harness-v6-design.md`
- `2026-04-09-skills-restructure-and-reference-gaps.md`

其中：

- `2026-04-02-harness-v6-design.md` 负责主流程与 harness 架构。
- `2026-04-09-skills-restructure-and-reference-gaps.md` 负责 `skills / references / scripts` 的职责边界与 reference 设计原则。
- **本 spec** 负责在现有 CSV 知识库之上，补出一个新的系统层：`Story System`。

### 1.2 本 spec 要解决的问题

当前系统已经能做离散检索，但仍存在三个结构性问题：

1. 检索结果是“散条目”，不是“系统设定”。
2. 大模型看完单次搜索结果后，容易遗忘全局约束与毒点。
3. 不同章节缺少稳定的“局部覆盖全局”的持久化承载方式。

因此需要引入一个新的上层能力：

- 先做题材/流派层面的全局路由
- 再做多表聚合
- 最后持久化为 `MASTER + Chapter Overrides`

---

## 2. 目标与非目标

### 2.1 目标

本轮改造目标只有五个：

1. 新增一张“题材与调性推理”路由表，用来把模糊题材输入转成结构化写作方向。
2. 新增 `story_system.py`，作为现有 CSV 检索之上的聚合器。
3. 定义 `StorySystemDict` 的稳定数据契约。
4. 建立 `.story-system/` 的持久化规范，并明确 `Master + Overrides` 的覆盖规则。
5. 为后续 skills / prompt 集成预留稳定挂点。

### 2.2 非目标

本轮**不做**以下事情：

1. 不替换或改写现有 `reference_search.py` 的职责。
2. 不把所有 md reference 全量迁入 CSV。
3. 不强制把所有现有 CSV 表的毒点字段改成同一个列名。
4. 不在本 spec 中假定某个具体 `SKILL.md` 文件一定存在于当前仓库。
5. 不要求重型测试矩阵，也不要求对每个知识点逐条写测试。

---

## 3. 设计原则

### 3.1 保留底层检索 primitive

[`reference_search.py`](D:/wk/novel%20skill/webnovel-writer/webnovel-writer/scripts/reference_search.py) 当前已经稳定承担以下职责：

- 读取 CSV
- 按 `skill / table / query / genre` 过滤
- 做 BM25-lite 评分
- 返回稳定 JSON envelope

该脚本已有回归测试保护，见：

- [`test_reference_search.py`](D:/wk/novel%20skill/webnovel-writer/webnovel-writer/scripts/tests/test_reference_search.py)

因此本轮不应把它改造成系统级聚合器。正确分层应为：

- `reference_search.py`：底层单次搜索 primitive
- `story_system.py`：系统级 orchestration 与持久化入口

### 3.2 不强推现有表结构大改

现有 CSV 契约已在 [`README.md`](D:/wk/novel%20skill/webnovel-writer/webnovel-writer/references/csv/README.md) 中明确，当前内容量也已经较大。

本轮应坚持：

- **新增优于重写**
- **映射优于大规模改列名**
- **只对真正缺失的能力加新结构**

### 3.3 Master 与 Chapter 必须可机读

如果 `.story-system/` 只保存“给人看的 markdown”，后续 agent 仍需要再次解析半结构化文本，容易变脆。

因此本轮持久化必须采用**双产物**：

- Markdown：给人读
- JSON：给脚本和 agent 读

### 3.4 覆盖规则必须显式，不允许模糊覆盖

不能只写“chapter 覆盖 master”。

必须把字段分成三类：

1. `locked`：禁止局部覆盖
2. `append_only`：局部只能补充
3. `override_allowed`：局部允许覆盖

否则局部设定会轻易冲掉全局设定与全局红线。

### 3.5 Anti-Patterns 只做归一化聚合，不做强行同名

现有各表的“毒点/误区”字段不统一，例如：

- `场景写法.csv`：`反面写法`
- `写作技法.csv`：`常见误区`
- `爽点与节奏.csv`：`常见崩盘误区`
- `人设与关系.csv`：`忌讳写法`

这本身没有问题。

本轮正确做法是：

- 在 `story_system.py` 内建立 anti-pattern source field 映射
- 在渲染阶段统一归一化为 `Anti-Patterns`
- 只对真正缺失毒点承载的表，新增专门字段

---

## 4. 当前基线

### 4.1 当前可用 CSV 表

当前 `references/csv` 中已存在：

- `命名规则.csv`
- `场景写法.csv`
- `写作技法.csv`
- `桥段套路.csv`
- `人设与关系.csv`
- `爽点与节奏.csv`
- `金手指与设定.csv`

### 4.2 当前 CSV 通用契约

现有通用列已稳定：

- `编号`
- `适用技能`
- `分类`
- `层级`
- `关键词`
- `意图与同义词`
- `适用题材`
- `大模型指令`
- `核心摘要`
- `详细展开`

因此新增表应继续遵守这个契约，而不是重新发明一套列体系。

### 4.3 当前缺失能力

当前系统缺失的不是“知识量”，而是以下能力：

1. 对模糊题材输入做全局路由的能力
2. 在多张表之间做分层聚合的能力
3. 把聚合结果稳定落地为章节级覆盖文档的能力

---

## 5. 新增数据结构：题材与调性推理.csv

### 5.1 文件位置

新增文件：

- `webnovel-writer/references/csv/题材与调性推理.csv`

建议前缀：

- `GR-`

### 5.2 文件职责

这不是普通知识条目表，而是**路由表**。

它的职责不是提供某一个桥段/某一种技法，而是回答：

- 这个题材的大基调是什么
- 这个题材的节奏应该怎么起
- 这个题材优先查哪些基础表
- 这个题材优先查哪些动态表
- 这个题材绝对不能碰哪些毒点

### 5.3 列设计

除通用列外，新增以下专属列：

| 列名 | 必填 | 说明 |
|------|------|------|
| `题材/流派` | 是 | 主标签，如“赘婿流”“赛博朋克黑客流”“规则动物园” |
| `题材别名` | 是 | 同义词、平台黑话、俗称，使用 `|` |
| `核心调性` | 是 | 全局情绪与气质 |
| `节奏策略` | 是 | 开局节奏、兑现节奏、章节节拍 |
| `主冲突模板` | 否 | 默认冲突骨架 |
| `必选爽点` | 否 | 该题材高频必备交付 |
| `强制禁忌/毒点` | 是 | 题材级全局红线 |
| `推荐基础检索表` | 是 | 如 `命名规则|人设与关系|金手指与设定` |
| `推荐动态检索表` | 是 | 如 `桥段套路|爽点与节奏|场景写法` |
| `基础检索权重` | 否 | 对基础表的排序提示 |
| `动态检索权重` | 否 | 对动态表的排序提示 |
| `默认查询词` | 否 | 当用户输入过于模糊时的默认扩展检索词 |

### 5.4 设计说明

这张表必须能同时服务三类输入：

1. 明确题材输入
   例如：`赘婿流`

2. 组合题材输入
   例如：`赛博朋克黑客流`

3. 模糊风格输入
   例如：`压抑一点，后面爆`

因此 `题材别名` 和 `默认查询词` 是必要字段，不是可有可无。

---

## 6. Anti-Patterns 归一化规则

### 6.1 现有表的归一化映射

本轮不强制全表改名，采用映射层：

```python
ANTI_PATTERN_SOURCE_FIELDS = {
    "场景写法": ["反面写法"],
    "写作技法": ["常见误区"],
    "爽点与节奏": ["常见崩盘误区"],
    "人设与关系": ["忌讳写法"],
    "桥段套路": ["忌讳写法"],
    "题材与调性推理": ["强制禁忌/毒点"],
}
```

### 6.2 桥段套路.csv 的处理

当前 `桥段套路.csv` 只有：

- `桥段名称`
- `前置铺垫`
- `核心爽点`
- `转折设计`
- `反套路变种`

其中 `反套路变种` 不是 anti-pattern 字段，不能直接拿来当“毒点”。

因此本轮建议：

- 为 `桥段套路.csv` **新增** `忌讳写法` 列
- 新录入条目逐步补齐
- 老条目允许暂时为空

### 6.3 最终聚合规则

系统渲染时的 `Anti-Patterns` 为以下内容的并集：

1. `题材与调性推理.csv` 的全局毒点
2. 动态检索命中的条目级毒点
3. Chapter 局部追加毒点

注意：

- Chapter 可以**新增**局部毒点
- Chapter 不能删除 Master 的全局毒点

---

## 7. 新增脚本：story_system.py

### 7.1 文件位置

新增：

- `webnovel-writer/scripts/story_system.py`

### 7.2 角色定位

`story_system.py` 是系统聚合层，不是底层检索层。

它负责：

1. 题材路由
2. 多表查询编排
3. 结果聚合
4. Markdown / JSON 双格式输出
5. `.story-system/` 持久化

它不负责：

1. 替代 `reference_search.py`
2. 直接生成正文
3. 解析或执行具体 skill 主流程

### 7.3 CLI 设计

建议 CLI：

```bash
python story_system.py "玄幻退婚流"
python story_system.py "玄幻退婚流" --persist
python story_system.py "拍卖会打脸" --persist --chapter chapter_015
python story_system.py "压抑一点，后面爆" --genre 现言 --persist
python story_system.py "规则动物园" --format json
```

建议参数：

| 参数 | 必填 | 说明 |
|------|------|------|
| 位置参数 `query` | 是 | 用户当前意图或题材描述 |
| `--genre` | 否 | 手动指定题材 |
| `--chapter` | 否 | 章节 override 名，如 `chapter_015` |
| `--persist` | 否 | 是否写入 `PROJECT_ROOT/.story-system/` |
| `--format` | 否 | `markdown` / `json` / `both` |
| `--csv-dir` | 否 | 兼容测试与自定义目录 |
| `--story-root` | 否 | 指定显式 `.story-system/` 目录；仅开发/测试场景使用，主链运行时默认基于 `PROJECT_ROOT` 解析 |

### 7.4 主流程

`story_system.py` 的执行顺序应固定为：

#### Step 1：题材推理

输入 `query` 后，优先查 `题材与调性推理.csv`：

- 若命中明确题材 → 使用题材路由结果
- 若命中多个题材 → 做加权排序并返回主路由 + 候选路由
- 若未命中 → 进入 fallback

#### Step 2：fallback 路由

未命中时，按以下顺序降级：

1. 用户手动传入 `--genre` 时，以 `--genre` 为主
2. 从 `query` 中抽取与现有各表高频关键词最接近的题材名
3. 若仍失败，进入“通用写作路由”：
   - 基础表默认查：`命名规则|人设与关系|金手指与设定`
   - 动态表默认查：`桥段套路|爽点与节奏|场景写法`

#### Step 3：基础表检索

根据题材路由表给出的 `推荐基础检索表`：

- 对每张基础表取 Top 1
- 基础表默认包括：
  - `命名规则`
  - `人设与关系`
  - `金手指与设定`
  - 未来可扩展：`题材与调性推理`

#### Step 4：动态表检索

根据题材路由表给出的 `推荐动态检索表`：

- 对每张动态表取 Top 2
- 动态表默认包括：
  - `桥段套路`
  - `爽点与节奏`
  - `场景写法`
  - 可选补充：`写作技法`

#### Step 5：Anti-Patterns 聚合

把题材级毒点和条目级误区字段做统一归并。

#### Step 6：渲染与持久化

输出：

- `StorySystemDict`
- Markdown 视图
- 可选写入 `.story-system/`

---

## 8. StorySystemDict 数据契约

### 8.1 顶层结构

建议数据结构：

```json
{
  "meta": {},
  "route": {},
  "master_constraints": {},
  "base_context": {},
  "dynamic_context": {},
  "anti_patterns": [],
  "override_policy": {},
  "source_trace": []
}
```

### 8.2 详细字段

#### `meta`

记录：

- 查询词
- 显式题材
- 推理命中题材
- 是否 chapter 模式
- 生成时间

#### `route`

记录：

- 主路由题材
- 候选题材
- 路由命中依据
- 推荐基础表
- 推荐动态表

#### `master_constraints`

记录全局不可轻易改动的内容：

- 核心调性
- 节奏策略
- 主冲突模板
- 金手指硬限制
- 主角硬约束
- 全局毒点

#### `base_context`

保存基础表检索结果：

- `命名规则`
- `人设与关系`
- `金手指与设定`
- 可选 `写作技法`

#### `dynamic_context`

保存动态表检索结果：

- `桥段套路`
- `爽点与节奏`
- `场景写法`

#### `anti_patterns`

统一格式：

```json
[
  {
    "source_table": "爽点与节奏",
    "source_id": "PA-054",
    "text": "质疑太弱没有压迫"
  }
]
```

#### `override_policy`

显式写出：

- `locked`
- `append_only`
- `override_allowed`

#### `source_trace`

记录本次命中的来源：

- 表名
- 编号
- 摘要
- 指令

这部分主要用于调试和回溯。

---

## 9. Markdown Formatter 规范

### 9.1 输出目标

Markdown 不是原始数据，而是人类和 agent 的可读视图。

它必须做到：

1. 有明显层次
2. 一眼能看见全局基调
3. 一眼能看见本章覆盖项
4. 一眼能看见绝对毒点

### 9.2 建议结构

建议 Markdown 输出结构：

```markdown
# Story System

## Meta

## Route

## Master Constraints

## Base Context

## Dynamic Context

## Anti-Patterns

## Source Trace
```

### 9.3 Anti-Patterns 章节要求

必须保留一个显著章节：

```markdown
## Anti-Patterns（绝对毒点，切勿触碰）
```

展示规则：

- 每条红线单独成条
- 用反引号包裹短句
- 标明来源表与编号

例如：

```markdown
- `严禁配角连续抢戏超过 300 字`（来源：GR-003）
- `打脸节奏不能缺最后一拍补刀`（来源：PA-054）
```

### 9.4 JSON 与 Markdown 的关系

规则必须明确：

- JSON 是真实源数据
- Markdown 是 JSON 的投影视图
- 任何覆盖合并逻辑以 JSON 为准，不以 Markdown 反向解析为准

---

## 10. 持久化架构：.story-system

### 10.1 目录结构

这里必须遵守项目现有运行时目录术语，而不是使用当前源码仓库目录做推断：

1. `CLAUDE_PLUGIN_ROOT`
   - 插件安装目录
   - 存放 `skills / scripts / references`
   - 不写入书项目数据
2. `WORKSPACE_ROOT`
   - Claude 工作区根目录
   - 通过 `.claude/.webnovel-current-project` 指针解析当前书项目
3. `PROJECT_ROOT`
   - 真实书项目根目录
   - 定义为：包含 `.webnovel/state.json` 的目录

因此 `.story-system/` 的默认落盘位置必须是：

- `PROJECT_ROOT/.story-system/`

而不是：

- 当前源码仓库目录
- `CLAUDE_PLUGIN_ROOT`
- `WORKSPACE_ROOT`

建议目录：

```text
PROJECT_ROOT/
  .webnovel/
  正文/
  大纲/
  设定集/
  .story-system/
    MASTER_SETTING.md
    MASTER_SETTING.json
    chapters/
      chapter_001.md
      chapter_001.json
      chapter_015.md
      chapter_015.json
```

运行时约束补充：

1. skills 默认从 `WORKSPACE_ROOT` 出发
2. 统一经 `webnovel.py --project-root "${WORKSPACE_ROOT}" where` 解析到真实 `PROJECT_ROOT`
3. `story_system` 若进入主链，应只认解析后的 `PROJECT_ROOT`
4. `--story-root` 只作为开发期 override，不应成为 skills 的默认输入

### 10.2 MASTER 的职责

`MASTER_SETTING.*` 负责保存：

- 题材主路由
- 全局调性
- 主角硬约束
- 金手指硬约束
- 世界级约束
- 长线节奏策略
- 全局 anti-patterns

### 10.3 Chapter 的职责

`chapters/chapter_xxx.*` 负责保存：

- 本章桥段
- 本章场景
- 本章局部节奏
- 本章局部额外毒点
- 本章特殊强调项

### 10.4 覆盖分类

#### 10.4.1 `locked`

以下内容只能从 Master 读取，chapter 不允许覆盖：

- 主路由题材
- 核心调性
- 主角底层人设
- 金手指硬限制
- 世界规则闭环
- 全局 anti-patterns

#### 10.4.2 `append_only`

以下内容 chapter 只能补充，不可删除 master 已有内容：

- 命名语系
- 长线伏笔
- 长线关系提醒
- 全局禁区补充
- 重要 source trace

合并方式：

- 并集
- 去重

#### 10.4.3 `override_allowed`

以下内容 chapter 可覆盖 master 默认值：

- 本章桥段
- 本章场景
- 本章节奏目标
- 本章局部情绪侧重
- 本章输出重点

### 10.5 Anti-Patterns 合并规则

最终写作时生效的红线为：

```text
生效红线 = Master 全局红线 ∪ Chapter 局部红线
```

注意：

- Chapter 可以加新红线
- Chapter 不能移除 Master 红线

### 10.6 文件更新策略

为避免覆盖人工修改，本轮建议采用以下策略：

1. JSON 文件由脚本完全管理
2. Markdown 文件可带人工备注区
3. 脚本只更新带 marker 的自动生成区块

建议 marker：

```markdown
<!-- STORY-SYSTEM:BEGIN -->
... 自动生成内容 ...
<!-- STORY-SYSTEM:END -->
```

marker 外的手写内容，脚本不得改动。

---

## 11. Prompt / Skill 集成契约

### 11.1 本轮只定义契约，不假定具体挂点

当前仓库中未直接暴露可改的 `webnovel-plan` / `webnovel-write` 的 `SKILL.md` 文件落点。

因此本 spec 不假定：

- prompt 一定在本仓库
- skill 一定在本仓库
- 运行时一定从哪个路径自动读取

本轮只定义**接入契约**。

### 11.2 标准读取逻辑

未来接入层必须满足：

1. 如果存在 `chapters/[当前章节].json`，优先读取它。
2. 对于 `override_allowed` 字段，chapter 优先。
3. 对于 `append_only` 字段，chapter 与 master 合并。
4. 对于 `locked` 字段，只能读取 master。
5. 最终始终附带全局与局部合并后的 `Anti-Patterns`。

### 11.3 标准提示词片段

接入层建议使用如下约束：

```markdown
【核心状态读取逻辑】
1. 若存在 `.story-system/chapters/[当前章节].json`，先读 chapter。
2. `override_allowed` 字段以 chapter 为准。
3. `append_only` 字段按并集合并。
4. `locked` 字段只能服从 `.story-system/MASTER_SETTING.json`。
5. `Anti-Patterns` 为全局与局部的并集，任何一条都不可违反。
```

---

## 12. 实施阶段

### Phase 1：数据层

交付：

1. 新增 `题材与调性推理.csv`
2. 为 `桥段套路.csv` 新增 `忌讳写法`
3. 更新 `references/csv/README.md`

本阶段不要求批量改写既有表内容。

### Phase 2：聚合脚本

交付：

1. 新增 `story_system.py`
2. 保持 `reference_search.py` 不改职责
3. 实现 `StorySystemDict`
4. 实现 Markdown / JSON 输出

### Phase 3：持久化

交付：

1. `.story-system/` 自动创建
2. `MASTER_SETTING.*` 持久化
3. `chapter_xxx.*` 持久化
4. marker 区块更新逻辑

### Phase 4：接入层

交付：

1. 定位真实的 skill / prompt 挂点
2. 按本 spec 的读取优先级接入
3. 验证 chapter override 能正确覆盖局部字段

---

## 13. 测试策略

### 13.1 测试原则

本项目不需要把每个知识点都写成测试。

本轮测试只保护系统契约，不保护内容细节。

### 13.2 必要测试

至少新增以下轻量测试：

1. **题材路由测试**
   - 输入明确题材时能命中 `题材与调性推理.csv`
   - 输入模糊 query 时能走 fallback

2. **聚合结构测试**
   - `StorySystemDict` 顶层字段完整
   - 基础表与动态表结果落在正确 section

3. **anti-pattern 聚合测试**
   - 不同表的误区字段能被统一提取
   - Master 与 Chapter 的红线会做并集

4. **覆盖规则测试**
   - `locked` 不会被 chapter 覆盖
   - `append_only` 正确并集
   - `override_allowed` chapter 优先

5. **持久化测试**
   - `--persist` 会写出 md + json
   - marker 外的人工内容不会被覆盖

6. **底层搜索回归**
   - 现有 `reference_search.py` 测试继续通过

### 13.3 不要求的测试

本轮不要求：

1. 每条 CSV 知识点逐条断言
2. Markdown 渲染的视觉细节快照测试
3. 复杂端到端 agent 测试

---

## 14. 风险与约束

### 14.1 最大风险

最大风险不是代码复杂度，而是职责混淆。

必须避免：

1. 把 `reference_search.py` 改坏
2. 把 Markdown 当源数据
3. 让 Chapter 冲掉 Master 硬限制
4. 把 `反套路变种` 错当成毒点字段

### 14.2 数据录入约束

本轮仍遵守当前 CSV 原则：

- 新内容以人工整理为主
- 不做 md 全量自动迁移
- 不要求一次性补全所有题材

### 14.3 上线顺序约束

正确上线顺序必须是：

1. 先补路由表
2. 再写聚合器
3. 再做持久化
4. 最后才接入 prompt / skill

不能跳过中间层，直接让 prompt 去拼 CSV 检索结果。

---

## 15. 最终结论

本轮架构升级的核心不是“把检索做得更大”，而是：

1. **保留现有检索 primitive 的稳定性**
2. **新增一层 Story System 聚合器**
3. **把全局约束与局部覆盖持久化**
4. **让大模型服从结构化系统，而不是每次重新理解散乱结果**

最终目标不是“搜索更花”，而是：

**开书有 Master，写章有 Override，任何时刻都有可追溯、可持久、可服从的系统级上下文。**
