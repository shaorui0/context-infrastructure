#!/usr/bin/env python3
"""
loki_fetch.py — Query Loki HTTP API directly (bypass Grafana MCP).

Usage:
    # With explicit LogQL
    LOKI_URL="https://loki.dv-api.com" LOKI_ORG_ID="prod" \
      python3 loki_fetch.py --expr '{cluster="aws-uswest2-prod-a"} |= "ERROR"' --from now-1h

    # From Grafana Explore URL (auto-parses panes= param)
    LOKI_URL="https://loki.dv-api.com" LOKI_ORG_ID="nonprod" \
      python3 loki_fetch.py '<grafana_explore_url>'
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

_RELATIVE_RE = re.compile(r"^now(?:-(\d+)([smhd]))?$")


def _parse_time(raw: str) -> int:
    """Return epoch seconds from 'now-Xh/m/s/d' or ISO-8601 string."""
    m = _RELATIVE_RE.match(raw)
    if m:
        now = datetime.now(timezone.utc)
        if m.group(1):
            amount = int(m.group(1))
            unit = m.group(2)
            delta = {"s": timedelta(seconds=amount),
                     "m": timedelta(minutes=amount),
                     "h": timedelta(hours=amount),
                     "d": timedelta(days=amount)}[unit]
            now -= delta
        return int(now.timestamp())
    # Try ISO-8601
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue
    # Try raw epoch
    try:
        return int(float(raw))
    except ValueError:
        pass
    raise SystemExit(f"Cannot parse time: {raw!r}")


def _epoch_to_iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ---------------------------------------------------------------------------
# Grafana Explore URL parser
# ---------------------------------------------------------------------------

def _parse_grafana_url(url: str):
    """Extract LogQL expr, start, end from a Grafana Explore URL.

    Supports both old-style 'left' param and new 'panes' JSON param.
    Returns (expr, start_epoch, end_epoch) or raises SystemExit.
    """
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)

    # --- new style: panes= JSON ---
    if "panes" in qs:
        panes = json.loads(qs["panes"][0])
        for _pane_id, pane in panes.items():
            queries = pane.get("queries", [])
            if queries:
                expr = queries[0].get("expr", "")
                rng = pane.get("range", {})
                start = rng.get("from", "now-1h")
                end = rng.get("to", "now")
                return expr, _parse_time(start), _parse_time(end)

    # --- old style: left= JSON ---
    if "left" in qs:
        left = json.loads(qs["left"][0])
        if isinstance(left, list) and len(left) >= 4:
            expr = left[3].get("queries", [{}])[0].get("expr", "")
            return expr, _parse_time(left[0]), _parse_time(left[1])

    raise SystemExit("Could not extract LogQL from Grafana URL. Supply --expr instead.")


# ---------------------------------------------------------------------------
# Safety checks
# ---------------------------------------------------------------------------

_MAX_WINDOW_HOURS = 6


def _validate(expr: str, start: int, end: int):
    """Enforce safety rules."""
    if not re.search(r'\{[^}]+\}', expr):
        raise SystemExit("Safety: LogQL must include at least one stream selector {…}")
    window_h = (end - start) / 3600
    if window_h > _MAX_WINDOW_HOURS:
        raise SystemExit(f"Safety: time window {window_h:.1f}h exceeds {_MAX_WINDOW_HOURS}h limit")
    if '=~".*"' in expr:
        raise SystemExit('Safety: avoid =~".*" on high-cardinality labels')


# ---------------------------------------------------------------------------
# Loki query
# ---------------------------------------------------------------------------

def _query_loki(base_url: str, org_id: str, expr: str,
                start: int, end: int, limit: int, direction: str):
    """Call Loki query_range and return parsed JSON response."""
    params = urllib.parse.urlencode({
        "query": expr,
        "start": str(start),
        "end": str(end),
        "limit": str(limit),
        "direction": direction,
    })
    url = f"{base_url.rstrip('/')}/loki/api/v1/query_range?{params}"
    req = urllib.request.Request(url, headers={"X-Scope-OrgID": org_id})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise SystemExit(f"Loki HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Loki connection error: {e.reason}")


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def _print_human(data: dict):
    """Pretty-print log lines grouped by stream."""
    results = data.get("data", {}).get("result", [])
    if not results:
        print("(no results)")
        return
    total = 0
    for stream in results:
        labels = stream.get("stream", {})
        label_str = ", ".join(f'{k}={v}' for k, v in sorted(labels.items())
                              if k in ("app", "pod", "namespace", "container", "cluster", "client"))
        values = stream.get("values", [])
        total += len(values)
        print(f"\n--- [{label_str}] ({len(values)} lines) ---")
        for ts_ns, line in values:
            ts = datetime.fromtimestamp(int(ts_ns) / 1e9, tz=timezone.utc)
            print(f"[{ts.strftime('%H:%M:%S.%f')[:-3]}] {line}")
    stats = data.get("data", {}).get("stats", {}).get("summary", {})
    print(f"\n=== {total} lines | "
          f"{stats.get('totalBytesProcessed', 0) / 1024 / 1024:.1f} MB scanned | "
          f"{stats.get('execTime', 0):.2f}s ===")


def _print_ndjson(data: dict):
    """Output NDJSON: one {timestamp, labels, line} per line."""
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        for ts_ns, line in stream.get("values", []):
            ts = datetime.fromtimestamp(int(ts_ns) / 1e9, tz=timezone.utc).isoformat()
            print(json.dumps({"timestamp": ts, "labels": labels, "line": line},
                             ensure_ascii=False))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Query Loki HTTP API directly (bypass Grafana MCP)")
    parser.add_argument("grafana_url", nargs="?", default=None,
                        help="Grafana Explore URL (auto-parse panes= param)")
    parser.add_argument("--expr", default=None, help="LogQL expression")
    parser.add_argument("--from", dest="from_time", default="now-1h",
                        help="Start: now-Xh/m/s or ISO8601 (default: now-1h)")
    parser.add_argument("--to", default="now",
                        help="End: now-Xh/m/s or ISO8601 (default: now)")
    parser.add_argument("--limit", type=int, default=200, help="Max log lines (default: 200)")
    parser.add_argument("--direction", choices=["backward", "forward"],
                        default="backward", help="Sort direction (default: backward = newest first)")
    parser.add_argument("--loki-url", default=None, help="Loki base URL (default: $LOKI_URL)")
    parser.add_argument("--org-id", default=None, help="X-Scope-OrgID tenant (default: $LOKI_ORG_ID)")
    parser.add_argument("--json", action="store_true", help="Output NDJSON")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved params, don't fetch")
    args = parser.parse_args()

    # Resolve Loki URL and org ID
    loki_url = args.loki_url or os.environ.get("LOKI_URL")
    org_id = args.org_id or os.environ.get("LOKI_ORG_ID", "fake")
    if not loki_url:
        raise SystemExit("LOKI_URL not set. Pass --loki-url or export LOKI_URL.")

    # Resolve expr + time window
    if args.grafana_url and not args.expr:
        expr, start, end = _parse_grafana_url(args.grafana_url)
    elif args.expr:
        expr = args.expr
        start = _parse_time(args.from_time)
        end = _parse_time(args.to)
    else:
        raise SystemExit("Provide --expr or a Grafana Explore URL.")

    _validate(expr, start, end)

    if args.dry_run:
        print(json.dumps({
            "loki_url": loki_url,
            "org_id": org_id,
            "expr": expr,
            "start": start,
            "start_human": _epoch_to_iso(start),
            "end": end,
            "end_human": _epoch_to_iso(end),
            "limit": args.limit,
            "direction": args.direction,
        }, indent=2))
        return

    data = _query_loki(loki_url, org_id, expr, start, end, args.limit, args.direction)

    if data.get("status") != "success":
        print(json.dumps(data, indent=2), file=sys.stderr)
        raise SystemExit("Loki query failed")

    if args.json:
        _print_ndjson(data)
    else:
        _print_human(data)


if __name__ == "__main__":
    main()
