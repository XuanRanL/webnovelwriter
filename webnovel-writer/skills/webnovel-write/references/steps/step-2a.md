# webnovel-write · Step 2A 正文起草

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

### Step 2A：正文起草

执行前必须加载：
```bash
cat "${SKILL_ROOT}/../../references/shared/core-constraints.md"
cat "${SKILL_ROOT}/references/anti-ai-guide.md"
cat "${SKILL_ROOT}/references/visual-concreteness-rubric.md"
# Round 19.1 P0-3：chapter ≤ 5 时必须加载 first-chapter-hook-rubric（首章追读契约 + Ch2-3 跨章弱版）
if [ "${CHAPTER_NUM}" -le 5 ]; then
  cat "${SKILL_ROOT}/references/first-chapter-hook-rubric.md"
fi
```

#### Round 19.1 P0-3 · 前 5 章写前自检（X1 强制流程，对应 anti-ai-guide.md §"前 5 章 reader-critic 写前自检清单"）

仅当 `chapter ≤ 5` 时，**起草前**必须输出 `tmp/pre_draft_self_check_ch{NNNN}.json`，含 5 类自检项：

```json
{
  "chapter": 3,
  "phase": "pre_draft_self_check",
  "items": [
    {"id": "1_golden_finger_timing", "verdict": "PASS|WARN|FAIL", "evidence": "本章金手指披露符合 state.golden_finger 梯度"},
    {"id": "2_unbacked_terms", "verdict": "...", "evidence": "新出场实体均有 1 句以上身份暗示"},
    {"id": "3_climax_payoff_rate", "verdict": "...", "evidence": "outline 列出爽点 2/2 兑现"},
    {"id": "4_loop_pacing", "verdict": "...", "evidence": "新铺设钩子 1 条，先闭上章 2 条"},
    {"id": "5_reader_stuck_points", "verdict": "...", "evidence": "无突兀编号 / 无单段说明 / 无跨语境隐喻"}
  ],
  "verdict": "PASS|NEEDS_ADJUST|REWRITE_RECOMMENDED",
  "all_fail_count": 0,
  "all_warn_count": 0
}
```

**自检 verdict 处理规则**（违反即阻断 Step 2A）：

- `verdict=REWRITE_RECOMMENDED`（≥ 2 FAIL）→ writer 必须**回 Step 1** 重做大纲再起草，禁止本步进入正文起草
- `verdict=NEEDS_ADJUST`（1 FAIL 或 ≥ 3 WARN）→ writer 起草时刻意规避，并在 `tmp/pre_draft_self_check_ch{NNNN}.json` 同时写 `writing_constraints_addendum`：起草中至少包含对应规避动作 1 处
- `verdict=PASS` → 正常起草

5 类自检项详细定义见 `references/anti-ai-guide.md` § "Round 19 Phase X1 · 前 5 章 reader-critic 写前自检清单"。

**与 Phase X1 reader-critic <75 全卷 P0 阻止配套**：写前自检接住 Ch1-5 的"金手指披露突兀 / 编号无铺垫 / 爽点未兑现 / 伏笔超载"等高风险（这些是 reader-critic Ch3=62/Ch4=58 历史谷底的真实根因）。

硬要求：
- 只输出纯正文到章节正文文件；若详细大纲已有章节名，优先使用 `正文/第{chapter_padded}章-{title_safe}.md`，否则回退为 `正文/第{chapter_padded}章.md`。
- 默认按 2200-3800 字执行；若大纲为关键战斗章/高潮章/卷末章或用户明确指定，则按大纲/用户优先。
- 禁止占位符正文（如 `[TODO]`、`[待补充]`）。
- 保留承接关系：若上章有明确钩子，本章必须回应（可部分兑现）。
- 爽点密度（按章节类型，Round 29 调整为指引而非配额）：推进/战斗/高潮章建议每 800 字 1 个微爽点（信息揭示/小胜/认可/逆转/兑现）；日常/buffer/铺垫章**不设配额**，以执行包的爽点规划与 high-point-checker 的语境评估为准——为凑配额插入假爽点比密度不足伤害更大（R22.x 调性裁决：前期日常种田节奏优先）。
- 典故引用融入：若 Context Agent 在执行包中推荐了引用（0-2 条），按推荐的载体和融入方式写入正文。化用 > 引用，角色内化 > 旁白注释。判断不适合时可跳过——**允许不用**。无推荐时不主动引用。（详见 `references/writing/classical-references.md`）
- **复述前章人物原话必须 Grep 原文校验**。任何时候在正文写"X说过/告诉过/吩咐过/警告过……"等复述句，**起草前必须 Grep 该角色名+关键词在前章正文**确认原话。Ch42 L9 凭印象写"<antagonist>告诉他……合作化路那处守得严，先别动"——但 Grep Ch19/Ch20 发现<antagonist>原话只说"金陵饭店人最齐别先去"，从未提合作化路守严——continuity-checker 给出 13 分 critical。**规则**：复述句中的"原话"必须 100% 在前章正文 Grep 命中，禁止凭印象添加细节或合成多段对白。
- **禁止"X章前/X章后/X章之前"等数字章号距离指代**。这是 H40 元叙述泄漏的隐蔽变体——把"Ch19 第十九章"换成更隐蔽的"二十二章前"仍属章号自我指称，post_draft_check.py 已扩展 cn_chapter_meta_pattern 涵盖多位中文数词。用"那一晚/上个月/那回/记忆里那次"等自然时间表达替代。

中文思维写作约束（硬规则）：
- **禁止“先英后中”**：不得先用英文工程化骨架（如 ABCDE 分段、Summary/Conclusion 框架）组织内容，再翻译成中文。
- **中文叙事单元优先**：以“动作、反应、代价、情绪、场景、关系位移”为基本叙事单元，不使用英文结构标签驱动正文生成。
- **禁止英文结论话术**：正文、审查说明、润色说明、变更摘要、最终报告中不得出现 Overall / PASS / FAIL / Summary / Conclusion 等英文结论标题。
- **英文仅限机器标识**：CLI flag（`--fast`）、checker id（`consistency-checker`）、DB 字段名（`anti_ai_force_check`）、JSON 键名等不可改的接口名保持英文，其余一律使用简体中文。

> **🔴 Round 28.51 · Step 2A 起草前必跑 outline self-check（Ch49 RCA · R29 瘦身保留核心）**
>
> ```bash
> # outline 大纲点逐项核对（起草前必跑）
> grep -nE "^[|│] Ch${chapter_num}" 大纲/第1卷-详细大纲.md | head -3
> # 输出大纲 L${chapter_num} 行, 起草前必须 100% 兑现 (含小括号"轻触"等定语)
> ```
>
> 背景：Ch49 大纲点"秦岳第二次出手"起草漏写 → reader-critic=72 critical。大纲点兑现是起草期唯一必须前置核对的硬项。

> **Round 29 · 起草期机械义务降级说明**：签名词预算、跨章 6-gram 自查、NPC entry/exit 配对、
> 时间锚过渡句、情感场面深度配额、时间戳精度解释——这些**不再作为起草期硬义务**。
> 理由：机械配额驱动填充句和公式化场面（时间跳切、人物淡出本是正常技法）。
> 兜底仍在：post_draft SIGNATURE_SUMMARY/H78 警示可见、hygiene H82-H85 P1 提示、
> continuity/emotion/naturalness checker 按语境判断真问题。起草时按执行包的 beat 设计自然书写即可。

引号与格式清洁硬约束（起草时必须严格遵守）：
- **禁止 ASCII 半角引号 `"`**：从第一笔起就必须用 U+201C（“）/U+201D（”）中文弯引号对。不得“先用 ASCII 写完再批量替换”——批量 flip-pair 脚本在段内多重嵌套引号时会跨段翻转配对，导致 7 处+错乱。
- **禁止 Markdown 标题/分隔线**：正文不得含 `#` / `##` / `---` / 粗体 `**...**`。章节文件直接以第一段叙事开头。
- **禁止 CRLF**：所有写入必须 LF 行尾。Windows 下注意 Write 工具的默认行尾。
- **禁止全角数字** 用于时间锚（“13:40” 保持半角，“一小时五十八分钟” 允许中文数字作叙述）。

ASCII 引号自动扫描（起草后立即执行，**任何 >0 必须停下来修**）：
```bash
python -c "
import pathlib, glob
files = glob.glob('${PROJECT_ROOT}/正文/第${chapter_padded}章*.md')
if not files: raise SystemExit('no chapter file')
t = pathlib.Path(files[0]).read_text(encoding='utf-8')
ascii_q = t.count(chr(34))
if ascii_q:
    raise SystemExit(f'FAIL: {ascii_q} ASCII 双引号（必须用 U+201C/U+201D）')
print('quote check: 0 ASCII, OK')
"
```

> **🔴 Round 28.49 · Write 工具中文引号 known bug 兜底（Ch48 实战 142 个 ASCII 复发）**
>
> Claude Code Write 工具有 known bug: 大段中文正文写入时, U+201C/U+201D 可能被转为 ASCII `"` 落地。每次 Write 中文正文 / 起草后, **必须**紧跟自动配对修复脚本（成对替换不依赖原始位置）：
>
> ```bash
> python -X utf8 -c "
> import pathlib, glob
> files = glob.glob('${PROJECT_ROOT}/正文/第${chapter_padded}章*.md')
> p = pathlib.Path(files[0])
> t = p.read_text(encoding='utf-8')
> out = []; depth = 0
> for ch in t:
>     if ch == chr(34):
>         out.append('“' if depth % 2 == 0 else '”'); depth += 1
>     else: out.append(ch)
> p.write_text(''.join(out), encoding='utf-8')
> print(f'paired {depth} ASCII -> Chinese curly')
> "
> ```
>
> 此脚本配对策略: 第1/3/5... 个 ASCII `"` → U+201C(`“`), 第2/4/6... → U+201D(`”`)。**适用于 Write 单次写入** (引号配对完整时)。若 Edit 局部替换出现奇数 ASCII 残留, 改用人工 Edit 精确修复。


U+FFFD 编码验证（写入后立即执行）：
```bash
python -c "
import glob, pathlib, sys
files = glob.glob('${PROJECT_ROOT}/正文/第${chapter_padded}章*.md')
if not files: sys.exit('No chapter file found')
t = pathlib.Path(files[0]).read_text(encoding='utf-8')
n = t.count('\ufffd')
print(f'FFFD check: {n} corrupted chars in {files[0]}')
sys.exit(1 if n > 0 else 0)
"
```
若检测到 U+FFFD（通常因上下文压缩截断中文字符），立即用 Grep 定位损坏位置，用 Edit 修复，修复后重新验证。**禁止带 FFFD 进入下一步。**

**起草后硬闸门**（Step 2A 完成后、Step 2B 开始前必跑 新增）：
```bash
python -X utf8 "${SCRIPTS_DIR}/post_draft_check.py" ${chapter_num} --project-root "${PROJECT_ROOT}"
```
7 类硬检查（详见 `references/post-draft-gate.md`）：
1. ASCII 双引号 = 0（必须 U+201C/U+201D）
2. U+FFFD = 0
3. Markdown（# 标题 / --- 分隔 / ** 粗体）= 0
4. 章号敏感禁用词（项目 `.webnovel/post_draft_config.json` 配置，如 Ch1 <power-faction>/<golden-finger-space>/灵泉）
5. 破例预算（如主角粗口 Ch1 最多 1 次）
6. 必须伏笔种子（如 Ch1 系统首发必含“你不是第一个”/“#4732”等精确短语）
7. 字数在 state.json 的 `average_words_per_chapter_min/max` 区间内

exit=0 才能进入 Step 2B。**禁止带任何 hard fail 进入 Step 3**——审查子代理的 13 内部 + 14 外部算力不应被机械问题浪费。

输出：
- 章节草稿（可进入 Step 2B 或 Step 3）。

## 本步专属硬约束（Round 29 自 SKILL.md 流程硬约束迁入）

- **禁止三连排比金句 / 诗化对偶金句 (Round 28.30 加入 · 防 reader-critic 79 三连金句 critical 重发)**：起草宣告/独白/认知里程碑场面时，单章 ABAB 三连排比 ≥1 组（如"一棵一棵种。一户一户教。一年一年做。"）或诗化对偶金句 ≥3 处（如"到头来不是X是Y"/"不是X，是Y"），post_draft_check H15 AI_SLOGAN 闸门 warn 1 / block 2 阻断。Ch43 实测 reader-critic / ooc / dialogue / flow / density / prose 6 checker 共识 critical/high。**修法**：宣告完整落字一次即可，**不要反复回响 / 不要排比 / 不要诗化收束**；对偶宣言保留核心 1-2 句，排比四联缩二联或单句，金句去承接词。
