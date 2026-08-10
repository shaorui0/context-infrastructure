#!/usr/bin/env python3
"""
converge.py — SRE agent refactor 的硬门禁。

读取：
  - records/inventory.json                (Phase 0 建立的原始清单)
  - records/audit/aggregated.jsonl        (Phase 2 合并出来的 per-file decision)
  - 当前文件系统状态                       (Phase 5 refactor 之后)

对每个 inventoried file 输出：
  path | audited | recommendation | action_taken | matches

exit 0 = 全部 audited 且 action 与 recommendation 一致
exit 1 = 有 gap

用法：
  python3 records/converge.py
  python3 records/converge.py --verbose
  python3 records/converge.py --phase 1   # Phase 1 后只检查 audit 覆盖率
  python3 records/converge.py --phase 5   # Phase 5 后检查 action_taken
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # agent root
RECORDS = ROOT / "records"
INV_PATH = RECORDS / "inventory.json"
AGG_PATH = RECORDS / "audit" / "aggregated.jsonl"


def load_inventory() -> list[dict]:
    if not INV_PATH.exists():
        die(f"inventory missing: {INV_PATH}")
    return json.loads(INV_PATH.read_text())["items"]


def load_aggregated() -> dict[str, dict]:
    """path -> decision record."""
    if not AGG_PATH.exists():
        return {}
    out: dict[str, dict] = {}
    for line in AGG_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "path" in rec:
            out[rec["path"]] = rec
    return out


def observe_action(path: str, rec: dict | None) -> str:
    """Infer action_taken from current FS state + recommendation."""
    fs_exists = (ROOT / path).exists()
    if rec is None:
        return "still_present" if fs_exists else "missing_unaudited"
    rec_kind = rec.get("recommendation", "keep")
    if rec_kind in {"keep", "rewrite"}:
        return "still_present" if fs_exists else "deleted_but_should_keep"
    if rec_kind == "prune":
        return "deleted" if not fs_exists else "still_present_but_should_prune"
    if rec_kind == "merge":
        target = rec.get("merge_target", "")
        if not fs_exists and target and (ROOT / target).exists():
            return f"merged_into:{target}"
        if fs_exists:
            return f"still_present_pending_merge:{target}"
        return "deleted_merge_target_missing"
    if rec_kind == "move":
        target = rec.get("merge_target") or rec.get("move_to", "")
        if not fs_exists and target and (ROOT / target).exists():
            return f"moved_to:{target}"
        if fs_exists:
            return f"still_present_pending_move:{target}"
        return "deleted_move_target_missing"
    return "unknown"


def matches_expectation(rec: dict | None, action: str) -> bool:
    if rec is None:
        return False
    r = rec.get("recommendation", "keep")
    if r == "keep" or r == "rewrite":
        return action == "still_present"
    if r == "prune":
        return action == "deleted"
    if r == "merge":
        return action.startswith("merged_into:")
    if r == "move":
        return action.startswith("moved_to:")
    return False


def die(msg: str, code: int = 2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument(
        "--phase",
        type=int,
        default=None,
        help="1 = audit coverage only; 5 = full action check (default: auto)",
    )
    args = ap.parse_args()

    inventory = load_inventory()
    aggregated = load_aggregated()

    n_total = len(inventory)
    n_audited = sum(1 for it in inventory if it["path"] in aggregated)
    missing_audit = [it["path"] for it in inventory if it["path"] not in aggregated]

    rows = []
    for it in inventory:
        path = it["path"]
        rec = aggregated.get(path)
        action = observe_action(path, rec)
        ok = matches_expectation(rec, action)
        rows.append(
            {
                "path": path,
                "audited": rec is not None,
                "recommendation": rec.get("recommendation") if rec else None,
                "action_taken": action,
                "matches": ok,
            }
        )

    n_match = sum(1 for r in rows if r["matches"])

    # Auto-detect phase if not provided
    phase = args.phase
    if phase is None:
        if n_audited == 0:
            phase = 0
        elif n_audited < n_total:
            phase = 1
        else:
            phase = 5

    print("=" * 60)
    print(f"CONVERGE @ phase={phase}")
    print(f"  inventoried: {n_total}")
    print(f"  audited:     {n_audited}/{n_total}  ({100 * n_audited // max(1, n_total)}%)")
    print(f"  matches:     {n_match}/{n_total}")
    print("=" * 60)

    exit_code = 0

    if phase <= 1:
        # Phase 1 gate: audit must cover 100%
        if missing_audit:
            exit_code = 1
            print("\nMISSING AUDIT (first 20):")
            for p in missing_audit[:20]:
                print(f"  - {p}")
            if len(missing_audit) > 20:
                print(f"  ... +{len(missing_audit) - 20} more")
    else:
        # Phase 5 gate: every file's action must match recommendation
        mismatches = [r for r in rows if r["audited"] and not r["matches"]]
        if missing_audit:
            exit_code = 1
            print("\nMISSING AUDIT (first 20):")
            for p in missing_audit[:20]:
                print(f"  - {p}")
        if mismatches:
            exit_code = 1
            print("\nMISMATCHES (first 30):")
            for r in mismatches[:30]:
                print(
                    f"  - {r['path']}  rec={r['recommendation']}  action={r['action_taken']}"
                )
            if len(mismatches) > 30:
                print(f"  ... +{len(mismatches) - 30} more")

    if args.verbose:
        print("\nALL ROWS:")
        for r in rows:
            mark = "OK" if r["matches"] else ("--" if r["audited"] else "??")
            print(
                f"  [{mark}] {r['path']}  rec={r['recommendation']}  action={r['action_taken']}"
            )

    # Always write the detailed report
    report_path = RECORDS / "converge_report.jsonl"
    with report_path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nDetailed per-file report: {report_path}")

    print(f"\nEXIT {exit_code}  ({'PASS' if exit_code == 0 else 'GAPS REMAIN'})")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
