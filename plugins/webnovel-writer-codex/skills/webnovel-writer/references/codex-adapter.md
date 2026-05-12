# Codex Adapter Notes

## Shape

This skill is a Codex bridge over the existing Claude Code implementation in this repository:

- Original skills: `webnovel-writer/skills/webnovel-*`
- Original agents/checkers: `webnovel-writer/agents/*.md`
- Original scripts: `webnovel-writer/scripts/*.py`
- Current project pointer: `.claude/.webnovel-current-project`

Do not duplicate the original long workflows into Codex context. Load the original `SKILL.md` for the requested command, then load only the referenced files needed by the current step.

## Command Map

| User command | Original skill to read | Main purpose |
|---|---|---|
| `/webnovel-init` | `webnovel-writer/skills/webnovel-init/SKILL.md` | Create a new novel project skeleton and constraints |
| `/webnovel-plan` | `webnovel-writer/skills/webnovel-plan/SKILL.md` | Build volume and chapter outlines |
| `/webnovel-write` | `webnovel-writer/skills/webnovel-write/SKILL.md` | Draft, review, polish, audit, and commit a chapter |
| `/webnovel-review` | `webnovel-writer/skills/webnovel-review/SKILL.md` | Review existing chapters and generate reports |
| `/webnovel-query` | `webnovel-writer/skills/webnovel-query/SKILL.md` | Query entities, foreshadowing, powers, factions, and urgency |
| `/webnovel-resume` | `webnovel-writer/skills/webnovel-resume/SKILL.md` | Recover interrupted workflow state |
| `/webnovel-dashboard` | `webnovel-writer/skills/webnovel-dashboard/SKILL.md` | Start the read-only dashboard |
| `/webnovel-learn` | `webnovel-writer/skills/webnovel-learn/SKILL.md` | Add reusable lessons to project memory |

## Tool Translation

Claude Code wording in original files maps to Codex as follows:

- `Read`, `Grep`: use file reads, `Select-String`, or `rg` when available.
- `Write`, `Edit`: use `apply_patch` for hand edits.
- `Bash`: use the shell tool with PowerShell commands on this machine.
- `Task`: read the referenced agent/checker markdown under `webnovel-writer/agents/` and execute the check as Codex. If the user explicitly requests parallel agents, Codex subagents may be used with disjoint scopes.
- `AskUserQuestion`: in Codex Default mode, make a reasonable assumption when safe; ask one concise question only when required.
- Claude plugin env vars such as `CLAUDE_PLUGIN_ROOT`: replace with the local plugin root `webnovel-writer/` found by `scripts/webnovel_codex.ps1`.

## Required First Steps

For every command:

1. Resolve the workspace and book project root:
   ```powershell
   .\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 where
   ```
2. Run preflight and stop on failure:
   ```powershell
   .\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 preflight
   ```
3. Read the original skill for the requested command.
4. Follow the original workflow step order. Do not skip gates unless the original mode explicitly permits it.

## Writing Workflow Guardrails

For `/webnovel-write`, the original workflow is authoritative:

- Standard mode runs Step 0 through Step 7.
- `--fast` and `--minimal` only use the reductions described in the original `webnovel-write/SKILL.md`.
- Do not start the next chapter until the chapter gate passes.
- Generate the standard files: chapter markdown, review report, summary, audit JSON, and state/index updates.
- Checker results must come from actual checks against the chapter and agent specs, not invented scores.
- If a post-commit polish is needed, use the original `polish_cycle.py` route rather than editing the chapter directly.

## Practical Commands

Use these PowerShell forms from the repository root:

```powershell
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 preflight
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 where
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 status -- --focus all
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 context -- --chapter 13
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 workflow detect
```

If the skill is installed outside the repository under `C:\Users\Windows\.codex\skills`, run from the repository or set:

```powershell
$env:WEBNOVEL_PLUGIN_ROOT = "I:\AI-extention\webnovel-writer\webnovel-writer"
```

## Sandbox I/O Note

Some `.webnovel` operations use SQLite journals or atomic `os.replace` writes. In Codex's normal filesystem sandbox on Windows, those can fail with `sqlite3.OperationalError: disk I/O error` or `WinError 5` even when `preflight` passes. If that happens:

1. Treat it as a likely sandbox limitation, not a workflow design failure.
2. Rerun the exact command with escalated permissions after asking for approval.
3. Check for stale files left by the failed run: `*.lock`, `*.tmp`, and `index.db-journal`.
4. Preserve any journal file by moving it into `.tmp/` before deleting it.
