# PIXEL WRITER HUB 设计规范

> Dashboard 前端设计规范，所有页面必须遵守。

## 视觉风格：复古像素 / 8-bit 游戏

像 RPG 状态面板遇上写作仪表盘。有趣、nerd、像素级精确。

## 色板

| 变量 | 色值 | 用途 |
|------|------|------|
| `--bg-main` | `#fff7e8` | 页面背景（带 14px 网格线） |
| `--bg-card` | `#fffaf0` | 卡片背景 |
| `--bg-card-2` | `#fff3d5` | 表头、次级卡片 |
| `--text-main` | `#2a220f` | 主文字 |
| `--text-sub` | `#5d5035` | 次要文字 |
| `--text-mute` | `#8f7f5c` | 标签、占位 |
| `--accent-blue` | `#26a8ff` | 主强调（数值、active 态） |
| `--accent-purple` | `#7f5af0` | 次强调（Strand、badge） |
| `--accent-green` | `#2ec27e` | 成功（审查通过、已回收） |
| `--accent-amber` | `#f5a524` | 警告（紧急伏笔、中等分数） |
| `--accent-red` | `#d7263d` | 危险（blocking、超期） |
| `--accent-cyan` | `#00b8d4` | 信息（badge） |

## 字体

- **标题/Logo**：`Press Start 2P`，11px，字间距 0.08em
- **正文/数据**：`Noto Sans SC`，14px，font-weight 500-700
- **数字**：tabular-nums（等宽数字）

## 边框与阴影

- 卡片：`3px solid #2a220f`，阴影 `6px 6px 0 #2a220f`
- 次级容器：`2px solid #8f7f5c`，阴影 `3px 3px 0 #8f7f5c`
- 无圆角（0px）——像素风不用圆角
- 所有边框硬直线

## 组件规范

**Badge**：`2px solid #2a220f`，padding `3px 8px`，配色见 `.badge-*` 类。

**表格**：`.table-wrap` 包裹，表头 `--bg-card-2` 底色，行 hover `#fff4d8`。

**进度条**：`12px` 高，`2px` 硬边框，填充渐变 `#26a8ff → #7f5af0`。

**按钮/导航**：`2px solid` 边框，hover 时微移 `-1px, -1px`。active 态蓝底。

**图表**（新增 Recharts）：
- 主线用 `--accent-blue`，次线用 `--accent-amber`
- 网格线 `#e8dcc4`（极淡）
- 无圆角 tooltip，用 `2px solid #2a220f` 硬边框
- 坐标轴标签 `--text-mute` 色，12px

## 布局

- 侧边栏 240px（金色渐变 `#ffe8b8 → #ffe19f`），`3px` 右边框
- 主区域可滚动，padding 22px
- 卡片网格 `repeat(auto-fill, minmax(220px, 1fr))`

## 不做的事

- 不用圆角
- 不用渐变背景（进度条除外）
- 不用 soft shadow
- 不用 glassmorphism / neumorphism
- 不用 SVG icon 库——用 emoji
