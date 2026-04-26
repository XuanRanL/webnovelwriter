# Ch1-12 全章体检报告

> **生成日期**：2026-04-26
> **触发**：Round 20 floor 上线后首次回看历史章节
> **方法**：Round 20 floor 数据 + 读者代理 Ch2/3/4 抽样 + 工程证据 12 章全表
> **核心发现**：3 章应重写（Ch3/Ch4/Ch6），5 章应 polish（Ch5/7/8/9/11），4 章可通过（Ch1/2/10/12）

---

## 0. 执行摘要（一张图看完）

| Ch | A9 floor | 读者追读 | 标题方向 | polish_log | nv | 致命问题 | **决策** |
|---:|:---:|:---:|:---:|:---:|:---:|---|:---:|
| 1 | ✓ pass | 7/10* | 末世 4 / 空间 1 / 基地 0 | 11 | v7 | 无（11 轮包袱已过去） | **✓ 通过** |
| 2 | ❌ fail | 7/10 | 末世 3 / 空间 0 / 基地 0 | 1 | v2 | 钱来太顺 + 同代重生者抛得过早 | **🔧 polish** |
| **3** | ❌ fail | 8/10 | 末世 2 / **空间 4** / **基地 4** | 1 | v1 | 抒情稀释钩子 + audit pending | **🔧 polish**（不是 rewrite）|
| **4** | ❌ fail | **4/10** | 末世 4 / 空间 3 / 基地 3 | 1 | v2 | **标题反向**（半指停下） + 全 micro 金手指 + omniscient POV | **❌ Step 0 重写** |
| 5 | ✓ pass | -* | 末世 2 / 空间 2 / 基地 1 | 1 | v2 | 标题方向推进弱 | **🔧 polish** |
| **6** | ✓ pass | -* | 末世 2 / **空间 -1** / 基地 4 | 2 | **v3** | **空间倒退 + 金手指 0 出货 + 五项 80 一线** | **❌ Step 0 重写** |
| 7 | ✓ pass | -* | 末世 4 / 空间 3 / 基地 2 | 2 | v3 | naturalness=83 单维度可补 | **🔧 polish** |
| 8 | ✓ pass | -* | 末世 4 / 空间 1 / 基地 0 | 2 | v3 | 金手指 0 出货 + post_recheck=3 | **🔧 polish** |
| 9 | ✓ pass | -* | 末世 2 / 空间 3 / 基地 0 | 0 | v1 | post_recheck=5（最多） + flow=78 | **🔧 polish** |
| 10 | ✓ pass | -* | 末世 2 / 空间 2 / 基地 2 | 1 | v1 | 全维度 ≥82 | **✓ 通过** |
| 11 | ✓ pass | -* | 末世 2 / 空间 0 / 基地 2 | 1 | v2 | 空间 0 + 金手指沉默 | **🔧 polish** |
| 12 | ✓ pass | -* | 末世 2 / 空间 1 / 基地 0 | 0 | v1 | 无 | **✓ 通过** |

*未抽样章节（仅工程证据）

**汇总**：✓ 通过 3 章 / 🔧 polish 7 章 / ❌ 重写 2 章

> **关键修订**：Ch3 工程数据看起来是 fail（rc=62），但读者代理抽样判断 8/10 + 标题方向唯一 milestone 章 + 标题双 4 分推进——**Ch3 不能重写，要保住，靠 polish 治 rc**。这是数据 vs 读者主观的分歧，**取读者更可信**。

---

## 1. 全局结构性警报（不是单章问题，是 12 章累积）

### 警报 1：决策钩 0/12 — `no_decision_hook_8=true` 持续亮红

```
Ch1-12 hook_close.primary_type 分布:
  动作钩  3 章 (Ch1/7/8)
  信息钩  7 章 (Ch2/3/4/6/10/11/12)  ← 58% 偏重
  情绪钩  2 章 (Ch5/9)
  决策钩  0 章                         ← 致命空白
```

**问题**：决策钩 = 主角主动选择类章末。12 章全没有，意味着主角从未在章末做过推动剧情的关键决定，全是被动应对/收信息/感受情绪。这是读者代理诊断的"主角无正面冲突"在工程层的**量化证据**。

**根治路径**：批 3-B 总纲 conflict_release_plan 已锁死 Ch13-15 必须有 1 次 D 类正面对抗。Ch13 起强制每 5 章至少 1 次决策钩。**这是结构问题，单章 polish 无法解决**。

### 警报 2：金手指 12 章只 4 章真出货

```
真正空间出货章: Ch5（米粒异化 small）, Ch7（物资 35% 入库 medium）,
              Ch9（南瓜汁愈合 medium）, Ch10（催草+籽 small）
金手指沉默章: Ch3 抒情稀释 / Ch6 0 出货 / Ch8 全对话戏 / Ch11 沉默
```

**问题**：标题"我在空间里种出整个基地"承诺 = 空间。12 章只有 4 章真在兑现，且都是 small/medium。Ch6 出现 **-1 倒退**（空间出货为 0，且 Ch3 已经长出齐肩麦穗，Ch6 完全冷处理空间）。

**根治路径**：批 3-B 总纲 golden_finger_release_plan 已锁死 Ch13 = 桃源种出第一批可食用作物（medium 里程碑）+ 每 3 章至少 1 次 medium 强度释放。

### 警报 3：标题三关键词推进失衡（12 章累计分）

| 关键词 | 累计分 | 评价 |
|---|---:|---|
| 末世掌控感 | **33** | 被严重过度推进（沙漏/印记/同代竞争者/反派戏） |
| 基地 | **23** | Ch6/7 基建启动有救（v4 锁死目标卷一末完成主火山口）|
| 空间 | **19** | **远低于其他两条**，且只 4 章真出货 |

**结论**：作者 12 章在悄悄把书写回"系统/重生/世界观文"，违反 CLAUDE.md 北极星"黑雾前 30 天重生，一亩荒地种出整座基地"的 21 字承诺。

---

## 2. 三章 BLOCK 的读者代理详细诊断（Ch2/3/4）

### Ch2 · 二十九天 · 追读 7/10 · 决策 polish
**致命问题**：钱来太顺 + 同代重生者抛得过早
- 原文："屏幕上那根 K 线先跳一小截，然后由绿翻红，直线拉起，冲到顶格停住...浮盈跳到三百四十七万"——零回撤一把顶板，作弊感
- 备忘录"#4732 晚醒了 7 天" Ch2 就抛同代重生者，世界观推得比《末日方案供应商》Ch2 还快

**polish 三条具体修法**：
1. K 线段加 30 秒"先冲到 +5% 回撤一下"的呼吸（消除作弊感）
2. 347 万浮盈不在本章兑现，留"未平仓的浮盈"悬置到 Ch3（让读者攒着）
3. 备忘录 10 个字推迟到 Ch3 末尾（世界观节奏放缓）

**A9 floor 触发原因**：reader-critic=76，前 5 章 <80 触发 cap 80。修后 rc 升到 ≥80 即解除 floor。

### Ch3 · 一颗种子 · 追读 8/10 · 决策 **保住 + polish**

**这一章是这本书的命**——三章里唯一真正在兑现标题"种出整座基地"，标题双 4 分推进（空间 4 + 基地 4）。

> 读者代理原话："三分钟到膝盖，六分钟及腰，十分钟齐肩，半个小时不到，麦穗沉沉"——**这个画面是标题的兑现瞬间**

**致命问题**：钩子被前 100 行抒情稀释 + AI 比喻残留
- "院子中间那棵老榆树还在……叶子在风里晃，像许多小手掌在拍" — 比喻句意象贴标签
- 结尾"他想，昨晚，谁来过"——好钩子但被前面抒情稀释
- reader-critic=62 是真的，不冤；但这是**工艺问题不是结构问题**

**polish 三条具体修法**：
1. 砍 15% 抒情（外公旱烟锅、青砖矮墙那段印记浮现可压缩）
2. 脚印钩子前移到全章 1/2 处先吊一次（章末再呼应）
3. "植物催化（一星觉醒者初阶）" 系统提示太干，加一句具身代价（喉咙发干已有，可加"明天还能不能催"的自我怀疑）

**A9 floor 触发原因**：reader-critic=62 触 hard floor + soft floor。polish 后必须升到 ≥75 才能离开 fail critical。

### Ch4 · 邻居陆老师 · 追读 4/10 · 决策 **❌ Step 0 重写**

**这是三章里最差，也是 12 章里最差的一章**。

**致命问题（三连）**：
1. **标题反向**：Ch3 长出齐肩麦穗，Ch4 退回"半指顶下，两片嫩叶打开，翠色。就停下了"——读者刚被喂饱，Ch4 把金手指收回去，**标题反向就是 critical block**（reader-thrill-checker THRILL_HARD_001 命中）
2. **节奏散文 + 全 micro 金手指**：沙漏 28→27 micro / 空间嫩芽半指 micro / 印记节律不对 micro / 信息差汽修厂老张做记号 micro——**全是 micro，consistency=47 我信**
3. **omniscient POV 偷渡**：陆老师 POV 那一段（"他——变了"）不是第三人称限制，AI 腔很重

**重写后必须发生的核心事件**（Step 0 重启大纲）：
1. **陆老师当面敲院门** 借东西/撞见院里东西，制造首次 NPC 互动（不是巷口背影）
2. **空间至少出 1 个 D 级新成果**（不是降速嫩芽 — 标题方向 medium）
3. **支线任务"找两名核心成员"必须给出第一个候选锁定线索**（不是接完没下文）
4. **外公那条线推进半步**（电话/养老院某事件，呼应 Ch3 老宅）
5. **章末决策钩**（主角对陆老师做出第一次主动选择，破 12 章 0 决策钩）

**Ch4 重写的核心使命**：把 Ch3 的爆发**接住并推向第一位邻居关系**。现在它把爆发**收回去**了——这是**结构性失败**，polish 救不了。

---

## 3. 工程证据触发的额外重写候选（读者未抽样）

### Ch6 · 邻居的狗叫 · narrative_v=v3 · 决策 **❌ Step 0 重写**

**为什么进 rewrite 桶**（虽然 A9 floor pass）：
1. **空间方向 -1 倒退**（Ch3 大爆发后 Ch6 0 出货，比 Ch4 的标题反向更隐蔽）
2. **金手指 0 出货 + 全靠基建撑场**（违反"金手指为主、基建为辅"的标题承诺）
3. **narrative_version=v3** + 五项 80 一线（continuity=78 / flow=79 / reader-pull=80 / high-point=80 / pacing=83）— sunk cost 高
4. polish_log=2 已 polish 两次仍五项 80 一线，再 polish 是 sunk cost trap

**重写后必须发生的核心事件**：
1. 空间至少 1 次 medium 出货（不能 0）
2. 基建只能是次要副本，不能撑全章
3. 章末必须有 1 个决策钩（破 hook trend 紧急）
4. 字数控制 2800-3200（不是当前 3451 偏长）

**风险评估**：Ch6 重写会触发 Ch7-8 上下文链断裂（Ch7-8 已基于 Ch6 v3 写完）。**实施前必须先评估 Ch7-8 修改成本**，否则可能引发连锁。

### 其他工程层值得注意

- **Ch1 polish 11 轮 v7** 虽然通过（A9 pass + audit approve），但 polish_log=11 是 sunk cost 警报。**Round 20 max-rounds=3 防御已落地**，未来不会再重演。Ch1 当前状态接受历史包袱，**不动**。

---

## 4. 5 章 polish 名单（最该优先做的 3 件事）

| Ch | 主要问题 | polish 具体动作 | 预期 floor 解除 |
|---:|---|---|---|
| 2 | rc=76 | K 线加摩擦 + 推迟世界观信息 + 浮盈悬置 | rc 升 ≥80 解 EARLY_RC |
| 3 | rc=62 | 砍 15% 抒情 + 钩子前移 + 加具身代价 | rc 升 ≥75 解 hard+soft |
| 5 | 标题方向弱 | Ch5 加 1 段"米粒异化的更明确回甘" + 林晚秋伏笔加深 | 已 pass，纯加分 |
| 7 | naturalness=83 | reader-naturalness 子维度定向 polish（参 Round 19 Phase C K/L/M/N）| 单维度提升 |
| 8 | 金手指 0 出货 + post_recheck=3 | 加 1 段沙漏读出秦岳更多信息 + 桃源至少出 1 件物 | 标题方向推进 |
| 9 | post_recheck=5 (最多) + flow=78 | flow 子维度定向 + 5 项复测分整理一致性 | 单维度提升 |
| 11 | 空间 0 + 金手指沉默 | Ch11 加 1 段桃源夜间观察"印记呼应汽笛"具象化 | 标题方向 |

---

## 5. 重写名单（Ch4 + Ch6）实施路径

### Ch4 重写流程
```
1. 用 polish_cycle 把当前 Ch4 v2 标记为 v2.archived（保留备份）
2. 走 /webnovel-write 4（标准模式 Step 0→7）
3. context-agent 必须读：
   - 总纲三计划（golden_finger / conflict / title_promise）
   - Ch3 hook_close（信息钩"昨晚谁来过"）
   - Ch5/6 已写正文（保持下游一致性）
4. Step 1 执行包硬约束（reader-thrill 6 子维度目标）：
   - golden_finger_release ≥ 75（D 级新成果）
   - protagonist_victory ≥ 70（邻居首次互动主动）
   - title_promise_payoff ≥ 75（标题方向 medium）
   - plot_momentum ≥ 80（事件密度）
5. Step 3+3.5 跑全套 13 内 + 14 外（含 thrill）+ A9 floor 验证
6. Step 4 polish 直到 A9 pass（任一 <60 = block，rc <80 = block 前 5 章）
7. Step 6 audit_decision ∈ {approve, approve_with_warnings}
8. Step 7 commit
```

**估算工时**：Ch4 重写 ≈ 5-8h（大纲层调整 + 起草 + 审查 + polish）

### Ch6 重写流程（更复杂）
```
比 Ch4 多一步：先评估 Ch7-8 上下文链断裂成本
- 如果 Ch7-8 引用 Ch6 钩子的部分能保住，重写 Ch6 + 微调 Ch7-8 的 1-2 段引用
- 如果 Ch7-8 整体依赖 Ch6 v3 的具体事件链，建议 polish 而不是重写
- 建议：先做 Ch6 dry-run 重写（不 commit），看 Ch7-8 影响面
```

**估算工时**：Ch6 重写 + Ch7-8 微调 ≈ 8-12h

---

## 6. 这次体检要根治的 3 个潜伏 bug

### Bug 1：标题方向倒退未被自动检测
**root cause**：reader-thrill-checker 已注册（Round 20）但还没真实跑过；A9 floor 只看 13 维度数值，不看"标题方向是否倒退"。Ch4 半指停下 vs Ch3 齐肩麦穗，A9 不会 catch。

**根治**：当 Ch13 真实跑 reader-thrill 时，THRILL_HARD_001（标题反向 → critical）会自动触发。回填验证 Ch4 应被 thrill block。

**短期权宜**：手动用 reader-thrill 子维度 prompt 重测 Ch4 → 写入 chapter_meta.thrill_score 作为重写决策依据。

### Bug 2：连续无决策钩 8 章但只是 P1 warn 不阻断
**root cause**：H25 hook_trend 设计是"提醒下章 reader-pull-checker 切换钩子类型"，没有硬阻断。

**根治建议**：扩展 hygiene H25 → 当 `no_decision_hook_8=true` 时升 P0 fail（决策钩 = 主角主动选择 = 网文核心爽点，不能连续 8 章缺）。

**短期权宜**：Ch13 起在 context-agent 执行包硬塞 "本章必须有决策钩" 约束。

### Bug 3：narrative_version=v3 + polish_log≥2 是 sunk cost 警报，但流程没识别
**root cause**：Round 20 加了 polish max-rounds=3 上限，但**已经达到 v3 的章节**（Ch6/7/8）不会回头被识别为"该重写而不是再 polish"。

**根治建议**：扩展 hygiene 加 H27 — 当章节 narrative_version >= v3 且 polish_log >= 2 + 5 项以上 checker 在 80 一线 → 升 deviation 提示"考虑回 Step 0 重写而非继续 polish"。

**短期权宜**：手动按本报告 §3 评估 Ch6 是否走重写路径。

---

## 7. 推荐实施顺序

### 立刻做（今天 ≈ 30 分钟）
1. ✓ 已完成：Ch1-12 体检报告（本文档）
2. ✓ 已完成：Round 20 commit（5551f07）
3. **新增**：手动测 Ch4 reader-thrill（用 prompt 跑 6 子维度，验证 THRILL_HARD_001 命中）

### 这周做（≈ 4-6h · polish 优先批）
4. **Ch3 polish**：砍 15% 抒情 + 钩子前移 + 加具身代价。预期 rc 62→78+。
5. **Ch2 polish**：K 线加摩擦 + 推迟世界观信息。预期 rc 76→80+。
6. polish_cycle 跑完后 A9 floor 应解除 Ch2/Ch3 的 fail critical。

### 下周做（≈ 8-12h · 重写批）
7. **Ch4 Step 0 重写**：参 §5 流程，读者代理复诊 → 追读分目标 ≥7。
8. **Ch6 dry-run 评估**：先看 Ch7-8 上下文链断裂成本，再决定是否重写。

### 不做的事（明确边界）
- ❌ Ch1 不动（11 轮 polish 是历史包袱，已通过 A9 + audit approve，再修 sunk cost）
- ❌ Ch5/7/8/9/11 暂不动（A9 pass + 主要是单维度补丁，等 Ch13 跑通新流程后再回来 polish 一批）
- ❌ Ch10/12 不动（全维度 ≥82，无须修）

---

## 8. 终极判断

> **这本书 12 章里只有 1 章（Ch3）真在兑现标题，2 章（Ch4/Ch6）在偷偷把书写回"内心戏 + 基建文"。**
>
> **Ch3 必须保住、Ch4 必须重写、Ch6 评估后决定。其他 9 章先放一边，等 Ch13 跑通新流程后再统一 polish。**
>
> **Round 20 floor + reader-thrill + 三计划已经把"未来不会再发生"的护栏建好。这次体检是把"过去已经发生的"漂移找出来——3 个根治措施都不需要再加新代码，直接用现有工具修。**

---

## 附录 A · 数据来源

- `state.json/chapter_meta.0001-0012.checker_scores` (13 维度逐章分数)
- `state.json/chapter_meta.0001-0012.polish_log + narrative_version`
- `state.json/chapter_meta.0001-0012.hook_close.primary_type`
- `audit_reports/ch{0001-0012}.json` (audit_decision)
- `tmp/reader_pull_ch{0001-0012}.json` (hook_close 子对象)
- `webnovel.py state get-hook-trend --last-n 12` (跨章决策钩缺失检测)
- 读者代理 Read 4 章正文（Ch1 前 800 字 + Ch2/3/4 全文）

## 附录 B · Ch1-12 在 Round 20 评分体系下的 floor 结果（量化命中）

```
Ch1  92→92 ✓ pass
Ch2  89→80 ❌ fail (FLOOR_EARLY_RC: rc=76 <80 cap 80)
Ch3  85→80 ❌ fail (FLOOR_SOFT: rc=62 <75 cap 85; FLOOR_EARLY_RC cap 80)
Ch4  88→70 ❌ FAIL CRITICAL (FLOOR_HARD: cons=47, rc=58 <60; FLOOR_SOFT 4 维; FLOOR_EARLY_RC)
Ch5  89→90 ✓ pass
Ch6  85→85 ✓ pass (但 5 项 80 一线，sunk cost)
Ch7  89→89 ✓ pass
Ch8  89→89 ✓ pass
Ch9  89→89 ✓ pass
Ch10 88→88 ✓ pass
Ch11 90→90 ✓ pass
Ch12 89→89 ✓ pass
```

**Ch4 旧 88 → 新 70 = 第一次"评分体系不撒谎"的真实证据。**

---

**报告结束。**
