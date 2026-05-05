"""Round 28.6 · B2 遗留补丁：set_progress_chapter 必须同步 progress.last_completed_chapter

Ch29 RCA 暴露：

- B2 遗留漏洞：set_progress_chapter 已能同步以下三个字段：
      progress.current_chapter      (嵌套)
      last_completed_chapter         (顶层)
      current_chapter                (顶层)
  但遗漏了 progress.last_completed_chapter（嵌套字段）。
  后果：progress.last_completed_chapter 卡死在旧值（如 Ch26），不随章节推进更新。

根治方案：在 progress.current_chapter 同步后，立即同步 progress.last_completed_chapter。
"""

from pathlib import Path
import json
import sys


def _ensure_scripts_on_path():
    here = Path(__file__).resolve()
    scripts_dir = here.parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


# ---------- B2 补丁：set_progress_chapter 同步 progress.last_completed_chapter ----------

def test_set_progress_chapter_syncs_nested_last_completed(tmp_path):
    """R28.6 B2 补丁：set_progress_chapter 必须同时同步 progress.last_completed_chapter。

    Root cause: 只同步了顶层 last_completed_chapter，遗漏 progress 子对象。
    """
    _ensure_scripts_on_path()
    from data_modules import state_manager as sm
    from data_modules.config import DataModulesConfig

    # 构建含旧 progress.last_completed_chapter 的 state
    state_path = tmp_path / ".webnovel" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    initial_state = {
        "last_completed_chapter": 26,
        "current_chapter": 26,
        "progress": {
            "current_chapter": 26,
            "last_completed_chapter": 26,
            "total_words": 80000,
            "last_updated": "2026-05-03T00:00:00+00:00",
        },
        "chapter_meta": {},
    }
    state_path.write_text(json.dumps(initial_state, ensure_ascii=False), encoding="utf-8")

    config = DataModulesConfig.from_project_root(tmp_path)
    manager = sm.StateManager(config)

    result = manager.set_progress_chapter(30)
    manager.save_state()

    # 验证 changes 列表包含 progress.last_completed_chapter
    assert any("progress.last_completed_chapter" in c for c in result["changes"]), (
        f"set_progress_chapter 的 changes 应含 progress.last_completed_chapter，实际：{result['changes']}"
    )

    # 验证四个字段全部同步到 30
    assert manager._state["progress"]["last_completed_chapter"] == 30, (
        f"progress.last_completed_chapter 未同步（B2 补丁目标）"
        f"，实际 {manager._state['progress'].get('last_completed_chapter')}"
    )
    assert manager._state["progress"]["current_chapter"] == 30, (
        "progress.current_chapter 未同步"
    )
    assert manager._state["last_completed_chapter"] == 30, (
        "顶层 last_completed_chapter 未同步"
    )
    assert manager._state["current_chapter"] == 30, (
        "顶层 current_chapter 未同步"
    )

    # 验证 state.json 落盘正确
    updated = json.loads(state_path.read_text(encoding="utf-8"))
    assert updated["progress"]["last_completed_chapter"] == 30, (
        "state.json 落盘后 progress.last_completed_chapter 仍未更新"
    )
    assert updated["last_completed_chapter"] == 30
    assert updated["current_chapter"] == 30
    assert updated["progress"]["current_chapter"] == 30


def test_set_progress_chapter_idempotent_when_already_synced(tmp_path):
    """R28.6 B2 补丁：progress.last_completed_chapter 已是目标值时，不重复写 changes。"""
    _ensure_scripts_on_path()
    from data_modules import state_manager as sm
    from data_modules.config import DataModulesConfig

    state_path = tmp_path / ".webnovel" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    initial_state = {
        "last_completed_chapter": 30,
        "current_chapter": 30,
        "progress": {
            "current_chapter": 30,
            "last_completed_chapter": 30,
            "total_words": 90000,
        },
        "chapter_meta": {},
    }
    state_path.write_text(json.dumps(initial_state, ensure_ascii=False), encoding="utf-8")

    config = DataModulesConfig.from_project_root(tmp_path)
    manager = sm.StateManager(config)

    result = manager.set_progress_chapter(30)

    # 全部字段已是目标值，changes 应为空
    assert result["changes"] == [], (
        f"全字段已同步时 changes 应为空，实际：{result['changes']}"
    )


def test_set_progress_chapter_creates_progress_dict_if_missing(tmp_path):
    """R28.6 B2 补丁：progress 子对象不存在时应自动创建并写入 last_completed_chapter。"""
    _ensure_scripts_on_path()
    from data_modules import state_manager as sm
    from data_modules.config import DataModulesConfig

    state_path = tmp_path / ".webnovel" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    # 不含 progress 子对象
    initial_state = {
        "last_completed_chapter": 28,
        "current_chapter": 28,
        "chapter_meta": {},
    }
    state_path.write_text(json.dumps(initial_state, ensure_ascii=False), encoding="utf-8")

    config = DataModulesConfig.from_project_root(tmp_path)
    manager = sm.StateManager(config)

    result = manager.set_progress_chapter(29)

    assert manager._state.get("progress", {}).get("last_completed_chapter") == 29, (
        "progress 不存在时自动创建并写入 last_completed_chapter 失败"
    )
    assert manager._state.get("progress", {}).get("current_chapter") == 29
