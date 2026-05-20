"""Extract daily activity from Claude Code session JSONLs across all workspaces.

Reads ~/.claude/projects/<slug>/*.jsonl, filters sessions with mtime in target
date, extracts real user prompts + assistant text (drops tool I/O, thinking,
sidechains, and subagent files), writes one markdown file per session.

Usage: python extract.py [YYYY-MM-DD]   (defaults to today)
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
OUT_DIR = Path(__file__).parent / "extracted"


def parse_session(path: Path) -> dict | None:
    events: list[dict] = []
    cwd = None
    git_branch = None
    first_ts = None
    last_ts = None

    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            t = d.get("type")
            if t not in ("user", "assistant"):
                continue
            if d.get("isSidechain"):
                continue

            cwd = cwd or d.get("cwd")
            git_branch = git_branch or d.get("gitBranch")
            ts = d.get("timestamp")
            if ts:
                first_ts = first_ts or ts
                last_ts = ts

            msg = d.get("message", {})
            content = msg.get("content")

            if t == "user" and isinstance(content, str):
                text = content.strip()
                if text:
                    events.append({"role": "user", "ts": ts, "text": text})
            elif t == "assistant" and isinstance(content, list):
                texts = [
                    b.get("text", "").strip()
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                joined = "\n".join(t for t in texts if t)
                if joined:
                    events.append({"role": "assistant", "ts": ts, "text": joined})

    if not events:
        return None

    return {
        "session_id": path.stem,
        "slug": path.parent.name,
        "cwd": cwd,
        "git_branch": git_branch,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "size_bytes": path.stat().st_size,
        "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "events": events,
    }


def render_markdown(s: dict) -> str:
    lines = [
        f"# Session {s['session_id']}",
        "",
        f"- cwd: `{s['cwd']}`",
        f"- branch: `{s['git_branch']}`",
        f"- window: {s['first_ts']} → {s['last_ts']}",
        f"- raw size: {s['size_bytes']:,} bytes",
        f"- events kept: {len(s['events'])}",
        "",
        "---",
        "",
    ]
    for e in s["events"]:
        role = "**USER**" if e["role"] == "user" else "**ASSISTANT**"
        lines.append(f"## {role}  _{e['ts']}_")
        lines.append("")
        lines.append(e["text"])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    start = datetime.combine(target, datetime.min.time()).timestamp()
    end = start + 86400

    out_root = OUT_DIR / target.isoformat()
    out_root.mkdir(parents=True, exist_ok=True)

    summary_rows: list[tuple[int, str, int, str]] = []
    total_events = 0
    total_kept_bytes = 0

    for jsonl in PROJECTS_DIR.rglob("*.jsonl"):
        if "/subagents/" in str(jsonl):
            continue
        mt = jsonl.stat().st_mtime
        if not (start <= mt < end):
            continue

        session = parse_session(jsonl)
        if not session:
            continue

        slug_dir = out_root / session["slug"]
        slug_dir.mkdir(exist_ok=True)
        out_path = slug_dir / f"{session['session_id']}.md"
        md = render_markdown(session)
        out_path.write_text(md)

        total_events += len(session["events"])
        total_kept_bytes += len(md.encode())
        summary_rows.append(
            (session["size_bytes"], session["slug"], len(session["events"]), session["session_id"])
        )

    summary_rows.sort(reverse=True)
    print(f"Date: {target.isoformat()}")
    print(f"Sessions with content: {len(summary_rows)}")
    print(f"Total events kept: {total_events}")
    print(f"Total markdown size: {total_kept_bytes:,} bytes")
    print(f"Output: {out_root}")
    print()
    print(f"{'raw KB':>8}  {'events':>6}  slug / session")
    for raw, slug, n, sid in summary_rows:
        print(f"{raw // 1024:>8}  {n:>6}  {slug}/{sid[:8]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
