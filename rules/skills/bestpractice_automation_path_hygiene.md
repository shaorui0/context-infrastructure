# Skill: Automation Path Hygiene

## When to Use
Any automation that scans, reads, or writes files across machines, cron, nested repos, or partial checkouts.

## Goal
Make automation portable and fail-loud when it is about to read/write the wrong place.

## Principles
1. **No hardcoded absolute paths** in code.
2. **Derive workspace root at runtime** from the current file location or a provided env var.
3. **Preflight before work**: validate expected directories/files exist under the derived root.
4. **Fail closed**: if root cannot be proven, abort with a clear error.
5. **Log the resolved root + targets** so operators can audit what happened.

## Recommended Root Derivation (robust to nested git)
Prefer a sentinel-dir search rather than `git rev-parse`:

```python
from __future__ import annotations

from pathlib import Path


def find_workspace_root(start: Path, *, required_dirs: tuple[str, ...] = ("contexts", "rules")) -> Path:
    p = start.resolve()
    for cand in (p, *p.parents):
        if all((cand / d).is_dir() for d in required_dirs):
            return cand
    raise RuntimeError(
        f"workspace root not found from {start}; expected dirs: {', '.join(required_dirs)}"
    )


ROOT = find_workspace_root(Path(__file__).parent)
```

## Preflight Checklist
- Confirm `ROOT/contexts/` and `ROOT/rules/` exist.
- Confirm every scan root exists. Missing roots are errors unless explicitly marked optional.
- Confirm every write target is inside `ROOT` (no `..` escapes).
- Confirm the exact persistence target exists (or create it explicitly with a guarded code path).
- Print/log: `ROOT`, scan roots, and persistence targets.

## Path Drift Handling
- If a scan root is missing, do not silently skip it. Either abort (recommended for write paths) or record an explicit `missing_paths=[...]` in the run output.
- If a document/SOP references a path that does not exist, treat it as configuration drift: fix the reference or create the directory with an explicit, guarded migration step.

## Failure Modes This Prevents
- Writing memory/outputs to a wrong folder due to cwd drift.
- Missing data because a submodule repo root differs from workspace root.
- Silent no-op scans because the expected directories are absent.
