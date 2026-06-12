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
- 爽点密度约束：每 800 字至少安排 1 个微爽点（信息揭示/小胜/认可/逆转/兑现）；纯铺垫章允许降至每 1200 字 1 个，但全章不得为零。
- 典故引用融入：若 Context Agent 在执行包中推荐了引用（0-2 条），按推荐的载体和融入方式写入正文。化用 > 引用，角色内化 > 旁白注释。判断不适合时可跳过——**允许不用**。无推荐时不主动引用。（详见 `references/writing/classical-references.md`）
- **复述前章人物原话必须 Grep 原文校验**。任何时候在正文写"X说过/告诉过/吩咐过/警告过……"等复述句，**起草前必须 Grep 该角色名+关键词在前章正文**确认原话。Ch42 L9 凭印象写"<antagonist>告诉他……合作化路那处守得严，先别动"——但 Grep Ch19/Ch20 发现<antagonist>原话只说"金陵饭店人最齐别先去"，从未提合作化路守严——continuity-checker 给出 13 分 critical。**规则**：复述句中的"原话"必须 100% 在前章正文 Grep 命中，禁止凭印象添加细节或合成多段对白。
- **禁止"X章前/X章后/X章之前"等数字章号距离指代**。这是 H40 元叙述泄漏的隐蔽变体——把"Ch19 第十九章"换成更隐蔽的"二十二章前"仍属章号自我指称，post_draft_check.py 已扩展 cn_chapter_meta_pattern 涵盖多位中文数词。用"那一晚/上个月/那回/记忆里那次"等自然时间表达替代。

中文思维写作约束（硬规则）：
- **禁止“先英后中”**：不得先用英文工程化骨架（如 ABCDE 分段、Summary/Conclusion 框架）组织内容，再翻译成中文。
- **中文叙事单元优先**：以“动作、反应、代价、情绪、场景、关系位移”为基本叙事单元，不使用英文结构标签驱动正文生成。
- **禁止英文结论话术**：正文、审查说明、润色说明、变更摘要、最终报告中不得出现 Overall / PASS / FAIL / Summary / Conclusion 等英文结论标题。
- **英文仅限机器标识**：CLI flag（`--fast`）、checker id（`consistency-checker`）、DB 字段名（`anti_ai_force_check`）、JSON 键名等不可改的接口名保持英文，其余一律使用简体中文。

> **🔴 Round 28.51 · Step 2A 起草前必跑 outline + signature self-check (Ch49 RCA)**
>
> Ch49 v1 走完全流程后 reader-critic=72 critical blocking, root cause = 大纲 L130 "周晓兰生日 + 秦岳第二次出手" 中"秦岳第二次出手"在起草时完全漏写; root cause 2 = 单章签名词 "了一X" 34 / "那一X" 23 / "没X" 39 全部 block 阈值; root cause 3 = Ch48 末"外公递水"段 6-gram 重合 10 处。
>
> **新 self-check 模板** (Step 2A 起草前必跑):
> ```bash
> # 1. outline 大纲点逐项核对
> grep -nE "^[|│] Ch${chapter_num}" 大纲/第1卷-详细大纲.md | head -3
> # 输出大纲 L${chapter_num} 行, 起草前必须 100% 兑现 (含小括号"轻触"等定语)
>
> # 2. 签名词起草前预算 (近 5 章累计)
> for w in 了一 那一 半 没 点头 一档 桌沿 没掉头 指尖; do
>   echo "  $w: $(grep -hroE "$w" 正文/第00{$((chapter_num-5))..$((chapter_num-1))}章*.md 2>/dev/null | wc -l) / 100 (5章累计上限)"
> done
>
> # 3. 跨章 6-gram 自查 (起草后立即)
> python -c "
> import re
> prev = open('正文/第00${prev_chapter}章<title>.md', encoding='utf-8').read()
> cur = open('正文/第00${chapter_num}章<title>.md', encoding='utf-8').read()
> prev_grams = set(prev[i:i+6] for i in range(len(prev)-5) if re.match(r'^[一-鿿]+$', prev[i:i+6]))
> cur_grams = set(cur[i:i+6] for i in range(len(cur)-5) if re.match(r'^[一-鿿]+$', cur[i:i+6]))
> overlap = prev_grams & cur_grams
> n_open = sum(1 for g in overlap if g in cur[:500])
> print(f'前 500 字与上章 6-gram 重合: {n_open}')
> assert n_open < 6, '首段与上章 6-gram 过载, 必须重写开篇'
> "
> ```
>
> **修法**: 起草前先核对大纲点 → 实时计数签名词 → 起草后立即验证首段不与上章 deja vu。

> **🔴 Round 28.49 · Step 2A 起草后必跑 4 项 self-check (Ch48 deep audit 漏检根治)**
>
> Ch48 v1 走完 13 checker + 15 外模型 + Step 4.5 复测后, deep research subagent 仍发现 4 高问题被全部审查机制漏检:
>
> 1. **NPC entry/exit pairing 缺**: 老吴 L37 入场 → L77 最后一句 → L205 章末"竹篮还在桌沿"但无出门描写 = ghost-exit. **修法**: Step 2A 起草后 grep 所有有名角色, 验证每个 entry 必有 exit (出门/告别/视线离开) 至少 1 句
> 2. **Timeline transition fill 缺**: L3 "六点整" → L37 "老吴七点四十到" = 100 分钟无 atmosphere/action 桥. **修法**: Step 2A 时间锚之间 >30 min 必须至少 1 句过渡 (等候 / 物动 / 环境变化)
> 3. **Emotional 高潮 minimum depth 缺**: 林母 50米共享规则首次质疑这种 critical relationship beat 仅 6 句对话被 "妈,洒水" 打发 = 法律咨询语气而非"商量恳求语气". **修法**: 情感锚 ≥2 轮对话 + 身体语言 ≥3 处 + reaction shot ≥1 个 (孩子拽衣角 / 同辈触碰 / 物理位置变化 等)
> 4. **同章内部 timestamp 精度 sanity 缺**: L141 八点整 vs L171 SMS 七点五十四 = 6 分钟 gap 无 in-prose 解释 (收到延迟 / 静音 / 设备故障). **修法**: 同章内部时间精度 mins 差 ≥5 必须有 in-prose 解释
>
> **新 self-check 模板** (Step 2A complete-step 前必跑):
> ```python
> # 1. NPC entry/exit pair
> grep -n "<NPC名>" 正文/第${chapter_padded}章*.md
> # 验证每个 NPC 入场后有出场描写
>
> # 2. Time anchor transition
> grep -nE "六点|七点|八点|九点|十点|中午|下午|晚上" 正文/第${chapter_padded}章*.md
> # 验证相邻时间锚之间有过渡行
>
> # 3. Emotional climax depth
> # 手动检查情感锚场景 dialogue rounds + body-lang + reaction shots
>
> # 4. Internal timestamp sanity
> grep -nE "[0-9一二三四五六七八九十]+点[0-9一二三四五六七八九十]*" 正文/第${chapter_padded}章*.md
> # 验证 mins 差 ≥5 必有解释
> ```

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
