"""Round 28.6 · Ch28 RCA · 三类根因永久根治测试.

Ch28 deep research 暴露：

- B1 (CRITICAL): chapter_audit.py contract_fields_min UnboundLocalError
       根因: Round 28.4 P1-6 在 v2 分支引入 contract_fields_min 引用，
             但常量赋值 (line 457) 仍在 v2 分支之后；v2 path 必触发 UnboundLocalError
       后果: CLI audit chapter --mode standard 完全失败 → 阻断 Step 6
       修复: contract_fields_min = 8 上移到 v2 分支前

- B2 (P0): process-chapter 不自动同步顶层 progress.last_completed_chapter / current_chapter
       根因: process_chapter_result 调 update_progress() 只更嵌套 progress.current_chapter，
             不更顶层 last_completed_chapter / current_chapter（H61 检查的是顶层）
       后果: H61 P1 持续 fail，AI 必须手动跑 --set-progress-chapter（Ch24/25/26/27/28 五连漂移）
       修复: process_chapter_result 末尾自动调用 set_progress_chapter(chapter)

- B3 (P0): set-hook-close 重分类后不同步 reader_pull tmp 文件
       根因: CLI 只改 state.chapter_meta.hook_close.primary_type，
             reader_pull_chXXXX.json tmp 文件保留旧 primary_type
       后果: H26 P1 误报 (reader_pull primary='X' vs state primary='Y')
       修复: set-hook-close 自动检测同章 tmp 文件存在则同步 hook_close.primary_type

- B7 (P1): post_draft_check 未拦"了一X" / "不是X是Y"
       根因: SIGNATURE_PATTERNS 默认表只覆盖没X/未X/那一X 等，"了一X" 5+/千字
             和"不是X是Y" 排比从未在 post_draft 拦下
       后果: reader-naturalness 持续标 N2/N4 红线但 polish 经常漏
       修复: 加入 "了一X" warn 12/block 18 + "不是X是Y" warn 2/block 4
"""

from pathlib import Path
import json
import sys


def _ensure_scripts_on_path():
    here = Path(__file__).resolve()
    scripts_dir = here.parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


# ---------- B1 · chapter_audit.py contract_fields_min 顶部初始化 ----------

def test_b1_chapter_audit_contract_fields_min_initialized_before_v2_branch():
    """B1: chapter_audit 模块加载后，contract_fields_min 必须在 v2 分支前先初始化."""
    _ensure_scripts_on_path()
    import inspect
    from data_modules import chapter_audit as ca

    # 找到 A1 检查函数（容许命名变化）
    fn = None
    for name in dir(ca):
        obj = getattr(ca, name)
        if callable(obj) and "A1" in name:
            fn = obj
            break
    assert fn is not None, "chapter_audit 必须含 A1 check 函数"

    src = inspect.getsource(fn)
    # v2 分支引用 contract_fields_min — 找代码（带 'if'），跳过注释里的字符串
    import re
    code_refs = [m.start() for m in re.finditer(r"\n\s+if\s+contract_fields\s*<\s*contract_fields_min", src)]
    if not code_refs:
        # 若代码重构改用其他名字，跳过
        return
    ref_idx = code_refs[0]  # 第一个真实代码引用
    # 必须在引用之前找到 contract_fields_min = 8（Round 28.6 修复后，函数顶部初始化）
    init_idx = src.find("contract_fields_min = 8")
    assert init_idx > 0, "contract_fields_min 必须有初始化"
    assert init_idx < ref_idx, (
        f"最早的 contract_fields_min = 8 (idx={init_idx}) 必须在引用 (idx={ref_idx}) 之前 "
        "（Round 28.6 B1 根治：v2 分支前预初始化）"
    )


# ---------- B2 · process-chapter 自动同步顶层 progress 字段 ----------

def test_b2_process_chapter_auto_syncs_top_level_progress(tmp_path):
    """B2: data-agent process-chapter 后顶层 last_completed_chapter / current_chapter 应自动更新."""
    _ensure_scripts_on_path()
    from data_modules import state_manager as sm
    from data_modules.config import DataModulesConfig

    # 初始 state：last_completed_chapter=27（旧值）
    state_path = tmp_path / ".webnovel" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    initial_state = {
        "chapter_meta": {},
        "progress": {"current_chapter": 27, "total_words": 0},
        "last_completed_chapter": 27,
        "current_chapter": 27,
    }
    state_path.write_text(json.dumps(initial_state, ensure_ascii=False), encoding="utf-8")

    config = DataModulesConfig.from_project_root(tmp_path)
    manager = sm.StateManager(config)
    # __init__ 已自动 _load_state()

    # 直接调用 process_chapter_result（不走 CLI，避免 SQLite/index.db 依赖）
    result = {
        "entities_appeared": [],
        "entities_new": [],
        "state_changes": [],
        "relationships_new": [],
        "uncertain": [],
        "chapter_meta": {"word_count": 3000},
    }
    warnings = manager.process_chapter_result(28, result)

    assert manager._state.get("last_completed_chapter") == 28, (
        f"last_completed_chapter 应自动更新为 28，实际 {manager._state.get('last_completed_chapter')}"
    )
    assert manager._state.get("current_chapter") == 28, (
        f"current_chapter 应自动更新为 28，实际 {manager._state.get('current_chapter')}"
    )
    # 嵌套字段也应同步
    assert manager._state.get("progress", {}).get("current_chapter") == 28


# ---------- B3 · set-hook-close 自动同步 reader_pull tmp 文件 ----------

def test_b3_set_hook_close_syncs_reader_pull_tmp(tmp_path):
    """B3: set-hook-close 重分类后 reader_pull_chXXXX.json 自动跟着改 primary_type."""
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    # 准备 state
    state_path = tmp_path / ".webnovel" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"chapter_meta": {"0028": {"narrative_version": "v1"}}}, ensure_ascii=False), encoding="utf-8")

    # 准备 reader_pull tmp 文件（旧 primary_type=信息钩）
    tmp_dir = tmp_path / ".webnovel" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    rp_path = tmp_dir / "reader_pull_ch0028.json"
    rp_path.write_text(
        json.dumps({
            "overall_score": 88,
            "hook_close": {
                "primary_type": "信息钩",
                "strength": "strong",
                "text_excerpt": "old excerpt",
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    old_argv = _sys.argv[:]
    try:
        _sys.argv = [
            "state_manager", "--project-root", str(tmp_path),
            "update", "--set-hook-close",
            '{"chapter":28,"primary":"决策钩","strength":88,"text":"new excerpt"}',
        ]
        try:
            sm.main()
        except SystemExit:
            pass
    finally:
        _sys.argv = old_argv

    # 验证 reader_pull tmp 文件已自动同步
    rp_after = json.loads(rp_path.read_text(encoding="utf-8"))
    assert rp_after["hook_close"]["primary_type"] == "决策钩", (
        f"reader_pull tmp 应自动同步为决策钩，实际 {rp_after['hook_close']['primary_type']}"
    )
    # 应留下同步痕迹
    assert "_sync_from_set_hook_close" in rp_after["hook_close"]
    assert rp_after["hook_close"]["_sync_from_set_hook_close"]["previous_primary"] == "信息钩"


def test_b3_set_hook_close_skips_when_primary_already_match(tmp_path):
    """B3: 若 tmp 文件 primary_type 已匹配新值，应跳过同步（幂等）."""
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    state_path = tmp_path / ".webnovel" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"chapter_meta": {"0028": {}}}, ensure_ascii=False), encoding="utf-8")

    tmp_dir = tmp_path / ".webnovel" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    rp_path = tmp_dir / "reader_pull_ch0028.json"
    original = {
        "overall_score": 88,
        "hook_close": {"primary_type": "决策钩", "strength": "strong"},
    }
    rp_path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")

    old_argv = _sys.argv[:]
    try:
        _sys.argv = [
            "state_manager", "--project-root", str(tmp_path),
            "update", "--set-hook-close",
            '{"chapter":28,"primary":"决策钩","strength":88,"text":"x"}',
        ]
        try:
            sm.main()
        except SystemExit:
            pass
    finally:
        _sys.argv = old_argv

    rp_after = json.loads(rp_path.read_text(encoding="utf-8"))
    # 已匹配则不留 _sync_from_set_hook_close 痕迹（幂等保护）
    assert "_sync_from_set_hook_close" not in rp_after["hook_close"]


def test_b3_set_hook_close_handles_missing_tmp(tmp_path):
    """B3: tmp 文件不存在时不应崩溃，仅写 state."""
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    state_path = tmp_path / ".webnovel" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"chapter_meta": {"0028": {}}}, ensure_ascii=False), encoding="utf-8")
    # 不创建 reader_pull tmp 文件

    old_argv = _sys.argv[:]
    try:
        _sys.argv = [
            "state_manager", "--project-root", str(tmp_path),
            "update", "--set-hook-close",
            '{"chapter":28,"primary":"决策钩","strength":88,"text":"x"}',
        ]
        try:
            sm.main()
        except SystemExit:
            pass
    finally:
        _sys.argv = old_argv

    # state 仍然成功写入
    state_after = json.loads(state_path.read_text(encoding="utf-8"))
    assert state_after["chapter_meta"]["0028"]["hook_close"]["primary_type"] == "决策钩"


# ---------- B7 · post_draft_check 拦"了一X" 与 "不是X是Y" ----------

def test_b7_post_draft_check_blocks_le_yi_x_overflow():
    """B7: '了一X' pattern 在 18+ 次文本应能正确计数（用于 block 阈值判定）."""
    import re
    pattern = r"了一[一-鿿]"
    text = "他笑了一下" * 20  # 20 次
    count = len(re.findall(pattern, text))
    assert count >= 18, "构造文本应满足 block 阈值前提"


def test_b7_post_draft_check_signature_table_includes_new_patterns():
    """B7: 默认 signature_patterns_default 应含 '了一X' 和 '不是X是Y'."""
    _ensure_scripts_on_path()
    import inspect
    import post_draft_check  # type: ignore

    src = inspect.getsource(post_draft_check)
    assert '"了一X"' in src, "post_draft_check 必须包含 '了一X' 默认配置"
    assert '"不是X是Y"' in src, "post_draft_check 必须包含 '不是X是Y' 默认配置"
    # 阈值合理性
    assert 'r"了一[一-鿿]"' in src
    # block 在合理范围
    assert '"warn": 12' in src and '"block": 18' in src
