# LIGHT 长期记忆系统说明

## 文档目标

本文档将论文中的 LIGHT 系统整理成可落地的工程方案，重点说明三层记忆结构、读写链路、核心数据结构，以及在产品化实现时需要重点处理的问题。

## 一句话定义

LIGHT 不是单纯把上下文窗口做大，而是把长期记忆拆成三层：

- 情节记忆 `episodic memory`：负责从历史对话中检索证据
- 工作记忆 `working memory`：负责保留最近上下文
- 草稿板 `scratchpad`：负责沉淀长期稳定的高价值事实

回答时由统一的记忆编排器组合这三层记忆，再交给生成模型。

## 设计目标

- 支持超长会话下的稳定问答
- 降低“上下文很长但还是忘事”的问题
- 兼顾近期上下文、远期事实和长期偏好
- 为信息更新、偏好跟随、跨轮总结提供结构化基础

## 总体架构

```text
┌────────────────────────────────────────────────────┐
│                    用户对话流                      │
└────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────┐
│                  回合后处理器                      │
├────────────────────────────────────────────────────┤
│ 1. 保存原始 turn 到会话存储                        │
│ 2. 提取 key-value 和摘要，写入情节记忆             │
│ 3. 提炼显著事实，增量更新 scratchpad              │
└────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────┐
│                  用户新问题到达                    │
└────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────┐
│                  记忆编排器                        │
├────────────────────────────────────────────────────┤
│ 1. 检索 episodic top-k                             │
│ 2. 读取最近 N 轮 working memory                    │
│ 3. 对 scratchpad 分块并过滤相关内容                │
│ 4. 组装 prompt，交给回答模型                       │
└────────────────────────────────────────────────────┘
```

## 三层记忆拆解

### 1. 情节记忆 `episodic memory`

作用：

- 存储历史对话中的离散事件与事实证据
- 在远距离问题中召回“当时具体说过什么”
- 为答案提供可追溯的历史片段

写入方式：

- 每轮 `user-assistant turn pair` 结束后执行一次
- 提取结构化 `key-value pairs`
- 生成该轮摘要 `summary`
- 对结构化结果或摘要做向量化
- 将原始对话片段与索引共同存入向量库

建议字段：

```json
{
  "session_id": "session-001",
  "turn_id": 1842,
  "timestamp": "2026-03-19T18:00:00+08:00",
  "entities": [
    {"key": "居住城市", "value": "苏州"},
    {"key": "宠物名字", "value": "团子"}
  ],
  "summary": "用户提到已搬到苏州，并养了一只叫团子的猫。",
  "raw_span": "原始对话片段",
  "embedding_text": "居住城市=苏州；宠物名字=团子；用户提到已搬到苏州，并养了一只叫团子的猫。"
}
```

工程建议：

- 不要只存全文向量，优先存“摘要 + 结构化提取”的索引文本
- 检索后返回原始片段，避免摘要失真带来的二次误导
- `top-k` 不要盲目调大，过多召回会引入噪声

### 2. 工作记忆 `working memory`

作用：

- 保留最近若干轮原始对话
- 维持局部连贯性、代词解析、刚更新的信息
- 防止系统只看远期记忆，忽略当前上下文

实现方式：

- 直接从会话存储读取最近 `N` 轮
- 或按 `token budget` 截断，而不是写死固定轮数

工程建议：

- 优先按 token 上限裁剪，而不是按回合数裁剪
- 最近轮的优先级通常高于远期记忆
- 回答冲突时，应优先检查工作记忆中是否存在更近更新

### 3. 草稿板 `scratchpad`

作用：

- 沉淀对长期任务真正重要的高层事实
- 存储偏好、长期约束、时间线、未完成事项等
- 避免只依赖相似度检索导致关键信息漏召回

写入方式：

- 每轮结束后由 LLM 提炼“显著信息”
- 将新信息合并到现有 scratchpad
- 超过阈值后执行压缩

推荐分槽位组织，而不是一整段自由文本：

```json
{
  "profile": [
    "用户当前住在苏州"
  ],
  "preferences": [
    "默认使用简体中文",
    "倾向简洁回答"
  ],
  "instructions": [
    "代码注释使用中文",
    "避免未验证结论"
  ],
  "timeline": [
    "2025-12: 从杭州搬到苏州",
    "2026-04: 计划去东京出差"
  ],
  "open_loops": [
    "简历修改尚未完成"
  ]
}
```

工程建议：

- 将 `profile / preferences / instructions / timeline / open_loops` 分开维护
- 超过长度阈值后做压缩，但要保留高优先级槽位
- 回答前不要整块全部注入，应先按问题相关性过滤

## 读写链路

### 写入链路

每轮对话结束后：

1. 保存原始 turn 到会话存储
2. 用提取模型生成 `key-value + summary`
3. 写入情节记忆索引
4. 更新 scratchpad
5. 超过阈值时压缩 scratchpad

### 读取链路

收到新问题后：

1. 对问题做向量化
2. 从情节记忆中召回 `top-k`
3. 从会话存储取最近若干轮 working memory
4. 将 scratchpad 分块
5. 对每块做相关性过滤
6. 将三层记忆拼装为回答上下文
7. 调用生成模型作答

## 关键数据存储

建议至少拆成四类存储：

- `conversation_store`：保存原始对话 turn
- `episodic_index`：保存摘要、结构化提取、embedding、原始片段引用
- `scratchpad_store`：保存长期摘要与槽位化事实
- `memory_metadata`：保存版本号、状态、更新时间、冲突标记

可选状态字段：

- `active`：当前有效
- `outdated`：已过期
- `contradicted`：被冲突信息覆盖
- `tentative`：不确定信息，需后续确认

## 记忆编排器职责

记忆编排器是系统核心，职责包括：

- 控制每类记忆的 token 预算
- 决定检索数量与排序策略
- 在冲突信息出现时做优先级裁决
- 过滤与问题无关的 scratchpad 块
- 统一输出给回答模型的上下文格式

一个简单的优先级顺序可以是：

1. 当前轮明确指令
2. working memory 中的最近事实
3. scratchpad 中的长期约束与偏好
4. episodic memory 中召回的历史证据

## 最小可用实现（MVP）

最小版本只需要五个组件：

- `conversation_store`
- `episodic_indexer`
- `scratchpad_manager`
- `memory_orchestrator`
- `response_generator`

伪代码：

```python
def on_turn_end(session_id, user_msg, assistant_msg):
    save_raw_turn(session_id, user_msg, assistant_msg)

    memory_item = extract_kv_and_summary(user_msg, assistant_msg)
    vector_store.upsert(session_id, memory_item)

    scratchpad = load_scratchpad(session_id)
    scratchpad = update_scratchpad(scratchpad, user_msg, assistant_msg)
    if token_len(scratchpad) > 30000:
        scratchpad = compress_scratchpad(scratchpad, target_tokens=15000)
    save_scratchpad(session_id, scratchpad)


def answer(session_id, question):
    episodic_docs = retrieve_topk(session_id, question, k=15)
    recent_turns = load_recent_turns(session_id, token_budget=8000)
    scratchpad = load_scratchpad(session_id)
    scratch_chunks = semantic_chunk(scratchpad)
    filtered_scratch = filter_relevant_chunks(question, scratch_chunks)

    prompt = build_prompt(
        question=question,
        episodic_memory=episodic_docs,
        working_memory=recent_turns,
        scratchpad=filtered_scratch,
    )
    return llm_generate(prompt)
```

## 与普通 RAG 的区别

普通 RAG 常见流程是：

- 文本切块
- 向量检索
- 拼接上下文

LIGHT 的差异在于：

- 有独立的 working memory，保证近期连续性
- 有 scratchpad，维护高层抽象事实
- 有持续写入机制，而不是只在回答前做一次检索
- 更接近“记忆系统”，而不是单次检索增强

## 落地时最难的四个问题

### 1. 信息更新

同一事实会变化，例如“住在杭州”后来变成“搬到苏州”。系统不能只追加，不做状态管理。

### 2. 矛盾消解

不同时间的记忆可能互相冲突。系统需要判断：

- 哪条是最新的
- 哪条是已过期的
- 哪条只是暂时猜测

### 3. Scratchpad 膨胀

如果长期只追加不整理，scratchpad 会退化成另一份噪声上下文，导致检索和回答质量持续下降。

### 4. 写入污染

每轮写入依赖 LLM 提取。如果提取错误，错误会长期保留并反复影响后续回答。

## 产品化增强建议

如果从论文原型继续往前做，建议增加以下能力：

- 混合召回：结合 dense、keyword、时间排序和 rerank
- 冲突检查：回答前先做 memory conflict check
- 偏好单独建表：用户偏好和长期指令不要完全混在 scratchpad 中
- 版本化更新：对关键事实保留变更历史和生效时间
- 可观察性：记录每次回答用了哪些记忆，便于审计和调试

## 适用场景

LIGHT 适合以下系统：

- 长对话助手
- 需要记住用户偏好的智能体
- 多轮写作/策划协作系统
- 长期任务跟踪与提醒系统
- 小说创作助手中的角色、设定、剧情记忆系统

## 对本项目的启发

如果把 LIGHT 思路引入当前小说写作系统，可以这样映射：

- 情节记忆：存章节事件、角色状态变化、伏笔和回收线索
- 工作记忆：存当前章节任务书、最近章节摘要、当前写作约束
- 草稿板：存角色设定、长期世界观规则、主线目标、未回收伏笔

这样可以把“长篇连载的一致性问题”从单次检索，升级成持续维护的记忆闭环。

## 总结

LIGHT 的核心价值不在于更大的上下文窗口，而在于把长期记忆拆成：

- 可检索的历史证据层
- 保持局部连贯的短期层
- 稳定沉淀长期事实的抽象层

工程上最值得复用的是这套分层记忆与统一编排思路，而不是某个固定模型或具体实现细节。
