# AI Infra / MLOps / AI Agent Dev 深度调研蒸馏

**Session 日期**: 2026-03-28 ~ 2026-03-30
**完整报告**: `contexts/survey_sessions/ai_infra_survey_20260328.md` + `contexts/survey_sessions/mlops_ai_agent_dev_survey_20260330.md`

---

## Key Insights

### AI Infrastructure

- **AI Infra 不是传统 IT 升级，是围绕极端并行计算重新设计的全栈。** 差异本质：传统 IT 跑小事务并发，AI Infra 跑数千 GPU 互联的超大规模并行。网络层（NVLink 1.8TB/s/GPU、InfiniBand）、存储层（50%+ 企业瓶颈在存储）、调度层（K8s DRA 2026.03 GA）都有 AI 专属需求。
- **推理正在吃掉训练。** 2023 年推理占 AI 算力 1/3，2025 年 1/2，2026 年将达 **2/3**（Deloitte）。Prefill-Decode 分离成为标准架构。vLLM（PagedAttention，24x 吞吐提升）是事实标准。整个 infra 重心从"如何训练更大的模型"转向"如何更便宜地服务推理请求"。
- **RoCE 正在挑战 InfiniBand。** 良好调优的 RoCE 在多数训练场景可达 IB 性能，成本节省 1.5-2.5x。这会改变数据中心网络采购决策。
- **Hyperscaler 2026 capex $660-690B 是供给约束而非需求约束。** 所有 hyperscaler 一致报告是"装不够快"而非"卖不出去"。Microsoft 有 $800 亿 Azure 订单积压因电力限制无法交付。
- **GPU 利用率是最大的脏秘密。** 75% 企业 GPU 利用率不到 70%（峰值），推理阶段低至 15-30%。Meta 2023 年低估需求 400% 多花 $8 亿，对面有企业过度配置 300% 闲置 $1.2 亿两年。容量规划是纯粹的赌博。
- **泡沫争论的最佳框架：不是"是不是泡沫"，而是"10-20 年的赌注用 2-3 年的 ROI 衡量合不合理"。** AI 支出占 GDP 0.8%，低于历史科技投资高峰 1.5%+。但 Sequoia 的 $6000 亿收入缺口和 95% GenAI 项目零 ROI（MIT）也是真的。两者不矛盾——基础设施投资和应用层回报的时间差。

### MLOps

- **MLOps → LLMOps → AgentOps 不是三个市场，是同一运维理念的三次跃迁。** 每一跳引入新的不确定性维度：确定性预测 → 概率生成 → 自主决策链。核心反转：成本从训练期主导变成推理期主导（LLM 推理成本比传统 ML 高 100x）。
- **85% ML 项目到不了生产这个数字在 Agent 时代更糟（88% PoC 失败）。** 根因一致：不是模型不行，是集成、数据、治理、组织变革跟不上。
- **Platform Engineering 正在吞噬 MLOps。** 2026 年底的终态是：一个 Platform 团队用统一 pipeline 管应用、模型、Agent。DevOps + MLOps + AgentOps 合流。Gartner 预测 2026 年 80% 软件组织有 Platform 团队。
- **FinOps for AI 从可选变成硬性要求。** 管理 AI 支出的 FinOps 从业者从 31% 跳到 63%。Plan-and-Execute 模式可节省 90% Token 成本——架构选择直接决定成本量级。
- **开源控标准，商业赢企业。** MLflow 是实验追踪事实标准但 Databricks 商业化赚钱；vLLM 是推理事实标准但各云厂商提供托管版赚钱。这个模式在每一层都在重复。

### AI Agent Dev

- **78% pilot / 14% production / 4.7 个月平均停滞——这组数字定义了 2026 年的 Agent 落地现实。** 89% 的失败不在模型层，在系统层（遗留系统集成 48%、数据质量 42%、治理缺失、变更管理 83%、ROI 不确定 42%）。
- **框架选型是不可逆决策。** 中途迁移代价 50-80% 代码重写。LangGraph 是开源默认（高天花板/陡学习曲线），Microsoft Agent Framework 是 Azure 企业标准（40% Fortune 100 已用）。CrewAI/OpenAI SDK 适合原型但天花板低。
- **MCP 和 A2A 互补不竞争。** MCP 解决 Agent↔工具（类比 USB），A2A 解决 Agent↔Agent（类比 HTTP）。MCP 已成事实标准（Claude/Gemini/OpenAI 全支持）。
- **Agent 安全的攻击面是动态推理链，不是静态基础设施。** 88% 企业出过事件，Prompt Injection 是新时代的 SQL Injection——不需要攻破网络，邮件里藏一句话就够。攻击已从 Model Layer 转到 Execution Layer。MCP 供应链攻击是全新向量（CVE-2026-26029，CVSS 8.8）。
- **Klarna 是 Agent 落地的教科书，不是成功故事也不是失败故事。** 完整展示了全生命周期：惊艳发布（230 万对话/月）→ 过度自动化 → 质量下降 → 重新引入人工 → 混合模式。真正的生产系统是 AI 处理常规量，人工处理例外。
- **Agent 任务 Horizon 正在从分钟级扩展到天级。** Anthropic 2026 报告明确预测此趋势。"Agent 是短任务执行者"的设计假设正在失效，整个基础设施需要围绕长时间自主运行重新设计。Temporal.io（$5B 估值）填补 Durable Execution 这个缺口。
- **治理前置是生存条件。** Databricks 研究：统一治理的组织 AI 项目进入生产的数量高出一个数量级；系统化评估框架的组织成功率高 6 倍。新加坡 IMDA（2026.01）是全球首个 Agentic AI 专项治理框架，EU AI Act / NIST / ISO 42001 都不是为 Agent 设计的。

---

## Open Questions

1. **Platform Engineering 吞噬 MLOps/AgentOps 的时间线是什么？** 趋势确定，但 2026 年大多数企业的 Platform 团队还不具备 ML/Agent 运维能力。过渡期怎么走？
2. **Agent 长任务（天级 Horizon）的基础设施该怎么设计？** Temporal 是目前的答案，但 Agent 的非确定性行为 + 长时间运行 = 新的可靠性挑战。故障恢复、状态一致性、成本控制都是未解问题。
3. **MCP 供应链安全怎么解？** 动态包加载绕过审批、工具投毒、命名空间碰撞——目前没有成熟方案，OWASP MCP Top 10 刚刚建立。
4. **Agent 时代的 SRE 是什么样的？** 传统 SRE 管理的是确定性系统的可靠性（SLI/SLO/Error Budget）。Agent 是非确定性系统，同一输入不同输出——怎么定义 SLO？怎么做 error budget？
5. **入门级岗位消失后的人才管道断裂问题。** 白领入门岗位发布下降 35%，Anthropic CEO 预测 5 年内 50% 消失。如果没有入门级，10 年后谁来做高级？这个结构性问题没人有答案。

---

## Concrete Artifacts

两份完整调研报告（含 60+ 引用 URL、原文摘录、交叉验证）：
- `contexts/survey_sessions/ai_infra_survey_20260328.md` — AI Infrastructure 全景
- `contexts/survey_sessions/mlops_ai_agent_dev_survey_20260330.md` — MLOps + AI Agent Dev
