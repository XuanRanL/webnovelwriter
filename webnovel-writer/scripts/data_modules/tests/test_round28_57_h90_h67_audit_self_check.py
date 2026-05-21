"""Round 28.57 · Ch52 deep audit RCA · 3 道 R28.57 修复单测.

测试范围:
- H90 chapter_meta R28.55-patch2 mirror 字段必填
- H67 介词 prefix 收紧（移除朝/往/顺/依，保留在/按/到/于/至/靠）
- audit-agent.md 自检 3 decision matrix medium in [1,4] 分支补漏（regression test）
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _ensure_scripts_on_path():
    p = str(SCRIPTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def _make_project_with_review(tmp_path, chapter_meta_extra=None, with_review_report=True):
    """工具：构造一个含审查报告的迷你项目."""
    pr = tmp_path / "book"
    (pr / ".webnovel").mkdir(parents=True)
    (pr / "正文").mkdir()
    (pr / "审查报告").mkdir()
    (pr / "正文" / "第0999章-test.md").write_text("末世第二十八天。\n这是测试章节。", encoding="utf-8")
    if with_review_report:
        (pr / "审查报告" / "第0999章审查报告.md").write_text("# 测试报告\n> overall_score: 86\n", encoding="utf-8")
    cm = {"chapter": 999, "narrative_version": "v1"}
    if chapter_meta_extra:
        cm.update(chapter_meta_extra)
    state = {
        "project_info": {"name": "test", "protagonist": "陆沉",
                         "word_count_policy": {"hard_min": 2200, "hard_max": 3800}},
        "chapter_meta": {"0999": cm},
    }
    (pr / ".webnovel" / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return pr


class _Rep:
    def __init__(self):
        self.records = []

    def record(self, priority, h_id, msg, ok=True):
        self.records.append({"priority": priority, "h": h_id, "ok": ok, "msg": msg})


# ===== H90 chapter_meta R28.55-patch2 mirror 字段必填 =====

def test_h90_missing_all_mirror_fields_warns(tmp_path):
    """Ch52 实战 case: chapter_meta 缺所有 5 个 mirror 字段 → P1 warning."""
    _ensure_scripts_on_path()
    pr = _make_project_with_review(tmp_path, chapter_meta_extra={})
    from hygiene_check import check_r28_55_patch2_mirror_fields
    rep = _Rep()
    check_r28_55_patch2_mirror_fields(pr, 999, rep)
    h90 = [r for r in rep.records if r["h"] == "H90"]
    assert len(h90) == 1
    assert h90[0]["ok"] is False, "缺所有 5 字段必须 P1 fail"
    assert "external_review_effective_avg" in h90[0]["msg"]


def test_h90_all_mirror_fields_present_passes(tmp_path):
    """全部 5 字段填齐 → P1 pass."""
    _ensure_scripts_on_path()
    pr = _make_project_with_review(tmp_path, chapter_meta_extra={
        "external_review_effective_avg": 86.13,
        "external_review_outlier_models": ["gemini-3.1-pro"],
        "external_review_raw_avg": 84.15,
        "audit_decision": "approve_with_warnings",
        "aggregate_score": 86,
    })
    from hygiene_check import check_r28_55_patch2_mirror_fields
    rep = _Rep()
    check_r28_55_patch2_mirror_fields(pr, 999, rep)
    h90 = [r for r in rep.records if r["h"] == "H90"]
    assert len(h90) == 1
    assert h90[0]["ok"] is True


def test_h90_partial_missing_warns(tmp_path):
    """缺 2 个字段也必须 P1 fail（不能全过半就放过）."""
    _ensure_scripts_on_path()
    pr = _make_project_with_review(tmp_path, chapter_meta_extra={
        "external_review_effective_avg": 86.13,
        "external_review_outlier_models": [],
        "external_review_raw_avg": 84.15,
        # audit_decision 和 aggregate_score 缺失
    })
    from hygiene_check import check_r28_55_patch2_mirror_fields
    rep = _Rep()
    check_r28_55_patch2_mirror_fields(pr, 999, rep)
    h90 = [r for r in rep.records if r["h"] == "H90"]
    assert len(h90) == 1
    assert h90[0]["ok"] is False
    assert "audit_decision" in h90[0]["msg"]
    assert "aggregate_score" in h90[0]["msg"]


def test_h90_null_value_treated_as_missing(tmp_path):
    """None 值也视为缺失（防止 audit-agent 写 None 漂白）."""
    _ensure_scripts_on_path()
    pr = _make_project_with_review(tmp_path, chapter_meta_extra={
        "external_review_effective_avg": None,
        "external_review_outlier_models": None,
        "external_review_raw_avg": None,
        "audit_decision": None,
        "aggregate_score": None,
    })
    from hygiene_check import check_r28_55_patch2_mirror_fields
    rep = _Rep()
    check_r28_55_patch2_mirror_fields(pr, 999, rep)
    h90 = [r for r in rep.records if r["h"] == "H90"]
    assert h90[0]["ok"] is False, "None 必须当缺失处理"


def test_h90_no_review_report_skips(tmp_path):
    """审查报告不存在（未跑 Step 3.5）→ skip 不报警."""
    _ensure_scripts_on_path()
    pr = _make_project_with_review(tmp_path, chapter_meta_extra={}, with_review_report=False)
    from hygiene_check import check_r28_55_patch2_mirror_fields
    rep = _Rep()
    check_r28_55_patch2_mirror_fields(pr, 999, rep)
    h90 = [r for r in rep.records if r["h"] == "H90"]
    assert h90[0]["ok"] is True
    assert "审查报告不存在" in h90[0]["msg"] or "跳过" in h90[0]["msg"]


def test_h90_no_state_skips(tmp_path):
    """state.json 不存在 → skip 不抛 KeyError."""
    _ensure_scripts_on_path()
    pr = tmp_path / "no_state"
    pr.mkdir()
    (pr / "审查报告").mkdir()
    (pr / "审查报告" / "第0999章审查报告.md").write_text("ok", encoding="utf-8")
    from hygiene_check import check_r28_55_patch2_mirror_fields
    rep = _Rep()
    check_r28_55_patch2_mirror_fields(pr, 999, rep)
    h90 = [r for r in rep.records if r["h"] == "H90"]
    assert h90[0]["ok"] is True
    assert "state.json" in h90[0]["msg"]


# ===== H67 介词 prefix 收紧（regression: 朝/往/顺/依 移除）=====

def test_h67_prefix_strictness_removed_zhao_wang_shun_yi(tmp_path):
    """R28.57 验证：朝/往/顺/依 4 介词从 prefix 白名单移除（防 false negative）."""
    _ensure_scripts_on_path()
    from hygiene_check import check_canon_locked_terms
    # 检查源码中 4 介词已移除（防 deep audit 漏检 真新地名 case）
    src = (SCRIPTS_DIR / "hygiene_check.py").read_text(encoding="utf-8")
    # R28.56 加的是 在/到/于/至/朝/往/顺/依/按/靠 10 个
    # R28.57 收紧为 在/按/到/于/至/靠 6 个
    # 找到 R28.56/R28.57 注释下方的 prefix list
    lines = src.split("\n")
    found_marker = False
    relevant_block = []
    for i, line in enumerate(lines):
        if "R28.57 修正" in line or "R28.57 移除" in line or ("R28.56" in line and "介词" in line):
            found_marker = True
        if found_marker and i < len(lines) - 1:
            relevant_block.append(line)
            if "靠" in line and "在" in line:
                break
    assert found_marker, "R28.57 修正注释必须存在"
    block_text = "\n".join(relevant_block[-3:])  # 取最后 3 行（包含 prefix list）
    # 朝/往/顺/依 必须不出现在 prefix list
    for forbidden in ['"朝"', '"往"', '"顺"', '"依"']:
        assert forbidden not in block_text, f"R28.57 应移除 {forbidden} prefix（false negative 风险）"
    # 在/按/到/于/至/靠 必须保留
    for required in ['"在"', '"按"', '"到"', '"于"', '"至"', '"靠"']:
        assert required in block_text, f"R28.57 应保留 {required} prefix"


# ===== audit-agent self-check 3 medium in [1,4] 分支补漏（regression test）=====

def test_audit_agent_self_check_3_medium_branch_present():
    """R28.57 验证：audit-agent.md 自检 3 含 medium in [1,4] 分支."""
    audit_md = REPO_ROOT / "agents" / "audit-agent.md"
    src = audit_md.read_text(encoding="utf-8")
    # 必须含 medium in (1, 2, 3, 4) 或 medium in [1,4] 等价写法
    assert "medium_count in (1, 2, 3, 4)" in src or "medium_count in [1, 2, 3, 4]" in src, \
        "R28.57 必须补 medium in [1,4] 分支防 regression"
    # 必须含 all-pass approve 兜底
    assert "all pass" in src.lower() or "approve" in src
