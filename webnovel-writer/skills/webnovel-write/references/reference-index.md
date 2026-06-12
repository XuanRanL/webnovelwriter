# webnovel-write · References 逐文件引用索引

> Round 29 Phase 2 由 SKILL.md 拆分。各 Step 的必读文件已写入 references/steps/step-N.md；
> 本索引用于：条件加载判断（题材/问题定向加读）与新增引用文件时的登记。

## References（逐文件引用清单）

### 根目录

- `references/step-3-review-gate.md`
  - 用途：Step 3 审查调用模板、汇总格式、落库 JSON 规范。
  - 触发：Step 3 必读。
- `references/step-3.5-external-review.md`
  - 用途：Step 3.5 外部模型审查完整规范（15模型架构 · Round 25/供应商 fallback 链/Prompt模板/输出JSON Schema/路由验证/审查报告模板）。
  - 触发：Step 3.5 必读。
- `references/step-5-debt-switch.md`
  - 用途：Step 5 债务利息开关规则（默认关闭）。
  - 触发：Step 5 必读。
- `references/step-6-audit-gate.md`
  - 用途：Step 6 审计闸门调用模板、执行时序、决议逻辑、产物约定、失败恢复路径。
  - 触发：Step 6 必读（主流程 + audit-agent 共同消费）。
- `references/step-6-audit-matrix.md`
  - 用途：Step 6 七层审计矩阵（A 过程真实性 / B 跨产物一致性 / C 读者体验 / D 作品连续性 / E 创作工艺 / F 题材兑现 / G 跨章趋势），约 70 个检查项。
  - 触发：Step 6 必读（audit-agent 执行时加载）。
- `../../references/shared/core-constraints.md`
  - 用途：Step 2A 写作硬约束（大纲即法律 / 设定即物理 / 发明需识别）。
  - 触发：Step 2A 必读。
- `references/polish-guide.md`
  - 用途：Step 4 问题修复、Anti-AI 与 No-Poison 规则。
  - 触发：Step 4 必读。
- `references/no-meta-leak.md`
  - 用途：正文严禁创作术语 / 元叙述泄漏（28 类禁止词全表 + 11 个修复模板 + self-check 清单）。
  - 触发：Step 2A 起草前必读 + Step 4 polish 必检 + 任何项目都适用（本插件所有项目）。
  - hygiene H40 P0 闸门自动检测（commit 前阻断）。
- `references/writing/typesetting.md`
  - 用途：Step 4 移动端阅读排版与发布前速查。
  - 触发：Step 4 必读。
- `references/style-adapter.md`
  - 用途：Step 2B 风格转译规则，不改剧情事实。
  - 触发：Step 2B 执行时必读（`--fast`/`--minimal` 跳过）。
- `references/anti-ai-guide.md`
  - 用途：Step 2A 起草前 AI 倾向预防（8 倾向 + 5 即时检查 + 替代速查表 + 本作 N1-N5 根因映射）。
  - 触发：Step 2A 执行时必读（与 core-constraints.md 并列加载）。
- `references/first-chapter-hook-rubric.md`
  - 用途：Ch1 专属“读者 3 秒决定追读”硬规则，叠加 Round 10 既有 9 项严格规则
  - 触发：chapter == 1 时由 reader-pull-checker 加载并强制走；chapter ∈ (2,3) 跨章衔接弱检查
- `references/visual-concreteness-rubric.md`
  - 用途：Step 2A 起草时即时遵守 + Step 3 prose-quality-checker 评分硬卡
  - 触发：永久加载（与 anti-ai-guide.md 并列）
- `references/chapter-end-hook-taxonomy.md`
  - 用途：reader-pull-checker 必读 + data-agent Step K 必读
  - 触发：永久加载（每章 Step 3 reader-pull-checker 评分 + Step 5 data-agent 落库）
- `references/style-variants.md`
  - 用途：Step 1（内置 Contract）开头/钩子/节奏变体与重复风险控制。
  - 触发：Step 1 当需要做差异化设计时加载。
- `../../references/reading-power-taxonomy.md`
  - 用途：Step 1（内置 Contract）钩子、爽点、微兑现 taxonomy。
  - 触发：Step 1 当需要追读力设计时加载。
- `../../references/genre-profiles.md`
  - 用途：Step 1（内置 Contract）按题材配置节奏阈值与钩子偏好。
  - 触发：Step 1 当 `state.project.genre` 已知时加载。
- `references/writing/genre-hook-payoff-library.md`
  - 用途：电竞/直播文/克苏鲁的钩子与微兑现快速库。
  - 触发：Step 1 题材命中 `esports/livestream/cosmic-horror` 时必读。
- `references/post-commit-polish.md`
  - 用途：Step 8（Post-Commit Polish）完整规范：触发场景、polish_cycle.py 用法、多轮 polish、跨章影响、审计兼容性、恢复策略。
  - 触发：Step 7 commit 之后任何修改正文前必读。
- `references/gate-matrix.md`
  - 用途：充分性闸门 vs hygiene_check H* 项的一一对应表 + 多层防御设计 + 同步维护规则。
  - 触发：新增/修改/删除任一闸门前必读；调试闸门打架时必读。
- `references/round20-quality-floor.md`
  - 用途：Round 20.x 累积的 5 道质量护栏完整规范（A9 dimension floor / reader-thrill 6 子维度 / H26 hook_close 落库一致性 / H27 sunk cost 警报 / polish_cycle max-rounds + deviation 出口）。
  - 触发：所有项目通用必读；Step 3+3.5 → Step 4 → Step 6 → Step 8 链路涉及评分判定/polish 决策/hygiene 检查时必读。
- `references/outline-release-plans-template.md`
  - 用途：所有新书 `大纲/总纲.md` 必含的三计划 schema：`golden_finger_release_plan` / `conflict_release_plan` / `title_promise_payoff_plan`。
  - 触发：`/webnovel-init` 创建新书时 + Step 1 context-agent 读取三计划生成执行包硬约束 + reader-thrill-checker 比对兑现度。

### writing（问题定向加读）

- `references/writing/combat-scenes.md`
  - 触发：战斗章或审查命中“战斗可读性/镜头混乱”。
- `references/writing/dialogue-writing.md`
  - 触发：审查命中 OOC、对话说明书化、对白辨识差。
- `references/writing/emotion-psychology.md`
  - 触发：情绪转折生硬、动机断层、共情弱。
- `references/writing/scene-description.md`
  - 触发：场景空泛、空间方位不清、切场突兀。
- `references/writing/desire-description.md`
  - 触发：主角目标弱、欲望驱动力不足。
- `references/writing/classical-references.md`
  - 用途：典故/诗词/史料/原创口诀/互联网梗的融入技巧、密度控制、“典故即伏笔”技法、项目设定集模板。
  - 触发：Step 1 设计引用方案时 / 审查命中“引用生硬/炫学/出处错误” / Step 4 修复引用问题。
