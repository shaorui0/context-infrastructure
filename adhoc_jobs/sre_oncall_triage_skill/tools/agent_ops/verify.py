#!/usr/bin/env python3
"""SRE oncall triage agent output verifier.

Runs deterministic checks on investigation output files to validate
schema completeness, evidence consistency, language safety, time precision,
and baseline comparison with historical triages.

Supports both single-file and directory-based output:
    python3 verify.py tmp/sre-triage-2026-03-31_14-23-45.md
    python3 verify.py tmp/oncall/20260416_1240_westernunion-p99-spike/
    python3 verify.py <path> --json
    python3 verify.py <path> --no-baseline   # skip historical comparison

Exit codes:
    0 = PASS (all checks passed)
    1 = WARN (warnings only, review before sending)
    2 = FAIL (failures found, fix required)
"""

import argparse
import glob
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path for _parse import
sys.path.insert(0, str(Path(__file__).parent))
from _parse import (
    parse_sections,
    parse_investigation_log,
    parse_yaml_block,
    extract_field,
    find_debug_tree_ref,
    count_debug_tree_steps,
    has_unknown_results,
    count_hypotheses,
    count_evidence_items,
    extract_event_type,
    find_relative_time_usage,
)

# --- Constants ---

REQUIRED_SECTIONS = [
    "investigation plan",
    "slack response",
    "internal notes",
    "extracted signals",
    "links",
    "investigation log",
    "操作命令方案",       # Section 8: operation commands (Chinese)
]
# Alternate headings for sections
SECTION_ALIASES = {
    "操作命令方案": ["操作命令方案", "建议操作", "operation commands"],
    "investigation plan": ["investigation plan", "调查计划"],
}
# Historical Pattern Matches is optional

INTERNAL_NOTES_SUBSECTIONS = [
    "triage result",
    "conclusion",
    "event type",
    "hypothesis tree",
    "evidence checklist",
    "next verification",
    "guardrail check",
    "uncertainty note",
]

# Regex patterns for non-conservative language in Slack responses
ASSERTION_PATTERNS = [
    (r"\broot cause is\b(?!.*\b(?:likely|possibly|probably)\b)", "Asserts root cause without hedging"),
    (r"\bdefinitely\b", "Uses 'definitely' — too assertive for Slack response"),
    (r"\bcertainly\b", "Uses 'certainly' — too assertive for Slack response"),
    (r"\bclearly\b", "Uses 'clearly' — too assertive for Slack response"),
    (r"\ball users\b", "Asserts scope 'all users' — use 'some users may be affected'"),
    (r"\ball customers\b", "Asserts scope 'all customers' — use 'some customers may be affected'"),
    (r"\beveryone\b", "Asserts scope 'everyone' — use 'users may be affected'"),
    (r"\bwill cause\b", "Speculates about future — use 'may cause'"),
    (r"\bwill result\b", "Speculates about future — use 'may result'"),
    (r"\bconfirmed that\b", "Strong assertion — use 'evidence suggests' or 'consistent with'"),
]

# Debug trees directory relative to the agent root
DEBUG_TREES_DIR = Path(__file__).parent.parent.parent / "knowledge" / "debug-trees"


# --- Check functions ---

def check_schema_completeness(sections: dict[str, str]) -> list[dict]:
    """Check 1: All required output sections present."""
    results = []
    for section in REQUIRED_SECTIONS:
        # Check section name and any aliases
        aliases = SECTION_ALIASES.get(section, [section])
        found = any(
            alias in key
            for alias in aliases
            for key in sections
        )
        if not found:
            results.append({
                "check": "schema_completeness",
                "level": "FAIL",
                "message": f"Missing required section: '{section}'",
            })

    # Check Internal Notes subsections
    internal_notes_text = ""
    for key, val in sections.items():
        if "internal notes" in key:
            internal_notes_text += val + "\n"
    # Also gather subsection keys that might be parsed as separate sections
    for subsection in INTERNAL_NOTES_SUBSECTIONS:
        found_in_sections = any(subsection in key for key in sections)
        found_in_text = subsection.replace(" ", "").lower() in internal_notes_text.replace(" ", "").lower()
        # More lenient: check if the subsection title appears anywhere
        found_anywhere = any(
            subsection in key or subsection.replace(" ", "") in key.replace(" ", "")
            for key in sections
        )
        if not (found_in_sections or found_in_text or found_anywhere):
            results.append({
                "check": "schema_completeness",
                "level": "WARN",
                "message": f"Missing Internal Notes subsection: '{subsection}'",
            })

    if not results:
        results.append({
            "check": "schema_completeness",
            "level": "PASS",
            "message": "All required sections present",
        })
    return results


def check_debug_tree_completion(sections: dict[str, str]) -> list[dict]:
    """Check 2: If debug tree was used, verify all steps have results."""
    results = []
    tree_ref = find_debug_tree_ref(sections)

    if tree_ref is None:
        results.append({
            "check": "debug_tree_completion",
            "level": "PASS",
            "message": "No debug tree used (FACETS-based investigation)",
        })
        return results

    # Find the debug tree file
    tree_filename = tree_ref.split("/")[-1]
    tree_path = DEBUG_TREES_DIR / tree_filename
    if not tree_path.exists():
        # Try with .md extension
        if not tree_filename.endswith(".md"):
            tree_path = DEBUG_TREES_DIR / f"{tree_filename}.md"
        if not tree_path.exists():
            results.append({
                "check": "debug_tree_completion",
                "level": "WARN",
                "message": f"Debug tree file not found: {tree_filename}",
            })
            return results

    tree_text = tree_path.read_text()
    expected_steps = count_debug_tree_steps(tree_text)

    # Parse investigation log
    log_text = ""
    for key, val in sections.items():
        if "investigation log" in key or "inspection checklist" in key:
            log_text += val + "\n"

    log_rows = parse_investigation_log(log_text)
    completed_steps = set()
    for row in log_rows:
        step_val = row.get("step", "")
        # Extract step number/id
        step_match = re.match(r"(\w+)", step_val)
        if step_match:
            completed_steps.add(step_match.group(1))

    # Check for missing steps (allowing for branch skips)
    missing = []
    for step in expected_steps:
        if step not in completed_steps:
            missing.append(step)

    if missing:
        # Check if missing steps were skipped via branch logic
        branch_skip_indicators = [
            "different triage", "skip", "not applicable", "branched",
            "scenario", "→ step", "escalate", "manual",
        ]
        all_branches = " ".join(
            row.get("branch", "") for row in log_rows
        ).lower()

        for step in missing:
            is_branch_skip = any(ind in all_branches for ind in branch_skip_indicators)
            if is_branch_skip:
                results.append({
                    "check": "debug_tree_completion",
                    "level": "PASS",
                    "message": f"Step {step} skipped via branch logic",
                })
            else:
                results.append({
                    "check": "debug_tree_completion",
                    "level": "WARN",
                    "message": f"Debug tree step {step} has no result in investigation log",
                })
    else:
        results.append({
            "check": "debug_tree_completion",
            "level": "PASS",
            "message": f"All {len(expected_steps)} debug tree steps completed",
        })

    return results


def check_conclusion_evidence(sections: dict[str, str]) -> list[dict]:
    """Check 3: Verdict and evidence chain consistency."""
    results = []

    # Find verdict and confidence
    all_text = "\n".join(sections.values())
    verdict = extract_field(all_text, "verdict")
    confidence = extract_field(all_text, "confidence")
    evidence_chain = extract_field(all_text, "evidence_chain")

    if verdict is None:
        results.append({
            "check": "conclusion_evidence",
            "level": "WARN",
            "message": "No verdict field found in output",
        })
        return results

    # Check: verdict exists but evidence_chain is empty/missing
    if evidence_chain is None or evidence_chain.strip() in ("", "[]", "none"):
        results.append({
            "check": "conclusion_evidence",
            "level": "FAIL",
            "message": f"Verdict is '{verdict}' but evidence_chain is missing or empty",
        })

    # Check: FALSE_ALERT verdict but alert is firing
    if "false_alert" in verdict.lower():
        # Look for positive assertions of firing state in investigation log
        log_text = "\n".join(
            val for key, val in sections.items()
            if "investigation log" in key or "inspection" in key
        )
        log_rows = parse_investigation_log(log_text)
        for row in log_rows:
            result_text = row.get("result", "").lower()
            # Match "state=firing" or "state: firing" but NOT "not firing" or "no firing"
            if re.search(r"state\s*[=:]\s*firing", result_text):
                results.append({
                    "check": "conclusion_evidence",
                    "level": "FAIL",
                    "message": "Verdict is FALSE_ALERT but investigation log shows alert state = firing",
                })
                break

    if not results:
        results.append({
            "check": "conclusion_evidence",
            "level": "PASS",
            "message": f"Verdict '{verdict}' consistent with evidence (confidence: {confidence or 'not specified'})",
        })

    return results


def check_slack_language(sections: dict[str, str]) -> list[dict]:
    """Check 4: Slack response uses conservative language."""
    results = []

    slack_text = ""
    for key, val in sections.items():
        if "slack response" in key:
            slack_text += val + "\n"

    if not slack_text.strip():
        results.append({
            "check": "slack_language",
            "level": "WARN",
            "message": "Slack response section is empty or not found",
        })
        return results

    for pattern, description in ASSERTION_PATTERNS:
        matches = re.findall(pattern, slack_text, re.IGNORECASE)
        if matches:
            results.append({
                "check": "slack_language",
                "level": "WARN",
                "message": description,
            })

    if not results:
        results.append({
            "check": "slack_language",
            "level": "PASS",
            "message": "Slack response language is conservative",
        })

    return results


def check_links(sections: dict[str, str]) -> list[dict]:
    """Check 5: Link validation — Ready links have no placeholders, Templates have missing list."""
    results = []

    links_text = ""
    for key, val in sections.items():
        if "links" in key and "deep" not in key:
            links_text += val + "\n"

    if not links_text.strip():
        results.append({
            "check": "links",
            "level": "WARN",
            "message": "Links section is empty or not found",
        })
        return results

    # Check Ready links for unfilled placeholders
    ready_section = False
    template_section = False
    for line in links_text.split("\n"):
        line_lower = line.strip().lower()
        if "ready" in line_lower and (":" in line_lower or "##" in line_lower):
            ready_section = True
            template_section = False
        elif "template" in line_lower and (":" in line_lower or "##" in line_lower):
            ready_section = False
            template_section = True

        # Check for placeholders in Ready URLs
        if ready_section and re.search(r"\{[a-z_]+\}", line):
            results.append({
                "check": "links",
                "level": "FAIL",
                "message": f"Ready link contains unfilled placeholder: {line.strip()[:80]}",
            })

    if not results:
        results.append({
            "check": "links",
            "level": "PASS",
            "message": "Links validated",
        })

    return results


def check_unknown_documented(sections: dict[str, str]) -> list[dict]:
    """Check 6: UNKNOWN results in investigation log are mentioned in Uncertainty Note."""
    results = []

    # Parse investigation log
    log_text = ""
    for key, val in sections.items():
        if "investigation log" in key or "inspection" in key:
            log_text += val + "\n"

    log_rows = parse_investigation_log(log_text)
    unknown_rows = has_unknown_results(log_rows)

    if not unknown_rows:
        return []  # No unknowns, nothing to check

    # Find uncertainty note
    uncertainty_text = ""
    for key, val in sections.items():
        if "uncertainty" in key:
            uncertainty_text += val + "\n"

    if not uncertainty_text.strip():
        results.append({
            "check": "unknown_documented",
            "level": "WARN",
            "message": f"{len(unknown_rows)} step(s) have UNKNOWN result but Uncertainty Note is missing",
        })
    else:
        # Check that unknowns are at least mentioned
        for row in unknown_rows:
            step = row.get("step", "?")
            tool = row.get("tool", "")
            # Lenient check: just see if the step number or tool name appears in uncertainty note
            if step not in uncertainty_text and tool not in uncertainty_text:
                results.append({
                    "check": "unknown_documented",
                    "level": "WARN",
                    "message": f"Step {step} result is UNKNOWN but not mentioned in Uncertainty Note",
                })

    return results


def check_scope_consistency(sections: dict[str, str]) -> list[dict]:
    """Check 7: Investigation scope declaration vs actual queries (WS3)."""
    results = []

    # Find scope declaration
    scope_text = ""
    for key, val in sections.items():
        if "investigation scope" in key or "scope" in key:
            scope_text += val + "\n"

    if not scope_text.strip():
        # Scope declaration not present — not a failure, just skip
        return []

    scope = parse_yaml_block(scope_text)
    out_of_scope_raw = scope.get("out_of_scope", "")

    if not out_of_scope_raw:
        return []

    # Parse out_of_scope list
    out_of_scope_items = [
        item.strip().lower()
        for item in re.findall(r"[^,\[\]]+", out_of_scope_raw)
        if item.strip()
    ]

    # Check investigation log queries against out_of_scope
    log_text = ""
    for key, val in sections.items():
        if "investigation log" in key or "inspection" in key:
            log_text += val + "\n"

    log_rows = parse_investigation_log(log_text)
    for row in log_rows:
        query = row.get("query", "").lower()
        for item in out_of_scope_items:
            if item in query:
                results.append({
                    "check": "scope_consistency",
                    "level": "WARN",
                    "message": f"Step {row.get('step', '?')} queries '{item}' which is declared out_of_scope",
                })

    return results


# --- Directory structure checks (P2.7) ---

INIT_REQUIRED_FILES = ["plan.md", "log.md", "report.md"]
INIT_REQUIRED_DIRS = ["evidence"]

# Fields in plan.md that must have a non-empty, non-placeholder value
PLAN_REQUIRED_SIGNALS = ["cluster", "client", "event_ts"]
PLAN_SIGNAL_PLACEHOLDERS = {"", "<missing>", "unknown", "tbd", "to-be-discovered"}


def check_init_structure(workdir: Path) -> list[dict]:
    """Check 8: Directory structure from sre-oncall-init exists."""
    results = []
    for fname in INIT_REQUIRED_FILES:
        fpath = workdir / fname
        if not fpath.exists():
            results.append({
                "check": "init_structure",
                "level": "FAIL",
                "message": f"Missing required file: {fname}",
            })
        elif fpath.stat().st_size == 0:
            results.append({
                "check": "init_structure",
                "level": "WARN",
                "message": f"File is empty: {fname}",
            })

    for dname in INIT_REQUIRED_DIRS:
        dpath = workdir / dname
        if not dpath.exists() or not dpath.is_dir():
            results.append({
                "check": "init_structure",
                "level": "WARN",
                "message": f"Missing required directory: {dname}/",
            })

    if not results:
        results.append({
            "check": "init_structure",
            "level": "PASS",
            "message": "All init structure files present (plan.md, log.md, report.md, evidence/)",
        })
    return results


def check_plan_completeness(plan_text: str) -> list[dict]:
    """Check 9: plan.md signals are filled, not just skeleton."""
    results = []
    sections = parse_sections(plan_text)

    # Check Extracted Signals table is filled
    signals_text = ""
    for key, val in sections.items():
        if "extracted signals" in key or "signal" in key:
            signals_text += val + "\n"

    if not signals_text.strip():
        results.append({
            "check": "plan_completeness",
            "level": "FAIL",
            "message": "plan.md has no Extracted Signals section",
        })
        return results

    # Parse signal table rows and check required fields
    # Support both "field: value" format and "| field | value |" table format
    for field in PLAN_REQUIRED_SIGNALS:
        field_value = extract_field(signals_text, field)
        # Also try markdown table format: | field | value |
        if field_value is None:
            table_match = re.search(
                rf"\|\s*{re.escape(field)}\s*\|\s*([^|]+)\|",
                signals_text, re.IGNORECASE,
            )
            if table_match:
                field_value = table_match.group(1).strip()
        if field_value is None or field_value.strip().lower() in PLAN_SIGNAL_PLACEHOLDERS:
            results.append({
                "check": "plan_completeness",
                "level": "FAIL",
                "message": f"plan.md signal '{field}' is missing or placeholder",
            })

    # Check Routing Decision is filled
    routing_text = ""
    for key, val in sections.items():
        if "routing" in key:
            routing_text += val + "\n"

    if not routing_text.strip() or "triage cluster" not in routing_text.lower():
        results.append({
            "check": "plan_completeness",
            "level": "WARN",
            "message": "plan.md Routing Decision not filled",
        })

    # Check Time Window is filled
    time_text = ""
    for key, val in sections.items():
        if "time window" in key or "time_window" in key:
            time_text += val + "\n"

    if not time_text.strip():
        results.append({
            "check": "plan_completeness",
            "level": "WARN",
            "message": "plan.md Time Window section not filled",
        })

    if not results:
        results.append({
            "check": "plan_completeness",
            "level": "PASS",
            "message": "plan.md signals and routing filled",
        })
    return results


# --- Fan-out parallelism checks (Phase A: Parallel Fan-out Investigation) ---

# Known sub-agent descriptions from sre-oncall-quick-check skill
FANOUT_SUBAGENT_NAMES = {
    "current-state", "recent-changes", "historical-context",
    "correlated-alerts", "topology",
}

# Threshold: sub-agent start timestamps within this spread = concurrent
FANOUT_PARALLELISM_THRESHOLD_SEC = 5.0

# Anti-pattern thresholds for sub-agent Result field
FANOUT_RESULT_MAX_CHARS = 500              # ≤5 bullet summary soft ceiling
FANOUT_RESULT_MAX_CONSECUTIVE_NUMERIC = 5  # above this = metric dump


def _is_fanout_row(row: dict) -> bool:
    """True if log row looks like a fan-out sub-agent invocation."""
    step = row.get("step", "").strip().lower()
    action = row.get("action", "").strip().lower()
    return step.startswith("fanout") or action in FANOUT_SUBAGENT_NAMES


def _parse_iso_timestamp(ts_str: str) -> datetime | None:
    """Parse ISO8601 timestamp string; return None if unparseable."""
    if not ts_str:
        return None
    ts_str = ts_str.strip()
    # Accept trailing Z as UTC
    ts_normalized = ts_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts_normalized)
    except ValueError:
        return None


def check_fan_out_parallelism(sections: dict[str, str]) -> list[dict]:
    """Check 12: Fan-out sub-agent start timestamps should be concurrent (≤5s spread)."""
    results = []

    log_text = ""
    for key, val in sections.items():
        if "investigation log" in key or "inspection" in key:
            log_text += val + "\n"

    log_rows = parse_investigation_log(log_text)
    fanout_rows = [row for row in log_rows if _is_fanout_row(row)]

    if len(fanout_rows) < 2:
        # No fan-out or single sub-agent: nothing to check (not a failure).
        return []

    # Parse timestamps
    timestamps: list[datetime] = []
    missing_ts_count = 0
    for row in fanout_rows:
        ts = _parse_iso_timestamp(row.get("timestamp", ""))
        if ts is not None:
            timestamps.append(ts)
        else:
            missing_ts_count += 1

    if missing_ts_count > 0:
        results.append({
            "check": "fan_out_parallelism",
            "level": "WARN",
            "message": (
                f"{missing_ts_count}/{len(fanout_rows)} fan-out row(s) missing "
                f"parseable ISO8601 Timestamp field — cannot verify concurrency"
            ),
        })

    if len(timestamps) < 2:
        return results

    spread_sec = (max(timestamps) - min(timestamps)).total_seconds()
    if spread_sec > FANOUT_PARALLELISM_THRESHOLD_SEC:
        results.append({
            "check": "fan_out_parallelism",
            "level": "WARN",
            "message": (
                f"Fan-out sub-agents appear serial — {len(timestamps)} agents span "
                f"{spread_sec:.1f}s (threshold {FANOUT_PARALLELISM_THRESHOLD_SEC:.0f}s). "
                f"Expected concurrent via run_in_background=true."
            ),
        })
    else:
        results.append({
            "check": "fan_out_parallelism",
            "level": "PASS",
            "message": (
                f"Fan-out sub-agents concurrent "
                f"({len(fanout_rows)} agents, start-ts spread {spread_sec:.1f}s)"
            ),
        })

    return results


def check_subagent_output_discipline(sections: dict[str, str]) -> list[dict]:
    """Check 13: Fan-out sub-agent Result field should be ≤5 bullet summary, not raw data."""
    results = []

    log_text = ""
    for key, val in sections.items():
        if "investigation log" in key or "inspection" in key:
            log_text += val + "\n"

    log_rows = parse_investigation_log(log_text)
    fanout_rows = [row for row in log_rows if _is_fanout_row(row)]

    if not fanout_rows:
        return []

    violations = 0
    for row in fanout_rows:
        result_text = row.get("result", "")
        label = row.get("action", "") or row.get("step", "?")

        # Skip UNKNOWN/timeout markers — those are expected short strings
        if result_text.strip().upper().startswith("UNKNOWN"):
            continue

        # Heuristic 1: size ceiling
        if len(result_text) > FANOUT_RESULT_MAX_CHARS:
            results.append({
                "check": "subagent_output_discipline",
                "level": "WARN",
                "message": (
                    f"Sub-agent '{label}' result is {len(result_text)} chars — "
                    f"should be ≤5 bullet summary (soft ceiling {FANOUT_RESULT_MAX_CHARS})"
                ),
            })
            violations += 1
            continue

        # Heuristic 2: code block / JSON dump
        if "```" in result_text:
            results.append({
                "check": "subagent_output_discipline",
                "level": "WARN",
                "message": (
                    f"Sub-agent '{label}' result contains code block — return summary bullets instead"
                ),
            })
            violations += 1
            continue
        if re.search(r"\{[^{}]{50,}\}", result_text):  # a JSON-ish blob > 50 chars
            results.append({
                "check": "subagent_output_discipline",
                "level": "WARN",
                "message": (
                    f"Sub-agent '{label}' result contains JSON-like blob — return summary bullets instead"
                ),
            })
            violations += 1
            continue

        # Heuristic 3: many consecutive numeric/timestamp lines (metric dump)
        consecutive_numeric = 0
        max_consecutive = 0
        for line in result_text.split("\n"):
            # Matches lines starting with a number, timestamp, or metric-like content
            if re.match(r"^\s*[\d\-:T.+Z]+\s+[\d.eE+-]+", line):
                consecutive_numeric += 1
                max_consecutive = max(max_consecutive, consecutive_numeric)
            else:
                consecutive_numeric = 0
        if max_consecutive > FANOUT_RESULT_MAX_CONSECUTIVE_NUMERIC:
            results.append({
                "check": "subagent_output_discipline",
                "level": "WARN",
                "message": (
                    f"Sub-agent '{label}' result has {max_consecutive} consecutive "
                    f"numeric rows (looks like metric/log dump)"
                ),
            })
            violations += 1

    if violations == 0 and fanout_rows:
        results.append({
            "check": "subagent_output_discipline",
            "level": "PASS",
            "message": (
                f"Sub-agent output discipline OK "
                f"({len(fanout_rows)} fan-out row(s), all summary-form)"
            ),
        })

    return results


def check_time_precision(sections: dict[str, str]) -> list[dict]:
    """Check 10: No relative time patterns (now-6h) in links or queries."""
    results = []
    all_text = "\n".join(sections.values())
    findings = find_relative_time_usage(all_text)

    for desc in findings:
        results.append({
            "check": "time_precision",
            "level": "WARN",
            "message": desc + " — use epoch_ms for precise time windows",
        })

    if not results:
        results.append({
            "check": "time_precision",
            "level": "PASS",
            "message": "All time references use precise timestamps",
        })
    return results


# --- Baseline diff (P1.6) ---

# Directories to scan for historical triages
# Agent root is tools/agent_ops/../../ = sre_oncall_triage_agent/
# Output files are in work-harness/tmp/ = agent_root/../../tmp/
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
HISTORY_DIRS = [
    _AGENT_ROOT.parent.parent / "tmp",  # /work-harness/tmp/
]
HISTORY_GLOB_PATTERNS = [
    "sre-triage-*.md",       # legacy format
    "oncall/*/report.md",    # new directory format
]


def _collect_historical_metrics(history_dir: Path, exclude_file: str | None = None) -> list[dict]:
    """Collect metrics from recent historical triage files."""
    files = []
    for pattern in HISTORY_GLOB_PATTERNS:
        files.extend(history_dir.glob(pattern))

    metrics_list = []
    for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
        if exclude_file and f.name == exclude_file:
            continue
        try:
            text = f.read_text()
        except (OSError, UnicodeDecodeError):
            continue

        sections = parse_sections(text)
        if not sections:
            continue

        log_text = ""
        for key, val in sections.items():
            if "investigation log" in key or "inspection" in key:
                log_text += val + "\n"
        log_rows = parse_investigation_log(log_text)

        metrics_list.append({
            "file": f.name,
            "hypothesis_count": count_hypotheses(sections),
            "evidence_count": count_evidence_items(sections),
            "step_count": len(log_rows),
            "event_type": extract_event_type(sections),
        })

        if len(metrics_list) >= 10:  # cap at 10 most recent
            break

    return metrics_list


def check_baseline_diff(sections: dict[str, str], current_file: str | None = None) -> list[dict]:
    """Check 11: Compare current investigation quality with historical baseline."""
    results = []

    # Extract current metrics
    log_text = ""
    for key, val in sections.items():
        if "investigation log" in key or "inspection" in key:
            log_text += val + "\n"
    log_rows = parse_investigation_log(log_text)

    current = {
        "hypothesis_count": count_hypotheses(sections),
        "evidence_count": count_evidence_items(sections),
        "step_count": len(log_rows),
    }

    # Collect historical
    historical = []
    for hist_dir in HISTORY_DIRS:
        if hist_dir.exists():
            historical.extend(_collect_historical_metrics(hist_dir, current_file))

    if len(historical) < 2:
        results.append({
            "check": "baseline_diff",
            "level": "PASS",
            "message": f"Baseline diff skipped — only {len(historical)} historical file(s) available (need ≥2)",
        })
        return results

    # Compute baseline averages
    avg_hypotheses = sum(m["hypothesis_count"] for m in historical) / len(historical)
    avg_evidence = sum(m["evidence_count"] for m in historical) / len(historical)
    avg_steps = sum(m["step_count"] for m in historical) / len(historical)

    baseline = {
        "avg_hypotheses": round(avg_hypotheses, 1),
        "avg_evidence": round(avg_evidence, 1),
        "avg_steps": round(avg_steps, 1),
        "sample_count": len(historical),
    }

    # Compare — warn if current is significantly below baseline
    # Threshold: less than 50% of average (quality regression)
    if avg_hypotheses > 0 and current["hypothesis_count"] < avg_hypotheses * 0.5:
        results.append({
            "check": "baseline_diff",
            "level": "WARN",
            "message": (
                f"Hypothesis count ({current['hypothesis_count']}) is below baseline "
                f"(avg {baseline['avg_hypotheses']} from {baseline['sample_count']} files)"
            ),
        })

    if avg_evidence > 0 and current["evidence_count"] < avg_evidence * 0.5:
        results.append({
            "check": "baseline_diff",
            "level": "WARN",
            "message": (
                f"Evidence count ({current['evidence_count']}) is below baseline "
                f"(avg {baseline['avg_evidence']} from {baseline['sample_count']} files)"
            ),
        })

    if avg_steps > 0 and current["step_count"] < avg_steps * 0.3:
        results.append({
            "check": "baseline_diff",
            "level": "WARN",
            "message": (
                f"Investigation steps ({current['step_count']}) is significantly below baseline "
                f"(avg {baseline['avg_steps']} from {baseline['sample_count']} files)"
            ),
        })

    if not results:
        results.append({
            "check": "baseline_diff",
            "level": "PASS",
            "message": (
                f"Quality metrics within baseline "
                f"(hypotheses: {current['hypothesis_count']} vs avg {baseline['avg_hypotheses']}, "
                f"evidence: {current['evidence_count']} vs avg {baseline['avg_evidence']}, "
                f"steps: {current['step_count']} vs avg {baseline['avg_steps']}; "
                f"n={baseline['sample_count']})"
            ),
        })
    return results


# --- Main ---

def _load_input(filepath: Path) -> tuple[str, Path | None]:
    """Load markdown text from a file or directory.

    Returns (md_text, workdir_or_None).
    If filepath is a directory, reads plan.md + log.md + report.md and concatenates.
    """
    if filepath.is_dir():
        workdir = filepath
        parts = []
        for fname in ["plan.md", "log.md", "report.md"]:
            fpath = workdir / fname
            if fpath.exists():
                parts.append(fpath.read_text())
        return "\n\n".join(parts), workdir
    else:
        return filepath.read_text(), None


def run_all_checks(md_text: str, workdir: Path | None = None,
                   current_file: str | None = None,
                   skip_baseline: bool = False) -> list[dict]:
    """Run all verification checks and return results."""
    sections = parse_sections(md_text)
    all_results = []

    # Directory structure checks (only for new format)
    if workdir is not None:
        all_results.extend(check_init_structure(workdir))
        plan_path = workdir / "plan.md"
        if plan_path.exists():
            all_results.extend(check_plan_completeness(plan_path.read_text()))

    # Core checks (both formats)
    all_results.extend(check_schema_completeness(sections))
    all_results.extend(check_debug_tree_completion(sections))
    all_results.extend(check_conclusion_evidence(sections))
    all_results.extend(check_slack_language(sections))
    all_results.extend(check_links(sections))
    all_results.extend(check_unknown_documented(sections))
    all_results.extend(check_scope_consistency(sections))
    all_results.extend(check_time_precision(sections))
    all_results.extend(check_fan_out_parallelism(sections))
    all_results.extend(check_subagent_output_discipline(sections))

    # Baseline diff
    if not skip_baseline:
        all_results.extend(check_baseline_diff(sections, current_file))

    return all_results


def summarize(results: list[dict]) -> tuple[str, int]:
    """Summarize check results into overall verdict and exit code."""
    has_fail = any(r["level"] == "FAIL" for r in results)
    has_warn = any(r["level"] == "WARN" for r in results)

    if has_fail:
        return "FAIL", 2
    elif has_warn:
        return "WARN", 1
    else:
        return "PASS", 0


def main():
    parser = argparse.ArgumentParser(
        description="Verify sre_oncall_triage_agent investigation output"
    )
    parser.add_argument("file", help="Path to sre-triage output .md file or directory")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    parser.add_argument("--no-baseline", action="store_true", help="Skip historical baseline comparison")
    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: not found: {filepath}", file=sys.stderr)
        sys.exit(2)

    md_text, workdir = _load_input(filepath)
    if not md_text.strip():
        print(f"Error: no content found in {filepath}", file=sys.stderr)
        sys.exit(2)

    current_file = filepath.name if filepath.is_file() else None
    results = run_all_checks(
        md_text,
        workdir=workdir,
        current_file=current_file,
        skip_baseline=args.no_baseline,
    )
    verdict, exit_code = summarize(results)

    if args.json:
        output = {
            "file": str(filepath),
            "format": "directory" if workdir else "single-file",
            "verdict": verdict,
            "checks": results,
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        fail_count = sum(1 for r in results if r["level"] == "FAIL")
        warn_count = sum(1 for r in results if r["level"] == "WARN")
        pass_count = sum(1 for r in results if r["level"] == "PASS")

        fmt_label = f" (directory)" if workdir else ""
        print(f"Verification: {verdict}{fmt_label}")
        print(f"  PASS: {pass_count}  WARN: {warn_count}  FAIL: {fail_count}")
        print()

        for r in results:
            if r["level"] == "FAIL":
                print(f"  ✗ [{r['check']}] {r['message']}")
            elif r["level"] == "WARN":
                print(f"  ⚠ [{r['check']}] {r['message']}")

        if verdict == "PASS":
            print("  All checks passed.")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
