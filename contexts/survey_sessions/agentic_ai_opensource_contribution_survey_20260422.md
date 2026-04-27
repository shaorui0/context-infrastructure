# Agentic AI 开源生态贡献路径调研（2026-04-22）

> 调研对象：瑞哥想切入 agentic AI 开源领域做贡献，背景是资深 SRE + AI（K8s、Prometheus/VictoriaMetrics、Loki、Grafana、SLO、Go/Python）。
> 方法：4 个独立 sub-agent 并行调研 infra/sandbox、observability/eval、framework、social validation，维度间 overlap ≥50% 做交叉验证。
> 时间窗口：优先近 6 个月（2025-11 至 2026-04）的信号，避开 2024 及更早的过期数据。

---

## TL;DR — 三句话

1. **"中间层坍缩"是 2026 Q2 的主旋律**：模型厂商的 Agent SDK（Claude/OpenAI/Google）已经吃掉了 LangChain 类 framework 的大部分价值，幸存者要么上移做 runtime（LangGraph、OpenHands、Microsoft Agent Framework），要么下移做 infra（E2B、Daytona、kagent、kubernetes-sigs/agent-sandbox）。
2. **SRE + K8s 背景的最高杠杆位置在"下移"这一侧**，而不是 framework 层。按 ROI 排序：① CNCF agent infra（`kubernetes-sigs/agent-sandbox` + `kagent`）；② OpenTelemetry GenAI semantic conventions 标准化；③ production runtime 的 SRE-flavored issue（LangGraph、OpenHands K8s runtime、Agno、OpenAI Agents SDK）。
3. **有几个现成的 first-PR 靶子**（第 7 节列出 9 个），其中最容易落地的是 `huggingface/smolagents #2165`（retry/backoff 彻底没有）和 `langfuse Discussion #2508`（Prometheus exporter 是公开痛点）。License 雷区清单见第 9 节。

---

## 1. 调研方法与数据来源

四个独立 sub-agent 并行调研，任务设计让维度间有 ≥50% overlap 以实现交叉验证：

| Agent | 调研范围 | 主要交叉验证点 |
|---|---|---|
| A1 | Agent infra / runtime / sandbox | K8s operator、Firecracker microVM、gVisor/Kata、license |
| A2 | Observability / eval / tracing | OTel GenAI、Langfuse、Phoenix、SRE 切入点 |
| A3 | Orchestration / framework + SRE 贡献面 | LangGraph/CrewAI/DSPy/OpenAI Agents SDK 等的 issue 活跃度 |
| A4 | Production 真实度 + 社区健康度 + 争议 | 独立第二意见：HN/Reddit/CVE/license 变更/rug pull |

**所有数据点都标注 URL**，关键引用保留英文原文摘录。本报告的打分是**综合 4 份独立判断后的加权结果**，在 sub-agent 之间有争议处显式说明。

---

## 2. 近期关键事件（近 90 天，直接影响"投哪个项目"的判断）

| 日期 | 事件 | 对决策的影响 |
|---|---|---|
| **2026-04-03** | [Microsoft Agent Framework 1.0 GA](https://cloudsummit.eu/blog/microsoft-agent-framework-production-ready-convergence-autogen-semantic-kernel)；AutoGen 正式进 maintenance mode | 不要新投入 AutoGen |
| **2026-03-24** | [LiteLLM supply-chain 攻击](https://docs.litellm.ai/blog/security-update-march-2026)：`litellm==1.82.7/1.82.8` 被 TeamPCP 植入 infostealer；40 分钟内 quarantine，但已命中 Trivy/KICS/Telnyx 同一 campaign（[Snyk](https://snyk.io/blog/poisoned-security-scanner-backdooring-litellm/), [Trend Micro](https://www.trendmicro.com/en_us/research/26/c/inside-litellm-supply-chain-compromise.html)） | 这是**结构性**问题不是孤立事件；"可审计 AI gateway"空缺是时间窗口 |
| **2026-03-20** | [Kubernetes Blog 正式发文](https://kubernetes.io/blog/2026/03/20/running-agents-on-kubernetes-with-agent-sandbox/) 推 `kubernetes-sigs/agent-sandbox`（含 gVisor/Kata，WarmPool / scale-to-zero） | SRE 最高杠杆入口正式官宣 |
| **2026-03-03** | Helicone 被 Mintlify 收购，进入 **maintenance mode**（见 [DEV.to 观察](https://dev.to/stockyarddev/the-llm-proxy-landscape-in-2026-helicone-acquired-litellm-compromised-and-whats-next-3oon)） | Helicone 新贡献不值得；既有 user 规划迁移 |
| **2026-02** | [Agno 把 license 改成 Apache-2.0](https://www.agno.com/blog/community-roundup-february-2026)（之前是更受限的社区 license） | Agno 可以进红榜候选 |
| **2026-02** | [Daytona $24M A 轮](https://upfront.com/thoughts/daytonas-24m-series-a)（FirstMark / Upfront / Pace / Datadog / Figma） | sandbox 层资金集中，但 Daytona 核心 AGPL-3.0 license 对贡献者仍是阻力 |
| **2026-01-16** | [ClickHouse $400M D 轮同时收购 Langfuse](https://clickhouse.com/blog/clickhouse-acquires-langfuse-open-source-llm-observability)，MIT license 承诺不变 | Langfuse 财务风险降低，但新东家方向变化是中期不确定性 |
| **2025-12 → 2026-03** | [LangChain CVE-2025-68664 "LangGrinch"](https://nvd.nist.gov/vuln/detail/CVE-2025-68664) CVSS 9.3 反序列化注入 → secrets 泄漏 / SSRF / RCE | 任何 `langchain-core < 1.2.5 / 0.3.81` 的 production 必须立刻升；**贡献 langchain core 本体 ROI 极低**，应选 LangGraph |
| **2025-11-18** | [OpenHands $18.8M A 轮](https://www.businesswire.com/news/home/20251118768131/en/OpenHands-Raises-$18.8M-Series-A-to-Bring-Open-Source-Cloud-Coding-Agents-to-Enterprises)（Madrona / Menlo / Fujitsu / Obvious） | OpenHands 是 coding-agent 开源里资金最稳、工程最扎实的 |
| **2025-11** | [Google 官宣 Agent Sandbox](https://opensource.googleblog.com/2025/11/unleashing-autonomous-ai-agents-why-kubernetes-needs-a-new-standard-for-agent-execution.html) 作为 K8s SIG 项目 | SRE 阵营的战略入口 |

这张表本身就是一个"状态快照"。每 30 天应该刷一次。

---

## 3. 综合排行榜（SRE 切入友好度）

综合 4 份报告打分（加权后），按"对瑞哥的 ROI"排序。

| 等级 | 排名 | 项目 | 综合分 | 一句话 |
|---|---|---|---|---|
| 🟥 红 | 1 | **kubernetes-sigs/agent-sandbox** | 9.5 | Google + CNCF SIG，K8s CRD + gVisor/Kata，SRE 技能 1:1 对口 |
| 🟥 红 | 2 | **OpenTelemetry GenAI semconv** | 9.5 | 战略层，SIG 缺运维视角；TTFT/burn rate/SLO 模板没人做 |
| 🟥 红 | 3 | **LangGraph** | 9.3 | runtime 事实标准（Q1 2026 大厂架构文档 34% 占有率），reliability issue 多到用不完 |
| 🟥 红 | 4 | **e2b-dev/infra** | 9.0 | Nomad + Firecracker + Terraform，纯 SRE 栈，Apache 2.0 |
| 🟥 红 | 5 | **Langfuse** | 9.0 | LLM obs 事实标准，MIT，**现成 PR 靶子（Prometheus exporter）** |
| 🟥 红 | 6 | **OpenAI Agents SDK** | 9.0 | 刚有外部贡献者做 S3/Redis/Postgres SessionStore 的模板，可复刻 |
| 🟥 红 | 7 | **kagent-dev/kagent** | 8.5 | CNCF Sandbox，Go controller，内置 Prometheus/Grafana 工具 |
| 🟥 红 | 8 | **Agno** | 8.5 | 2026-02 转 Apache-2.0；"stateless FastAPI 横向扩展"明确 SRE 定位 |
| 🟥 红 | 9 | **SigNoz** | 8.5 | Go + OTel-native，LLM observability 追赶中 |
| 🟥 红 | 10 | **OpenHands** | 8.0 | 70k stars，K8s runtime 刚进 v1.6.0，$18.8M A 轮 |
| 🟨 黄 | 11 | **PydanticAI** | 8.0 | OTel/Logfire 原生，但团队小、设计 review 严 |
| 🟨 黄 | 12 | **DSPy** | 7.5 | 630 commits/13wk，有现成 retry bug 可修，但 reliability 不是主叙事 |
| 🟨 黄 | 13 | **dagger/container-use** | 8.0 | Go + Apache 2.0，但生态绑 Dagger，"early development" |
| 🟨 黄 | 14 | **OpenLLMetry** | 8.0 | Python-only；conventions 已上游到 OTel，杠杆通过上游放大 |
| 🟨 黄 | 15 | **Helicone AI Gateway (Rust)** | 7.0 | Rust proxy 对 SRE 有吸引力，但母公司刚被收购进 maintenance，前景不明 |
| 🟨 黄 | 16 | **smolagents** | 7.5 | Apache 2.0，`#2165` 是完美 first PR；HF 实验性长期稳定性无承诺 |
| 🟨 黄 | 17 | **Laminar (lmnr)** | 7.0 | Rust + ClickHouse，规模小但技术栈前卫 |
| 🟨 黄 | 18 | **microsandbox** | 7.0 | Rust + libkrun，YC 背书，**但 K8s 集成弱** |
| 🟨 黄 | 19 | **CrewAI** | 6.5 | stars 高但 issue tracker 被 AI-slop 污染，"60% Fortune 500" 是 exec-speak |
| 🟨 黄 | 20 | **Letta** | 6.5 | 差异化清晰，但近 13 周 22 commits，外部 PR 少 |
| 🟨 黄 | 21 | **Mastra** | 5.5 | TS 栈（瑞哥不是最强），**`ee/` 是源码可见企业 license**，core Apache |
| 🟨 黄 | 22 | **Arize Phoenix** | 5.0 | 技术好但 **Elastic License 2.0**（非 OSI 认定 OSS）——要贡献走 OpenInference |
| 🟨 黄 | 23 | **Google ADK** | 6.0 | Apache 2.0，但 Google 内部驱动，外部 PR 与内部节奏不同步 |
| 🟨 黄 | 24 | **Microsoft Agent Framework** | 7.0 | GA 太新，等 3-6 个月看生态再说 |
| 🟫 黑 | 25 | **LiteLLM**（作为贡献目标） | — | 供应链攻击事件+ Python 包形态本身是攻击面；做替代品 ROI 高于贡献主线 |
| 🟫 黑 | 26 | **Helicone observability 主 repo** | — | Mintlify 收购后 maintenance mode，API 不跟新 provider |
| 🟫 黑 | 27 | **AutoGen** | — | 2026-04 进 maintenance；接班是 Microsoft Agent Framework |
| 🟫 黑 | 28 | **Daytona** | — | **AGPL-3.0**，商业用途受限；72k stars 已过饱和 |
| 🟫 黑 | 29 | **restate** | — | **BSL 1.1**（4 年后转 Apache）；商业化场景有红线 |
| 🟫 黑 | 30 | **LangChain core** | — | 产品焦点转移到 LangGraph；这里只剩 legacy compat PR |
| 🟫 黑 | 31 | **MetaGPT** | — | 近 13 周仅 1 commit，事实上 dormant |
| 🟫 黑 | 32 | **AgentOps** | — | 2025-08 以后几乎无大更新 |
| 🟫 黑 | 33 | **Claude Agent SDK / agentuity** | — | Anthropic 内部驱动 / agentuity 主产品闭源；作为 user OK，作为贡献目标不推荐 |
| 🟫 黑 | 34 | **Braintrust / LangSmith** | — | 本质闭源 SaaS，OSS 组件只是 SDK/proxy |
| 🟫 黑 | 35 | **apple/container** | — | Swift + macOS-only，对 Linux SRE 是全新技术栈 |

---

## 4. 红榜详细分析（Top 10）

### 4.1 kubernetes-sigs/agent-sandbox — 9.5/10

- **Repo**: [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox)（1.9k stars, v0.3.10 2026-04-08）
- **License**: Apache-2.0
- **Backer**: Google + Kubernetes SIG Apps，CNCF 项目（[Google OSS Blog](https://opensource.googleblog.com/2025/11/unleashing-autonomous-ai-agents-why-kubernetes-needs-a-new-standard-for-agent-execution.html)）
- **架构原文**：
  > "The Sandbox custom resource natively supports different runtimes, like gVisor or Kata Containers, providing the necessary kernel and network isolation required for multi-tenant, untrusted execution."
  > "Agent Sandbox supports scaling idle environments to zero to save resources, while ensuring they can resume exactly where they left off."
- **CRD**：`Sandbox` / `SandboxTemplate` / `SandboxClaim` / `SandboxWarmPool`
- **SRE 切入点（瑞哥 K8s + runtime 背景 1:1 对口）**：
  - gVisor / Kata runtimeclass 集成 + benchmark
  - `SandboxWarmPool` 的 pre-warm / cold-start 策略
  - Multi-tenancy 和 node-level isolation
  - Controller reconcile、scale-to-zero 语义
  - Observability hook（metrics / tracing）
- **风险**：API 年轻（v0.3.x）可能还会变，但 SIG 级别治理不会跑路

### 4.2 OpenTelemetry GenAI Semantic Conventions — 9.5/10

- **URL**: [opentelemetry.io/docs/specs/semconv/gen-ai/](https://opentelemetry.io/docs/specs/semconv/gen-ai/) · [GitHub](https://github.com/open-telemetry/semantic-conventions/tree/main/docs/gen-ai)
- **License**: Apache 2.0 / CNCF 治理
- **状态（2026-04）**："GenAI semantic conventions are currently in **Development** status, not yet stable."
- **已定义 metrics**（全部 Development 状态）:
  - `gen_ai.client.token.usage`
  - `gen_ai.client.operation.duration`
  - `gen_ai.server.time_to_first_token`（TTFT — SRE 最关心的 SLI）
  - `gen_ai.server.time_per_output_token`
- **SIG 贡献者**："Amazon, Elastic, Google, IBM, Langtrace, Microsoft, OpenLIT, Scorecard, Traceloop"（[OTel Blog](https://opentelemetry.io/blog/2024/otel-generative-ai/)）
- **进行中争议**：Agent framework semantic convention 仍在讨论中（CrewAI / AutoGen / LangGraph）—[OTel Blog 2025](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- **SRE 切入点（SIG 目前缺的声音）**：
  - 定义 SLO/SLI 模板（TTFT p99、operation.duration burn rate）
  - Prometheus recording rules / alerting rules
  - Grafana dashboard 贡献到 dashboards.grafana.com
  - 参与 CNCF Slack `#otel-genai-instrumentation`
- **为什么是战略层**：这是所有下游项目都要对齐的根 spec。在这儿贡献 = 定义标准。

### 4.3 LangGraph — 9.3/10

- **Repo**: [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)（29.9k stars, 498 open issues, 306 commits/13wk）
- **License**: MIT · **Stack**: Python（+ `langgraph-js`）
- **Production 占有率**：
  > "LangGraph appeared in 34% of production architecture documents at companies with 1,000+ employees in Q1 2026 — more than any other framework."
  > — [LangGraph Agents in Production](https://use-apify.com/blog/langgraph-agents-production)
- **公开生产案例**：Uber（代码迁移 agent）、LinkedIn（SQL Bot）、Klarna（85M 用户客服，解决时间 -80%）、Replit、Elastic、AppFolio（[LangChain 官方](https://blog.langchain.com/is-langgraph-used-in-production/)）
- **PR merge 速度**：Aidan Daly 的 OTel 修复 ~2 小时合并；1.1.x 版本每日滚动
- **SRE-flavored open issues（现成靶子）**：
  - [#7554 RetryPolicy jitter 超过 max_interval](https://github.com/langchain-ai/langgraph/issues/7554)（2026-04-20）
  - [#7263 SqliteSaver.list() N+1 query](https://github.com/langchain-ai/langgraph/issues/7263)
  - [#7467 MongoDb checkpointer ObjectId msgpack 问题](https://github.com/langchain-ai/langgraph/issues/7467)
  - [#7411 InMemoryStore.put() 覆盖 created_at](https://github.com/langchain-ai/langgraph/issues/7411)
  - [#7179 checkpoint 相同时间戳 tie-break](https://github.com/langchain-ai/langgraph/issues/7179)
  - [CVE-2026-28277](https://advisories.gitlab.com/pkg/pypi/langgraph/CVE-2026-28277/) msgpack 反序列化安全加固
- **生产痛点原文**：
  > "When using PostgresSaver directly (outside of LangGraph Platform deployments), the default behavior holds a database connection for the entire run duration, which for long-running workflows can cause connection timeout issues."
  > — [LangChain Support](https://support.langchain.com/articles/6253531756-understanding-checkpointers-databases-api-memory-and-ttl)

### 4.4 e2b-dev/infra — 9.0/10

- **Repo**: [e2b-dev/infra](https://github.com/e2b-dev/infra)（1.0k stars, **7 open issues** — 竞争不激烈）
- **License**: Apache-2.0 · **Stack**: Go 85% + HCL/Terraform 8.2%
- **Tech**: Nomad + Firecracker + Consul + KVM，部署在 GCP（AWS beta）
- **Funding**: [$21M Series A 2025-07](https://e2b.dev/blog/series-a)（Insight Partners 领投）
- **SRE 切入点（和瑞哥技能栈 1:1）**：
  - Nomad job scheduling / driver plugins
  - Firecracker microVM 启停 / snapshot / restore 优化
  - Terraform module（GCP → AWS → 多云）
  - Observability：OTel collector、metrics pipeline（**VictoriaMetrics 经验可直接迁移**）
  - Cold start 优化（E2B 核心竞争力）
- **对比 Daytona**：Daytona 72k stars 但 AGPL-3.0；E2B infra 只有 1k stars 是因为注意力集中在 SDK 侧，**infra 侧反而更容易被 maintainer 看到**

### 4.5 Langfuse — 9.0/10

- **Repo**: [langfuse/langfuse](https://github.com/langfuse/langfuse)（25.3k stars, v3.169.0 2026-04-17）· Helm: [langfuse-k8s](https://github.com/langfuse/langfuse-k8s)
- **License**: MIT（核心，2025-06 [把 product features 全部开源](https://langfuse.com/blog/2025-06-04-open-sourcing-langfuse-product)）
- **Backer**: [ClickHouse 2026-01 收购](https://clickhouse.com/blog/clickhouse-acquires-langfuse-open-source-llm-observability) + ClickHouse $400M D 轮 ($15B 估值)
- **License 承诺原文**:
  > "Langfuse remains 100% open-source under its existing MIT license... There are no planned changes to licensing."
- **规模**: 2300+ 公司, 26M/月 SDK 安装
- **SRE 现成 PR 靶子**：
  - ⭐ [Discussion #2508 Prometheus exporter](https://github.com/orgs/langfuse/discussions/2508)：社区公开痛点，"not yet available... mentioned as a future feature"。**瑞哥最快的 first PR 路径**
  - langfuse-k8s Helm chart 没有 ServiceMonitor / PodMonitor CRD 支持
  - Grafana dashboard（ClickHouse datasource）几乎为空
  - SLO 模板（trace ingestion rate、queue depth）完全空白

### 4.6 OpenAI Agents SDK — 9.0/10

- **Repo**: [openai/openai-agents-python](https://github.com/openai/openai-agents-python)（24.4k stars, **65 open issues** — 良好维护, 491 commits/13wk）
- **License**: MIT · **Stack**: Python（+ TS sibling）
- **关键可复刻模式**：2026-04 外部贡献者 **Qing Wang (qing-ant)** 两天内合并了完整的 SessionStore adapter protocol（S3, Redis, Postgres 三个 reference adapters）。这是瑞哥可以照搬的模板。
- **durable execution 原文**：
  > "With built-in snapshotting and rehydration, the Agents SDK can restore the agent's state in a fresh container and continue from the last checkpoint if the original environment fails or expires."
  > — [OpenAI Expands Agents SDK With Production Control Patterns](https://letsdatascience.com/news/openai-expands-agents-sdk-with-production-control-patterns-61bc011d)
- **SRE-flavored open issues**：
  - [#782 Rate Limit Support](https://github.com/openai/openai-agents-python/issues/782)（2025-05 以来未实现）
  - [#325 ModelBehaviorError Retry](https://github.com/openai/openai-agents-python/issues/325)
  - [#2868 Per-tool authorization middleware](https://github.com/openai/openai-agents-python/issues/2868)

### 4.7 kagent-dev/kagent — 8.5/10

- **Repo**: [kagent-dev/kagent](https://github.com/kagent-dev/kagent)（2.6k stars, 112 issues, v0.9.0-beta7 2026-04-21）
- **License**: Apache 2.0 · **Stack**: Go 49.8% + TS 23.8% + Python 21.3%
- **Backer**: [Solo.io → CNCF Sandbox](https://www.solo.io/blog/bringing-agentic-ai-to-kubernetes-contributing-kagent-to-cncf)
- **关键特性**：内置 MCP tools for "Kubernetes, Istio, Helm, Argo, Prometheus, Grafana, Cilium"（**即本身就是给 SRE 用的**）
- **Go ADK 性能（release 摘录）**：
  > "You can now choose between two Agent Development Kit runtimes: Python (default) and Go, with the Go ADK providing significantly faster startup (~2 seconds vs ~15 seconds for Python) and lower resource consumption."
- **SRE 切入点**：Controller reconcile、CRD 设计、Go ADK 性能优化、observability 集成（直接对接 VictoriaMetrics/Grafana 经验）

### 4.8 Agno (ex-Phidata) — 8.5/10

- **Repo**: [agno-agi/agno](https://github.com/agno-agi/agno)（39.6k stars, 786 open issues, 463 commits/13wk）
- **License**: [Apache-2.0（2026-02 改过来的）](https://www.agno.com/blog/community-roundup-february-2026)
- **定位原文**：
  > "Agno is built for production-grade reliability with built-in error handling, retries, observability (logging and monitoring), and state persistence... runtime layer that serves systems as stateless, horizontally scalable FastAPI backends."
  > — [agentwiki.org/agno](https://agentwiki.org/agno)
- **SRE-flavored open issues（goldmine）**：
  - [#4442 Thread safe rate limiter](https://github.com/agno-agi/agno/issues/4442)
  - [#5326 [PRIORITY] [PRODUCTION] Team agent 多项可靠性问题](https://github.com/agno-agi/agno/issues/5326)
  - [#6917 OpenAIEmbedder batch fallback 是串行的，慢 ~5x](https://github.com/agno-agi/agno/issues/6917)
  - [#5973 HTTP request/response logging hooks](https://github.com/agno-agi/agno/issues/5973)
  - [#7596 Runtime governance middleware](https://github.com/agno-agi/agno/issues/7596)
- **风险**：单公司主导（Agno Inc），bus factor 待观察；但"FastAPI 横向扩展"定位非常 SRE-friendly

### 4.9 SigNoz — 8.5/10

- **Repo**: [SigNoz/signoz](https://github.com/SigNoz/signoz)（**26.6k stars — 全场最高**）
- **License**: [MIT（核心）+ 专有（`ee/` 和 `cmd/enterprise/`）](https://github.com/SigNoz/signoz/blob/main/LICENSE)，dual licensing
- **Stack**: **Go 38.1% + TS 51.8%** — Go 栈对瑞哥最友好
- **Backer**: Y Combinator W21, Series A 2022
- **LLM 支持**：已有 [LLM observability 文档](https://signoz.io/docs/llm-observability/)，支持 Claude Agent SDK / CrewAI / LangChain / LangGraph / LiteLLM
- **原文**："SigNoz plans to actively update its dashboards as OTel GenAI semantic conventions become more mature" — **前瞻贡献空间**
- **SRE 切入点**：OTel GenAI dashboard 贡献（等标准成熟）；Go 版 OTel collector/exporter；ClickHouse 查询优化；多 tenant / 大规模 trace 采集性能

### 4.10 OpenHands — 8.0/10

- **Repo**: [All-Hands-AI/OpenHands](https://github.com/All-Hands-AI/OpenHands)（71.7k stars, ~500 contributors, MIT, v1.6.0 2026-03-30）
- **Funding**: $23.8M 累计（[$18.8M A 轮 2025-11-18](https://openhands.dev/blog/press-release-all-hands-announces-5m-to-scale-ai-agent-for-software-development)）；CEO Robert Brennan，Chief Scientist Graham Neubig
- **SWE-Bench Verified**: 77.6%
- **企业采用**：TikTok、VMware、Roche、Amazon、C3 AI、Netflix、Mastercard、Red Hat、MongoDB、Apple、NVIDIA、Google
- **SRE 切入点（v1.6.0 刚进的区域）**：
  - **Kubernetes runtime + multi-user + RBAC** 是 2026-03 才由 @brettstewart 首次引入，大量优化空间
  - 官方 Helm charts 有独立 repo
  - Runtime / agent-server 拆分（6 个 Docker package）
- **为什么 8.0 不是 9.0**：71.7k stars + 500 contributors 意味着竞争激烈，但 K8s runtime 是**差异化切入口**

---

## 5. 黄榜（有机会但有显著风险）

精选几个重点，详情见第 3 节排行榜。

### 5.1 PydanticAI — 8.0/10

- [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai)（16.5k stars, MIT, Sequoia $17M）
- **OTel/Logfire 原生**（Logfire == Pydantic 基于 OTel GenAI 的商业 observability 产品）
- **SRE issue**：[#3023 Circuit Breaker for Fallback model](https://github.com/pydantic/pydantic-ai/issues/3023) · [#3352 per-tool usage limits](https://github.com/pydantic/pydantic-ai/issues/3352)
- **Samuel Colvin 主题演讲**：["From Stateless Nightmares to Durable Agents"](https://www.youtube.com/watch?v=flf_IKnFYnE)
- **风险**：团队小（31 人）、设计 review 严，PR 门槛比 LangGraph 高

### 5.2 DSPy — 7.5/10

- [stanfordnlp/dspy](https://github.com/stanfordnlp/dspy)（33.9k stars, **630 commits/13wk — 最高**, MIT）
- **Stanford NLP 血统，不会 rug pull**
- ⭐ [#9459 Streaming skips num_retries](https://github.com/stanfordnlp/dspy/issues/9459) — trivially fixable, 高可见度
- 风险：reliability 不是 DSPy 核心叙事（核心是 signatures/optimizers）；PR 被 review 到，但"名气/PR"比 LangGraph 低

### 5.3 smolagents — 7.5/10

- [huggingface/smolagents](https://github.com/huggingface/smolagents)（26.8k stars, Apache 2.0）
- ⭐⭐ [#2165 No built-in retry/backoff for transient model API errors](https://github.com/huggingface/smolagents/issues/2165) — **完美 first PR**（代码 <1000 行，问题清晰）
- 原文：
  > "Auth, rate limiting, and logging must be built from scratch, and smolagents lives in HuggingFace's experimental space where enterprise support and long-term API stability aren't guaranteed."
  > — [Python AI Agent Library Comparison 2026](https://jangwook.net/en/blog/en/python-ai-agent-library-comparison-2026/)

### 5.4 Helicone AI Gateway — 7.0/10（Gateway 子项目本身）

- [Helicone/ai-gateway](https://github.com/Helicone/ai-gateway)（独立 Rust proxy）
- 性能："P95 latency drops below 5ms, memory footprint 64MB, 3,000 RPS, 30MB binary, 100ms cold start"（[BrightCoding](https://www.blog.brightcoding.dev/2026/03/14/helicone-ai-gateway-the-revolutionary-rust-powered-llm-router)）
- ⚠️ **母公司 2026-03-03 被 Mintlify 收购进 maintenance mode**（[DEV.to](https://dev.to/stockyarddev/the-llm-proxy-landscape-in-2026-helicone-acquired-litellm-compromised-and-whats-next-3oon)）
- Gateway 子项目短期内还活着，但前景不明。**如果押 Rust proxy 方向，等 fork / 继任项目更稳**

### 5.5 CrewAI — 6.5/10

- [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI)（49.5k stars, 399 commits/13wk, MIT, Insight $18M A 轮）
- ⚠️ **issue tracker 被 AI-slop 污染**（FlowZap / I Ching state machines / Signet / ClawMem / TaijiOS 等 SEO-driven feature 提案）
- 但有**真实** SRE bug：[#5510 blocking LLM call at module import crashes containers](https://github.com/crewAIInc/crewAI/issues/5510) / [#5148 AnthropicCompletion 丢 stop_reason](https://github.com/crewAIInc/crewAI/issues/5148) / [#5057 memory 注入 prompt 无 sanitization](https://github.com/crewAIInc/crewAI/issues/5057)
- **策略**：可以做精准外科手术 PR，不要尝试架构层贡献

### 5.6 Mastra — 5.5/10

- [mastra-ai/mastra](https://github.com/mastra-ai/mastra)（23.2k stars, YC W25, **$35M 累计 / $22M A 轮 2026-04-09**, TypeScript）
- **License 陷阱**：[Apache-2.0 for core, `ee/` directory 是 Mastra Enterprise License](https://mastra.ai/docs/community/licensing)（GitHub API 显示 NOASSERTION 就是这个原因）
- 提交一个 PR 前**确认代码路径不在 `ee/` 下**
- TS 栈对瑞哥不是最优，**除非刻意学 TS**

### 5.7 Arize Phoenix — 5.0/10（License 陷阱）

- [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix)（9.4k stars, 活跃）
- ⚠️ **Elastic License 2.0（ELv2）** — [不是 OSI 认定 OSS](https://arize.com/docs/phoenix/self-hosting/license)
  > "You may not provide the software to third parties as a hosted or managed service"
- **替代**：要贡献 Arize 生态请走 [OpenInference（Apache 2.0）](https://github.com/Arize-ai/openinference)，同样是 Arize 主导，license 干净

---

## 6. 黑榜（建议避开）

| 项目 | 理由 |
|---|---|
| **AutoGen** | 2026-04 进 maintenance mode，接班是 Microsoft Agent Framework |
| **LangChain core** | 产品焦点转 LangGraph；这里只剩 legacy compat PR，还有 CVSS 9.3 CVE 的安全债 |
| **LiteLLM**（贡献目标） | 供应链攻击是结构性问题；做替代品（TensorZero / Stockyard / Portkey OSS 部分）ROI 更高 |
| **Helicone observability 主 repo** | Mintlify 收购进 maintenance；新 provider API 不会及时跟 |
| **Daytona** | **AGPL-3.0** 对企业 SRE 不友好；72k stars 过饱和 |
| **restate** | **BSL 1.1**，商业化场景是红线（4 年后转 Apache，但对"想把贡献带回前东家"的瑞哥是顾虑） |
| **Phoenix 本体** | ELv2 license，要贡献走 OpenInference |
| **MetaGPT** | 近 13 周仅 1 commit，事实上 dormant |
| **AgentOps** | 2025-08 后几乎无大更新 |
| **Claude Agent SDK / Google ADK / agentuity** | 本质是厂商内部 SDK 公开版，外部 PR 影响面小 |
| **Braintrust / LangSmith / Modal** | 本质闭源；OSS 部分只是 SDK / proxy，不是核心 runtime |
| **apple/container** | Swift + macOS-only，对 Linux SRE 技能不迁移 |
| **任何 Show HN 爆火玩具** | star 曲线陡 ≠ 工程成熟度 |

---

## 7. 具体 First-PR 靶子清单（按难度升序）

**Tier 0（一个周末能落地的第一个 PR）**：
1. ⭐⭐⭐ [huggingface/smolagents #2165](https://github.com/huggingface/smolagents/issues/2165) — MultiStepAgent 的 retry/backoff 完全没有。<1000 行代码，问题单一，Apache-2.0，HF 品牌加分。
2. ⭐⭐ [stanfordnlp/dspy #9459](https://github.com/stanfordnlp/dspy/issues/9459) — Streaming 路径跳过了 `num_retries`。一个简单 bug fix。
3. ⭐⭐ [langchain-ai/langgraph #7554](https://github.com/langchain-ai/langgraph/issues/7554) — RetryPolicy jitter 让 sleep 超过 max_interval。典型 backoff 数学错误，一行代码的 fix。

**Tier 1（2-4 周可以落地的有分量 PR）**：
4. ⭐⭐⭐ [langfuse Discussion #2508](https://github.com/orgs/langfuse/discussions/2508) — Prometheus `/metrics` endpoint + Helm ServiceMonitor + Grafana dashboard JSON 三件套。ClickHouse 新收购有资源，review 会快。**瑞哥 VictoriaMetrics/Grafana 经验直接变现**。
5. ⭐⭐ [agno-agi/agno #4442](https://github.com/agno-agi/agno/issues/4442) — Thread safe rate limiter（开了半年没做）。
6. ⭐⭐ [langchain-ai/langgraph #7263](https://github.com/langchain-ai/langgraph/issues/7263) — SqliteSaver.list() N+1 query 优化，经典性能 PR。
7. ⭐⭐ [openai/openai-agents-python](https://github.com/openai/openai-agents-python) — 复刻 Qing Wang 的 SessionStore adapter pattern，做 **MongoDB / DynamoDB / Valkey** 的 reference adapter（上游已接受这种模式）。

**Tier 2（2-3 个月战略性贡献）**：
8. ⭐⭐⭐ [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) — 选一个方向深耕：SandboxWarmPool 策略优化 / gVisor runtimeclass 集成 benchmark / observability hook。**目标是成为 SIG 认识的贡献者**。
9. ⭐⭐⭐ **OpenTelemetry GenAI SIG** — 加入 `#otel-genai-instrumentation`，贡献：① TTFT p99 / operation duration burn rate 的 SLO 模板 RFC；② Prometheus recording rules；③ 参考 dashboard 设计。这是**定义标准**的位置。

---

## 8. 战略建议（针对瑞哥 3-6 个月路线图）

### Step 1（Week 1-2）：建立"在场感"
- 注册 OTel Slack 的 `#otel-genai-instrumentation` 和 CNCF Slack 的 `#sig-apps`，每周看一遍讨论
- 订阅 LangChain / OpenHands / kagent / Langfuse 的 release RSS
- 在 GitHub 上 watch 上述红榜项目 + 关注 5-8 个核心 maintainer

### Step 2（Week 3-6）：落地第一个 PR
- **推荐路径 A（最快）**：smolagents #2165 + DSPy #9459 各一个，两周内拿下 "I've merged PRs to HF and Stanford NLP" 的履历信号
- **推荐路径 B（高杠杆）**：Langfuse Prometheus exporter 三件套（/metrics endpoint + ServiceMonitor + Grafana dashboard），一个 PR 横跨 observability 整个技术栈

### Step 3（Week 7-12）：选一个"长期主场"
- 候选 A：**kubernetes-sigs/agent-sandbox** — SRE 技能 100% 对口，CNCF 履历，长期回报最高
- 候选 B：**LangGraph** — runtime 事实标准，影响面最广，但需要学 Python async 细节
- 候选 C：**Agno** — 定位 SRE-friendly，竞争不如 LangGraph 激烈，"PRIORITY PRODUCTION" bug 是现成靶子

### Step 4（Month 4+）：建立标准/品牌
- 在 OTel GenAI semconv 提一个"SLO 模板 RFC"，把 VictoriaMetrics / Loki / Grafana 实战经验系统化
- 把自己的 agent observability 心得写成博客（瑞哥已有 agent_dev_vs_agent_ops_infra 等调研笔记，可以深化）
- 考虑把几个贡献的 SRE-flavored 主题（durable execution / checkpointing / warm pool / rate limit pattern）串成 conference talk（KubeCon CNCF agent track 或 AI Engineer Summit）

### 什么不要做
- ❌ 不要 **"all in" 押单个框架**（中间层坍缩风险）
- ❌ 不要在 **AGPL / BSL / ELv2** license 的项目上投入核心时间
- ❌ 不要把 **"star 数"** 当选择标准（MetaGPT 67k stars 但 dormant）
- ❌ 不要追 **Show HN 玩具**（OpenClaw 10 天 68k→337k 这种）
- ❌ 不要**贡献 langchain core 本体**（legacy + CVE 债务 + 注意力已转 LangGraph）

---

## 9. License / 安全 / bus factor 雷区清单

### License 危险级别

| 级别 | License | 项目 | 备注 |
|---|---|---|---|
| 🟢 安全 | Apache-2.0 / MIT | agent-sandbox, e2b-dev/infra, kagent, OpenHands, LangGraph, Langfuse, SigNoz (core), Agno, DSPy, PydanticAI, smolagents, OpenInference, OpenLLMetry, Helicone, Laminar, container-use, OpenAI Agents SDK, Claude Agent SDK, Google ADK, microsandbox | 可自由商用 |
| 🟡 注意 | Apache + 源码可见企业 license | Mastra (`ee/`), SigNoz (`ee/`, `cmd/enterprise/`) | PR 前确认路径不在 enterprise 目录 |
| 🟡 注意 | CC-BY-4.0 | AutoGen | 非标软件 license，但已 maintenance 影响有限 |
| 🟠 风险 | ELv2（Elastic License 2.0）| Arize Phoenix | 不能做 managed service；个人贡献 OK，商业化受限 |
| 🔴 红线 | AGPL-3.0 | Daytona, Uptrace | 任何托管分发要 open source |
| 🔴 红线 | BSL 1.1 | restate | 4 年后转 Apache，但短期内不能做 managed service 转售 |

### 已知安全事件（2026 近期）

| 事件 | 日期 | 影响 |
|---|---|---|
| [LangChain CVE-2025-68664 "LangGrinch"](https://cyata.ai/blog/langgrinch-langchain-core-cve-2025-68664/) CVSS 9.3 | 2025-12 / 2026-03 | 任何 `langchain-core < 1.2.5 / 0.3.81` 必须升 |
| [LangGraph CVE-2026-28277](https://advisories.gitlab.com/pkg/pypi/langgraph/CVE-2026-28277/) | 2026 | checkpoint msgpack 反序列化 |
| [LiteLLM supply chain（TeamPCP）](https://docs.litellm.ai/blog/security-update-march-2026) | 2026-03-24 | 同一 campaign 已命中 Trivy / KICS / Telnyx |

### Bus factor 分级

- **低风险**：agent-sandbox（SIG），OTel GenAI semconv（SIG），LangGraph（LangChain 公司 + 400 家 prod 用户），OpenHands（$23.8M A 轮），DSPy（Stanford），kagent（Solo.io + CNCF），Google ADK（Google），Microsoft Agent Framework（MS）
- **中风险**：Langfuse（ClickHouse 收购后方向风险），Daytona，E2B，Letta，Agno，PydanticAI（31 人公司）
- **高风险**：CrewAI（创始人个人品牌绑定），Mastra（YC 速度过快），smolagents（HF 实验性），container-use（Dagger 商业压力）
- **已退出**：Helicone 主 repo，AutoGen，Phidata（已 rebrand），MetaGPT（dormant），AgentOps

---

## 10. 2026 Q2 agentic AI 开源整体态势（收尾总结）

**中间层坍缩**是这一季度的核心叙事。模型厂商的 Agent SDK（Claude/OpenAI/Google）已经吃掉 LangChain 类通用框架的大部分 value，迫使幸存者做选择题：要么**上移做 runtime/orchestration**（LangGraph、OpenHands、Microsoft Agent Framework、Temporal 对 agent 场景的适配），要么**下移做 infra/sandbox**（E2B、Daytona、kagent、agent-sandbox、Helicone AI Gateway）。Middle ground 越来越难站稳。

与此同时，**供应链和 license 风险进入主流视野**：LiteLLM 一次供应链攻击让全行业 audit gateway、LangChain 一个 CVSS 9.3 的反序列化 CVE 暴露"把任何 LLM 返回都 pickle 反序列化"的整类问题、Helicone 收购后熄火、Langfuse 被 ClickHouse 吞下。"可审计的 AI gateway"是 2026 年下半年的开放机会。

对 SRE + AI 背景的贡献者来说，杠杆最大的三个位置：**（1）CNCF agent 基础设施**（kagent + agent-sandbox）——这是 K8s operator / multi-tenancy / runtime isolation 技能的 1:1 迁移；**（2）OpenTelemetry GenAI 标准化**——SIG 目前缺运维视角，SLO/alerting/TTFT 这些概念还没有社区标准；**（3）LiteLLM 之后的"可审计 AI gateway"空缺**——Rust/Go 的 proxy + policy engine + audit log 方向还在重新洗牌。

**不要追 star 曲线陡的玩具项目**。追有 paying production 用户 + 资金稳（≥A 轮）+ license 干净（Apache/MIT）+ bus factor ≥3 的 runtime/infra 层项目。

---

## 11. Sources（按类别）

**Infra / Sandbox**:
- [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) · [Kubernetes Blog 2026-03-20](https://kubernetes.io/blog/2026/03/20/running-agents-on-kubernetes-with-agent-sandbox/) · [Google OSS Blog 2025-11](https://opensource.googleblog.com/2025/11/unleashing-autonomous-ai-agents-why-kubernetes-needs-a-new-standard-for-agent-execution.html)
- [e2b-dev/infra](https://github.com/e2b-dev/infra) · [E2B Series A](https://e2b.dev/blog/series-a)
- [kagent.dev](https://kagent.dev/) · [Solo.io 贡献到 CNCF](https://www.solo.io/blog/bringing-agentic-ai-to-kubernetes-contributing-kagent-to-cncf)
- [dagger/container-use](https://github.com/dagger/container-use) · [InfoQ 报道](https://www.infoq.com/news/2025/08/container-use/)
- [All-Hands-AI/OpenHands](https://github.com/All-Hands-AI/OpenHands) · [$18.8M A 轮](https://www.businesswire.com/news/home/20251118768131/en/OpenHands-Raises-$18.8M-Series-A-to-Bring-Open-Source-Cloud-Coding-Agents-to-Enterprises)
- [superradcompany/microsandbox](https://github.com/superradcompany/microsandbox) · [emirb.github.io MicroVM 2026](https://emirb.github.io/blog/microvm-2026/)
- [Daytona A 轮](https://upfront.com/thoughts/daytonas-24m-series-a) · [restate BSL](https://github.com/restatedev/restate/blob/main/LICENSE)

**Observability / Eval**:
- [Langfuse](https://github.com/langfuse/langfuse) · [ClickHouse 收购](https://clickhouse.com/blog/clickhouse-acquires-langfuse-open-source-llm-observability) · [Prometheus 需求 Discussion #2508](https://github.com/orgs/langfuse/discussions/2508)
- [SigNoz](https://github.com/SigNoz/signoz) · [SigNoz LLM Observability](https://signoz.io/docs/llm-observability/)
- [OpenTelemetry GenAI semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/) · [OTel Blog 2024 GenAI](https://opentelemetry.io/blog/2024/otel-generative-ai/) · [OTel Blog 2025 Agent Observability](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- [OpenLLMetry](https://github.com/traceloop/openllmetry) · [OpenInference](https://github.com/Arize-ai/openinference)
- [Phoenix ELv2 license](https://arize.com/docs/phoenix/self-hosting/license)
- [Helicone ai-gateway](https://github.com/Helicone/ai-gateway) · [BrightCoding](https://www.blog.brightcoding.dev/2026/03/14/helicone-ai-gateway-the-revolutionary-rust-powered-llm-router)
- [Laminar](https://github.com/lmnr-ai/lmnr) · [ClickHouse case study](https://clickhouse.com/blog/how-laminar-reimagined-observability-for-ai-browser-agents)

**Framework**:
- [LangGraph](https://github.com/langchain-ai/langgraph) · [Is LangGraph Used In Production?](https://blog.langchain.com/is-langgraph-used-in-production/) · [use-apify production](https://use-apify.com/blog/langgraph-agents-production)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) · [Agents SDK production patterns](https://letsdatascience.com/news/openai-expands-agents-sdk-with-production-control-patterns-61bc011d)
- [Agno](https://github.com/agno-agi/agno) · [Agno Feb 2026 Apache-2.0](https://www.agno.com/blog/community-roundup-february-2026)
- [PydanticAI](https://github.com/pydantic/pydantic-ai) · [Samuel Colvin 访谈](https://www.startuphub.ai/ai-news/artificial-intelligence/2026/pydantic-ai-s-samuel-colvin-on-building-better-llm-agents)
- [DSPy](https://github.com/stanfordnlp/dspy) · [smolagents](https://github.com/huggingface/smolagents) · [CrewAI $18M A 轮](https://siliconangle.com/2024/10/22/agentic-ai-startup-crewai-closes-18m-funding-round/)
- [Letta](https://github.com/letta-ai/letta) · [Mastra licensing](https://mastra.ai/docs/community/licensing) · [Mastra $22M A 轮](https://technews180.com/funding-news/mastra-raises-13m-seed-for-typescript-ai-framework/)
- [Microsoft Agent Framework GA](https://cloudsummit.eu/blog/microsoft-agent-framework-production-ready-convergence-autogen-semantic-kernel) · [AutoGen maintenance](https://github.com/microsoft/autogen/discussions/7066)

**Security / License**:
- [LangChain "LangGrinch" CVE-2025-68664](https://cyata.ai/blog/langgrinch-langchain-core-cve-2025-68664/) · [NVD](https://nvd.nist.gov/vuln/detail/CVE-2025-68664)
- [LiteLLM 供应链](https://docs.litellm.ai/blog/security-update-march-2026) · [Snyk 分析](https://snyk.io/blog/poisoned-security-scanner-backdooring-litellm/) · [Trend Micro](https://www.trendmicro.com/en_us/research/26/c/inside-litellm-supply-chain-compromise.html)
- [LangGraph CVE-2026-28277](https://advisories.gitlab.com/pkg/pypi/langgraph/CVE-2026-28277/)

**第三方对比与观察**:
- [Helicone 收购 / LiteLLM 事件后 proxy 格局](https://dev.to/stockyarddev/the-llm-proxy-landscape-in-2026-helicone-acquired-litellm-compromised-and-whats-next-3oon)
- [Python AI Agent Library Comparison 2026](https://jangwook.net/en/blog/en/python-ai-agent-library-comparison-2026/)
- [OpenAI vs LangGraph vs CrewAI Matrix 2026](https://www.digitalapplied.com/blog/openai-agents-sdk-vs-langgraph-vs-crewai-matrix-2026)
- [Claude vs OpenAI vs Google ADK](https://composio.dev/content/claude-agents-sdk-vs-openai-agents-sdk-vs-google-adk)
- [AI Code Sandbox Benchmark 2026](https://www.superagent.sh/blog/ai-code-sandbox-benchmark-2026)
- [Open Source in 2026: Fork Wars](https://dev.to/gabrielanhaia/open-source-in-2026-the-fork-wars-are-getting-ugly-28n)
- [Jimmy Song Agentic Runtime Realism](https://jimmysong.io/blog/agentic-runtime-realism/)

---

**调研完成时间**：2026-04-22
**下次更新建议**：60-90 天后。中间层坍缩还在进行，license / M&A / supply-chain 事件的节奏快，状态快照会过期。
