---
name: webnovel-init
description: 深度初始化网文项目。通过分阶段交互收集完整创作信息，生成可直接进入规划与写作的项目骨架与约束文件。
allowed-tools: Read Write Edit Grep Bash Task AskUserQuestion
---

# Project Initialization (Deep Mode)

## 目标

- 通过结构化交互收集足够信息，避免“先生成再返工”。
- 产出可落地项目骨架：`.webnovel/state.json`、`设定集/*`、`大纲/总纲.md`、`.webnovel/idea_bank.json`。
- 保证后续 `/webnovel-plan` 与 `/webnovel-write` 可直接运行。

## 执行原则

1. 先收集，再生成；未过充分性闸门，不执行 `init_project.py`。
2. 分波次提问，每轮只问“当前缺失且会阻塞下一步”的信息。
3. 允许调用 `Read/Grep/Bash/Task/AskUserQuestion` 辅助收集（搜索通过 Bash 调用 `tavily_search.py`）。
4. 用户已明确的信息不重复问；冲突信息优先让用户裁决。
5. Deep 模式优先完整性，允许慢一点，但禁止漏关键字段。

## 引用加载等级（strict, lazy）

采用分级加载，避免一次性灌入全部资料：

- L0：未确认任务前，不预加载参考。
- L1：每个阶段仅加载该阶段“必读”文件。
- L2：仅在题材、金手指、创意约束触发条件满足时加载扩展参考。
- L3：市场趋势类、时效类资料仅在用户明确要求时加载。

路径约定：
- `references/...` 相对当前 skill 目录（`${CLAUDE_PLUGIN_ROOT}/skills/webnovel-init/references/...`）。
- `templates/...` 相对插件根目录（`${CLAUDE_PLUGIN_ROOT}/templates/...`）。

默认加载清单：
- L1（启动前）：`references/genre-tropes.md`
- L2（按需）：
  - 题材模板：`templates/genres/{genre}.md`
  - 金手指：`../../templates/golden-finger-templates.md`
  - 世界观：`references/worldbuilding/faction-systems.md`
  - 创意约束：按下方“逐文件引用清单”触发加载
- L3（显式请求）：
  - `references/creativity/market-trends-2026.md`

## References（逐文件引用清单）

### 根目录

- `references/genre-tropes.md`
  - 用途：Step 1 题材归一化、题材特征提示。
  - 触发：所有项目必读。
- `references/system-data-flow.md`
  - 用途：初始化产物与后续 `/plan`、`/write` 的数据流一致性检查。
  - 触发：Step 0 预检必读。

### narrative

- `references/narrative-voice-guide.md`
  - 用途：初始化阶段建立叙事声音基准，含各题材推荐配置与风格样本。
  - 触发：Step 1 规划风格锚点时必读，后续由 `/write` 的 Step 1 内置消费。

### worldbuilding

- `references/worldbuilding/character-design.md`
  - 用途：Step 2 角色维度补问（目标、缺陷、动机、反差）。
  - 触发：用户人物信息抽象或扁平时加载。
- `references/worldbuilding/faction-systems.md`
  - 用途：Step 4 势力格局与组织层级设计。
  - 触发：Step 4 默认加载。
- `references/worldbuilding/power-systems.md`
  - 用途：Step 4 力量体系类型与边界定义。
  - 触发：涉及修仙/玄幻/高武/异能时加载。
- `references/worldbuilding/setting-consistency.md`
  - 用途：Step 6 一致性复述前做设定冲突检查。
  - 触发：Step 6 默认加载。
- `references/worldbuilding/world-rules.md`
  - 用途：Step 4 世界规则与禁忌项收束。
  - 触发：Step 4 默认加载。

### creativity

- `references/creativity/creativity-constraints.md`
  - 用途：Step 5 创意约束包主 schema。
  - 触发：Step 5 必读。
- `references/creativity/category-constraint-packs.md`
  - 用途：Step 5 按平台/题材选择约束包模板。
  - 触发：Step 5 必读。
- `references/creativity/creative-combination.md`
  - 用途：复合题材（A+B）融合规则。
  - 触发：用户选择复合题材时加载。
- `references/creativity/inspiration-collection.md`
  - 用途：用户卡住时提供卖点/钩子候选。
  - 触发：Step 1 或 Step 5 卡顿时加载。
- `references/creativity/selling-points.md`
  - 用途：Step 5 卖点生成与筛选。
  - 触发：Step 5 必读。
- `references/creativity/market-positioning.md`
  - 用途：目标读者/平台定位与商业化语义统一。
  - 触发：Step 1 用户提及平台或商业目标时加载。
- `references/creativity/market-trends-2026.md`
  - 用途：时间敏感市场趋势参考。
  - 触发：仅用户明确要求“参考当下趋势”时加载。
- `references/creativity/anti-trope-xianxia.md`
  - 用途：反套路库（修仙/玄幻/高武/西幻）。
  - 触发：题材命中对应映射时加载。
- `references/creativity/anti-trope-urban.md`
  - 用途：反套路库（都市/历史）。
  - 触发：题材命中对应映射时加载。
- `references/creativity/anti-trope-game.md`
  - 用途：反套路库（游戏/科幻/末世）。
  - 触发：题材命中对应映射时加载。
- `references/creativity/anti-trope-rules-mystery.md`
  - 用途：反套路库（规则/悬疑/灵异/克苏鲁）。
  - 触发：题材命中对应映射时加载。

## 工具策略（按需）

- `Read/Grep`：读取项目上下文与参考文件（`README.md`、`CLAUDE.md`、`templates/genres/*`、`references/*`）。
- `Bash`：执行 `init_project.py`、文件存在性检查、最小验证命令。
- `Task`：拆分并行子任务（如题材映射、约束包候选生成、文件验证）。
- `AskUserQuestion`：用于关键分歧裁决、候选方案选择、最终确认。
- `Bash`（Tavily 搜索）：通过 `${SCRIPTS_DIR}/tavily_search.py` 直连 Tavily API，支持快速搜索（`search`）和深度研究（`research`），禁止使用 MCP 工具（WebSearch/WebFetch）。
- 外部检索触发条件：
  - 用户明确要求参考市场趋势或平台风向；
  - 创意约束需要”时间敏感依据”；
  - 对题材信息存在明显不确定。

## 交互流程（Deep）

### Step 0：预检与上下文加载

环境设置（bash 命令执行前）：
```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"

if [ -z "${CLAUDE_PLUGIN_ROOT}" ] || [ ! -d "${CLAUDE_PLUGIN_ROOT}/scripts" ]; then
  echo "ERROR: 未设置 CLAUDE_PLUGIN_ROOT 或缺少目录: ${CLAUDE_PLUGIN_ROOT}/scripts" >&2
  exit 1
fi
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/scripts"
```

必须做：
- 确认当前目录可写。
- 解析脚本目录并确认入口存在（仅支持插件目录）：
  - 固定路径：`${CLAUDE_PLUGIN_ROOT}/scripts`
  - 入口脚本：`${SCRIPTS_DIR}/webnovel.py`
- 建议先打印解析结果，避免写到错误目录：
  - `python "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where`
- 加载最小参考：
  - `references/system-data-flow.md`（用于校对 init 产物与 plan/write 输入链路）
  - `references/genre-tropes.md`
  - `templates/genres/`（仅在用户选定题材后按需读取）

输出：
- 进入 Deep 采集前的“已知信息清单”和“待收集清单”。

### Search Tool 使用规则（init阶段高频使用）

**搜索统一使用 Tavily 直连 API 脚本**（`${SCRIPTS_DIR}/tavily_search.py`），禁止使用 MCP 工具（WebSearch/WebFetch）。

init 阶段搜索是一次性投入、长期受益，应高频使用：

**两种搜索模式**：
- **快速搜索**：`python -X utf8 "${SCRIPTS_DIR}/tavily_search.py" search "查询词" --max 5`
- **深度研究**：`python -X utf8 "${SCRIPTS_DIR}/tavily_search.py" research "研究问题" --model pro`

每个 Step 的具体搜索内容：
- Step 1：搜索同题材近期爆款（"网文 {题材} 2025 2026 爆款 卖点"），了解市场竞争和差异化空间
- Step 2：搜索该题材经典主角原型（"{题材} 主角 原型 反差 设计"），获取角色设计灵感
- Step 3：搜索同类金手指（"网文 {金手指类型} 设计 案例"），确保差异化
- Step 4：搜索世界观设计常见问题（"{题材} 世界观 设定 创新 问题"）
- Step 5：搜索反套路趋势（"网文 {题材} 套路 反套路 2025 2026"）
每个 Step 至少 1 次 search，关键 Step（1/4/5）推荐 2-3 次。

Search 失败处理：立即停止，检查 Tavily API key 配置（环境变量 / `.env` / `~/.claude.json`）。

调研笔记：搜索到的有价值信息保存到 `调研笔记/题材参考.md`，供后续 plan/write 复用。

### Step 1：故事核与商业定位

收集项（必收）：
- 书名（可先给工作名）
- 题材（支持 A+B 复合题材）
- 目标规模（总字数或总章数）
- 一句话故事
- 核心冲突
- 目标读者/平台
- 主题内核（一句话：这个故事探讨什么？如"权力必然腐化"/"成长需要代价"/"自由与责任的悖论"）

收集项（可选）：
- 参考作品（1-3 部标杆作品 + 学什么，如"斗破苍穹-升级节奏"/"诡秘之主-伏笔回收"）

题材集合（用于归一化与映射）：
- 玄幻修仙类：修仙 | 系统流 | 高武 | 西幻 | 无限流 | 末世 | 科幻
- 都市现代类：都市异能 | 都市日常 | 都市脑洞 | 现实题材 | 黑暗题材 | 电竞 | 直播文
- 言情类：古言 | 宫斗宅斗 | 青春甜宠 | 豪门总裁 | 职场婚恋 | 民国言情 | 幻想言情 | 现言脑洞 | 女频悬疑 | 狗血言情 | 替身文 | 多子多福 | 种田 | 年代
- 特殊题材：规则怪谈 | 悬疑脑洞 | 悬疑灵异 | 历史古代 | 历史脑洞 | 游戏体育 | 抗战谍战 | 知乎短篇 | 克苏鲁

交互方式：
- 优先让用户自由描述，再二次结构化确认。
- 若用户卡住，给 2-4 个候选方向供选。

### Step 1：叙事声音基准

> **目的**：在初始化阶段建立全书统一的风格锚点，供后续 `/write` 的 Step 1、style-adapter 和 prose-quality-checker 作为跨章一致性基准。缺失此基准会导致跨章风格漂移、Anti-AI 检测不过。

收集项（必收）：
- 叙述视角（第一人称/第三人称有限/第三人称全知）
- 语气基调（硬朗冷峻/热血激昂/幽默戏谑/温暖治愈/讽刺辛辣/克制内敛/轻松日常）
- 描写密度（精简干练/适中均衡/细腻丰富）
- 感官侧重（视觉为主/听觉为主/触觉为主/均衡多感官/按场景切换）
- 对话叙事比例（高对话型 ≥50%/均衡型 30-50%/叙述主导型 ≤30%）

收集项（可选）：
- 修辞风格偏好（朴实直白/比喻丰富/诗意典雅/口语化）
- 3-5 条全书风格禁忌（如"不用四字成语堆砌"/"不写大段心理独白"/"禁止元叙述"）
- 参考作品的具体风格特征（若 Step 1 提供了参考作品，提取其风格锚点）

交互方式：
- 给出 2-3 个风格样本片段（各 50-100 字），让用户选择最接近的方向。
- 若用户不确定，基于题材+目标读者推荐默认配置。
- 确认后输出 `设定集/叙事声音.md`。

**参考加载**：`references/narrative-voice-guide.md`（L1 必读）

### Step 2：角色骨架与关系冲突

收集项（必收）：
- 主角姓名
- 主角欲望（想要什么）
- 主角缺陷（会害他付代价的缺陷）
- 主角结构（单主角/多主角）
- 感情线配置（无/单女主/多女主）
- 反派分层（小/中/大）与镜像对抗一句话

收集项（可选）：
- 主角原型标签（成长型/复仇型/天才流等）
- 多主角分工

### Step 3：金手指与兑现机制

收集项（必收）：
- 金手指类型（可为“无金手指”）
- 名称/系统名（无则留空）
- 风格（硬核/诙谐/黑暗/克制等）
- 可见度（谁知道）
- 不可逆代价（必须有代价或明确“无+理由”）
- 成长节奏（慢热/中速/快节奏）

收集项（条件必收）：
- 若为系统流：系统性格、升级节奏
- 若为重生：重生时间点、记忆完整度
- 若为传承/器灵：辅助边界与出手限制

### Step 4：世界观与力量规则

收集项（必收）：
- 世界规模（单城/多域/大陆/多界）
- 力量体系类型
- 势力格局
- 社会阶层与资源分配

收集项（题材相关）：
- 货币体系与兑换规则
- 宗门/组织层级
- 境界链与小境界

收集项（新增 - 节奏偏好）：
- 爽点频率（高频密集：每章2+个/适中：每章1个/慢热积累：2-3章1个大爽点）
- 整体节奏（快节奏紧凑/中等张弛有度/慢热型层层铺垫）
- 每卷预期高潮数（1-2个/2-3个/3+个）

> 节奏偏好写入 `state.json` 的 `pacing_preference`，供 pacing-checker 调整阈值而非使用硬编码默认值。

### Step 5：创意约束包（差异化核心）

流程：
1. 基于题材映射加载反套路库（最多 2 个主相关库）。
2. 生成 2-3 套创意包，每套包含：
   - 一句话卖点
   - 反套路规则 1 条
   - 硬约束 2-3 条
   - 主角缺陷驱动一句话
   - 反派镜像一句话
   - 开篇钩子
3. 三问筛选：
   - 为什么这题材必须这么写？
   - 换成常规主角会不会塌？
   - 卖点能否一句话讲清且不撞模板？
4. 展示五维评分（详见 `references/creativity/creativity-constraints.md` 的 `8.1 五维评分`），辅助用户决策。
5. 用户选择最终方案，或拒绝并给出原因。

备注：
- 若用户要求”贴近当下市场”，可触发外部检索并标注时间戳。

### Step 5.5：情感蓝图与开篇策略

> **目的**：前者防止情感分布不均（全书一个调无波动），后者直接影响首章留存率（网文最关键指标）。

#### 5.5A 情感蓝图

收集项（必收）：
- 全书情感基调（热血/虐心/温馨/暗黑/轻松/混合型 - 说明主副基调）
- 第一卷关键情感节点（至少 2 个）：
  - 事件描述（一句话）
  - 目标情感（燃/虐/暖/恐惧/爽/释放）
  - 预计位置（章节范围或卷内比例，如”卷首1/4”/”高潮前”）
- 情感禁区（不做的事，如”不无故虐主角”/”不用绝症煽情”/”不杀宠物”）

交互方式：
- 基于题材 + 主角缺陷 + 核心冲突，推荐 2 套情感节奏方案。
- 用户选择或自定义后确认。

输出：`设定集/情感蓝图.md`

#### 5.5B 开篇策略（高优先级）

> 首章留存率是网文最关键的指标。”前三章黄金法则”：必须在前三章完成核心世界/身份/冲突的铺垫并留下章节级悬念。

收集项（必收）：
- 开篇类型（冲突开场/悬疑开场/动作开场/对话开场/氛围开场）
- 第 1 章场景设计（地点+氛围+主角初始状态）
- 第 1 章必须传达的核心信息（3-5 条，如”主角身份”/”世界核心规则”/”金手指存在”）
- 第 1 章钩子设计（章末悬念的具体内容和类型：危机钩/悬念钩/选择钩/反差钩/渴望钩）
- 前 3 章节奏蓝图（每章一句话描述重点和推进目标）
- 金手指首次展示时机（第几章+什么场景+展示方式：暗示/小试/全面展示）

交互方式：
- 结合 Step 5 的创意约束包 opening_hook 字段，深化为具体可执行方案。
- 用”对比法”给 2 种开篇方案让用户选择。

输出：`设定集/开篇策略.md`，同时将核心字段写入 `idea_bank.json` 的 `opening_strategy`。

### Step 5.6：典故引用系统偏好（必收，防 AI 默默跳过）

> **目的**：决定本书是否启用典故引用系统（古典诗词 / 民俗 / 经典 / 地方歌谣 / 原创口诀 / 互联网梗）以及密度等级。这是质感护城河的核心决策，也是《道诡异仙》《我不是戏神》《十日终焉》级作品的隐藏护城河。
>
> **位置的重要性**：必须在 Step 6 一致性复述**之前**完成。若此步骤被跳过，Step 6 摘要会缺失"典故系统核"，进而导致执行生成阶段无法创建 `典故引用库.md` 和 `原创诗词口诀.md`，最终 init 成功标准 fail。

**触发强度表**（AI 必须基于 Step 1 题材自动判断并展示给用户）：

| 题材 | 启用强度 | 默认推荐密度 |
|---|---|---|
| 规则怪谈 / 悬疑灵异 / 克苏鲁 / 民俗志怪 | **强制启用** | 中密度（每 5 章 1 次）|
| 修仙 / 仙侠 / 玄幻 / 历史 / 古言 / 历史脑洞 | **强制启用** | 中密度 |
| 都市脑洞 / 现实题材 / 现代言情 | **默认启用** | 低密度（每 10 章 1 次）|
| 科幻 / 网游 / 电竞 | **可选启用** | 低密度 / 按需 |
| 作者选"品质路线" 或对标《道诡异仙》《十日终焉》等 | **强制启用（覆盖题材默认）** | 高密度（每 3 章 1 次）|

收集项（必收）：

1. **`density_level`**：典故密度偏好（AI 必须展示 5 个选项让用户选择）
   - **高密度**（每 3 章 1 次，对标《道诡异仙》《我不是戏神》）
   - **中密度**（每 5 章 1 次，推荐，对标《十日终焉》）
   - **低密度**（每 10 章 1 次，克制派）
   - **按需**（Context Agent 根据每章场景自动判断是否引用）
   - **不启用**（必须给出拒绝原因，写入 `state.json.cultural_reference_disabled_reason`）

2. **`source_pools`**：启用的来源池（多选，至少选 2 个，不启用时跳过此项）
   - 古典诗词（悼亡 / 山水 / 情感 / 哲思）
   - 民俗典故（地方神祇 / 民间传说 / 禁忌 / 节庆）
   - 儒道释经典（庄子 / 论语 / 礼记 / 心经 / 道德经等）
   - 地方歌谣（哭丧调 / 开路经 / 民间说唱）
   - **原创诗词/口诀**（为本书量身创作，优先级最高）
   - 史料节点（时代背景 / 历史事件）
   - 互联网梗（**仅配角使用，严禁主角**；需明确"重梗黑名单"）

3. **`character_literary_totem`**：为关键角色（主角 / 女主 / 主要反派 / 师傅级导师）分配文学图腾
   - 每角色 1-2 首诗词或 1-2 个典故作为"专属图腾"
   - 示例：主角 → 《诗经·蓼莪》（母亲主题） / 反派 → 苏轼《江城子》（未婚妻主题）

4. **`original_poems_plan`**：原创诗词创作计划
   - 是否在 init 阶段 AI 创作 1-2 条原创诗词草稿（推荐，如"账册扉页题词"/"角色挽联"）
   - 各卷题诗是否作为"每卷开头"的固定资产（推荐）

5. **`internet_meme_policy`**：互联网梗使用政策（若选择启用"互联网梗"来源池）
   - 主角是否可以用：**严禁** / 允许
   - 可用轻梗白名单（如"班味" "松弛感" "多巴胺" "已读乱回" "精神内耗"）
   - 禁用重梗黑名单（如"绝绝子" "栓Q" "泰裤辣" "YYDS"，以及任何与题材严肃场景冲突的梗）

交互方式：
- **AI 必须主动展示触发强度表和 5 个密度选项**，不得默默跳过或自行决定
- 根据 Step 1 题材自动高亮推荐值（如规则怪谈 → 推荐中密度）
- 根据 Step 5 创意约束包的"品质路线"标签覆盖默认推荐
- 根据 Step 2 角色骨架推荐"角色文学图腾"的候选诗词
- 用户必须做出明确选择（或明确拒绝并给出理由）

**参考加载（L1 必读）**：`${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/writing/classical-references.md` — 完整的引用类型分级、融入技法、密度控制、"典故即伏笔"技法

输出：
- 将 `cultural_reference_system` 字段写入 `idea_bank.json`（详细 schema 见"执行生成"段落）
- Step 6 一致性复述必须包含"典故系统核"
- 充分性闸门 #15 检查此字段非空

**AI 违规判定**：
- AI 未主动展示触发强度表 → init fail（AI 自决违规）
- AI 未询问 `density_level` → init fail
- AI 用户选"不启用"但未记录原因 → init fail

### Step 6：一致性复述与最终确认

必须输出”初始化摘要草案”并让用户确认：
- 故事核（题材/一句话故事/核心冲突/主题内核）
- 主角核（欲望/缺陷）
- 金手指核（能力与代价）
- 世界核（规模/力量/势力）
- 叙事声音核（视角/语气/密度/感官/比例）
- 创意约束核（反套路 + 硬约束）
- 情感蓝图核（基调 + 第一卷情感节点）
- 开篇策略核（开篇类型 + 第1章钩子 + 前3章蓝图）
- 节奏偏好核（爽点频率/整体节奏/每卷高潮数）
- **典故系统核**（启用/不启用 + 密度等级 + 来源池 + 角色文学图腾 + 原创诗词计划 + 互联网梗政策）

确认规则：
- 用户未明确确认，不执行生成。
- 若用户仅改局部，回到对应 Step 最小重采集。

## 内部数据模型（初始化收集对象）

```json
{
  "project": {
    "title": "",
    "genre": "",
    "target_words": 0,
    "target_chapters": 0,
    "one_liner": "",
    "core_conflict": "",
    "target_reader": "",
    "platform": ""
  },
  "protagonist": {
    "name": "",
    "desire": "",
    "flaw": "",
    "archetype": "",
    "structure": "单主角"
  },
  "relationship": {
    "heroine_config": "",
    "heroine_names": [],
    "heroine_role": "",
    "co_protagonists": [],
    "co_protagonist_roles": [],
    "antagonist_tiers": {},
    "antagonist_level": "",
    "antagonist_mirror": ""
  },
  "golden_finger": {
    "type": "",
    "name": "",
    "style": "",
    "visibility": "",
    "irreversible_cost": "",
    "growth_rhythm": ""
  },
  "world": {
    "scale": "",
    "factions": "",
    "power_system_type": "",
    "social_class": "",
    "resource_distribution": "",
    "currency_system": "",
    "currency_exchange": "",
    "sect_hierarchy": "",
    "cultivation_chain": "",
    "cultivation_subtiers": ""
  },
  "constraints": {
    "anti_trope": "",
    "hard_constraints": [],
    "core_selling_points": [],
    "opening_hook": ""
  },
  "narrative_voice": {
    "pov": "",
    "tone": "",
    "description_density": "",
    "sensory_focus": "",
    "dialogue_ratio": "",
    "rhetoric_style": "",
    "style_taboos": []
  },
  "emotional_blueprint": {
    "overall_tone": "",
    "volume1_emotional_peaks": [
      {"event": "", "target_emotion": "", "position": ""}
    ],
    "emotional_taboos": []
  },
  "opening_strategy": {
    "opening_type": "",
    "chapter1_scene": "",
    "chapter1_must_convey": [],
    "chapter1_hook": "",
    "first3_chapters_plan": [],
    "golden_finger_reveal": ""
  },
  "pacing_preference": {
    "coolpoint_frequency": "",
    "overall_pace": "",
    "climaxes_per_volume": ""
  },
  "theme": {
    "core_theme": "",
    "reference_works": []
  }
}
```

## 充分性闸门（必须通过）

未满足以下条件前，禁止执行 `init_project.py`：

1. 书名、题材（可复合）已确定。
2. 目标规模可计算（字数或章数至少一个）。
3. 主角姓名 + 欲望 + 缺陷完整。
4. 世界规模 + 力量体系类型完整。
5. 金手指类型已确定（允许“无金手指”）。
6. 创意约束已确定：
   - 反套路规则 1 条
   - 硬约束至少 2 条
   - 或用户明确拒绝并记录原因。
7. 主角卡.md 的"性格与底色"和"OOC警戒"段落有实质内容（非空模板）。
8. 主角卡.md 包含"语音规则"段落（3-5条具体规则）。
9. 世界观.md 至少有世界结构+势力格局+核心规则。
10. 若有女主，女主卡.md 至少有基本信息+性格底色+语音规则。
11. 道具与技术.md / 伏笔追踪.md / 资产变动表.md 已创建（允许初始为空模板）。
12. 叙事声音.md 包含叙述视角+语气基调+描写密度（非空模板，有实质选择）。
13. 情感蓝图.md 包含全书情感基调 + 至少 2 个第一卷情感节点（有事件+目标情感+预计位置）。
14. 开篇策略.md 包含开篇类型 + 第 1 章场景 + 第 1 章钩子 + 前 3 章节奏蓝图 + 金手指展示计划。
15. **典故引用系统偏好已确定**（来自 Step 5.6）：
    - `idea_bank.json.cultural_reference_system.enabled` 字段非空（true/false）
    - 若 enabled=true：`density_level` 非空（高/中/低/按需之一），`source_pools` 至少 2 项，`character_literary_totem` 至少为主角配置 1 项
    - 若 enabled=false：`state.json.cultural_reference_disabled_reason` 非空
    - 强制启用类题材（规则怪谈/修仙/历史/古言/悬疑灵异/克苏鲁/民俗志怪或品质路线）enabled 必须为 true，违反则 init fail

## 项目目录安全规则（必须）

- `project_root` 必须由书名安全化生成（去非法字符，空格转 `-`）。
- 若安全化结果为空或以 `.` 开头，自动前缀 `proj-`。
- 禁止在插件目录下生成项目文件（`${CLAUDE_PLUGIN_ROOT}`）。

## 执行生成

### 1) 运行初始化脚本

```bash
python "${SCRIPTS_DIR}/webnovel.py" init \
  "{project_root}" \
  "{title}" \
  "{genre}" \
  --protagonist-name "{protagonist_name}" \
  --target-words {target_words} \
  --target-chapters {target_chapters} \
  --golden-finger-name "{gf_name}" \
  --golden-finger-type "{gf_type}" \
  --golden-finger-style "{gf_style}" \
  --core-selling-points "{core_points}" \
  --protagonist-structure "{protagonist_structure}" \
  --heroine-config "{heroine_config}" \
  --heroine-names "{heroine_names}" \
  --heroine-role "{heroine_role}" \
  --co-protagonists "{co_protagonists}" \
  --co-protagonist-roles "{co_protagonist_roles}" \
  --antagonist-tiers "{antagonist_tiers}" \
  --world-scale "{world_scale}" \
  --factions "{factions}" \
  --power-system-type "{power_system_type}" \
  --social-class "{social_class}" \
  --resource-distribution "{resource_distribution}" \
  --gf-visibility "{gf_visibility}" \
  --gf-irreversible-cost "{gf_irreversible_cost}" \
  --currency-system "{currency_system}" \
  --currency-exchange "{currency_exchange}" \
  --sect-hierarchy "{sect_hierarchy}" \
  --cultivation-chain "{cultivation_chain}" \
  --cultivation-subtiers "{cultivation_subtiers}" \
  --protagonist-desire "{protagonist_desire}" \
  --protagonist-flaw "{protagonist_flaw}" \
  --protagonist-archetype "{protagonist_archetype}" \
  --antagonist-level "{antagonist_level}" \
  --target-reader "{target_reader}" \
  --platform "{platform}"
```

### 2) 写入 `idea_bank.json`

写入 `.webnovel/idea_bank.json`：

```json
{
  "selected_idea": {
    "title": "",
    "one_liner": "",
    "anti_trope": "",
    "hard_constraints": []
  },
  "constraints_inherited": {
    "anti_trope": "",
    "hard_constraints": [],
    "protagonist_flaw": "",
    "antagonist_mirror": "",
    "opening_hook": ""
  },
  "opening_strategy": {
    "opening_type": "",
    "chapter1_scene": "",
    "chapter1_must_convey": [],
    "chapter1_hook": {"type": "", "content": ""},
    "first3_chapters_plan": ["", "", ""],
    "golden_finger_reveal": ""
  }
}
```

### 3) 自动填充设定集（新增）

基于收集到的数据，自动生成**实质性内容**（非空模板）：

**角色卡填充（必做）**：
- `主角卡.md`：从 protagonist.desire/flaw/archetype 生成完整的性格底色、动机、OOC警戒
  - **必须生成"语音规则"段落**：3-5条具体的说话风格规则（用什么词/不用什么词/句子长度/标志性表达）
- `金手指设计.md`：从 golden_finger 数据生成使用规则、升级路线、爽点嵌入、反馈节奏
- `女主卡.md`：若 heroine_config != "无"，至少填写基本信息+性格底色+与主角关系定位+语音规则
  - 若信息不足，标注"[待展开]"但不留完全空白
- `反派设计.md`：从 antagonist_tiers 生成分层设计+镜像对抗+第1卷小反派详细

**叙事声音文件生成（必做）**：
- `设定集/叙事声音.md`：从 narrative_voice 数据生成，包含：
  - 基础设定（视角/语气/密度/感官/比例）
  - 修辞风格与风格禁忌
  - 风格样本（基于设定生成 1 段 80-120 字的示范段落，展示目标风格）
  - 使用说明：`style-adapter (Step 2B) 必须参照此基准，prose-quality-checker 用此检查跨章一致性`

**情感蓝图文件生成（必做）**：
- `设定集/情感蓝图.md`：从 emotional_blueprint 数据生成，包含：
  - 全书情感基调
  - 第一卷关键情感节点表（事件/目标情感/预计位置）
  - 情感禁区
  - 使用说明：`emotion-checker 参照蓝图验证情感节奏，Context Agent 参照设计 emotion_rhythm`

**开篇策略文件生成（必做）**：
- `设定集/开篇策略.md`：从 opening_strategy 数据生成，包含：
  - 开篇类型与选择理由
  - 第 1 章设计（场景/必传信息/钩子）
  - 前 3 章节奏蓝图
  - 金手指展示计划
  - 使用说明：`Context Agent 在第 1-3 章必须读取此文件，write Step 1 Golden Opening Protocol 参照执行`

**配套文件创建（必做）**：
- `设定集/道具与技术.md`：创建带章节时间线模板头的空文件
- `设定集/伏笔追踪.md`：创建带分类模板的空文件（含"典故伏笔"分类段）
- `设定集/资产变动表.md`：创建带表头的空文件

**典故引用库创建（按题材自动触发，必做或明确拒绝才跳过）**：

> **触发策略**（AI 必须主动执行，不得默默跳过）：
>
> | 题材类型 | 启用强度 | 说明 |
> |---|---|---|
> | 规则怪谈 / 悬疑灵异 / 克苏鲁 / 民俗志怪 | **强制启用** | 典故是世界规则的载体，不启用会导致文笔塌掉 |
> | 修仙 / 仙侠 / 玄幻 / 历史 / 古言 / 历史脑洞 | **强制启用** | 古典诗词/道佛经典/正史野史是天然素材库 |
> | 都市脑洞 / 现实题材 / 现代言情 | **默认启用** | 网络梗 + 现代文化典故，可通过配角使用 |
> | 科幻 / 网游 / 电竞 | **可选启用** | 需要原创口诀/术语库支撑，典故较少 |
> | 作者选择"悬疑正剧品质路线" / 对标《道诡异仙》《十日终焉》《我不是戏神》等 | **强制启用（覆盖题材默认）** | 质感护城河之一 |
>
> **AI 必须在创建流程中主动询问作者一次**："本书是否启用典故引用系统？（诗词/民俗/原创口诀/互联网梗融合）" 选项：
> - **启用 · 高密度**（每 3 章 1 次，对标道诡异仙）
> - **启用 · 中密度**（每 5 章 1 次，推荐）
> - **启用 · 低密度**（每 10 章 1 次，克制派）
> - **按需**（Context Agent 自动判断）
> - **不启用**（必须记录原因到 `state.json.cultural_reference_disabled_reason`）

**创建内容**：
- `设定集/典故引用库.md`：基于题材和世界观，创建带完整模板的引用库初稿。包含：
  - 使用规则（全卷上限/单章上限/允许不用）
  - 角色文学图腾分配（每个主要角色对应 1-2 首诗词/典故）
  - 按题材预填的 6 大分类：
    - **题材核心典籍**（A 级·世界骨架）：如修仙文→道经/佛偈；规则怪谈→礼记/民俗
    - **哲学/思想**（B 级·角色内化）：如庄子/论语/道德经的适用段落
    - **诗词意象**（C 级·氛围点缀）：悼亡诗/山水诗/情感诗
    - **历史典故/人物**（C 级·世界厚度）：如孟婆/奈何桥/泰山府君
    - **地方歌谣/民间文学**（D 级·环境音）：如川渝哭丧调/湘西开路经
    - **互联网梗**（D 级·社交载体）：配角使用，禁主角
  - 每类 2-3 条种子引用（从 Step 4 世界观 + Step 5 创意约束中提取，且对应到具体章节预约）
  - 空的"第 N 卷引用规划总表"表格（待 plan 阶段填充）
  - 指向 `原创诗词口诀.md` 的索引段
- `设定集/原创诗词口诀.md`：创建带完整模板的文件。必须包含：
  - 至少 1-2 条为本书量身创作的原创诗词/口诀（由 AI 在 init 阶段创作草稿）
  - 每条含：世界内来源 + 全文 + 逐句伏笔解析 + 分批释放规划 + 使用约束
  - 角色标志性台词库（每个主角/关键配角 1-3 条）
- **若用户明确表示"不启用"**：记录到 `state.json.cultural_reference_disabled_reason` 字段，并在 `idea_bank.json` 标注 `cultural_reference_system.enabled: false`
- 模板格式详见 `${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/writing/classical-references.md` 第六节

**整合到 idea_bank.json**（必做）：
```json
{
  "cultural_reference_system": {
    "enabled": true,
    "density_level": "高/中/低/按需",
    "reference_files": ["设定集/典故引用库.md", "设定集/原创诗词口诀.md"],
    "character_literary_totem": {"角色名": "对应诗词/典故"},
    "original_poems_planned": [...],
    "key_chapter_allusions": {"第1章": "...", "第3章": "...", "第N章": "..."},
    "internet_meme_policy": {"protagonist_use": "严禁/允许"}
  }
}
```

**语音规则格式**（每个角色卡必须包含）：
```markdown
## 语音规则（写作时强制遵循）
1. {具体的用词/句式规则}
2. {具体的语气/节奏规则}
3. {具体的情绪表达方式}
4. {标志性口头禅或说话习惯}（可选）
5. {禁止的表达方式}（可选）
```

### 4) Patch 总纲

必须补齐：
- 故事一句话
- 主题内核（一句话）
- 核心主线 / 核心暗线
- 创意约束（反套路、硬约束、主角缺陷、反派镜像）
- 反派分层
- 关键爽点里程碑（2-3 条）
- 节奏偏好摘要（爽点频率/整体节奏）
- 参考作品（若有）

## 验证与交付

执行检查：

```bash
test -f "{project_root}/.webnovel/state.json"
find "{project_root}/设定集" -maxdepth 1 -type f -name "*.md"
test -f "{project_root}/大纲/总纲.md"
test -f "{project_root}/.webnovel/idea_bank.json"
test -d "{project_root}/调研笔记"
```

成功标准：
- `state.json` 存在且关键字段不为空（title/genre/target_words/target_chapters）。
- 设定集核心文件存在且有实质内容：`世界观.md`、`力量体系.md`、`主角卡.md`、`金手指设计.md`。
- 主角卡.md 包含"语音规则"段落。
- 若有女主，`女主卡.md` 存在且至少有基本信息+语音规则。
- **`叙事声音.md` 存在且包含视角+语气+密度+感官+比例（非空模板）**。
- **`情感蓝图.md` 存在且包含情感基调+至少2个情感节点**。
- **`开篇策略.md` 存在且包含开篇类型+第1章设计+前3章蓝图**。
- 配套文件已创建：`道具与技术.md`、`伏笔追踪.md`、`资产变动表.md`。
- **典故引用系统（按题材自动触发，必做或明确拒绝才跳过）**：
  - 若题材属于"强制启用"类（规则怪谈/修仙/历史/古言/悬疑灵异/克苏鲁/民俗志怪/作者明确选择品质路线）→ `典故引用库.md` 和 `原创诗词口诀.md` **必须存在且非空模板**，缺失判 init fail
  - 若题材属于"默认启用"或"可选启用"类 → 两个文件**必须存在**（可以是种子模板），或在 `state.json.cultural_reference_disabled_reason` 记录拒绝原因
  - `idea_bank.json` 必须包含 `cultural_reference_system` 顶层字段（enabled/density_level/reference_files/character_literary_totem/original_poems_planned/key_chapter_allusions/internet_meme_policy）
  - AI 未主动询问作者典故偏好直接创建或跳过 → 判 init fail（AI 自决违规）
- `总纲.md` 已填核心主线、约束字段与主题内核。
- `idea_bank.json` 已写入且包含 opening_strategy 且与最终选定方案一致。

## 失败处理（最小回滚）

触发条件：
- 关键文件缺失；
- 总纲关键字段缺失；
- 约束启用但 `idea_bank.json` 缺失或内容不一致。

恢复流程：
1. 仅补缺失字段，不全量重问。
2. 仅重跑最小步骤：
   - 文件缺失 -> 重跑 `init_project.py`；
   - 总纲缺字段 -> 只 patch 总纲；
   - idea_bank 不一致 -> 只重写该文件。
3. 重新验证，全部通过后结束。
