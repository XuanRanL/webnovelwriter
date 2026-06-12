# webnovel-write · Step 2B 风格适配

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

### Step 2B：风格适配（`--fast` / `--minimal` 跳过）

执行前加载：
```bash
cat "${SKILL_ROOT}/references/style-adapter.md"
```

硬要求：
- 只做表达层转译，不改剧情事实、事件顺序、角色行为结果、设定规则。
- 对"模板腔、说明腔、机械腔"做定向改写，为 Step 4 留出问题修复空间。

> **🔴 Round 28.51 · Step 2B no-op 显式声明 (Ch49 RCA)**
>
> Ch49 实战发现 Step 2B 与 Step 4 polish 职责重叠: 当 Step 2A 已严格按项目克制风格起草 + 签名密度 OK + 无模板腔时, Step 2B 实际改动量 < 5 字 / 章, 接近 no-op。
> **新规则**: 起草已符合项目风格时, Step 2B 可声明 no-op, 但必须显式登记:
>
> ```bash
> python webnovel.py workflow start-step --step-id "Step 2B" --step-name "Style adapter"
> # ... 实际只做 grep verify (无 Edit), 或 1-2 处微调
> python webnovel.py workflow complete-step --step-id "Step 2B" \
>   --artifacts '{"style_applied": false, "deviation_notes": "Step 2A 已严格按项目克制风格起草 + post_draft_check 通过 + 0 模板腔, Step 2B 仅 grep verify 无 Edit"}'
> ```
>
> deviation_notes 必填, 留 audit-agent trace。**禁止**完全跳过 Step 2B 登记。

输出：
- 风格化正文（覆盖原章节文件）或 verify-only artifact。

U+FFFD 编码验证（同 Step 2A，风格转译后再次执行，确保转译未引入损坏）。

**起草后硬闸门再次执行**（Step 2B 后 · 转译可能引入新问题）：
```bash
python -X utf8 "${SCRIPTS_DIR}/post_draft_check.py" ${chapter_num} --project-root "${PROJECT_ROOT}"
```
