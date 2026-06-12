# webnovel-write · Step 3.5 外部模型审查（含 Step 3+3.5 完成闸门）

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

### Step 3.5：外部模型审查（与 Step 3 并行或紧接执行）

执行前必须加载：
```bash
cat "${SKILL_ROOT}/references/step-3.5-external-review.md"
```

硬要求：
- **必须使用 `--model-key all --dimension-strategy auto` 一次性执行全部 15 模型**，禁止手动逐个调用（防止遗漏模型）。
- 默认 combined：每个模型 1 次请求返回 13 个 `dimension_reports`，避免 13 次重复发送完整上下文；JSON 不可用或维度缺失时自动 split fallback。
- 不再有核心3必成硬耦合；Step 6 A3 按 ≥10/15 有效模型判定健康。
- 按 reference 文件中的 Prompt 模板构建 system 消息。
- 每次 API 调用后验证路由（检查 response.model 字段）。
- Round 14+ 3-tier fallback 链：ark-coding（火山，主 · 重试 2 次）/ openclawroot（主 · fail-fast）→ siliconflow（兜底，仅 glm-5/glm-4.7/deepseek/V4-Flash 备用或主路）。
- 输出 JSON 必须包含 model_actual、routing_verified、provider_chain、cross_validation。
- 生成审查报告必须包含 15 模型 × 13 维度（含 reader_flow + naturalness + reader_critic · Round 13 v2）评分矩阵 + 共识问题 + Step 4 修复清单。

**上下文文件准备（调用脚本前必须完成）**：

脚本从 `{PROJECT_ROOT}/.webnovel/tmp/external_context_ch{chapter_padded}.json` 加载上下文。**若文件不存在，脚本将报错退出（exit 1）**。主流程必须在调用脚本前构建此文件，包含 **14 个字段**（核心 6 + 质感 3 + 典故 2 + 状态 + 前章）：

```bash
# 收集设定集、大纲、前章正文，写入 14 字段 context JSON
python -X utf8 "${SCRIPTS_DIR}/build_external_context.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter ${chapter_num}
```

`build_external_context.py` 加载的 14 字段：
- 核心 6：总纲 / 主角卡 / 金手指设计 / 女主卡 / 反派设计 / 力量体系 / 世界观
- 质感 3：叙事声音 / 情感蓝图 / 开篇策略
- 典故 2：典故引用库 / 原创诗词口诀（存在即加载，不存在自动跳过）
- 状态：protagonist_state（来自 state.json）
- 前章：前 N-1 章正文（最多 15000 字）

若脚本失败，手动从设定集文件读取并用 `Write` 工具写入 JSON。**禁止跳过此步骤直接调用 external_review.py**。**禁止回退到旧的 9 字段内联脚本，否则外部 15 个模型将盲评无法看到作者要求的克制风格、情感蓝图、典故伏笔等关键信息。**

> **🔴 Round 28.50 · 调用前必跑 healthcheck (Ch48 实战 4/15 静默挂死 根治)**
>
> Ch48 实战首次 `python external_review.py --model-key all` 后台跑 → 4/15 模型完成后**静默卡死**, stderr 0 行, 必须手动重启才完成 15/15. 根因: 多并发 + 单个 provider 超时未触发 fast-fail.
>
> **永久根治** — 主调用之**前**必跑 healthcheck:
>
> ```bash
> # Step A: healthcheck (验证 API key + provider 可用 · ~30s)
> python -X utf8 "${SCRIPTS_DIR}/external_review.py" \
>   --project-root "${PROJECT_ROOT}" \
>   --chapter {chapter_num} \
>   --healthcheck
> # 输出 .webnovel/tmp/external_healthcheck_{ts}.json
> # 若 healthy_count < 10/15 → 修复 API key 或换 provider 再继续
> ```

调用命令：
```bash
python -X utf8 "${SCRIPTS_DIR}/external_review.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter {chapter_num} \
  --mode dimensions \
  --model-key all \
  --dimension-strategy auto \
  --max-concurrent 5   # Round 28.50 · 默认 6, 降到 5 防 timeout 集群挂死
```
⚠️ 脚本仅支持：`--project-root`, `--chapter`, `--mode`, `--model-key`, `--models`, `--dimension-strategy`, `--model-concurrent`, `--max-concurrent`, `--rpm-override`, `--rpm-override-provider`, `--no-merge-partial`, `--healthcheck`。不要传其他参数。

输出：
- 每模型一个 `.webnovel/tmp/external_review_{model_key}_ch{NNNN}.json`（共15个文件；combined 正常路径每文件由 1 次模型请求生成）
- 审查报告 `审查报告/第{NNNN}章审查报告.md`（含 15 模型 × 13 维度矩阵，包括 reader_flow + naturalness + reader_critic · Round 13 v2）

### Step 3+3.5 完成闸门（进入 Step 4 前必须通过）

**硬规则：Step 4 不得在 Step 3 或 Step 3.5 有任何子任务仍在运行时开始。**

验证方式：
1. 逐一检查所有 Step 3 内部 checker 的 Task 状态（`TaskOutput` 或等价轮询），确认每个 checker 都已返回结果（非空输出）。
2. 确认 Step 3.5 外部审查脚本已退出且 15 个 `external_review_{model_key}_ch{NNNN}.json` 文件已生成。
3. 按 `step-3-review-gate.md` 的“内外部分数合并规则”计算 `overall_score`（需要内部 + 外部都有分数）。
4. 生成审查报告（含内部 13 评分维度 + 外部 15 模型×13 维度矩阵，内外均含 reader_flow + naturalness + reader_critic · Round 13 v2 读者视角双维度进入外部模型评分体系）。
5. 落库 `review_metrics`。

**以上 5 步全部完成后，方可进入 Step 4。等待是流程的一部分。**

**Step 3→4 闸门强制验证**（在标记 Step 3 完成前必须执行）：
1. 对每个已启动的内部 checker Task 调用 `TaskOutput`，确认输出非空。若任一 checker 输出为空，继续等待（轮询间隔30s，每批最多等待10分钟，总超时20分钟）。超时仍未返回的 checker 标记为 timeout 并写入审查报告。注意：0+6+5 三段模式下，Batch 0（2 个读者视角 checker 并行：naturalness + reader-critic · Round 13 v2）先跑，两个都返回后启动 Batch 1（6 个含 flow-checker），Batch 1 全部返回后再启动 Batch 2（5 个），每段独立计时。Round 13 v2 取消 veto block——Batch 0 的结果直接合并进聚合，不单独 block。
2. 检查 `.webnovel/tmp/external_review_{model}_ch{NNNN}.json`：统计有效模型数；≥10/15 为健康，8-9/15 degraded_ok，5-7/15 degraded_warn，<5/15 critical。
3. 聚合分数：内部 13 个评分维度取平均（含 flow-checker + naturalness + reader-critic · Round 13 v2）；外部已成功模型取平均（13 维度）；合并 `round(internal * 0.6 + external * 0.4)`。
4. 写审查报告 + 落库 review_metrics。
**违规后果**：跳过此验证直接进入 Step 4，Step 6 审计 A2 检查项将检测到 checker 坍缩并可能 block 提交。

：5 个 checker（reader-pull / reader-naturalness / reader-critic / consistency / continuity）返回 findings 后未自动 Write 落盘，hygiene_check.py H26+H63 报 P0 阻断 commit，必须手动补盘 5 个 JSON 才能通过。

**根因**：subagent 定义 tools 列表此前缺 `Write`（已修：Round 28.21 给 14 个 checker 全部加上 Write 工具），但 subagent 仍可能"忘记调用 Write"。

**双保险硬规则**：

1. **subagent 侧**（已修复）：14 个 checker 的 tools 全部含 `Write`；每个 checker.md 的"执行"段第 4 步明确"Write 落盘到 `.webnovel/tmp/{checker_id}_ch{NNNN}.json`"。
2. **主流程侧**（本节硬约束）：Step 3 complete-step 之前，**必须**逐一验证 13 个 `.webnovel/tmp/{checker_id}_ch{NNNN}.json` 落盘存在；任一缺失则**主流程 Write 工具补盘**（用 subagent 返回的 findings 重建 JSON）。
3. **完整 checker JSON 文件名清单**（13 canonical）：
   - `reader_naturalness_check_ch{NNNN}.json`
   - `reader_critic_check_ch{NNNN}.json`
   - `consistency_check_ch{NNNN}.json`
   - `continuity_check_ch{NNNN}.json`
   - `ooc_check_ch{NNNN}.json`
   - `reader_pull_ch{NNNN}.json`（注：reader-pull 文件名约定无 `_check` 后缀）
   - `high_point_check_ch{NNNN}.json`
   - `flow_check_ch{NNNN}.json` 或 `flow_ch{NNNN}.json`（双名兼容）
   - `pacing_check_ch{NNNN}.json`
   - `dialogue_check_ch{NNNN}.json`
   - `density_check_ch{NNNN}.json`
   - `prose_quality_check_ch{NNNN}.json`
   - `emotion_check_ch{NNNN}.json`
4. **Step 3 complete-step 前 sanity check (Round 28.27 加强：必须 parseable)**：
   ```bash
   python -X utf8 -c "
   import json, os
   chap = '${chapter_padded}'
   files = ['reader_naturalness_check','reader_critic_check','consistency_check','continuity_check','ooc_check','reader_pull','high_point_check','flow_check','pacing_check','dialogue_check','density_check','prose_quality_check','emotion_check']
   for cid in files:
       p = f'.webnovel/tmp/{cid}_ch{chap}.json'
       if not os.path.exists(p):
           print(f'MISSING: {cid}'); continue
       try:
           json.load(open(p, encoding='utf-8'))
       except json.JSONDecodeError as e:
           # H71 嵌套引号 / 编码错误 / 截断 → 必须先修复
           print(f'BROKEN: {cid}: {e}')
   "
   ```
   任一 MISSING 必须先补盘再 complete-step。任一 BROKEN（通常因 H71 ASCII 引号嵌套）必须先用以下脚本修复：
   ```python
   # 自动 repair：把嵌套 ASCII " 改成括号 ( )
   import json, pathlib, re
   p = pathlib.Path('.webnovel/tmp/<broken_file>.json')
   raw = p.read_text(encoding='utf-8')
   out = []
   for line in raw.split('\n'):
       m = re.match(r'(\s*"[a-z_]+"\s*:\s*")(.*)("(,?)\s*)$', line)
       if m and not line.strip().startswith('"problems"'):
           prefix, content, suffix, _ = m.groups()
           depth = 0; new = []
           for ch in content:
               if ch == '"':
                   new.append('(' if depth % 2 == 0 else ')'); depth += 1
               else:
                   new.append(ch)
           out.append(prefix + ''.join(new) + suffix)
       else:
           out.append(line)
   fixed = '\n'.join(out)
   json.loads(fixed)  # 验证
   p.write_text(fixed, encoding='utf-8')
   ```
   **Round 28.27 RCA**: Ch41 reader-critic / ooc-recheck 两份 JSON 都 H71 复发, 即使
   subagent.md 已写禁嵌套规则。根因是 subagent prompt 落盘前未做 json.load 自检——
   主流程必须代替 subagent 做这道闸门, 否则 hygiene H71 P0 阻断 commit 才发现就晚了。
