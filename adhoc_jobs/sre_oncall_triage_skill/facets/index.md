# FACETS Index

结构化知识维度，用于 investigation 中的 evidence gathering。当没有 debug tree 匹配时，按 facet 生成 checklist。

## 路由

| Facet | 文件 | 用途 | 何时加载 |
|-------|------|------|---------|
| **Signal Extraction** | `signal_extraction.md` | 从告警文本提取信号（alertname, severity, cluster 等） | 每次 triage 必读 |
| **Slack Alert Intake** | `slack_alert_intake.md` | 从 Slack 链接获取告警消息（MCP 调用流程） | 输入是 Slack link 时 |
| **State / Database** | `state_database.md` | 数据库状态检查（YugaByte, ClickHouse, MySQL） | 告警涉及 DB 组件时 |
| **Traffic / Interface** | `traffic_interface.md` | 流量和接口层检查（ingress, rate-limit, QPS） | 告警涉及 traffic/networking 时 |

**注意**：Data Tools 和 Query Safety Rules 已迁移到 `skills/` 目录，通过 Claude Code skills 机制加载。见 `CLAUDE.md`。

## 使用原则

- **按需加载**：不要一次性读取所有 facet，根据 extracted signals 判断需要哪些
- **Signal extraction 是入口**：每次 triage 先读 `signal_extraction.md`，然后根据信号决定加载哪些 facet
- **Facet 生成 checklist**：每个 facet 提供 What / Where / How / Expected evidence 的结构化检查项
- **新增 facet**：发现新的检查维度时，创建新文件并更新此 index
