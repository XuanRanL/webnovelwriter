# webnovel-write · Step 2B 风格适配

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

### Step 2B：风格适配（`--fast` / `--minimal` 跳过 · Round 29 默认 verify-only）

> **Round 29 Phase 6.4 · 默认路径 = verify-only no-op**
>
> R28.51 实测：Step 2A 已按项目风格起草时，Step 2B 实际改动 < 5 字/章；而每多一次全文改写
> pass 就多一次引入 canon 漂移的机会（R28.36 "合肥物科院" 传染 12 处 / R28.46 canon 冲突均发生在
> 改写 pass）。因此 Step 2B **默认只做 grep verify，不动笔**；登记纪律保留（禁止跳过登记）。

**默认路径（verify-only）**：

```bash
python webnovel.py workflow start-step --step-id "Step 2B" --step-name "Style adapter"
# grep verify：扫模板腔/说明腔/机械腔标志（无 Edit）
# 示例：grep -nE "(他知道|她明白|事实上|显然|不得不说)" 正文/第${chapter_padded}章*.md
python webnovel.py workflow complete-step --step-id "Step 2B" \
  --artifacts '{"style_applied": false, "deviation_notes": "R29 默认 verify-only: Step 2A 已按项目风格起草 + post_draft_check 通过, grep verify 0 模板腔, 无 Edit"}'
```

deviation_notes 必填，留 audit-agent trace。**禁止**完全跳过 Step 2B 登记。

**改写路径（仅以下任一条件触发才动笔）**：
1. grep verify 检出模板腔/说明腔/机械腔 ≥ 3 处；
2. Step 1 执行包 `style_guidance` 明确要求本章风格转译（如视角实验章/文风特化章）；
3. 用户显式要求。

改写时执行前加载：
```bash
cat "${SKILL_ROOT}/references/style-adapter.md"
```

改写硬要求：
- 只做表达层转译，不改剧情事实、事件顺序、角色行为结果、设定规则。
- 对"模板腔、说明腔、机械腔"做定向改写，为 Step 4 留出问题修复空间。
- artifacts 填 `{"style_applied": true}`。

输出：
- 风格化正文（覆盖原章节文件）或 verify-only artifact。

改写路径专属收尾（verify-only 路径跳过）：
- U+FFFD 编码验证（同 Step 2A，确保转译未引入损坏）。
- **起草后硬闸门再次执行**（转译可能引入新问题）：
```bash
python -X utf8 "${SCRIPTS_DIR}/post_draft_check.py" ${chapter_num} --project-root "${PROJECT_ROOT}"
```
