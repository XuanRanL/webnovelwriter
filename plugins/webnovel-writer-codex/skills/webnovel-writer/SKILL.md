---
name: webnovel-writer
description: Adapter for this repository's Chinese webnovel writing system in Codex. Use when the user asks to initialize, plan, write, review, query, resume, learn from, or dashboard a webnovel project; when they mention the local webnovel-writer workflow; or when they type slash-style commands such as /webnovel-init, /webnovel-plan, /webnovel-write, /webnovel-review, /webnovel-query, /webnovel-resume, /webnovel-dashboard, or /webnovel-learn.
---

# Webnovel Writer

## Overview

Bridge the existing Claude Code `webnovel-writer` plugin into Codex without flattening its long workflows into memory. Resolve the local plugin root, run the unified `webnovel.py` CLI, and read the original command-specific `SKILL.md` plus references only when a step needs them.

## First Move

1. Read `references/codex-adapter.md`.
2. Run the wrapper preflight from the repository root:

```powershell
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 preflight
```

3. Resolve the active book project:

```powershell
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 where
```

Stop and report the exact failing preflight line if preflight fails.

## Route Commands

After preflight, route the user request by slash command or intent:

- `/webnovel-init`: read `webnovel-writer/skills/webnovel-init/SKILL.md`.
- `/webnovel-plan`: read `webnovel-writer/skills/webnovel-plan/SKILL.md`.
- `/webnovel-write`: read `webnovel-writer/skills/webnovel-write/SKILL.md`.
- `/webnovel-review`: read `webnovel-writer/skills/webnovel-review/SKILL.md`.
- `/webnovel-query`: read `webnovel-writer/skills/webnovel-query/SKILL.md`.
- `/webnovel-resume`: read `webnovel-writer/skills/webnovel-resume/SKILL.md`.
- `/webnovel-dashboard`: read `webnovel-writer/skills/webnovel-dashboard/SKILL.md`.
- `/webnovel-learn`: read `webnovel-writer/skills/webnovel-learn/SKILL.md`.

Load only the relevant section and its directly referenced files. The original skill is the source of truth for step order, gates, artifacts, and recovery rules.

## Codex Adaptation Rules

- Treat `webnovel-writer/scripts/webnovel.py` as the stable CLI entrypoint.
- Use PowerShell commands and `python -X utf8` on this Windows workspace.
- Translate Claude `Task` subagents into Codex inline checks using the corresponding files under `webnovel-writer/agents/`. Use Codex subagents only when the user explicitly asks for parallel agent work.
- Keep original project files and generated novel artifacts in the book project root returned by `where`.
- Do not skip workflow steps, audits, or checker gates unless the original `--fast` or `--minimal` mode explicitly permits it.
- For post-commit chapter edits, follow `webnovel-write/references/post-commit-polish.md` and `polish_cycle.py` instead of direct chapter edits.
- Preserve unrelated user changes in the worktree.

## Useful Wrapper Forms

```powershell
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 preflight
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 where
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 status -- --focus all
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 context -- --chapter 13
.\plugins\webnovel-writer-codex\skills\webnovel-writer\scripts\webnovel_codex.ps1 workflow detect
```

If running from outside the repository, set:

```powershell
$env:WEBNOVEL_PLUGIN_ROOT = "I:\AI-extention\webnovel-writer\webnovel-writer"
```

If a command that writes `.webnovel/index.db`, `.webnovel/context_snapshots`, or observability logs fails with `sqlite3.OperationalError: disk I/O error` or `WinError 5`, treat it as a likely Codex sandbox filesystem limitation. Rerun the same command with escalated permissions after asking for approval, then verify no stale `*.lock`, `*.tmp`, or `index.db-journal` file remains from the failed sandbox run.
