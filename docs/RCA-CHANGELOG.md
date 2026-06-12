# RCA 叙事归档（agent 不加载）

> Round 29 元规则：prompt 文件（SKILL.md / agents/*.md / references/steps/*.md）只保留可执行规则，
> 每条一行；事故复盘叙事（"根因 / 血教训 / 为什么需要"）归档到本文件，供人类回溯，agent 不加载。
> 新增护栏一律优先落为 CLI 闸门 + 单测；本文件按 Round 倒序追加。

---

## Round 29 · Phase 6（2026-06-12）质量纠偏的实证依据

- **签名词配额副作用**：Ch16/Ch23 "没X→未X" 替换污染三复发；R28.33 "过+量词" 替代效应 25+ 处；
  Ch36 五次 post_draft 打回循环。block 驱动的是同义替换打地鼠，不是更好的句子。
- **机械插入义务副作用**：R28.49 加入的 4 项起草义务（NPC exit / >30min 过渡 / 情感清单 / 时间戳解释）
  与 density-checker 反填充段目标自相矛盾；时间跳切、人物淡出本是正常小说技法。
- **复测锚定**：复测模板向 checker 传 prev_score + 要求 "≥+3"，是明示阅卷人涨分——Ch7 pacing 58→90
  的 +32 中有多少是锚定通胀无法区分。改盲评后 delta 才可信。
- **polish 副作用**：R28.36 "合肥物科院" 凭印象传染 12 处、R28.46 canon 冲突、R28.15 三章 polish 副作用——
  全部发生在全文改写 pass。Step 2B 默认 verify-only + medium/low 默认不修，收窄改写面。

## Round 29 · Phase 1-2（2026-06-12）

### Phase 1 · workflow 簿记代码化

**移除的 4 段 SKILL.md 红字块**（同源根因，已由 strict 默认开启 + run-step 代码强制替代）：

- Step 2B（R28.46 #2）：Ch46 主流程直接 Edit polish 后才调 complete-step → implicit_start=True → audit A6 HIGH warn 累积。
- Step 3.5（R28.22）：跳过 start-step 直接 complete-step → A6 HIGH 累积。
- Step 4（R28.49）：Ch48 完成 Step 3.5 后直接调 polish Edit → 同上。
- Step 5（R28.1）：Ch17/Ch25 直接调 data-agent → 同上。

**结论**：同类失误在 4 个步骤上各复发一次，证明"加红字"防不住流程性遗忘；代码层拒绝（strict 默认）让失误当场暴露当场自愈，4 段红字一起删除。

### Phase 2 · SKILL.md 骨架化

SKILL.md 1525 行 → 215 行骨架；15 个 Step 段落原文移入 `skills/webnovel-write/references/steps/step-N.md`
（lazy-load：进入该步时才加载，起草期上下文不再被 Step 3-8 的 ~800 行细节占用）。
References 逐文件清单移入 `references/reference-index.md`。
顺手修复一处原文内部矛盾：模式定义 `--minimal` 旧文"仅3个基础审查"与 Chapter Gate"5 checker"不一致，
统一为 5（Round 13 v2 口径：naturalness + reader-critic + consistency + continuity + ooc）。
