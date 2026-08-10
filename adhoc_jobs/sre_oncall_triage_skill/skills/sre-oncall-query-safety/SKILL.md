---
name: sre-oncall-query-safety
description: "MCP 查询安全规则：label filter, step floor, time ceiling, retry budget 等 6 条"
---

# Query Safety Rules

这些规则适用于 investigation 中的所有 MCP 查询。保护 observability stack 不被 agent 查询过载。

| Rule | Constraint | Why |
|------|-----------|-----|
| **Label filter required** | Every PromQL query MUST include at least one label filter (`namespace`, `job`, or `service`). Never query `metric_name{}` without labels. | Unfiltered queries scan all time series, can saturate VictoriaMetrics. |
| **Step floor** | `query_range` step MUST be >= 30s. Never use 1s or 5s step over ranges > 10 minutes. | Sub-second steps generate millions of data points, causing OOM or timeout. |
| **Time window ceiling** | `query_range` time window <= 24h. Loki (`loki_fetch.py`) window <= 6h. | Longer ranges are progressively more expensive. Use multiple bounded queries for longer history. |
| **Loki stream selector** | Every LogQL query MUST include at least one stream selector label (e.g., `{namespace="prod"}`). Never query `{} |= "error"`. | Full-scan Loki queries are extremely expensive. |
| **No regex wildcard on high-cardinality labels** | Don't use `=~".*"` on `pod`, `instance`, or `container` labels. | Thousands of values; regex match is a denial-of-service. |
| **Retry budget** | Max 2 retries per query. If a query fails twice, MARK_UNKNOWN and move on. | Prevents retry storms on a struggling backend. |
| **Time window precision** | 首轮查询使用 `event_ts ± 3min`（epoch_ms）。只在需要看趋势时扩大到 ±30min。**禁止使用 `now-6h` 等模糊窗口。** Grafana link 也用精确 epoch：`from=<epoch_ms>&to=<epoch_ms>`。 | 模糊窗口淹没关键信号，6h 数据里 3 分钟 spike 根本看不到。 |
| **Missing field gate** | 如果 alert 中 timestamp / cluster / (namespace 或 service) 任一缺失，**停止查询，向用户要信息**。不用默认值填充，不猜测。 | 没有时间窗口就无法定位；没有 label filter 就违反 Rule 1；猜错比不查更危险。 |
