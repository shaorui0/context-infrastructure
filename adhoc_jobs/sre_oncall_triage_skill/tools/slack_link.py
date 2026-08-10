#!/usr/bin/env python3
"""
Slack link parser — extracts channel_id and message_ts from Slack URLs.

Supports:
  - Message links:  https://<workspace>.slack.com/archives/<channel_id>/p<timestamp>
  - Thread links:   https://<workspace>.slack.com/archives/<channel_id>/p<timestamp>?thread_ts=<ts>&cid=<cid>

Usage:
  python3 slack_link.py "https://datavisor.slack.com/archives/CJT8ZPRJL/p1775790979547669"

Output (JSON):
  {
    "channel_id": "CJT8ZPRJL",
    "message_ts": "1775790979.547669",
    "thread_ts": null,
    "workspace": "datavisor"
  }

Then use the result to call Slack MCP:
  mcp__slack__slack_list_messages(channel=channel_id, oldest=message_ts, latest=message_ts, inclusive=true, limit=1)
  # If thread_ts is present, also pass thread_ts to get thread replies.
"""

import json
import re
import sys
import urllib.parse


def parse_slack_url(url: str) -> dict:
    """Parse a Slack message URL into channel_id, message_ts, and optional thread_ts.

    Slack URL format:
      https://<workspace>.slack.com/archives/<channel_id>/p<timestamp_without_dot>
      The 'p' prefix is stripped, and a dot is inserted 10 chars from the left
      to produce the Slack API message_ts (e.g., p1775790979547669 → 1775790979.547669).
    """
    parsed = urllib.parse.urlparse(url)

    # Extract workspace from hostname
    hostname = parsed.hostname or ""
    workspace = hostname.split(".")[0] if hostname else "unknown"

    # Extract channel_id and raw timestamp from path
    # Path format: /archives/<channel_id>/p<timestamp>
    path_match = re.match(r"/archives/([A-Z0-9]+)/p(\d+)", parsed.path)
    if not path_match:
        raise ValueError(
            f"Cannot parse Slack URL path: {parsed.path}\n"
            f"Expected format: /archives/<CHANNEL_ID>/p<TIMESTAMP>"
        )

    channel_id = path_match.group(1)
    raw_ts = path_match.group(2)

    # Convert raw timestamp to Slack API format: insert dot before last 6 digits
    if len(raw_ts) > 6:
        message_ts = f"{raw_ts[:-6]}.{raw_ts[-6:]}"
    else:
        message_ts = raw_ts

    # Extract thread_ts from query params if present
    query_params = urllib.parse.parse_qs(parsed.query)
    thread_ts = query_params.get("thread_ts", [None])[0]

    return {
        "channel_id": channel_id,
        "message_ts": message_ts,
        "thread_ts": thread_ts,
        "workspace": workspace,
    }


def build_mcp_instructions(parsed: dict) -> dict:
    """Generate MCP tool call instructions for fetching the message."""
    instructions = {
        "fetch_message": {
            "tool": "mcp__slack__slack_list_messages",
            "params": {
                "channel": parsed["channel_id"],
                "oldest": parsed["message_ts"],
                "latest": parsed["message_ts"],
                "inclusive": True,
                "limit": 1,
            },
        }
    }

    if parsed["thread_ts"]:
        instructions["fetch_thread"] = {
            "tool": "mcp__slack__slack_list_messages",
            "params": {
                "channel": parsed["channel_id"],
                "thread_ts": parsed["thread_ts"],
                "limit": 50,
            },
        }

    return instructions


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 slack_link.py <slack_url>", file=sys.stderr)
        print("  Parses a Slack message URL and outputs JSON with channel_id, message_ts.", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]

    try:
        parsed = parse_slack_url(url)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    result = {
        **parsed,
        "mcp_instructions": build_mcp_instructions(parsed),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
