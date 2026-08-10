# Career Evolution Diary Review: 22Q3 → 26Q1

> 来源：Notion Diary（407 files, 22Q3 - 26Q1）
> 整合自：insights / themes / timeline 三维分析
> 有实质内容文件约 120 篇，stub ~250，索引 ~57

---

## 身份演进主线

**应用开发者 → 平台开发者 → SRE → AI + SRE 融合体**

每次身份跳跃都伴随三阶段：密集面试准备（催化剂）→ 系统性知识重建（准备）→ 新环境快速 onboarding（执行）

最显著成长信号：从 23Q2 英文日记练习，到 26Q1 MCP 实践 + context-infrastructure 自建知识系统。三年半时间，从"学习方法的摸索"进化到"学习方法的系统化和自动化"。

---

## 逐季时间线

### 22Q3 — Intel 5G Telemetry 基础设施
- Prometheus/Grafana 持久化, dashboard 自动生成, profiling report
- Telegraf + PCM 集成, power controller operator
- 纯执行模式, 日记以 TODO/DONE 清单为主

### 23Q2 — 5G 解决方案 + 英语学习启蒙
- Metrics transfer service: 10ms 级高频采集, memory leak / goroutine thread safety, go pprof
- Power saving: CBO 基于 CPU usage/PRB/throughput 预测 CPU 调频
- ChatGPT 辅助英语学习闭环: raw writing → correction → enrichment → grammar
- 首次思考语言与思维模型关系 (Sapir-Whorf)
- 情绪：忙碌充实，偶尔空虚

> "Sometimes I feel emptiness, to the point, I should take a breath and do imaginary meditation" — diary_5_8.md

### 23Q3 — 面试准备启动 + 多线程展开
- 面试：STAR 框架, golang interview points, system design
- K8S → RedHat OpenShift (OCP) 迁移; 分布式系统基础 (2PC, ZooKeeper)
- 日语学习萌芽; 英文日记频率下降
- 有"学习停滞"的自我警觉

### 23Q4 — 低谷/反思期
- 日记频率明显下降, 记录稀疏
- "健身? 记录? 看书? 输出? 英语? 目标?" — 未给出答案
- 在思考方向但行动力不足

### 24Q1-Q2 — 平台级开发 + 投资学习启动
- Telemetry/Power controller operator 升级; E2E AI training platform 设计
- 多集群 observability 架构思考 (Thanos/Loki)
- 技术视野从应用层上升到平台层

### 24Q4 — 全面爆发期（Intel 末期）
- **Kubebuilder Operator**：AI model management (controller/CRD/MySQL/Argo Workflow)
- **BKC Agent**：Observer/Parser/Executor 三阶段流水线, Redfish/IPMI
- 面试全面化：每日 interview question, Anki 知识库, NVIDIA SRE JD 对标
- 自我定位梳理：SWE + SRE + infra developer 复合优势
- 情绪：高压但有方向感

> "如何体现工作量？把细节都讲一下，所有的细节都给他列出来" — 12_16.md

### 25Q1 — K8S 知识重建 + 离职决策
- K8S 全栈：CRI/CNI/CSI 原理, pod 启动流程, storage, network
- Golang 并发深入; Resume 重构; "Departure from Intel" 正式决定
- AI/LLM 思考启动：Cursor, "LLM 会如何冲击 SDE"
- 情绪：目标明确(SRE 转型)，学习密度全时间线最高

> "这回算是把整个cni/cri/csi 搞明白了" — 25q1_1_10.md

### DV-25Q1 — DataVisor Onboarding + AWS 学习
- AWS 全面学习：架构图, 安全组, VPC, Ansible IaC
- K8S 生产环境：pod 分析, kubectl 检查, patch operation
- Cost saving dashboard; Jenkins 迁移
- LLM + SRE 方向初探; SRE oncall 实战

### DV-25Q3 — 平台工程落地 + 个人系统化
- K8S 集群升级（生产环境）; customer insight 需求分析
- 创业方向探索："创业 - 市场"
- **"个人行为摩擦分析"** — 系统化自我管理的重要节点
- "记录琐碎，从今天做起" — 日记方法论转变

### DV-25Q4 — Customer Insight + LLM 课程 + 四维框架
- Customer insight 成为工作主线（scripts, SQL, data analysis）
- LLM class 系统学习; 面试探索（周期性出现）
- **"商业/技术/语言/自我系统"四维框架** — 思考层次提升
- "12/24 - done - 只是一个起点" — 年终心态转变

### DV-26Q1 — MCP + BigQuery + Context Infrastructure（当前）
- BigQuery 系统设计; MCP 系列 (本质/observability/cloud cost)
- K8S upgrade 工程化; 监控系列整理
- **context-infrastructure** 建立 — 个人知识基础设施物化
- 视野最开阔的时期，"构建者"模式

---

## Focus Heatmap

| 话题 | 22Q3 | 23Q2 | 23Q3 | 23Q4 | 24Q1 | 24Q4 | 25Q1 | DV-Q1 | DV-Q3 | DV-Q4 | 26Q1 |
|------|------|------|------|------|------|------|------|-------|-------|-------|------|
| Telemetry/监控 | ⬛⬛⬛ | ⬛⬛⬛ | ⬛⬛ | · | ⬛⬛ | · | · | · | · | · | ⬛⬛ |
| K8S/云原生 | · | · | 🟫 | · | ⬛⬛ | ⬛⬛⬛ | ⬛⬛⬛ | ⬛⬛⬛ | ⬛⬛ | 🟫 | ⬛⬛ |
| AI/LLM | · | 🟫 | · | · | · | · | ⬛⬛ | 🟫 | · | ⬛⬛ | ⬛⬛⬛ |
| 面试准备 | · | · | ⬛⬛ | · | 🟫 | ⬛⬛⬛ | ⬛⬛⬛ | · | · | 🟫 | 🟫 |
| 个人系统 | · | 🟫 | · | 🟫 | · | · | · | · | ⬛⬛ | ⬛⬛ | ⬛⬛⬛ |
| SRE 实战 | · | · | · | · | · | · | 🟫 | ⬛⬛ | ⬛⬛ | ⬛⬛ | ⬛⬛ |
| 英语学习 | · | ⬛⬛⬛ | ⬛⬛ | 🟫 | · | · | · | · | · | · | · |
| 投资/创业 | · | · | · | · | 🟫 | · | 🟫 | 🟫 | ⬛⬛ | 🟫 | · |

⬛ = 高活跃 | 🟫 = 中活跃 | · = 低/无

**加速话题：** AI/LLM, K8S/云原生, 个人系统化, SRE 实战, 商业/创业
**减速话题：** 5G/RAN, 英文日记写作, Power saving/CBO, 分布式系统理论

---

## 20 个主题聚类（按深度排序）

### Tier 1: 深度 5/5
1. **Telemetry/Observability** (22Q3-26Q1, 3.5年) — Prometheus/Grafana/Telegraf → Thanos/Loki → MCP-observability
2. **Kubernetes Deep Dive** (23Q3-26Q1) — 概念 → Operator 开发 → 全栈知识重建 → 生产运维
3. **AI Model Management & Power Saving** (23Q2-25Q1) — K8S Operator + Argo Workflow + CBO 节能

### Tier 2: 深度 4/5
4. **BKC Agent** (24Q4-25Q1) — Observer/Parser/Executor 三模块, Redfish/IPMI 自动化
5. **DataVisor SRE 日常** (25Q1-26Q1) — 100+ 文件, 最大主题
6. **面试准备与简历** (23Q3-26Q1) — STAR 框架, top-down 自我介绍, 周期性出现
7. **英语学习** (22Q3-24Q4) — ChatGPT 辅助闭环, 语言=思维模型
8. **AI/LLM 工作方式变革** (25Q1-26Q1) — Cursor → MCP → AI-native SRE
9. **个人反思与自我系统** (23Q2-26Q1) — 行为摩擦分析 → 四维框架 → context-infrastructure

### Tier 3: 深度 3/5
10. **AWS Cloud Infrastructure** (DV-25Q1-26Q1)
11. **CI/CD & DevOps** (24Q4-25Q1)
12. **日语学习** (23Q3-26Q1)
13. **SRE 系统性学习** (25Q1-DV-25Q1)
14. **数据系统/BigQuery** (DV-25Q4-26Q1)
15. **Intel 日常工作记录** (23Q2-24Q2)
16. **家庭与生活** (23Q2-DV-25Q3)

### Tier 4: 深度 2/5
17. **投资/金融/创业** — 多个 stub, 持续酝酿
18. **分布式系统基础** — 2PC/ZooKeeper, 已融入实践
19. **Golang** — 并发学习, 面试交叉
20. **OKR 与工作管理** — 散布各季度

---

## 原创洞察

### 1. 语言塑造思维模型，翻译式学习低效 [独特3/行动4]
> "more familiar with different language, we can thinking in different thought models" — english_learning.md

### 2. 管理期望值制造"复杂感"增加故事性 [独特4/行动4]
> "I want to control the anticipation from others, that will help me reach out much more stories" — diary_5_5.md

### 3. go pprof 定位内存泄漏的完整调试链 [独特3/行动5]
Grafana 间歇 → top 看内存 → go pprof → goroutine 堆积 → RLock 阻塞 metrics pushing。真实 SRE 排障经验。

### 4. Telegraf 高频采集的分层工程解法 [独特3/行动5]
拆实例 → 裁剪 metrics → 扩 buffer。SRE 在实际约束下的工程迭代思维。

### 5. Observer → Parser → Executor 流水线思维 [独特3/行动5]
将复杂系统拆解为观察→解析→执行三阶段。先打通链路，再连真实环境。

---

## 决策框架

1. **STAR/CAR + Top-Down** — 面试和工作汇报三层：全局 → STAR → What-How-Why
2. **"如何体现工作量"** — 把所有细节都列出来，增加工作可见性
3. **"优势即劣势"** — 将劣势重新框架为优势的变体
4. **Observer → Parser → Executor** — 自动化系统设计的通用流水线
5. **Bottom-up + Top-down 学习** — 从工作问题出发 + 从基础概念出发

---

## 矛盾与张力

| 张力 | 表现 | 频率 |
|------|------|------|
| 加班 vs 个人时间 | 认为加班有利技术成长，但同时意识到不应该 | 贯穿 23Q2 |
| 广度追求 vs 深度聚焦 | 同时学英语/日语/K8S/Go/系统设计... 反复反省停滞 | 每季度 |
| 制造复杂感 vs 实际简洁 | 技术上追求简洁，汇报上需要制造复杂感 | Intel 时期 |
| 家庭关怀 vs 个人空间 | 正常人际边界管理，有自我觉察 | 低频但深度高 |

---

## 未完成线索 & 行动项

### 高优先级
- [ ] **Observability/SRE 系列 blog** — 有真实项目经验支撑(Intel telemetry + DataVisor infra)，选题在社区仍有热度
- [ ] **LLM + SRE 定位文章** — 正在实践(context-infrastructure, MCP)，是差异化竞争力

### 中优先级
- [ ] **面试经验系统化** — 已有 STAR 框架、debug 故事、系统设计素材
- [ ] **K8S 知识体系结构化输出** — 花了大量时间但输出分散
- [ ] **"个人行为摩擦分析"模型** — 标题本身就是值得展开的自我管理工具

### 仍在酝酿
- 创业思考（多个 stub, 需补充内容后再评估）
- 投资/金融学习（与 decision book 有交叉）
- Anki 知识管理系统（context-infrastructure 已是更高级实现）

---

## 轨迹预判

### 高概率延续
1. **MCP + SRE Observability 融合** — 26Q1 已出现实践，天然互补
2. **数据基础设施方向深化** — BigQuery 已启动，结合 customer insight
3. **context-infrastructure 持续演化** — 从行为摩擦分析 → 四维框架 → 自动化闭环

### 中概率启动
4. SRE 系列 blog 落地（多次提及未完成）
5. 面试/职业跃迁（周期性出现，下一窗口 26Q2-Q3）
6. 创业方向 side project 验证

### 下一跳方向
大概率 **AI Infrastructure Engineering** — 不是纯 SRE，也不是纯 AI，而是用 AI 重塑基础设施运维方式的交叉地带。MCP 是第一个具体切入点。
