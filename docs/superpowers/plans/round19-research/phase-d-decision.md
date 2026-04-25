# Phase D · upstream CSV 9 表干货度抽查 + 决策

> Round 19 Phase D 立项时设定为"条件执行"——抽查 3 张 CSV 干货度评分 ≥ 8 才执行，否则降级 Round 20。

## 抽查时间
2026-04-25

## 抽查 3 张 CSV 头 8 行

- `裁决规则.csv` 17 题材（包括 RS-003 科幻末世）：`按冲突裁决排序命中条目` + 风格优先级 + 节奏默认策略 + 反模式
- `场景写法.csv` SP-001 战斗 / SP-002 对话：递进式战斗 + 声线差异化 + 反例对比
- `爽点与节奏.csv` PA-001 压抑爆发 / PA-002 微反转：限制累加 + 假结束停顿

## 干货度评分（4 项 × 3 张 = 12 分）

| CSV | 条目 ≥10 | 大模型指令可执行 | 毒点对本作适用 | 示例片段干货 | 小计 |
|---|---|---|---|---|---|
| 裁决规则 | ✅ | ✅ | ⚠️ (RS-003 适用末世) | ✅ | 3.5/4 |
| 场景写法 | ✅ | ✅ | ✅ (战斗/对话通用) | ✅ | 4/4 |
| 爽点与节奏 | ✅ | ✅ | ✅ (压抑/反转通用) | ✅ | 4/4 |
| **总分** | | | | | **11.5/12** |

11.5/12 ≥ 8 → **理论上达标**。

## 决策：仍降级 Round 20

虽然干货度过关，但以下 4 条理由判定**不在 Round 19 实施**：

### 1. RCA §2 五条 top 根因均不与"题材干货度"耦合

读 RCA 报告 §2 自然度 / 画面感 / 追读力的 top-5 根因清单，**无一条**说"因为题材契合度不足导致谷底分"。最接近的是 R2 大纲爽点未兑现，已落 Phase E（plan 跨卷感知）。Phase D 解决的是"upstream 通用作家级写作模式表"，但本作 11 章已沉淀为 Phase F 私库（136 条本作专属反例），私属性 ≫ 通用 CSV。

### 2. Integration 成本不低

引入 D 需要：
- `reference_search.py` BM25 检索引擎（~250 行 Python）
- `webnovel.py reference` 子命令转发（~20 行）
- `context-agent.md` Stage 2.5 题材-场景检索调用 + writing_guidance.csv_hints 输出（~40 行）
- `high-point-checker.md` + `pacing-checker.md` 引用 CSV 维度（~15 行 × 2）

总成本 ~3-4 小时；与 Phase A/F 杠杆比，性价比低。

### 3. Phase F 私库已"用本作数据替代泛用 CSV"

Phase F 4 张表（特别是 ai-replacement-vocab 89 条 / canon-violation-traps 28 条）是从 Ch1-11 真实 RCA 派生的。这种**本作专属反例**比 upstream 泛用 CSV 的价值高得多——上游 CSV 给"通用建议"（如 SP-001 战斗描写应试探→对抗→转折→高潮），本地私库给"本作 Ch5 critical：但节律比Ch4末那一回稳 → 改写为'比前两天院里那两回都稳'"（带具体句子）。

### 4. Phase X1 已接住 reader-critic <75 谷底

Phase D 的潜在收益主要是题材契合度（reader_critic 子项），但 Phase X1 已经把 reader-critic <75 全卷 P0 硬阻止 + 前 5 章写前自检 5 类清单。reader-critic 谷底已被双重接住。

## Round 20 触发条件

Phase 8 Ch12-13 兑现报告出来后，看以下指标是否仍有缺口：

- reader_critic 子项题材契合度 < 80
- reader-pull-checker 题材专属爽点未兑现命中数 ≥ 2
- 编辑反馈"题材描写显得通用化、不够本格"

任一命中 → 启动 Round 20 Phase D 实施 upstream CSV 9 表 + reference_search.py。

## 决策结论

**Phase D 跳过 Round 19，等 Phase 8 Ch12-13 数据决定 Round 20 是否实施。**
