# Deck Outline — DataVisor 监控体系导览 & Oncall 入门

- **目标观众**：DV 工程师 / 新 oncall / 想接手监控的同事（已有 k8s + Prometheus 基础常识）
- **核心论点**：DV 的监控体系不复杂，但**入口在哪、链条怎么 bisect、alert 怎么路由**这三件事讲清楚就能上手 oncall
- **Dual-use**：handout 也要看得懂——每张 slide 自带足够文字 + speaker notes
- **来源**：`contexts/survey_sessions/monitoring_overview_20260521/REPORT.md`
- **时长**：~20-25 分钟讲完，12 张 slide

## Slide 清单（12 张）

| # | 标题 | 核心论点 | 视觉元素 |
|---|------|---------|---------|
| 1 | DV 监控体系导览 | 封面：1 张图讲清楚谁应该看这套 deck + 学完能做什么 | 标题 + 副标题 + 三件事图标 |
| 2 | 监控栈架构（一图流） | metrics 全在 VM，告警全走 vmalert（**不是** Grafana managed），日志全在 Loki 多租户 | 三层架构图（exporters → VM → Grafana/Slack；Loki 旁挂） |
| 3 | 接到第一次 page 之前 | Grafana URL + Severity SLA 时间 + Ack 机制 + 命名陷阱 | Severity 时间表 + 两个 URL 卡片 + cluster→tenant 命名规则 |
| 4 | Latency 链条心智模型 | 完整请求路径：client → APISIX → Ingress(nginx) → fp → Yuga/MySQL；每一段都有对应 dashboard | 横向链条图，每段标 dashboard UID |
| 5 | **核心**：3 个 envelope + 4 象限决策 | SLA dashboard 上的 E2E / Upstream / Waiting 三个 latency envelope；用 4 象限决定下一站 | 三色条形对照 + 2×2 决策表 |
| 6 | 6 大核心 Dashboard 速查 | 一张表把入口 UID 列全（SLA / nginx logs / pod / node / Yuga / MySQL + FP/vmalert/AM 辅助） | 表格 + UID code 块 |
| 7 | 5 步通用 oncall 工作流 | 读 alert → 点 source URL → 第一站 dashboard → bisect → 钻日志 → 假设验证 | 5 步流程图（横向竖向） |
| 8 | Alert → Playbook 路由 | 11 类 alert 家族；alertname 模式 → playbook letter → first dashboard | 大表格 / 路由树 |
| 9 | 告警体系当前状态 | 540 rules / 932 firing；TOP 3 占 67%；91 条无 severity / 79 无 team | 柱图 + 数字大字 |
| 10 | 高频踩坑 TOP 5 | OOM 看 working_set / Batch_Pipeline 不跟 client / gcp-uswest1-prod-a 是 nonprod / PromQL 永远加 cluster filter / nodeHost 选具体 IP | 5 个卡片 |
| 11 | 如何改 / 加 alert | infra repo 路径 + 同步改两份 + sync 机制 + 必带 severity/team label | repo 目录树 + 流程箭头 |
| 12 | 30 秒电梯陈述 | 一段话 summary + 入口文档链接（REPORT.md + skill） | 大字 quote + 二维码/链接 |

## 拆分给 subagent

- Agent A：slides 1-4（intro + 架构 + 接 page 前 + latency 链条）
- Agent B：slides 5-8（**核心**：envelope + 4 象限 + 6 dashboard + 5 步 + 路由表）
- Agent C：slides 9-12（数字 + 坑 + 改 alert + 收尾）
