# Agentic AI Observability 2026 深度调研

- **调研日期**: 2026-04-22
- **方法**: 4 维度并行 subagent + 交叉验证
  - A: 工具生态 landscape
  - B: 技术复杂性
  - C: 标准化进展（OTel GenAI / OpenInference / OpenLLMetry）
  - D: 争议与最优解
- **调研范围**: 多步骤 LLM agent、工具调用链、嵌套 subagent、长会话记忆场景 — 不仅限单次 LLM 调用
- **交叉验证**: 四个 subagent 有 ≥50% overlap，至少一组直接矛盾（OTel semconv 成熟度），详见 §6

---

## 核心结论（直接回答你的 4 个问题）

### 1. 发展到什么情况？

三层结构看：

| 层级 | 状态 | 证据 |
|---|---|---|
| 单次 LLM 调用（prompt/token/latency/cost） | **基本解决** | OTel GenAI semconv 覆盖；所有主流工具做到 |
| Agent 级别（嵌套 trace、工具调用、trajectory replay） | **部分解决** | OTel 已定义 `invoke_agent` / `create_agent` / `execute_tool` spans；各家 schema 仍不完全一致 |
| Multi-agent + 长会话 + 语义级失败 | **仍未解决** | 没有任何厂商能真正覆盖跨会话记忆溯源、tool 返回 200 但 garbage、post-compaction 可见上下文 |

过去 12 个月最大结构性变化：**OTel GenAI 成为事实底层**，Datadog/Langfuse/LangSmith/Braintrust/Laminar/W&B Weave 都已 native 支持（但 semconv 本身仍为 Experimental，详见 §3）。

### 2. 是一个复杂的点吗？

**极复杂。** B 维度梳理了 10 个技术挑战，只有 2 个 "solved reasonably"，6 个 "partial"，2 个 "unsolved"（详见 §2 的状态表）。结构性难点集中在：

- **Non-determinism** — 没有泛化的 seeded replay（tool 触碰外部状态）
- **Trajectory eval vs final-output eval** — 最终答案对但路径错的失败模式没有通用解
- **长会话 / 跨 session 记忆溯源** — 追踪"哪段记忆影响了此刻决策"是开放研究问题
- **语义级工具失败** — HTTP 200 但返回 garbage，靠 judge 模型比 tool call 本身还贵
- **Post-compaction context introspection** — OTel 里没有"压缩后可见上下文"的标准属性

### 3. 需要人类权衡吗？

**必须权衡**，4 个核心轴，没有免费午餐：

| 权衡轴 | 一端 | 另一端 |
|---|---|---|
| Framework 深度 vs 可移植性 | LangSmith：对 LangGraph 最强 | Langfuse：OSS + 通用 OTel |
| 成本 vs 可观测性完整度 | Datadog LLM Obs：加了账单 +40-200% | OSS 自建 Langfuse：免许可费但吃 Postgres/ClickHouse/K8s 运维 |
| Eval 与 Observability 合并 vs 分离 | Braintrust：合并到同一工作流 | LangSmith + Datadog：eval 归 eval、APM 归 APM |
| 应用层 vs 系统层 | LangSmith/Phoenix：trace 到 agent 推理 | Datadog/Grafana：统一 GPU/infra/LLM |

### 4. 有最优解吗？

**没有。** 这是 D 维度最强的结论，直接引用：

> "2026 observability looks like 2012 APM before New Relic/Datadog consolidated — four viable architectures, loud tribal debates, a slowly-forming OpenTelemetry substrate, and a long tail of unsolved multi-agent problems that no vendor has credibly claimed. The 'best solution' question is currently a category error: the right answer depends on whether your dominant constraint is framework depth, data control, eval-loop velocity, or infrastructure integration."

真实选型按主约束分流成 4 camp（详见 §5）。

---

## 2. 技术复杂性（10 个挑战的 solved / unsolved 状态）

（来源：B 维度，交叉验证自 Anthropic 官方工程博客、Sierra τ-bench、Cognition Devin review、Jason Liu、Hamel Husain）

| # | 挑战 | 状态 | 最强工具/方案 | 剩余缺口 | 关键来源 |
|---|---|---|---|---|---|
| 1 | Non-determinism（同输入不同 trajectory） | Partial | pass^k 统计、τ-bench、Hamel 的 "20-50 manual review" | 无法做 deterministic replay（tool 碰外部状态） | [Sierra τ-bench](https://sierra.ai/blog/benchmarking-ai-agents)；[hamel.dev evals FAQ](https://hamel.dev/blog/posts/evals-faq/) |
| 2 | 嵌套 trace 层级 | Partial | OTel `gen-ai-agent-spans`（2025） | 各家 adoption 不均；MCP trace-ID propagation 仍 DIY | [OTel GenAI agent spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/) |
| 3 | Token / cost 跨嵌套 hop 归因 | 扁平已解决 / 嵌套 Partial | LangSmith、Langfuse 的 cost rollup | retry / cache / subagent 归属语义没 convention | [Langfuse cost tracking](https://langfuse.com/docs/observability/features/token-and-cost-tracking) |
| 4 | 长会话 / 多 session agent | **Unsolved** | AWS AgentCore Memory 能发 span | 跨 session provenance 追踪是研究问题 | [AWS Bedrock AgentCore Memory](https://aws.amazon.com/blogs/machine-learning/amazon-bedrock-agentcore-memory-building-context-aware-agents/) |
| 5 | Trajectory eval vs final-output eval | Partial | LangSmith trajectory、Agent-as-a-Judge、Anthropic rubric | Gold trajectories 稀少且常有 bug | [LangSmith trajectory evals](https://docs.langchain.com/langsmith/trajectory-evals)；[Anthropic: demystifying evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) |
| 6 | Streaming + interleaved tool calls | **Unsolved** | 大多数厂商拍平成 sibling spans | OTel 没有 mid-stream tool span 的首类模型 | [Traceloop visualizing LLM perf](https://www.traceloop.com/blog/visualizing-llm-performance-with-opentelemetry-tools-for-tracing-cost-and-latency) |
| 7 | Tool call 语义失败（200 但 garbage） | **Unsolved** | Cleanlab LLM trust scoring | judge 成本 > tool call 成本 | [Cleanlab τ² 分析](https://cleanlab.ai/blog/tau-bench/) |
| 8 | Compaction 可见上下文 | Anthropic 内部 Partial / 跨厂商 Unsolved | Claude Code `/context`、`applied_edits` 字段 | 没有跨厂商 OTel 属性描述"压缩后上下文" | [Claude cookbook: context compaction](https://platform.claude.com/cookbook/tool-use-automatic-context-compaction)；[Jason Liu on compaction](https://jxnl.co/writing/2025/08/30/context-engineering-compaction/) |
| 9 | Harness 级别可观测（Claude Code / Cursor / Cline） | Claude Code 最好 / Cline 部分 / Cursor/Amp 不透明 | Claude Code OTel 原生 | 闭源工具不公开 | [Claude Code observability](https://code.claude.com/docs/en/agent-sdk/observability)；[Cline telemetry](https://docs.cline.bot/more-info/telemetry) |
| 10 | 并行 tool 调用 | Partial | OTel spans + `disable_parallel_tool_use` | 并行 subagent 涌现行为调试仍是开放问题 | [Anthropic multi-agent system](https://www.anthropic.com/engineering/multi-agent-research-system) |

**Anthropic 官方原话对结构性问题的承认**（跨验证 B + D 都引用）：

> "Agents make dynamic decisions and are non-deterministic between runs, even with identical prompts. This makes debugging harder... Minor changes cascade into large behavioral changes, which makes it remarkably difficult to write code for complex agents that must maintain state... asynchronous execution adds challenges in result coordination, state consistency, and error propagation." — [Anthropic multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)

---

## 3. 标准化进展（OTel GenAI / OpenInference / OpenLLMetry）

### 3.1 OTel GenAI semantic conventions — 仍是 Experimental

**关键事实（权威直引 C 维度）**：截至 v1.37.0，OTel GenAI semconv **仍被分类为 Development / Experimental**，不是 stable。官方 spec 原话：

> "The default behavior is to continue emitting whatever version of the GenAI conventions the instrumentation was emitting (1.36.0 or prior), and this transition plan will be updated to include a stable version before the GenAI conventions are marked as stable." — [opentelemetry.io/docs/specs/semconv/gen-ai](https://opentelemetry.io/docs/specs/semconv/gen-ai/)

> ⚠️ **注意**：D subagent 原文写 "landed as stable in early 2026"，但 C 直接查了 spec 主页，spec 本身还在 Experimental。**采信 C。** 这是报告里最显著的单一矛盾点，采信原则是："直引 spec 主页" > "引用 OTel 博客的模糊表述"。

agent 相关属性已定义：`gen_ai.agent.id` / `gen_ai.agent.name` / `gen_ai.agent.description` / `gen_ai.agent.version`；span 名是 `invoke_agent {name}` 和 `create_agent {name}`；tool call 用 `execute_tool` 带 `gen_ai.tool.call.arguments` 和 `gen_ai.tool.call.result`。

**MCP 有独立的 semconv**：[opentelemetry.io/docs/specs/semconv/gen-ai/mcp](https://opentelemetry.io/docs/specs/semconv/gen-ai/mcp/) — 定义了 `mcp.method.name` / `mcp.protocol.version` / `mcp.session.id`；trace context 走 JSON-RPC 的 `params._meta` bag 注入 `traceparent`。

**关键未解决 issue**：[OTel Issue #2664](https://github.com/open-telemetry/semantic-conventions/issues/2664)（2025-08-20 开，2026-04 仍 Open）提出 6 个概念：tasks / actions / agents / teams / artifacts / memory。这是 agentic 最核心的 gap placeholder。

### 3.2 OpenInference（Arize）

自定位"与 OTel 互补而非取代"，传输是 OTLP 但属性词表不同。Arize 写 OpenInferenceSpanProcessor 和 OTel GenAI 互相转换器 — **说明两份规范预期长期共存，不会合并**。[Arize Phoenix docs](https://arize.com/docs/phoenix/tracing/concepts-tracing/translating-conventions)

### 3.3 OpenLLMetry（Traceloop）

自称"leading OpenTelemetry's LLM semantic convention working group"，覆盖最广（LangChain / LlamaIndex / Haystack / MCP / Pinecone / 各家模型）。但 [Issue #3515](https://github.com/traceloop/openllmetry/issues/3515) 暴露：`gen_ai.prompt` 和 `gen_ai.completion` 在上游 OTel 已 deprecated，OpenLLMetry 实际上在"追"自己声称领导的 spec。

### 3.4 厂商 / 框架 emission 矩阵（April 2026）

| 厂商 / 框架 | OTel GenAI native | OpenInference | OpenLLMetry | 仅专有 | 日期源 |
|---|---|---|---|---|---|
| Datadog LLM Obs | ✅ (v1.37+) | ❌ | ❌ | 兼有 DD-native | [DD OTel 公告](https://www.datadoghq.com/blog/llm-otel-semantic-convention/) |
| Langfuse | ✅ (ingests OTLP) | ✅ (ingests) | ✅ (ingests) | 有自 SDK | [langfuse native OTel](https://langfuse.com/integrations/native/opentelemetry) |
| LangSmith | ✅ (E2E, Mar 2025) | ❌ | ❌ | 兼有原生格式 | [LangSmith E2E OTel 公告](https://blog.langchain.com/end-to-end-opentelemetry-langsmith/) |
| Arize Phoenix | Partial (ingests) | Native emit | ingests | — | [OpenInference](https://github.com/Arize-ai/openinference) |
| Braintrust | ✅ (auto conversion) | ❌ | ❌ | 自属性 | [Braintrust OTel](https://www.braintrust.dev/docs/integrations/sdk-integrations/opentelemetry) |
| Helicone | ✅ | ❌ | ❌ | Proxy | [Helicone](https://www.helicone.ai/blog/the-complete-guide-to-LLM-observability-platforms) |
| Laminar | ✅ | ❌ | ✅ compatible | — | [Laminar GitHub](https://github.com/lmnr-ai/lmnr) |
| W&B Weave | ✅ (`/otel/v1/traces`) | ❌ | ❌ | Weave native | [Weave OTLP](https://weave-docs.wandb.ai/guides/tracking/otel/) |
| LangChain / LangGraph | ✅ (via LangSmith) | via OI | via OpenLLMetry | — | [LangChain OTel 公告](https://blog.langchain.com/opentelemetry-langsmith/) |
| LlamaIndex | community pkg | Native (2025-10-24) | community pkg | — | [PyPI](https://pypi.org/project/openinference-instrumentation-llama-index/) |
| MCP servers | Emerging | ❌ | OpenLLMetry MCP pkg | 多数仍专有 | [OTel MCP semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/mcp/) |

### 3.5 标准化批评

**最清晰的批评**（Dennis Zhuang, Greptime CEO，2025-12-16）：

> "You either stuff everything into logs (losing structure, making queries painful) or force it into traces (too rigid for dynamic structures)." — [Greptime](https://www.greptime.com/blogs/2025-12-11-agent-observability)

他的三点：(1) attributes 层如 `mcp.tool_name` / `agent.session_id` 还没社区共识；(2) 分布式 trace 挣扎于跨 agent 边界的 client-side 和 server-side 关联；(3) 传统 OTel 属性无法捕捉 memory 或推理状态。他呼吁"state tracking as a first-class concern"——当前 spec 缺这一层。

---

## 4. 工具生态现状（April 2026）

（综合 A 维度 landscape + D 维度批评，交叉验证）

### 4.1 LLM-native 阵营

**LangSmith（LangChain）** — 闭源 SaaS，对 LangGraph 零配置最深。[A5Labs 迁出原因](https://www.confident-ai.com/knowledge-base/compare/top-langsmith-alternatives-and-competitors-compared)：

> "too tied into the LangChain ecosystem and lacked the evaluation depth and pricing flexibility"

HN 对抽象层的吐槽：

> "once you need something a little original you have to go through 5 layers of abstraction just to change a minute detail" — [HN #40739982](https://news.ycombinator.com/item?id=40739982)

LangChain 反驳："LangSmith Observability is framework agnostic and works no matter how you build your agent"，自 2025-03 支持 E2E OTel。但实际用户感受依旧 LangChain-first。

**Langfuse（被 ClickHouse 收购）** — MIT OSS + 托管 SaaS。
> ⚠️ **单一源需验证**：A 报 [2026-01-16 ClickHouse 收购](https://clickhouse.com/blog/clickhouse-acquires-langfuse-open-source-llm-observability)，[估值 $15B](https://byteiota.com/clickhouse-acquires-langfuse-at-15b-valuation/)。公开博客有，但 $15B 这个数字来自 byteiota 二手报道，建议核实原始新闻稿。

Langfuse 公开数据（来源 [langfuse.com/blog/joining-clickhouse](https://langfuse.com/blog/joining-clickhouse)）：2,000+ 付费客户、26M+ SDK 安装/月、Fortune 50 里 19 家、Fortune 500 里 63 家。[AWS Bedrock AgentCore 教程默认 obs 合作方](https://aws.amazon.com/blogs/machine-learning/amazon-bedrock-agentcore-observability-with-langfuse/)。

自部署痛点：[#10391 UI 慢](https://github.com/langfuse/langfuse/issues/10391)、[#7591 高流量 liveness probe 失败](https://github.com/langfuse/langfuse/issues/7591) — Postgres + ClickHouse + Redis + S3/MinIO 栈对小团队沉重。

**Arize AI + Phoenix** — Phoenix MIT OSS / Arize AX 企业 SaaS。[2025 初 $70M Series C](https://arize.com/)。客户：DoorDash、Uber、Reddit、Instacart、Booking。"1 trillion spans + 50M+ evals per month"。
定价批评：[dual-axis pricing](https://langfuse.com/faq/all/best-phoenix-arize-alternatives) "actively punishes RAG architectures"。

**Braintrust** — eval-first 闭源 SaaS。
> ⚠️ **单一源需验证**：[$80M Series B, Feb 2026, ICONIQ 领投, $800M 估值](https://www.finsmes.com/2026/02/braintrust-raises-80m-in-series-b-funding.html)。两家二手来源，建议核实原始公告。

客户矩阵：**Notion / Replit / Cloudflare / Ramp / Dropbox / Vercel / Navan / BILL** — AI-native 最强 logo 名单。

**Helicone** — YC W23，proxy-based。Braintrust 的结构性反驳最重要：
> "If Helicone experiences downtime or network issues, your LLM calls fail even if OpenAI or Anthropic remain operational... you only see what passes through the proxy, as retrieval steps, tool calls, business logic, and application context remain invisible" — [Braintrust comparison](https://www.braintrust.dev/articles/helicone-vs-braintrust)

这是 proxy 模式在 agentic 场景的结构性劣势 — 大量有意思的行为发生在 LLM 调用之间。

**W&B Weave / Laminar / Traceloop / HoneyHive / LangWatch** — 见矩阵。

### 4.2 传统 APM 阵营

**Datadog LLM Observability** — [2025-06-10 agentic 扩张](https://www.datadoghq.com/about/latest-news/press-releases/datadog-expands-llm-observability-with-new-capabilities-to-monitor-agentic-ai-accelerate-development-and-improve-model-performance/)：AI Agent Monitoring、LLM Experiments、AI Agents Console。原生支持 OTel GenAI semconv v1.37+。

**定价争议（多源交叉确认）**：
- [SigNoz 2026 分析](https://signoz.io/blog/datadog-pricing/)：加 LLM obs 后账单"40-200% 增长"
- [OneUptime](https://oneuptime.com/blog/post/2026-04-01-ai-workload-observability-cost-crisis/view)：AI workload 产生"10-50x traditional services"的 telemetry
- [OpenObserve 对比](https://openobserve.ai/blog/datadog-pricing/)：同样 telemetry，Datadog $174/天 vs OpenObserve $3/天，"58x cost difference"
- [byteiota 独立报道](https://byteiota.com/observability-costs-2026-why-datadog-bills-explode-fix/)：Datadog "automatically activates a $120/day premium when detecting LLM spans with no opt-out"

**New Relic AIM** — [2025-11 Agentic AI Monitoring + Agents Service Map](https://siliconangle.com/2025/11/04/new-relic-steps-observability-agentic-ai-deployments/)。Partnership 策略，自己不直接做 delivery lifecycle。

**Dynatrace** — Davis AI + "operator agents supervising other agents"。企业为主。

**Honeycomb** — wide-events 模型扩展到 agent：
> "you can see every tool call, LLM invocation, and evaluation span, and immediately spot the one costing you 800 seconds of wall-clock time" — [Honeycomb blog](https://www.honeycomb.io/blog/honeycomb-is-built-for-the-agent-era-pt1)

支持 MCP，agents 可以直接查 Honeycomb。适合想把 LLM spans 和分布式系统其他部分关联的团队。

**Grafana Cloud AI** — 5 个预制 dashboard（GenAI / Evaluations / VectorDB / MCP / GPU），自动 instrument 50+ GenAI 工具。Grafana Assistant 是内嵌 LLM agent。价格比 Datadog 好，要自己装配。

### 4.3 云平台原生

- **AWS Bedrock AgentCore Observability**（2025-10 GA）— OTel native，"bring your own backend"，教程推 Langfuse / Arize / W&B Weave
- **Azure AI Foundry** — Application Insights 集成
- **Google Vertex AI** — Gemini 中心，整合 W&B Weave via ADK

---

## 5. 争议与 4 Camp 分化（最核心的权衡）

### 5.1 Vendor lock-in 辩论

历史数据才是最深的锁：
> "there's no automated migration path for historical trace data between platforms, though both tools export datasets as JSON or CSV" — [markaicode](https://markaicode.com/vs/langfuse-vs-langsmith/)

即你 1 年前的 trace 基本就留在当初那个平台。这是真实的 lock-in，和协议层 lock-in 是两回事。

### 5.2 Eval vs Observability — 合并派 vs 分离派

**Hamel Husain（合并派理论支撑）**：
> "there is an incredibly large overlap between the infrastructure needed for evaluation and that for debugging" — [hamel.dev/blog/posts/evals](https://hamel.dev/blog/posts/evals/)
> "You are doing it wrong if you aren't looking at lots of data"

**Braintrust（合并派产品实现）**— Goyal 的演化：从 eval 工具起家，用户追问"我怎么拿到数据做 evals"，于是观测作为副产品被合并。[latent.space 访谈](https://www.latent.space/p/braintrust)

**Shreya Shankar 的 criteria drift**（强化合并派）：
> "users need criteria to grade outputs, but grading outputs helps users define criteria" — [arxiv 2404.12272](https://arxiv.org/abs/2404.12272)

意思是 eval 标准无法静态，必须和生产观测共享状态。

**Eugene Yan 的折衷**：
> "evaluating LLM applications can be viewed as unit testing, observability, or data science — and all these perspectives are useful" — [eugeneyan.com/writing/evals](https://eugeneyan.com/writing/evals/)

**分离派（两工具现实）**：
> "LangSmith's focus is on the application layer, it doesn't monitor system metrics or GPU usage — you'd still rely on traditional APM tools like Datadog" — [LangChain articles](https://www.langchain.com/articles/llm-observability-tools)

### 5.3 LLM-native vs APM 扩展 — 数据引力 vs 性能 vs 成本

> "If you're already building with LangChain or LangGraph, LangSmith is the path of least resistance... Datadog LLM Observability should be chosen if you need unified infrastructure and LLM monitoring within an existing Datadog stack" — [Confident AI](https://www.confident-ai.com/knowledge-base/compare/top-7-llm-observability-tools)

数据引力（已在 Datadog 上）vs 成本（40-200% 账单涨幅）是真实拉锯。OTel GenAI 让 Datadog 不再独占 schema，但定价结构没变。

### 5.4 Build vs Buy

**Anthropic 内部自建**：
> "Adding full production tracing let us diagnose why agents failed and fix issues systematically" — [Anthropic multi-agent](https://www.anthropic.com/engineering/multi-agent-research-system)

**Cursor 自托管 agents 给 Fortune 500**（[thenewstack](https://thenewstack.io/cursor-self-hosted-coding-agents/)），自己 telemetry。

**Claude Code 公开 OTel**（[官方 observability 文档](https://code.claude.com/docs/en/agent-sdk/observability)）— 是所有 AI harness 里最透明的；Cline 只有 PostHog 匿名遥测（[cline telemetry](https://docs.cline.bot/more-info/telemetry)）；**Cursor 和 Sourcegraph Amp 的内部 telemetry schema 不公开**。

**Jason Liu 的反潮流立场**（最诚实的反观测主义声音）：
> "I don't really try to touch any of the observability aspects. I just add some deep debugging in place" — [humanloop interview](https://humanloop.com/blog/contrarian-guide-to-ai)

他偏好 validator + 人工专家评估，不信 LLM-judge dashboard。和他的 short agent 观点一致。

### 5.5 安全 / Governance 的观测缺口

> "Enterprise multi-agent AI systems produce thousands of inter-agent interactions per hour, yet existing observability tools capture these dependencies without enforcing anything... OpenTelemetry and Langfuse collect telemetry but treat governance as a downstream analytics concern, not a real-time enforcement target. The result is an 'observe-but-do-not-act' gap where policy violations are detected only after damage is done" — [arxiv 2604.05119](https://arxiv.org/abs/2604.05119)

> ⚠️ **单一源需验证**：arxiv 2604.05119 是未来日期 arxiv id，这个 ID 语义上是 2026 年 4 月论文；D agent 引用无误，但具体论文内容建议点开原文确认。

15 秒 dashboard 延迟对 PII 合规场景不够 — "观察但不能行动"的 gap 是 SRE + compliance 视角的真痛点。

### 5.6 真实 agent 失败模式（为什么观测如此重要）

> "An inventory agent invents a nonexistent SKU, then calls four downstream APIs to price, stock, and ship the phantom item, triggering a multi-system incident that bypasses traditional validation checks" — [Arize common failures](https://arize.com/blog/common-ai-agent-failures/)

> "When agents encounter errors, they cannot distinguish between 'I failed the task' and 'The task is impossible,' often hallucinating a success message. When an agent masks a backend failure with a polite success message, you need a trace to expose the deception." — [oneuptime](https://oneuptime.com/blog/post/2026-03-19-your-ai-agents-are-running-blind/view)

**EchoLeak（2025）** — 零点击 prompt injection 对 Microsoft Copilot：
> "attackers sent emails with hidden instructions that Copilot ingested, allowing AI to extract sensitive data and exfiltrate it via trusted Microsoft domains... No alert surfaced and no one noticed" — [reco.ai](https://www.reco.ai/blog/ai-and-cloud-security-breaches-2025)

**OpenAI 2025-12 官方声明**：
> "AI browsers may always be vulnerable to prompt injection attacks" — [TechCrunch](https://techcrunch.com/2025/12/22/openai-says-ai-browsers-may-always-be-vulnerable-to-prompt-injection-attacks/)

prompt injection 观测可能**结构性不可解** — 当前工具能记录 tool call，但无法判断"意图是否对抗性"。

---

## 6. 交叉验证、矛盾与存疑清单

### 已高可信（多源确认）

- Datadog LLM Obs 加费 40-200% + $174/天 vs $3/天 58x 差距 — A 和 D 各自引用 4 个独立源
- LangSmith lock-in 吐槽（A5Labs、HN 两源）
- multi-agent 长会话观测未解决（B + D + Anthropic 官方博客）
- trajectory-level observability 缺失（B + D：Jason Liu + Anthropic 都承认）
- OTel GenAI 是慢慢成形的底层共识（4 个 subagent 全部确认）
- Helicone proxy 模式的结构性盲区（A + Braintrust 的对比文章）

### 直接矛盾，已采信其中一方

| 主题 | C 的结论（采信） | D 的结论（不采信） | 理由 |
|---|---|---|---|
| OTel GenAI semconv 成熟度 | 仍 Experimental / Development | "landed as stable in early 2026" | C 直引 [spec 主页](https://opentelemetry.io/docs/specs/semconv/gen-ai/) 原文；D 是对 OTel blog 的模糊转述 |

### 单一来源，需人工核实

- Langfuse **$15B** 估值（来源：[byteiota 二手报道](https://byteiota.com/clickhouse-acquires-langfuse-at-15b-valuation/)；ClickHouse 官方 [收购公告](https://clickhouse.com/blog/clickhouse-acquires-langfuse-open-source-llm-observability) 未披露估值）— 收购事实真，具体估值建议查原始公告
- Braintrust **$80M Series B / $800M 估值**（2026-02，ICONIQ 领投）— 来源 [finsmes](https://www.finsmes.com/2026/02/braintrust-raises-80m-in-series-b-funding.html) + [siliconangle](https://siliconangle.com/2026/02/17/braintrust-lands-80m-series-b-funding-round-become-observability-layer-ai/)，两个二手源
- [arxiv 2604.05119](https://arxiv.org/abs/2604.05119)（governance enforcement gap 论文）— arxiv id 语义上合法（2026-04），建议点开核实
- [Greptime CEO 批评文章](https://www.greptime.com/blogs/2025-12-11-agent-observability) — 实名立场，URL 路径含日期不一致（2025-12-11 在路径、但 D 引用为 2025-12-16）— 轻微时间歧义，但核心立场清晰

### Marketing 话语 vs 用户实感（两者都保留）

- LangChain 自述 LangSmith "framework agnostic"；用户实际体验仍 LangChain-first — 两者都真
- Traceloop 自称"leading OTel GenAI working group"；实际 [issue #3515](https://github.com/traceloop/openllmetry/issues/3515) 显示他们在追赶自己声称领导的 spec

---

## 7. 4 Camp 选型地图（按主约束分流）

这是最终的实用建议，基于 D 的"无最优解，只有按约束分流"：

| Camp | 主约束 | 推荐工具 | 真实代价 |
|---|---|---|---|
| 1. LangChain-deep 团队 | 要最深 LangGraph introspection | **LangSmith** | 协议 lock-in 因 OTel 缓解，但最强功能仍 LangChain-first |
| 2. 数据敏感 / 成本敏感团队 | 数据不出边界、账单可预测 | **Langfuse 自部署** | 需要 Postgres + ClickHouse + K8s 运维人手 |
| 3. Eval-first / CI-driven 团队 | eval + obs 同一工作流、快速迭代 | **Braintrust** | 闭源 + 高价；数据在对方手里 |
| 4. 数据引力 APM 团队 | 已重度使用 Datadog、基础设施统一监控 | **Datadog LLM Obs**（硬扛） | 40-200% 账单涨幅、auto-activation 无 opt-out |

**如果你像瑞哥这样是 SRE + AI 背景**（个人建议，非 subagent 直接结论）：
- 观测 harness 本身优先选 Claude Code（已 OTel 原生）
- 后端用 **Langfuse 自部署**（数据控制 + OSS + OTel 原生，ClickHouse 作 storage 和 SRE 既有栈契合）
- 别只看 dashboard，重点关注 §5.5 的 governance enforcement latency gap — 这是 SRE-vs-应用层观测的真分歧
- Prompt injection 防御**不要**指望观测方案解决（OpenAI 自己都说可能结构性不可解）

---

## 8. 关键共识 & 非共识总结

**已共识**：
- 单次 LLM 调用观测基本解决，OTel GenAI 客户端 spans 是终局形态
- 通用 eval 框架不奏效（Hamel 观点无人反驳）
- Human-in-the-loop review 不可替代（Anthropic "People testing agents find edge cases that evals miss"）
- Trace 是安全基础，否则抓不到"agent 用礼貌成功消息掩盖失败"

**仍无共识**：
- Eval 和 obs 该不该合并为一个产品
- Trajectory-level observability 如何统一描述 — Liu、Anthropic、governance 论文都说缺，无产品真正覆盖
- Multi-agent 标准化 — OTel 在 IBM Bee / CrewAI / AutoGen / LangGraph 跨家定义 semconv，但 adoption 碎片
- Prompt-injection observability — 可能结构性无解（OpenAI 对 browsing agents 已承认）

---

## 附录：关键来源清单

### 一手工程博客
- [Anthropic: Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Anthropic: Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Cognition: Devin annual performance review 2025](https://cognition.ai/blog/devin-annual-performance-review-2025)
- [OpenTelemetry: AI Agent Observability — Evolving Standards](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- [Sierra: τ-bench benchmarking AI agents](https://sierra.ai/blog/benchmarking-ai-agents)

### 规范 / 标准
- [OTel GenAI semconv root](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [OTel GenAI agent spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)
- [OTel MCP semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/mcp/)
- [OTel Issue #2664: Agentic systems proposal](https://github.com/open-telemetry/semantic-conventions/issues/2664)
- [OpenInference GitHub](https://github.com/Arize-ai/openinference)
- [OpenLLMetry GitHub](https://github.com/traceloop/openllmetry)

### 实践者声音
- [Hamel Husain: Evals FAQ](https://hamel.dev/blog/posts/evals-faq/)
- [Hamel Husain: Evals](https://hamel.dev/blog/posts/evals/)
- [Jason Liu: Context engineering and compaction](https://jxnl.co/writing/2025/08/30/context-engineering-compaction/)
- [Jason Liu: Humanloop contrarian interview](https://humanloop.com/blog/contrarian-guide-to-ai)
- [Eugene Yan: Writing evals](https://eugeneyan.com/writing/evals/)
- [Shreya Shankar: Criteria drift (arxiv 2404.12272)](https://arxiv.org/abs/2404.12272)
- [Greptime (Dennis Zhuang): Agent observability critique](https://www.greptime.com/blogs/2025-12-11-agent-observability)

### 厂商对比 / 批评
- [Braintrust vs Helicone](https://www.braintrust.dev/articles/helicone-vs-braintrust)
- [LangWatch comparison: LangSmith vs Braintrust vs Langfuse](https://langwatch.ai/blog/langwatch-vs-langsmith-vs-braintrust-vs-langfuse-choosing-the-best-llm-evaluation-monitoring-tool-in-2025)
- [Confident AI: Top LangSmith alternatives](https://www.confident-ai.com/knowledge-base/compare/top-langsmith-alternatives-and-competitors-compared)
- [Langfuse alternatives FAQ](https://langfuse.com/faq/all/best-phoenix-arize-alternatives)

### 定价与成本
- [SigNoz: Datadog pricing 2026](https://signoz.io/blog/datadog-pricing/)
- [OneUptime: AI observability cost crisis](https://oneuptime.com/blog/post/2026-04-01-ai-workload-observability-cost-crisis/view)
- [OpenObserve vs Datadog cost comparison](https://openobserve.ai/blog/datadog-vs-openobserve-part-9-cost/)

### 失败模式 / 安全
- [Arize: Common AI agent failures](https://arize.com/blog/common-ai-agent-failures/)
- [OneUptime: Your AI agents are running blind](https://oneuptime.com/blog/post/2026-03-19-your-ai-agents-are-running-blind/view)
- [Reco: AI and cloud security breaches 2025 (EchoLeak)](https://www.reco.ai/blog/ai-and-cloud-security-breaches-2025)
- [TechCrunch: OpenAI on prompt injection](https://techcrunch.com/2025/12/22/openai-says-ai-browsers-may-always-be-vulnerable-to-prompt-injection-attacks/)

### 学术
- [τ-bench (arxiv 2406.12045)](https://arxiv.org/abs/2406.12045)
- [τ²-bench (arxiv 2506.07982)](https://arxiv.org/pdf/2506.07982)
- [Agent-as-a-Judge (arxiv 2508.02994)](https://arxiv.org/html/2508.02994v1)
- [Multi-agent governance enforcement (arxiv 2604.05119) ⚠️ 单源需核实](https://arxiv.org/abs/2604.05119)
