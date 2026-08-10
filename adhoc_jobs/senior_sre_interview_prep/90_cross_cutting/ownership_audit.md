# 归属审计（重做 bullet 之前必须过一遍）

2026-08-02 建。起因：自动切流系统印在简历上并被写成三块核心职责之一，但本人确认不是他做的。这暴露了一个系统性风险：**材料的归属判断此前主要依据简历与 intro.md 的自述，而那两份自述本身可能不准。**

bullet 体系要重做，而 bullet 只能装真正属于你的东西。所以先过这张表。

判断标准只有一条：**被面试官追到第三层实现细节时，你能不能答。** 答不出就不是你的，无论谁写的自述。

---

## 怎么用

每行在「你的裁决」栏填一个字：`是`（我做的，细节能答）、`半`（我定了范围或某一块，其余不是我）、`否`（不是我的，移除）、`查`（我需要回去确认）。

填完告诉我，我按裁决调整材料，然后再谈 bullet。

---

## A. 证据最硬的（git 或代码可背书，大概率无需改动）

| # | 故事 | 归属证据 | 你的裁决 |
|---|---|---|---|
| A1 | Doris FE 查询路由：`EXPLAIN ESTIMATE PLAN` / `EXPLAIN ROUTE PLAN` | git 作者是你，15 files / +1,310 | |
| A2 | dcluster 弹性 CN 控制面：幂等扩缩语义、队列去抖状态机、空闲 reaper、与 FE 的读信号契约 | git-attributed 到你，另有约 700 行你写的集成设计文档 | |
| A3 | CH→Doris 存算分离重构与迁移工程 | 你的项目主线，preprod 规模验证 | |
| A4 | 99.945% 双跑对账 | 同上 | |
| A5 | Doris 宽表内存工程（四 OOM 点、1.7B livelock） | 同上 | |
| A6 | 两次 compaction 事故排查（score ~2,500 / ~4,504） | 同上 | |
| A7 | 宽表点查优化（扇出是地板、proc_date 剪枝） | 7 月你自己的调研 | |
| A8 | oncall triage agent harness（phase lock / gate / 证据律 / iron law） | 你 workspace 里的代码与 skill，可逐文件指行 | |

**已知边界**：A2 里 dcluster 的平台可靠性那批（spot 中断回退、容量准入、多集群锁修复、审计日志）作者是 junhan.ouyang / Runzi Yang，不是你。A1 相关的 Arrow Flight 传输与 FE memory-kill backstop 是伙伴团队实现，你定的是输出契约。

---

## B. 需要你确认的（自述声称拥有，但缺独立佐证）

| # | 故事 | 自述怎么说 | 独立佐证情况 | 你的裁决 |
|---|---|---|---|---|
| B1 | **Prometheus Federation → VictoriaMetrics 迁移** | `intro.md` 写 ownership: 我做的架构决策、我定的数据生命周期策略、我执行的迁移 | 有 `p_vm_platform.md` 深页，但 FY2026 self-assessment 的目标清单里**没有**这一项（可能属更早周期）。另有拓扑口径冲突（cluster vs single，见 `number_baseline.md` §2.5） | |
| B2 | **三层告警 + per-tenant SLI recording rules** | 简历写 Designed | 与 B1 同源，且 7 月实测显示告警体系成熟度低于自述 | |
| B3 | **K8s 1.24→1.29 跨 50 集群升级与自动化工具** | 简历与 self-assessment Q3 都写是你的最大成就 | 有 runbook 但标 `status: draft`，无带日期的单次执行日志或复盘 | |
| B4 | **Jenkins 可靠性工程** | `p_jenkins.md` 深页 | 有 `jenkins_facts.md` 事实挖掘，未见 git 归属核对 | |
| B5 | **Iceberg / StarRocks 部署 + 三 warehouse 分 OD/spot** | self-assessment Q1 列为已达成目标 | `interview-6` 有细节，但「部署到位 vs lifecycle 维护」的边界此前标为设计态 | |
| B6 | **FY2026 云成本优化** | self-assessment Q1 列为已达成目标 | 全库零具体动作、零金额、零时点 | |
| B7 | **Intel BKC daemon / IaC** | `p_bkc.md` | 文内 SOURCES 分栏已标：只有 daemon 本体、约 30 台、E810、systemd 层、L1 审计层可说「我做了」，其余是设计口径 | |
| B8 | **ClickHouse 集群部署与复制拓扑** | `interview-clickhouse-sre.md` 开场写 I own the deployment and cluster topology | 那是 4 月的答题框架而非事实记录，其他 evidence 无印证。已按「在既有拓扑上运维」处理 | |

---

## C. 已裁决为否（保持移除）

| # | 故事 | 裁决 |
|---|---|---|
| C1 | 自动切流系统（Master-Detector，4 后端，5-15min→秒级） | **否**（2026-08-02 本人确认）。已从 05 / 07 / 90 移除。旧简历与 intro.md 仍有，重做 bullet 时不带过去 |

---

## D. 裁决之后的连锁影响

填完 B 栏后，下面这些会跟着变，我会一并处理。

如果 **B1 或 B2 判否或半**，02 监控方向会从「可当主力打」降级，README 的方向表、`positioning.md` 的三块职责、`opening_story.md` 的可观测性主线都要改。目前 02 是备选的「中」，这会影响 1 大 1 中 n 小 的映射。

如果 **B3 判半**，04 的「中」地位不变（规模事实不受影响），但 story_bank 里关于自动化工具是你写的那部分要调。

如果 **B6 判否**（也就是那条其实不是你主导的），06 成本方向只剩架构级降本，`README.md` §3 里那条简历风险的处置就从「补事实」变成「删措辞」。

如果 **B5 或 B8 判否**，01 的中环少两条，不影响内核。
