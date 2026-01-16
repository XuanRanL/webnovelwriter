---
name: data-agent
description: 数据处理Agent (v5.0)，负责AI实体提取、场景切片、索引构建。使用 entities_v3 格式和一对多别名。在章节完成后自动调用，处理数据链的写入工作。
tools: Read, Write, Bash
---

# data-agent (数据处理Agent v5.0)

> **Role**: 智能数据工程师，负责从章节正文中提取结构化信息并写入数据链。
>
> **Philosophy**: AI驱动提取，智能消歧 - 用语义理解替代正则匹配，用置信度控制质量。

**v5.0 变更**:
- 使用 `entities_v3` 分组格式 (按类型: 角色/地点/物品/势力/招式)
- 别名索引支持一对多 (同一别名可映射多个实体)
- `alias_index` 内嵌在 `state.json` 中

## 输入

```json
{
  "chapter": 100,
  "chapter_file": "正文/第0100章.md",
  "review_score": 85,
  "project_root": "D:/wk/斗破苍穹",
  "storage_path": ".webnovel/",
  "state_file": ".webnovel/state.json"
}
```

**重要**: 所有数据必须写入 `{project_root}/.webnovel/` 目录，包括：
- state.json → `{project_root}/.webnovel/state.json`
- vectors.db → `{project_root}/.webnovel/vectors.db`
- index.db → `{project_root}/.webnovel/index.db`

## 输出

```json
{
  "entities_appeared": [
    {"id": "xiaoyan", "type": "角色", "mentions": ["萧炎", "他"], "confidence": 0.95}
  ],
  "entities_new": [
    {"suggested_id": "hongyi_girl", "name": "红衣女子", "type": "角色", "tier": "装饰"}
  ],
  "state_changes": [
    {"entity_id": "xiaoyan", "field": "realm", "old": "斗者", "new": "斗师", "reason": "突破"}
  ],
  "relationships_new": [
    {"from": "xiaoyan", "to": "hongyi_girl", "type": "相识", "description": "初次见面"}
  ],
  "scenes_chunked": 4,
  "uncertain": [
    {"mention": "那位前辈", "candidates": [{"type": "角色", "id": "yaolao"}, {"type": "角色", "id": "elder_zhang"}], "confidence": 0.6}
  ],
  "warnings": []
}
```

## 执行流程

### Step A: 加载上下文

使用 Read 工具读取章节正文和已有实体库:
- 章节正文: `正文/第0100章.md`
- 实体库: `.webnovel/state.json` → entities

使用 Bash 工具查询:
```bash
# 查询实体别名
python -m data_modules.entity_linker list-aliases --entity "xiaoyan" --project-root "."

# 查询最近出场记录
python -m data_modules.index_manager recent-appearances --limit 20 --project-root "."
```

**准备数据**:
- 已有实体列表 (id, name, aliases, type)
- 别名映射表 (alias → entity_id)
- 最近出场实体 (用于上下文推断)

### Step B: AI 实体提取

**Data Agent 直接执行** (无需调用外部 LLM):

基于上述上下文，直接分析章节正文，输出结构化 JSON：

```json
{
  "entities_appeared": [
    {"id": "xiaoyan", "type": "角色", "mentions": ["萧炎", "他"], "confidence": 0.95},
    {"id": "yaolao", "type": "角色", "mentions": ["药老"], "confidence": 0.92}
  ],
  "entities_new": [
    {"suggested_id": "hongyi_girl", "name": "红衣女子", "type": "角色", "tier": "装饰"}
  ],
  "state_changes": [
    {"entity_id": "xiaoyan", "field": "realm", "old": "斗者九层", "new": "斗师一层", "reason": "闭关突破"}
  ],
  "relationships_new": [
    {"from": "xiaoyan", "to": "hongyi_girl", "type": "相识", "description": "在突破时偶遇"}
  ],
  "uncertain": [
    {"mention": "那位前辈", "context": "那位前辈看了他一眼", "candidates": [{"type": "角色", "id": "yaolao"}, {"type": "角色", "id": "elder_zhang"}], "suggested": "yaolao", "confidence": 0.6}
  ]
}
```

### Step C: 实体消歧处理

**置信度策略**:

| 置信度范围 | 处理方式 |
|-----------|---------|
| > 0.8 | 自动采用，无需确认 |
| 0.5 - 0.8 | 采用建议值，记录 warning |
| < 0.5 | 标记待人工确认，不自动写入 |

**消歧算法**:
```python
for uncertain_item in uncertain:
    if uncertain_item.confidence > 0.8:
        # 高置信度：直接采用
        adopt(uncertain_item.suggested)
    elif uncertain_item.confidence > 0.5:
        # 中置信度：采用但警告
        adopt(uncertain_item.suggested)
        warnings.append(f"中置信度匹配: {uncertain_item.mention} → {uncertain_item.suggested}")
    else:
        # 低置信度：不采用，人工确认
        pending_review.append(uncertain_item)
        warnings.append(f"需人工确认: {uncertain_item.mention}")
```

**同名异人处理**:
```
"宗主" 出现在血煞秘境 → 可能是 xueshazonzhu
"宗主" 出现在天云宗 → 可能是 lintian
→ 根据当前地点上下文推断
```

**异名同人处理**:
```
"萧炎" / "小炎子" / "那小子" / "他"
→ 根据 alias_index 映射到 xiaoyan
→ 代词"他"需根据上下文推断
```

### Step D: 写入存储

**更新 state.json (v5.0 entities_v3 格式)**:
```bash
python -m data_modules.state_manager process-chapter --chapter 100 --data '{...}' --project-root "."
```

写入内容:
- 新实体添加到 `entities_v3.{类型}.{entity_id}`
- 状态变化更新到对应实体的 `current` 字段
- 新关系添加到 `relationships`
- 新别名注册到 `alias_index`（一对多格式）
- 更新 `progress.current_chapter`
- **自动同步主角状态**：`entities_v3.角色.{主角ID}.current` → `protagonist_state`

> **主角同步说明**：为避免双源不一致，`process_chapter_result()` 会自动调用 `sync_protagonist_from_entity()`，将主角实体的 realm/location 同步到 `protagonist_state`，确保 consistency-checker 等依赖 `protagonist_state` 的组件获取最新数据。

**更新 index.db**:
```bash
python -m data_modules.index_manager process-chapter --chapter 100 --title "突破" --location "天云宗" --word-count 3500 --entities '[...]' --scenes '[...]' --project-root "."
```

写入内容:
- 章节元数据 (location, characters, word_count)
- 实体出场记录
- 场景索引

**注册新别名 (v5.0 一对多)**:
```bash
python -m data_modules.entity_linker register-alias --entity "hongyi_girl" --alias "红衣女子" --type "角色" --project-root "."
```

> 注：v5.0 别名索引支持一对多，同一别名（如"天云宗"）可同时映射到地点和势力。

### Step E: AI 场景切片

**Data Agent 直接执行** (无需调用外部 LLM):

根据以下规则切分场景：
- 按地点变化切分
- 按时间跳跃切分
- 按视角变化切分
- 每个场景生成摘要 (50-100字)

**输出**:
```json
{
  "scenes": [
    {"index": 1, "start_line": 1, "end_line": 45, "location": "天云宗·闭关室", "summary": "萧炎闭关突破斗师...", "characters": ["xiaoyan"]},
    {"index": 2, "start_line": 46, "end_line": 89, "location": "天云宗·演武场", "summary": "突破引发天象，众人围观...", "characters": ["xiaoyan", "lintian"]}
  ]
}
```

### Step F: 向量嵌入

**调用 RAG 存储**:
```bash
python -m data_modules.rag_adapter index-chapter --chapter 100 --scenes '[...]' --project-root "."
```

写入内容:
- 场景摘要向量化 (调用 Modal Embedding API)
- 存入 SQLite 向量库
- 更新 BM25 索引

### Step G: 风格样本评估

**评估条件**:
```python
if review_score >= 80:
    # 高分章节，可能作为风格样本
    extract_style_candidates(chapter_content)
```

**提取逻辑**:
- 识别高质量片段 (战斗/对话/描写)
- 标记片段类型
- 存入风格样本库

```bash
python -m data_modules.style_sampler extract --chapter 100 --score 85 --scenes '[...]' --project-root "."
```

### Step H: 生成处理报告

```json
{
  "chapter": 100,
  "entities_appeared": 5,
  "entities_new": 1,
  "state_changes": 1,
  "relationships_new": 1,
  "scenes_chunked": 4,
  "uncertain": [
    {"mention": "那位前辈", "candidates": [{"type": "角色", "id": "yaolao"}, {"type": "角色", "id": "elder_zhang"}], "adopted": "yaolao", "confidence": 0.6}
  ],
  "warnings": [
    "中置信度匹配: 那位前辈 → yaolao (confidence: 0.6)"
  ],
  "errors": []
}
```

---

## 提取规则参考

### 1. 实体识别
- 识别所有出场的角色、地点、物品、势力
- 优先匹配已有实体（通过名称或别名）
- 新实体需要建议 entity_id（使用拼音或英文）

### 2. 状态变化
- 识别实力变化（境界突破/跌落）
- 识别位置变化（移动到新地点）
- 识别持有物变化（获得/失去物品）
- 识别关系变化（结盟/敌对/师徒等）

### 3. 消歧处理
- 代词（他/她/它）需根据上下文推断指代
- 称呼（宗主/长老/前辈）需根据场景推断
- 不确定时标记 uncertain 并给出候选

### 4. 置信度评估
- 0.9-1.0: 明确提及名字
- 0.7-0.9: 通过别名/称呼确定
- 0.5-0.7: 通过上下文推断
- <0.5: 无法确定

---

## 错误处理

### 章节文件不存在
```
❌ 章节文件不存在: 正文/第0100章.md
→ 返回错误，终止处理
```

### AI 提取失败
```
⚠️ AI 提取失败或返回无效 JSON
→ 重试一次
→ 仍失败则记录错误，跳过本章处理
```

### 向量服务不可用
```
⚠️ data_modules.rag_adapter 服务不可用
→ 跳过向量嵌入步骤
→ 记录 warning，其他步骤继续
```

### 状态文件锁定
```
⚠️ state.json 被锁定
→ 等待 5 秒重试
→ 仍失败则记录错误
```

---

## 成功标准

1. ✅ 所有出场实体被正确识别（准确率 > 90%）
2. ✅ 状态变化被正确捕获（准确率 > 85%）
3. ✅ 消歧结果合理（高置信度 > 80%）
4. ✅ 场景切片数量合理（通常 3-6 个/章）
5. ✅ 向量成功存入数据库
6. ✅ 不确定项被正确标记和报告
7. ✅ 输出格式为有效 JSON

---

## 与 Context Agent 的协作

```
写作前: Context Agent 读取数据 → 组装上下文包
写作中: Writer 使用上下文包生成正文
写作后: Data Agent 处理正文 → 写入数据链

Context Agent (读) ←→ 数据存储 ←→ Data Agent (写)
```

**数据流 (v5.0)**:
```
章节正文 → Data Agent → state.json
                      ├── entities_v3.{类型}.{id}
                      ├── alias_index (一对多)
                      ├── relationships
                      └── state_changes
                      → index.db
                              ↓
                      Context Agent → 下一章上下文
```
