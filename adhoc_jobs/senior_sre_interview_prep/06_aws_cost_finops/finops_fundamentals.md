# FinOps 体系基础（06 方向的主要补课交付物）

> 这份材料的目标不是让瑞哥变成 FinOps 专家，是让他在面试里**听懂对方在说什么、接得上话、并且能把话题拉回自己的强项**（架构级降本 + unit economics）。
> 标注约定：`[一手]` = 他有真实场景可以锚定，答完可以往故事里引；`[理论]` = 知识层，答到机制为止，不装经历；`[⚠️ 需核对]` = 数字来自 2026-07 的调研，但源页面是动态渲染或第三方一致口径，面试前要用到小数点就自己再看一眼官方定价页。
> 所有价格默认 us-east-1、list price、2026-07 口径。

**读这份材料的正确顺序**：先读 §0（一张图看懂 FinOps 在说什么），再读 §7（组织维度）和 §8（反模式），因为那两节决定答题的框架；中间的 §1-§6 是被追问时的弹药，可以按需查。

---

## §0 一张图看懂：FinOps 到底在解决什么

云账单的本质是三层乘法：

```
账单 = Σ ( 用量 × 单价 × 时长 )
         ↑      ↑      ↑
      架构决定  折扣决定  弹性决定
```

三个因子对应三类完全不同的工作，价值也完全不同：

| 因子 | 工作类型 | 典型动作 | 天花板 | 谁在做 |
|---|---|---|---|---|
| **用量** | **架构级降本** | 改变系统结构让资源需求本身变小或归零 | 高（可以数量级） | 少数人，需要懂系统 |
| **时长** | **弹性/调度** | scale-to-zero、按需伸缩、时移到便宜时段 | 高（受负载形状限制） | 需要懂负载与 SLO |
| **单价** | **运营级降本** | RI/SP、spot、实例族现代化、存储类分层 | 有上限（折扣率封顶） | 多数 FinOps 岗位的日常 |

**瑞哥的定位就在这张表的前两行。** S01（弹性池 floor-0）动的是「时长」；S02（unit economics）和 S04（S3 请求费驱动的文件布局）动的是「用量」；他缺的是第三行的制度化运营。面试时把这张表画出来，然后说「我的经历集中在前两行，第三行是我的补课项」，这比任何包装都有力，因为**前两行本来就更难**。

FinOps Foundation 的官方框架现在是 4 个 Domain（Understand Usage & Cost / Quantify Business Value / Optimize Usage & Cost / Manage the FinOps Practice），下面挂具体 Capability；经典的 **Inform → Optimize → Operate 三阶段仍然是官方说法**，没有被替换 `[理论]`。2025-03 框架加入了 **Scopes**（Public Cloud / SaaS / Data Center，可自定义）；2026-03 进一步把 **AI** 列为独立的 Technology Category，并新增了 Executive Strategy Alignment 这个 capability，FinOps 的定义也从 "cloud value" 扩到 "technology value"（src: finops.org/framework，2026-07 核实）。FOCUS 规范当前是 **1.4** 版 `[理论] [⚠️ 需核对 ratify 日期]`。

**为什么这段值得记**：面试官如果是 FinOps 出身，一定会用 Inform/Optimize/Operate 的词汇。听到「你们在哪个阶段」，正确答法是：「我做的事情属于 Optimize，而且是 Optimize 里偏架构的那一半；Inform 层（成本可见性与归因）我们做得很薄，Operate 层（制度化）基本没有。这个顺序其实是反的，我认识到这一点是因为一次事故（见 S06 僵尸表：TB 级无主存储是被 OOM 发现的，不是被账单发现的）。」

---

## §1 成本的可见性与归因：Inform 层的工具链

### 1.1 五个工具，各管一段

| 工具 | 管什么 | 关键事实 | 费用 |
|---|---|---|---|
| **Cost Explorer** | 交互式看趋势、切维度、做预测 | 日/月粒度默认保留 **14 个月**，开 Multi-year data 可到 **38 个月**；**resource-level 粒度只留 14 天**；可预测未来 18 个月 | 控制台免费；**API 每次请求 $0.01**（跨多账户自定义 view 按 source 数量倍增） |
| **CUR / Data Exports** | 逐行明细，唯一能做深度归因的数据源 | **CUR 2.0（Data Exports）是当前主推**，legacy CUR 未正式 sunset 但无新功能；支持导出 **FOCUS 1.0 / 1.2** 格式 | 只付 S3 存储 + Athena 查询费 |
| **Budgets** | 阈值告警与自动动作 | 每账户每月 **2 个免费 action-enabled budget**；单账户上限 20,000 个 budget | 见左 |
| **Cost Anomaly Detection** | ML 检测异常花费 | 检测本身**免费**，只有 SNS 邮件超免费额度才收费 | 免费 |
| **Cost Optimization Hub** + **Compute Optimizer** | 汇总 rightsizing 与 SP 建议 | Hub 免费、只给建议不自动执行；Compute Optimizer 基础免费，默认回看 **14 天**，付费 Enhanced infrastructure metrics 把回看窗口延到 3 个月（约 $0.25/资源/月）`[⚠️ 需核对单价]` | 基本免费 |

`[理论]` 全部。这一段的正确用法不是背清单，是能回答**「你会用哪个工具做哪一步」**：

- 「这个月账单为什么涨了」→ Cost Explorer 切维度（service → usage type → 账户 → region），5 分钟能定位到大类。
- 「这 3 万美元具体是谁花的」→ 必须下到 CUR + Athena，因为 Cost Explorer 的 resource-level 只留 14 天，且它不给你 join 别的数据的能力。
- 「以后别再让它悄悄涨」→ Anomaly Detection（异常）+ Budgets（预算硬线），两个是不同用途：异常检测抓的是形状变化，预算抓的是绝对值越线。

### 1.2 Cost Explorer 到 CUR 的那道坎

面试常问「Cost Explorer 够不够用」。答法：**够用来发现，不够用来归因。**

- Cost Explorer 的维度是 AWS 预设的（service / instance type / tag / account / region / usage type）。想问「每个租户的成本是多少」「cost per query 是多少」，AWS 一个字都答不了，因为它不知道你的业务维度。
- CUR 是逐行明细（一行 = 一个资源在一个小时的一项用量），配 Glue Catalog + Athena 之后可以任意 SQL。官方给了 CloudFormation 模板自动建 Glue Database + Crawler + Lambda + S3 event notification 来保持 catalog 与新导出同步 `[理论]`。注意 Data Exports 不像 legacy CUR 那样附现成建表 SQL，得用模板或手配。
- **FOCUS** 是 FinOps Foundation 的开放成本数据规范，价值在于**跨云列名统一**（AWS/Azure/GCP 的账单字段名与语义对齐），多云环境下才有意义。单云环境提它是加分不是必需。

**锚到他的场景**：50 个 K8s 集群、6 个 region、600+ 节点，账单上看到的只有 EC2/EBS/S3/NAT 这几个大科目，**看不出哪个集群、哪个 namespace、哪个租户花的**。要下到那个粒度，路径只有两条：cost allocation tag（打到 ASG/LT 上，成本落到 EC2 实例级）+ EKS split cost allocation data（见 §3.4）。这正是他能诚实说「我们的成本归因停在账单科目层，没有下到 workload 层」的地方，而且能立刻说出补法。

### 1.3 成本分配标签（cost allocation tags）：三个必须记住的机制

`[理论]`

1. **能回溯，窗口 12 个月。** 2024-03 上线的 backfill 能力让新激活的 tag key 可以回填最多 12 个月的历史数据。但有两条限制：只能回填**标签历史上确实存在**的时段（不能凭空造标签值，也就是说资源当时没打这个 tag，回填也变不出来），且每 24 小时只能提交一次 backfill 请求，约 24 小时后反映到 Cost Explorer/CUR。
   → **这条是很多人的过时记忆**（老知识是「激活前的历史永远看不到」）。答对这条能显示知识是新的。
2. **必须显式激活才可见。** 打在资源上的 tag 默认不进账单，要在 Billing 控制台把 tag key 激活为 cost allocation tag，之后才带 `user:` 前缀出现在 CUR 里。账户级上限 **500 个** active cost allocation tag key（可通过 Service Quotas 上调），这与「单个资源最多 50 个用户自定义 tag」是两个不同配额。
3. **AWS-generated tag（`aws:` 前缀）不是万能的。** 一次性激活后组织级生效、不可编辑删除，基于 CloudTrail 尽力而为（**可能有缺口**），且不是所有 region 都生成。

**tagging 治理的真正难点不是技术，是覆盖率。** 面试如果问「怎么落地 tagging」，正确的答法有四步：
- 定**最小 tag 集**（owner / environment / cost-center / service，四个就够，多了没人填）
- 用**强制机制**而不是文档：SCP 或 IAM condition 拒绝无 tag 创建、Terraform/Ansible 模块里写死默认 tag、AWS Config rule 检测未打标资源
- 定**untagged 的兜底归属**（不能让 10% 的账单挂在「未知」上，那会让整个 showback 失去可信度）
- 把**覆盖率本身做成指标**（tagged spend / total spend），并定一个目标值
锚到他：50 集群的节点全走 ASG + Launch Template，所以 tag 的正确注入点是 **LT 的 TagSpecifications**，而不是事后给实例打标；这是他真实理解 ASG/LT 的地方能接上的话。

---

## §2 承诺折扣的完整决策模型

这一节是他的**纯外环**，但是高频必问。要点是把机制讲清楚，然后诚实说「采购决策我没参与过」。⚠️ 特别注意：`resume-expand.tex:86-88` 那条 bullet 写了 "Reserved baseline"，而 workspace 里零支撑（见 `story_bank.md` S07）。**要么补经历，要么改简历。**

### 2.1 四种定价模型的语义差异

| 模型 | 承诺什么 | 折扣量级 | 灵活性 | 中断风险 |
|---|---|---|---|---|
| **On-Demand** | 什么都不承诺 | 0 | 最高 | 无 |
| **Spot** | 什么都不承诺，但接受被回收 | 相对 OD 通常 60-90%；他的场景实测「该节点档位比 OD 低约 62%」（src: `p_elastic_compute.md:51`）`[一手]` | 高 | **2 分钟中断通知** |
| **Savings Plans** | 承诺**每小时消费额（$/hr）**，1 或 3 年 | Compute SP up to 66%，EC2 Instance SP up to 72% | 见下 | 无 |
| **Reserved Instances** | 承诺**具体的实例配置** | 与 SP 同量级 | 最低 | 无 |

**这里有一个概念区分必须说对，说错就露：** Savings Plans 承诺的是**消费金额**（$/hr），不是实例数量；RI 承诺的是**实例配置**。所以 SP 天然跟着你的实例族变化走，RI 不会。

### 2.2 SP 的四种类型与 AWS 的官方立场

`[理论]`，2026-07 核实：

| 类型 | 折扣上限 | 覆盖范围 |
|---|---|---|
| **Compute Savings Plans** | up to 66% | 最灵活：EC2 / Fargate / Lambda，任意 family、size、region、OS、tenancy |
| **EC2 Instance Savings Plans** | up to 72% | 锁定「某 region 的某 instance family」，region 内可换 size/OS |
| **SageMaker AI Savings Plans** | up to 64% | SageMaker（2024-12 随服务改名同步改名） |
| **Database Savings Plans** | up to 35%（12-35% 区间） | **2025-12 re:Invent 2025 新增**，覆盖 Aurora / RDS / DynamoDB / ElastiCache / DocumentDB / Neptune / Keyspaces / Timestream / DMS；2026-03 扩展到 OpenSearch / Neptune Analytics。仅 1 年期、No Upfront |

**AWS 官方现在明确推荐 SP 优先于 RI**，EC2 User Guide 里有一个 Important 提示框直说 "We recommend Savings Plans over Reserved Instances"（src: AWS EC2 User Guide，2026-07 核实）。这是一个很好的答题锚点：如果面试官问「RI 和 SP 怎么选」，先说 AWS 自己的立场是 SP 优先，再说 RI 剩下的两个真实理由。

**RI 现在还剩什么价值**：
- **RI Marketplace 转售能力**（SP 没有）：只能卖 Standard RI，Convertible 不可上架，AWS 收 12% 服务费，需上架满 30 天、剩余期限 ≥1 个月，单账户终身上限 $50,000 或 5,000 个 RI。也就是说 Standard RI 是唯一有二级市场退出通道的承诺。
- **容量预留**（zonal RI 才有 capacity reservation 语义，regional RI 和 SP 都没有）。这条在容量紧张的实例族上是真需求。
- Standard vs Convertible：Standard 不可交换（只能 modify 数量/AZ/network platform/scope），折扣更高；Convertible 可交换 family/type/platform/scope/tenancy，但**不能跨 region**，且新 RI 总价值须 ≥ 旧 RI（不够则自动增加数量补足）、No Upfront → Upfront 方向可换反向不可、须剩余 ≥24 小时。exchange 本身免费，只补差价。`[⚠️ 需核对]` Standard vs Convertible 的精确折扣百分比官方只有定性表述，没有公开对比数字，**面试别报具体百分比差**。

### 2.3 两个核心指标：coverage 与 utilization（一定要分清）

`[理论]`，这是承诺折扣管理的全部要害：

- **Coverage（覆盖率）** = 被承诺折扣覆盖的用量 / 总用量。**低了 = 钱没省够**（还在付 On-Demand 价）。
- **Utilization（利用率）** = 承诺被用掉的比例。**低了 = 买多了，在付没用的承诺**（这是纯损失，比不买还糟）。

两个指标是**反向拉扯**的：追 coverage 会买多导致 utilization 掉，追 utilization 会买少导致 coverage 掉。健康做法是**只对确定的 baseline 做承诺，波动部分留给 On-Demand 和 spot**，并且给 coverage 定一个刻意小于 100% 的目标（常见做法是覆盖到「历史最低谷用量」而不是「平均用量」）。

**这一段是他最该练熟的话，因为它直接连到他的强项**，见 §2.4。

### 2.4 为什么弹性架构会改变承诺策略（这是他的加分点，必须讲）

这是把外环知识和内核经历焊在一起的接缝，也是面试里最能拉分的一段：

**承诺折扣的前提是「用量可预测且不会消失」。而弹性架构的目的恰恰是让用量消失。** 这两件事有一个直接的互动关系，绝大多数只做运营降本的候选人讲不出来：

1. **scale-to-zero 让 baseline 变小，可承诺的部分就变小。** 他的 heavy 池从「静态 2 节点常驻」变成「平均每天 2 台跑 2 小时」（src: `p_elastic_compute.md:17`）`[一手]`。原来这 2 台是完美的 SP/RI 候选（7×24 稳定用量），现在它们变成了尖峰，**买承诺反而会 utilization 崩掉**。也就是说：**先做架构级降本，再定承诺策略；顺序反了会买一堆用不掉的承诺。** 这个顺序问题是本节最值钱的一句话。
2. **承诺应该覆盖真正的 baseline，也就是那个永远不上 spot 的部分。** 他的 serving 池是 on-demand 常驻、永远不上 spot（一次回收等于查询中断加缓存清空，src: `p_elastic_compute.md:51`）`[一手]`。**那个池子才是 SP 的正确目标**。同理 StarRocks 那边的 `query_wh` 是 on-demand always-on（src: `interview-6-starrocks-lakehouse.md:157`）`[一手]`，`refresh_wh` / `adhoc_wh` 是 spot，不该被承诺覆盖。
   → 讲法：「我把算力按风险容忍度分了池之后，承诺策略其实自然就清楚了：不能中断的池子用 SP 覆盖，能中断的池子用 spot，中间的波动留 On-Demand。分池这个动作同时解决了可靠性隔离和定价模型匹配两个问题。」
3. **spot 和承诺折扣不冲突但会互相吃份额。** SP 覆盖不到 spot（spot 本来就已经打折）。所以提高 spot 占比会**降低 SP 的可覆盖基数**，如果 SP 已经买了，spot 化会把 utilization 拉低。**这是一个真实的组织冲突**：FinOps 团队刚买了 3 年 SP，平台团队接着把负载 spot 化，两边都在「优化成本」，结果是浪费。答这道题能显示他懂组织维度。
4. **弹性有一个翻转点。** 负载变密到某个程度，弹性的收益（省闲置）会小于代价（冷启动 + 反复伸缩），常驻加承诺反而更便宜。这个翻转点应该被算出来当触发条件，而不是等账单异常了才发现（这句话在 `story_bank.md` S02 的 L5 里也用了，两处一致）。

### 2.5 期限与业务确定性的匹配

`[理论]` 简单但必答：

| 业务确定性 | 建议 |
|---|---|
| 3 年内一定还在跑（核心 serving 层） | 3 年 SP，折扣最深 |
| 1 年内确定、之后可能架构变化 | 1 年 SP |
| 正在迁移/重构中 | **不要承诺**，或只用 Compute SP（跨 family/region 灵活） |
| 明确要下线 | 一分钱都不承诺 |

**锚到他**：CH → Doris 迁移期间恰好是最不该做长期承诺的时候，因为实例族、节点数、region 分布全在变。如果那期间有人买了 EC2 Instance SP 锁定了旧 family，迁移完就是纯损失。这是他能用自己经历说明「架构变更期与承诺期限的冲突」的现成例子。

---

## §3 计算成本优化谱系

### 3.1 rightsizing 方法论：为什么只看 CPU 会犯错

`[理论] + [一手锚点]`

rightsizing 的正确判据是**多维 + 看分布不看均值 + 看约束不看用量**：

1. **CPU 均值是最容易误导的指标。** 均值 15% 可能是「一天两次跑到 100%、其余时间空转」，降配会直接砍掉峰值能力。至少要看 p95/p99，并且看**峰值的持续时间**（尖刺 30 秒和持续 2 小时是两回事）。
2. **内存往往是真正的约束。** CloudWatch 默认不采集 EC2 内存，需要 CloudWatch Agent 或自建监控。**这条对他非常有利**：他有 VictoriaMetrics 覆盖 600+ 节点、约 1.2M active series（src: `p_vm_platform.md:25`）`[一手]`，也就是说他手上本来就有做 rightsizing 所需的数据底座，缺的只是「把它接到成本维度上」这一步。这是一个很强的可信补课叙事。
3. **网络与磁盘的实例级上限经常先撞。** 小实例的 EBS 带宽和网络带宽 baseline 很低且可 burst，一旦把 burst credit 用完就掉到 baseline，表现是「CPU 很闲但是慢」。
4. **有硬约束的负载不能按利用率降配。** 最好的例子就在他手上：Doris BE 请求 `cpu=8` 跑在 8 vCPU 节点上，因为 kube-reserved 之后 allocatable 只有约 7.9，调度模拟永远报 Insufficient cpu，改成 `cpu=7` 才能扩起来（src: `p_elastic_compute.md:45`）`[一手]`。这个坑反过来讲就是 rightsizing 的一条规则：**request 必须严格小于节点 vCPU**，而这条规则和「把 request 压到贴近实际用量」是两个不同的优化方向，可能冲突。
5. **Compute Optimizer 的建议要当输入不当结论。** 它默认只回看 14 天，看不到月度或季度周期性负载（他的场景里有「月度累计窗口查询」这种月末才跑的形状，src: `p_elastic_compute.md:15`）。付费 Enhanced infrastructure metrics 把窗口延到 3 个月才勉强覆盖。

**答题骨架（被问「你怎么做 rightsizing」）**：先问这个 workload 的约束是什么（内存/CPU/IO/延迟 SLO），再看 p95 而不是均值，再看有没有周期性（回看窗口要覆盖最长周期），再小步调整并观察一个完整周期，最后把结论写回 IaC 而不是手改。

### 3.2 实例族现代化与 Graviton

`[理论]`，2026-07 核实：

- **代次现代化本身就是降本**：同规格的新代次单价通常更低、性能更好。这是最低风险的一类动作（改 Launch Template 的实例类型 + 滚动替换）。
- **Graviton 现状**：最新一代是 **Graviton5**（2025-12 re:Invent 预览，约 2026-06 GA，首发 M9g/M9gd，region 有限）`[⚠️ 需核对：C9g/R9g 是否已 GA 未确认]`。官方声称 Graviton5 对比 Graviton4 计算性能 up to 25% 提升（web 应用最高 35%、ML 推理最高 35%、数据库最高 30%）；家族级通用声明是「比同规格 x86 便宜 up to 20%、能耗低 up to 60%」。托管服务支持已经很广（Aurora/RDS/DocumentDB/Neptune/MemoryDB/ElastiCache/Redshift/OpenSearch/EMR/MSK/Lambda/Fargate/EKS/ECS/SageMaker 等）。
- **迁移摩擦点（面试爱问，四条）** `[第三方共识]`：
  1. **x86-only 容器基础镜像**直接阻塞启动 → 需要 multi-arch 镜像（`docker buildx` + manifest list）。
  2. **SIMD 指令集**：AVX / AVX-512 在 ARM 上没有等价物，需要移植到 NEON。数据库和压缩/编解码这类库最容易踩。
  3. **一个 x86-only 的 sidecar 或 DaemonSet 能阻止整个集群上 Graviton**（监控 agent、安全 agent 最常见）。这条在 50 集群的环境里特别现实：迁移的实际阻塞点往往不是主应用。
  4. **Graviton 1 vCPU = 1 物理核（无 SMT）**，而 x86 典型是 2 vCPU/核，所以「同 vCPU 数」不等于「同算力」，容量规划的换算关系会变。

**锚到他**：`[一手]` 他有一个真实的 arm64 相关经历但**不是云成本**，要分清：Doris FE 从 QEMU 模拟 amd64 编译换成原生 arm64 编译，build 从 43:55 压到约 3 分钟，镜像从 747MB 压到 43MB（src: `p_engine_routing.md:42`）。这是**开发效率**不是云账单。可以拿来证明「我处理过跨架构构建的实际问题」，但不能说成「我做过 Graviton 成本迁移」。诚实的说法：「跨架构的构建和镜像我踩过，但 Graviton 的生产迁移我没做过。」

### 3.3 Spot 的适用边界与中断成本

`[一手]` 这是他最强的一段，因为他有两个真实场景（Doris heavy 池、StarRocks refresh/adhoc warehouse）和一条明确的硬约束（on-demand 与 spot 不可混）。

**判据（四问）**：
1. **中断的代价是什么？** 可重跑的批任务（MV 刷新）代价接近零；用户面在线查询代价是 SLA 违约。他的原话：on-demand 与 spot 不可混，spot 回收等于 in-flight query 失败，用户面流量必须钉在 on-demand（src: `interview-6-starrocks-lakehouse.md:157`）。
2. **中断能不能在 2 分钟窗口内善后？** 他算过这笔时间账：FE 心跳约 2 秒检测失联，锁约 7 秒释放，失败查询重试一次，全部落在 spot 的 2 分钟回收窗口内（src: `p_elastic_compute.md:51`）。
3. **有没有状态被绑在节点上？** 存算分离让 BE 无本地数据，杀 spot 安全、不需要 DECOMMISSION（src: `resume_highlights_doris_dcluster.md` §1）。这是「能不能用 spot」的结构性前提。
4. **中断后的重做成本有多大？** 一条 60-500 秒的重查询中途被回收，浪费已完成的工作加约 3-4 分钟重新扩容（src: `p_elastic_compute.md:51`）。所以决策是先 on-demand、装好 node-termination handler 再切 spot 优先混合 ASG。

**理论侧要补的机制** `[理论]`：
- **中断通知只有 2 分钟**（EC2 metadata `/latest/meta-data/spot/instance-action`）；**Rebalance Recommendation** 更早发出但不保证一定会中断。
- **分配策略**：`capacity-optimized` 优先选中断率低的容量池，`lowest-price` 会追最低价但中断率高，`price-capacity-optimized` 是两者的平衡（现在的一般推荐）。
- **实例多样化是 spot 的核心可用性手段**：一个 ASG 里放多个实例族/多个 AZ，池子越多越不容易同时拿不到容量。**「spot 拿不到容量」这个风险的正确答法是多样化 + on-demand 兜底，不是重试。**
- Node termination handler（K8s 上是 aws-node-termination-handler 或 EKS 托管的 capacity rebalance）负责收到通知后 cordon + drain。
- ⚠️ **归属边界**：dcluster 里 spot 中断回退的实现不是他做的（src: `resume_highlights_doris_dcluster.md` §0）。上面这些机制他答理论，不说做过实现。

### 3.4 容器 bin-packing 与资源碎片（600+ 节点 50 集群，这是他最具体的话题）

`[一手场景 + 理论方法]` 这一节要花力气，因为它是他的规模优势能直接变成成本论点的地方。

**问题的本质：K8s 上你付的是节点的钱，但分配的是 request 的量。** 三者关系是：

```
节点成本  ≥  Σ requests  ≥  Σ actual usage
          ↑                ↑
      调度碎片          request 虚高
```

两个 gap 是两类完全不同的浪费，必须分开治：

| gap | 名字 | 根因 | 治法 |
|---|---|---|---|
| 节点容量 − Σrequests | **调度碎片（bin-packing loss）** | pod 尺寸与节点尺寸不匹配、反亲和/拓扑约束、DaemonSet 占位、kube-reserved | 节点规格与 pod 尺寸匹配、consolidation（Karpenter 类）、减少不必要的约束 |
| Σrequests − Σusage | **request 虚高** | 开发按「不 OOM 就行」拍数、复制粘贴、没人回头改 | VPA 建议值、历史 p95 驱动的定期修正、把 request 写进 IaC 而不是手改 |

**bin-packing 的具体反例，他手上就有一个教科书级的**：BE 请求 `cpu=8` 跑在 8 vCPU 节点上，kube-reserved 之后 allocatable 只有约 7.9，于是永远调度不上，且**没有任何事件指向那 0.1 核的差距**（src: `p_elastic_compute.md:45`）`[一手]`。这个坑的成本含义是：**如果当时的处理方式是「加大节点规格」而不是「把 request 降到 7」，就会为 0.1 核付一整档实例的钱。** 这是「碎片导致过度供给」的最小可复现例子，讲出来非常有说服力。

**requests / limits 的成本语义（必须说对）** `[理论]`：
- **CPU request 决定调度和保底份额，limit 决定节流（throttling）。** CPU 是可压缩资源，超了被 throttle 不被杀。
- **内存 request 决定调度，limit 决定 OOMKill。** 内存不可压缩，所以 memory limit 设低了是可靠性事故，不是性能问题。
- **QoS class 直接影响驱逐顺序**：Guaranteed（request == limit，所有容器都设）> Burstable > BestEffort。**成本与可靠性在这里正面冲突**：Guaranteed 最稳但最浪费（request 必须按峰值设），BestEffort 最省但最先被驱逐。
- 所以「把 request 全压到实际用量」是错的：**关键路径应该 Guaranteed 并接受浪费，批任务和可重跑负载才适合 Burstable/BestEffort**。这个答法和他 spot 分池的判据是同一个思路（按风险容忍度分级），能形成体系感。

**K8s 成本可见性的工具与语义** `[理论]`，2026-07 核实：
- **OpenCost** 是 CNCF 项目，2022-06 进 Sandbox、2024-10 晋升 **Incubating**（截至 2026-07 仍是 Incubating，未 Graduated）。
- **Kubecost 被 IBM 在 2024-09 收购**，商业版现在叫 IBM Kubecost；OpenCost 继续作为开源引擎。⚠️ **他的环境里确实部署了 Kubecost**（有 `kubecost-*.dv-api.com` 的痕迹，同一份记录里列了 29 个集群，src: `periodic_jobs/cross_workspace_daily/extracted/2026-04-27/...`），但**没有证据说他用过或维护过**。面试问到「你们有没有 K8s 成本工具」，诚实答法是「公司环境里有 Kubecost，但我没有深入用过它做决策」，并且这条要列进 S07 的提问清单去跟他确认。
- **AWS EKS Split Cost Allocation Data**（2024-04 GA）：把 CUR 里粗粒度的 EC2 实例成本，按每个容器/pod 实际消耗的 CPU/内存比例，拆到 pod / namespace / workload 级别，自动生成 `aws:eks:cluster-name` / `namespace` / `deployment` / `workload-type` 等 tag；2025-09 扩展支持 GPU/Trainium/Inferentia，2025-10 支持导入最多 50 个自定义 K8s label 作为 cost allocation tag。
  → ⚠️ **一个必须自己知道的边界**：他们的集群是 **kubeadm 自建控制面，不是 EKS**（src: `07_aws_fundamentals/README.md:5`）。所以 EKS split cost allocation data **对他们不可用**，只能走 OpenCost 这条路。这个细节答出来是加分的，因为它证明他知道自己环境的约束，而不是背了个 AWS feature 就往上套。
- **分摊语义**：OpenCost 规范采用 `Workload Cost = max(request, usage)`，故意让「预留但没用」的容量仍然算在申请方头上，倒逼合理 sizing；`Cluster Idle Cost = 集群总资产成本 − Σ(各 workload 成本)`。**这个 max() 的设计哲学值得讲**：requests-based 分摊反映「你从调度器占了多少」（适合 chargeback，因为你占了别人就不能用），usage-based 反映「你实际烧了多少」（更「公平」但会让闲置预留免费）。max() 是偏 requests 的折中。

**idle cost 是 K8s 成本治理的核心指标。** 如果集群 idle cost 占 40%，那么再怎么给 workload 做 rightsizing 都是在优化那 60%。正确顺序是先压 idle（节点规格匹配、consolidation、把 baseline 节点数降下来），再做 workload rightsizing。

### 3.5 Autoscaling 的成本效应（三层要分清）

`[一手] + [理论]`

| 层 | 组件 | 成本效应 | 他的一手细节 |
|---|---|---|---|
| Pod 数 | HPA | 减少 Σrequests，但只有配合节点伸缩才真的省钱 | 他有一段现成的论证：**为什么不用 HPA**（CN 冷启动 3-5 分钟，reactive 追不上秒级期望；HPA 只看 CPU/mem，识别不了「无 MV 命中的 ad-hoc 重查询」这种业务语义）（src: `interview-6-starrocks-lakehouse.md:160`）`[一手]` |
| Pod 尺寸 | VPA | 治 request 虚高 | 无一手 |
| 节点数 | Cluster Autoscaler / Karpenter | 真正省钱的那一层 | CA 从字面 0 节点扩容依赖 ASG 的 node-template label/taint tag 构造虚拟节点，缺 tag 就静默 Pending 且报错不提 tag（src: `p_elastic_compute.md:45`）`[一手]` |

**必答的一条**：**HPA 省钱是间接的**。缩了 pod 但节点还在，账单一分不少。所以「autoscaling 降本」这句话只有在 pod 层和节点层联动时才成立，而联动的瓶颈通常是节点层的时间尺度（分钟级）。他的原话可以直接搬：执行有 3-4 分钟延迟的系统，必须对**持续**压力反应，别以快于生效速度堆叠修正（src: `resume_highlights_doris_dcluster.md` §2.2）。

**Karpenter vs Cluster Autoscaler 的成本差异** `[理论]`：CA 只能在预定义的 ASG/node group 里增减节点数，实例规格是人事先选好的；Karpenter 直接按待调度 pod 的形状选实例类型并起节点，还能做 consolidation（把稀疏分布的 pod 重新打包到更少/更便宜的节点上）。所以 Karpenter 在**碎片治理**上结构性地更强。诚实边界：他们用的是 CA + ASG + Launch Template，**没有用 Karpenter**，所以这条答理论 + 说清「我们为什么没上：控制面自建、节点走 Packer + Ansible + kubeadm 的镜像流水线，Karpenter 的动态起节点模型和这套 AMI 流水线需要一次不小的改造」。

---

## §4 存储成本优化

### 4.1 EBS

`[理论] + [一手锚点]`

- **gp3 vs gp2 是最没争议的降本动作**：gp3 **$0.08/GB-月** vs gp2 **$0.10/GB-月**（官方称 up to 20% lower per GiB），而且 gp3 把 IOPS/吞吐与容量**解耦**：免费包含 3,000 IOPS / 125 MiB/s 不随容量走，最大可配到 80,000 IOPS / 2,000 MB/s，超出部分约 $0.005/provisioned IOPS-月、$0.04/provisioned MB/s-月 `[⚠️ 需核对超额单价]`。
  → gp2 时代常见的反模式是「为了拿 IOPS 而买大容量盘」（gp2 是 3 IOPS/GB），gp3 让这个动作变成纯浪费。**所以 gp2→gp3 的收益不只是单价差 20%，还包括「可以把为 IOPS 买的多余容量砍掉」。** 这一层才是这道题的满分答案。
- ⚠️ **他没做过 gp2→gp3 迁移**（workspace 零证据，`resume-expand.tex` 那条 bullet 也没提这个）。他有的是「PVC 在线扩容对 gp2/gp3 StorageClass 是支持的」这类运维事实。答法：机制答透，然后说「卷类型迁移这件事我们生产上没做过，如果做我会先按 IOPS 需求核算，因为 gp2 上很多容量是为 IOPS 买的」。
- **io2 Block Express** 定位大型关键数据库（Oracle / SAP HANA / SQL Server），最大 256,000 IOPS/卷、4,000 MB/s、64 TiB，耐久性 99.999%（比 gp3/标准 io2 的 99.8-99.9% 高约 100 倍）。他的场景用不到，知道定位就行。
- **快照计费是严格增量的**：只存自上次快照以来变化的 block。但有一条反直觉的重要事实：**删除某个快照未必降低存储成本**，因为其他快照可能仍引用同一批 block。这条是面试里很好的区分度问题。
- **Snapshot Archive tier**：$0.0125/GB-月（vs 标准层 $0.05/GB-月），restore 一次性 $0.03/GB，**最短存储 90 天**，提前永久 restore 或删除会按剩余天数补收早删费（临时 restore 不触发）。
- **典型僵尸存储清单**：未挂载的卷（`state=available`）、终止实例遗留的卷（`DeleteOnTermination=false`）、没有生命周期策略的老快照、废弃 AMI 背后的快照。⚠️ 他**没有做过云资源侧的僵尸盘点**；他做过的是数据层的 ClickHouse 僵尸表清理（TB 级，src: `w_zombie_oom.md`，见 `story_bank.md` S06）。这个区分要说清楚，但 S06 恰好能证明他懂「在增长但没有访问者」这个判据。

### 4.2 S3 存储类与生命周期

`[理论]`，2026-07 核实的完整列表与关键约束：

| 存储类 | 最短存储时长 | 定位 |
|---|---|---|
| Standard | 无 | 频繁访问 |
| Intelligent-Tiering | 无 | 访问模式未知/变化 |
| Express One Zone | **1 小时** | 单 AZ 超低延迟（2023 re:Invent 新增） |
| Standard-IA | 30 天 | 不频繁访问，多 AZ |
| One Zone-IA | 30 天 | 不频繁访问，可再生数据 |
| Glacier Instant Retrieval | 90 天 | 归档但要毫秒取回 |
| Glacier Flexible Retrieval | 90 天 | 归档，分钟到小时取回 |
| Glacier Deep Archive | 180 天 | 最冷，小时级取回 |

（Reduced Redundancy Storage 已从官方存储类页面移除，只作遗留兼容。）

**三条容易答错的要点**：
1. **最短存储时长是真实的成本陷阱。** 对象存进 Glacier Deep Archive 后 30 天删掉，仍然按 180 天计费。所以生命周期策略的转换时间点必须比最短时长留余量，否则「省钱」变成「多付」。
2. **取回费 + 请求费经常反超存储费省下的钱。** 冷存储类的单价低，但取回要付 retrieval fee，且请求单价更高。判据是**访问频率**：一份数据如果一个月被完整读一遍，放 IA 大概率比放 Standard 贵。
3. **Intelligent-Tiering 的适用条件有硬门槛**：监控费约 **$0.0025/1000 对象/月** `[⚠️ 需核对官方定价页]`，且**只对 ≥128KB 的对象生效**（小于此不监控、不移层、也不收监控费，始终按 Standard 费率）。
   → **所以小文件多的场景用 Intelligent-Tiering 是无效的**，这条正好接他的一手场景：Iceberg 小文件治理前是 619 个文件（治理后 49），生产 fact 表积累到 130K+ data files（src: `interview-6-starrocks-lakehouse.md:53`、`:171`）`[一手]`。对象数多而单个对象小的时候，监控费本身就是一笔钱，而且大部分对象根本不会被移层。

### 4.3 S3 请求费与小文件问题（他的最强一手场景，务必讲）

`[一手]` 这是本节的重点，因为他有一个完整的、profile 驱动的真实案例。

**当前单价（us-east-1、Standard）**：**GET/SELECT $0.0004/1000 请求**；**PUT/COPY/POST/LIST $0.005/1000 请求**。注意 **PUT 比 GET 贵约 12.5 倍**，这直接决定了「写侧文件数」比「读侧请求数」更值钱的治理优先级。

**为什么这条对存算分离架构是核心成本科目**：存算分离把「读数据」从「本地磁盘 IO（免费）」变成了「S3 GET（按次计费）」。也就是说**架构决定了成本的计费维度**。他有两条一手证据链：

1. **Iceberg 链：profile 出 99% 时间在 OpenFile，从「S3 按请求次数计费」这个模型推导出所有动作**，把文件数 619 降到 49，FSIOTime 7.9s → 63ms（125×），冷查询 7.5s → 744ms（src: `interview-6-starrocks-lakehouse.md:53`、`:70`）。手段是 `BATCH_SIZE` 50K→500K、`target-file-size` 512MB→1GB、`commit.interval` 60s→10min。
2. **Doris 链：实测出冷读的瓶颈是 GET 延迟 × GET 数量，不是带宽**（冷读聚合吞吐只有约 1MB/s，NIC 带宽用不到 1%）；一次未剪枝的点查要探遍 566 个 tablet / 6689 个 segment（src: `doris_wide_table_point_query_optimization_survey_20260724.md:12`、`:74`）。

**一个可以在白板上现算的示意算术**（标明是示意，不是他们的账单）：一次未剪枝点查约 6689 次 GET → 单次查询请求费约 `6689/1000 × $0.0004 ≈ $0.0027`。如果这类冷查询每月 100 万次，仅请求费约 **$2,675/月**，而传输的字节数少到 NIC 带宽用不到 1%。**这就是「小文件 + 高扇出」在账单上的样子：花的是请求费，不是带宽费。** 这个算术把他的性能发现直接翻译成了美元，是本方向最有说服力的一段。

**S3 请求费的治理杠杆（按优先级）**：
1. **减少要打开的文件数**（写侧治本：更大的 target file size、更长的 commit interval、更大的写批）。这是他做过的。
2. **减少要扫的分区**（分区剪枝。他的 Doris 场景里 `proc_date` 注入是最大杠杆且零成本，src: 同上 `:169`）。
3. **本地缓存**（消掉重复 GET。他的场景 8×1.3TB nvme file_cache 聚合 10.4TB > 4TB 表，整表装得下，src: 同上 `:35`）。
4. **但缓存治不了扇出**：暖查询全命中缓存仍然 1.12s（src: 同上 `:63`）。所以顺序必须是先减文件数和分区，再买缓存。反过来做就是花了钱指标不动。
5. **别忘了 LIST 也收费且和 PUT 同价**（$0.005/1000）。对象数极多的 prefix 上频繁 LIST 是隐形成本，Iceberg/Hudi 这类表格式的 metadata 层就是为了避免全量 LIST 而存在的。

---

## §5 网络成本的隐形陷阱（面试高频，且他简历上写了 cross-AZ）

`[理论]` 全部。⚠️ **重要**：`resume-expand.tex:89` 写了 "reducing unnecessary cross-AZ data transfer"，workspace 零支撑（见 `story_bank.md` S07）。这一节要练熟机制，同时准备好「这条我要么补经历要么改简历」的处理。

### 5.1 四个主要科目与当前单价

| 科目 | 单价（us-east-1） | 说明 |
|---|---|---|
| **NAT Gateway** | **$0.045/小时 + $0.045/GB 处理费** `[⚠️ 需核对]` | 处理费是按流量收的，**经 NAT 去互联网还要再叠加出网流量费**（双重收费） |
| **跨 AZ 流量（同 region）** | **$0.01/GB 单向，即往返 $0.02/GB** | ⚠️ **没有变成免费**。唯一的官方免费化是 **2022-04-01** 生效的 PrivateLink / Transit Gateway / Client VPN 跨 AZ 免费，**不含**普通 EC2-EC2 流量和 NLB 跨区流量 |
| **互联网出网（egress）** | 每月**前 100GB 免费**（永久，2021-12-01 起，非新用户限定），超出约 $0.09/GB（下 10TB）、$0.085（下 40TB）、$0.07（下 100TB）、$0.05（150TB+）`[⚠️ 需核对尾部单价]` | CloudFront 免费额度 1TB/月 |
| **跨 region 传输** | 按 region 对定价，通常显著高于跨 AZ | 多 region 架构的隐形大头 |

**一个必须记住的修正**：100GB/月免费出网额度是 **2021-12** 生效的，不是 2024 年。这类记忆点说错年份不致命，但说成「AWS 最近才免费」会显得知识不扎实。

### 5.2 VPC Endpoint 与「省 NAT」的算法

`[理论]`

- **Gateway Endpoint（只有 S3 和 DynamoDB）完全免费**：无小时费、无 GB 费。
- **Interface Endpoint（PrivateLink）**：**$0.01/小时/ENI/AZ + $0.01/GB**（首 1PB，阶梯递减）。
- **S3 Gateway Endpoint 的盈亏平衡计算：没有盈亏平衡点。** 走 NAT 处理 S3 流量是 $0.045/GB，走 Gateway Endpoint 是 $0/GB + $0/小时，**任何非零流量都是 Gateway Endpoint 更省**。唯一不用它的理由是场景不支持（比如跨 VPC 经 Transit Gateway 且没共享 endpoint）。
  → **这道题的满分答案就是「这题不需要算」**，然后立刻转到 Interface Endpoint 才需要算：Interface Endpoint 有小时费（每 AZ 一个 ENI），所以低流量服务上它可能比走 NAT 更贵，平衡点是 `月流量 × ($0.045 − $0.01) vs ENI 数 × 720h × $0.01`。
- **锚到他的场景**：Doris 存算分离让 BE 持续读写 S3，如果这些流量走 NAT，那就是 $0.045/GB 的处理费叠加在一个本来就请求密集的访问形态上。**「存算分离必须配 S3 Gateway Endpoint」是一条应该写进部署 checklist 的规则**，这是他能从自己架构推出来的具体结论，不是背的。诚实边界：他们当前有没有配，evidence 里没写（`interview-8-k8s-cluster-build.md` 只提到 NAT Gateway 是手动预建放 public subnet），**这条列进 S07 提问清单**。

### 5.3 为什么多 AZ 高可用会带来跨 AZ 流量成本，怎么权衡

`[理论]` 这是本节最好的一道题，因为它是成本与可靠性的正面冲突，答得好能显示他懂权衡不是只会省钱。

**冲突的机制**：
- 高可用要求副本跨 AZ 分布（一个 AZ 挂了还能服务）。
- 但**每一次跨 AZ 的数据流动都收 $0.01/GB 单向**。
- 于是三类流量天然产生跨 AZ 费：**副本同步**（数据库、Kafka ISR 复制）、**负载均衡转发**（LB 在 AZ-A，后端 pod 在 AZ-B）、**服务间调用**（微服务随机打到别的 AZ）。

**权衡框架（四步，可以直接背成答题结构）**：
1. **先分类：这份跨 AZ 流量是为了「可用性」还是「随机调度的副产品」？** 副本同步的跨 AZ 是在买可用性，该付；服务间调用随机跨 AZ 大多是纯浪费，可以治。
2. **治「副产品」那部分，不动「买可用性」那部分。** 手段：K8s 的 **Topology Aware Routing**（`service.kubernetes.io/topology-mode: Auto`，让 Service 优先转发到同 AZ 的 endpoint）、LB 关掉 cross-zone load balancing（注意：NLB 默认关、ALB 默认开且 ALB 的跨 AZ 免费，这个差异要说对）、把有 affinity 的服务组按 AZ 编排。
3. **算出「为可用性付的跨 AZ 费」到底是多少，然后跟可用性收益对话。** 这一步才是 senior 的做法：不是「跨 AZ 太贵所以单 AZ」，是「跨 AZ 副本每月 $X，一次 AZ 级故障的业务损失是 $Y，X 远小于 Y 所以这笔钱该花」。
4. **只有在明确可再生/可重建的数据上才考虑单 AZ**（One Zone-IA、单 AZ 的缓存层、可重跑的批处理中间产物）。

**锚到他**：6 个 region、50 集群、多租户 SaaS，副本跨 AZ 是硬要求。他真实的可用性设计里有一个现成例子可以配着讲：serving 池永远不上 spot（一次回收等于查询中断加缓存清空，src: `p_elastic_compute.md:51`）。**同一个逻辑**：可靠性关键路径上不做省钱动作，省钱动作只做在可容忍的部分。跨 AZ 和 spot 是同一个判断的两次应用。

### 5.4 一个常被忽略的科目：数据传输的「上游」

`[理论]` 简短但加分：**入网（ingress）到 AWS 基本免费，出网才贵。** 所以架构上「数据往哪个方向流」直接决定成本。典型误区是把处理放在云外、数据在云内，导致每次处理都要出网。正确原则是**把计算搬到数据旁边，而不是把数据搬到计算旁边**。这条和他的存算分离场景有一个有趣的对照：存算分离把计算和存储拆开了，但拆的是「同 region 内的 EC2 与 S3」，S3 到同 region EC2 的流量不收出网费，所以架构成立；如果 S3 在另一个 region，这套架构的账立刻崩。

---

## §6 可观测性自身的成本

`[一手]` 他有 1.2M active series / 80K samples/s / 600+ 节点的一手场景（src: `p_vm_platform.md:25`），这一节是他能讲得比大多数候选人深的地方。详细故事见 `story_bank.md` S08，这里只列体系。

### 6.1 指标成本的三个驱动因子

**成本 ≈ active series 数 × 保留时长 × 每 sample 的存储成本**，其中 active series 数是**乘法爆炸**的那一项：

```
series 数 = Σ (每个 metric 的 label 组合基数)
```

- 加一个 label 不是加法而是乘法。**加 tenant label 是最典型的爆炸源**（节点级指标乘租户数），这也是他的治理第一条就是「基础设施指标一律不带 tenant label」（src: `p_vm_platform.md:62`）`[一手]`。
- **高基数 label 的典型祸首**：user_id、request_id、query hash、pod name（每次重启换名）、完整 URL path。判据是「这个 label 的取值集合会不会随流量增长」。
- **治法四条（他做过的）**：核心 SLI 才做 tenant-level recording rules；基础设施指标不带 tenant；retention 分层（tenant SLA 90 天 / 排障 30 天 / 基础设施 15 天）；定期 cardinality 审查。
- **最值钱的一条是他自己的复盘**：cardinality budget 应该在第一天就存在，而不是等增长曲线逼出来（src: 同上 `:62`）`[一手]`。这句话的普适版本是：**成本护栏必须在系统上线前定，事后治理永远是被动的。**

### 6.2 存储引擎选择本身就是成本决策

`[一手]` 同一个 3 个月窗口，federation 下的 Prometheus 要约 930GB，VictoriaMetrics 约 250GB（约 4× 压缩）；冷数据 5 分钟降采样放 S3，180 天只要约 25GB（src: `p_vm_platform.md:25`）。

**这段的讲法要点**：省下来的 680GB 不是靠砍数据，是靠换引擎 + 降采样分层。**「降采样而不是删除」是可观测性成本治理里最重要的一个手段**，因为它把「保留时长」和「分辨率」解耦了：长周期趋势不需要秒级，短周期排障不需要 180 天，危险的是用同一份数据同一个 retention 去满足这两种需求。

recording rules 也降成本，但降的是**查询侧成本**（预计算掉重复的聚合），不是存储侧。这个区分要说对。

### 6.3 日志成本（他的诚实缺口）

`[理论]` + ⚠️ 明确无一手体系经验（见 `story_bank.md` S08 的 L5）。

- **日志通常比指标贵一个量级**，因为它是非结构化的、体积大、且很难降采样（一条日志降采样等于丢了它）。
- **Loki 的成本模型要点**：label 基数直接决定索引成本和查询性能，所以**高基数字段必须留在 log body 里而不是提成 label**；chunk 存对象存储，所以存储费便宜但请求费和查询扫描量是主要成本。
- **通用治法**：按 stream 分级保留（error 长留、debug 短留）；对高频重复日志采样（同一条 error 每秒 1000 条不比每秒 10 条更有信息量）；结构化日志减少体积；把「日志量」本身做成指标并给团队做 showback（这是最有效的一招，因为写日志的人平时看不到成本）。
- **他做过的最接近的动作**：ClickHouse 那次给默认无 TTL 的内部日志表加 TTL、把数据量最大的日志直接关闭（src: `w_zombie_oom.md:26`）`[一手]`，但驱动是 OOM 不是账单。诚实说法：「日志的成本治理我有零散动作，没有体系。」

### 6.4 追踪与 Profiling

`[理论]` 简短：追踪的成本主要在采样率上，而**采样率决定了它能回答什么问题**（低采样率下罕见错误路径基本抓不到）。正确做法是尾部采样（tail-based sampling，先收后决定，按「有错误/慢」保留），而不是均匀头部采样。这条他没有一手经验，答机制为止。

---

## §7 FinOps 的组织维度（决定答题框架，务必读）

### 7.1 Inform → Optimize → Operate

`[理论]`，官方仍在用这三个词：

| 阶段 | 在做什么 | 成熟的标志 | 他的位置 |
|---|---|---|---|
| **Inform** | 可见性与归因：谁花了多少、为什么 | 成本能拆到 team/service/环境，untagged 比例低，异常能被自动发现 | **薄**。成本归因停在账单科目层 |
| **Optimize** | 采取行动：架构、弹性、折扣、清理 | 有优先级排序而不是逮着什么优化什么 | **强，且偏架构那一半** |
| **Operate** | 制度化：谁负责、多久 review、怎么防回退 | 有 owner、有周期、有指标、有护栏 | **基本没有** |

**这个顺序有一个反直觉的重点：绝大多数团队跳过 Inform 直接做 Optimize。** 因为 Optimize 有立竿见影的成绩（「我关了一批闲置实例，省了 X」），Inform 是基础设施投入。跳过的代价是：你不知道该优化哪里，只能优化你正好看见的地方。

**他有一个完美的例子证明自己理解这一点**（S06 僵尸表）：TB 级的无主存储在多个集群持续增长，是被 OOM 发现的，不是被账单发现的。**如果 Inform 层做到位，这条曲线（用量在涨、访问量是零）本来是最干净的成本异常信号。** 主动讲这个自我批评，比声称自己会做 FinOps 有说服力得多。

### 7.2 Showback vs Chargeback

`[理论]` 一定要分清，这是 FinOps 的入门概念也是落地最难的部分。

| | Showback | Chargeback |
|---|---|---|
| 做什么 | 把成本**展示**给花钱的团队 | 把成本**计入**团队预算/P&L |
| 组织阻力 | 低 | 高 |
| 行为改变力 | 中（靠羞耻感和自觉） | 强（真的疼） |
| 前置条件 | 归因准确度「够用」 | 归因准确度必须**能被争议时站得住** |

**落地难点三条**：
1. **共享成本怎么分？** K8s 控制面、监控栈、日志栈、NAT、共享数据库都不属于任何单一团队。常见分法有按用量比例、按人头、按收入比例，没有一个是「公平」的。**关键是提前把规则说清楚并且不常改**，因为 chargeback 的可信度来自可预测性而不是精确性。
2. **idle 成本归谁？** 集群里 40% 是 idle，如果全摊给 workload，团队会觉得「我明明只用了这么多为什么账单这么高」；如果不摊，就没人有动力压 idle。OpenCost 的 `max(request, usage)` 语义就是对这个问题的一种回答：**预留但没用的容量算在申请方头上**，倒逼合理 sizing。
3. **归因的精度必须匹配后果的严重性。** Showback 阶段 80% 准确度就够（目的是引发对话）；一旦进 chargeback，每一个争议都会变成会议，所以要么把精度做上去，要么保持在 showback。**这条判断本身就是答题的加分点：不要为了「更严格」而过早上 chargeback。**

**锚到他**：多租户 SaaS + 50 集群，天然有 per-tenant 成本归因的需求（也是 SaaS 公司算毛利的基础）。他有 per-tenant SLI recording rules（src: `resume.tex`，见 `90_cross_cutting/number_baseline.md` §2）`[一手]`，也就是说**租户维度的可观测性已经存在了，缺的是把成本维度挂上去**。这是一个很自然的「我知道下一步该做什么」的答案。

### 7.3 Unit Economics：为什么它是终局指标

`[一手]` 这一节是他的**主场**，因为他真的做过 cost per query 分析（S02）。

**总额指标（月账单多少钱）的三个致命缺陷**：
1. **业务增长时它一定涨，涨了不代表变差。** 只看总额的团队在增长期会不断被质问，在萎缩期又会误以为自己优化得好。
2. **它不能回答「该不该花」。** 账单涨 20% 但请求量涨 50%，其实是效率提升了。
3. **它没有决策指向性。** 知道总额涨了不告诉你该动哪里。

**单位成本指标（cost per transaction / per tenant / per query / per token）解决全部三条**，因为它把成本除掉了业务量，剩下的就是效率本身。

**他能讲的三层**：
- **cost per query**：他实测的 1,240× 单查询成本比（src: `p_elastic_compute.md:15`）`[一手]`，而且他用这个分布做了架构决策（分池 + floor-0 弹性 + recall-first 风险姿态）。**这是 FinOps 里最难做到的一步，他做到了，只是没用这套词汇包装。**
- **cost per tenant**：SaaS 毛利的基础，他有租户维度的可观测性但没接成本维度（缺口，见 §7.2）。
- **cost per token / per inference**：FinOps for AI 的标准 KPI，2026 框架已经把 AI 列为独立 Technology Category，推荐的 KPI 是 cost-per-token、cost-per-inference、GPU 利用率、commitment coverage `[理论]`。这条对他有战略价值：他的 Doris 项目本来就是为 AI agent 负载做的，可以把话题接到「AI 负载的成本形状和人类负载完全不同：不可预测、突发、单查询成本重尾」，而这正是他做弹性池的原始动机。

**一个要主动交代的诚实点**：他的 cost per query 是**墙钟耗时比不是美元比**（见 `story_bank.md` S02 的 L1）。真正美元化需要给 compute group 打成本分配标签 + 用 node-hours 反推摊销。承认这一步没走完，比含糊过去强。

### 7.4 成本与可靠性的权衡怎么和业务对话

`[理论] + [一手锚点]` 这是最能体现 senior 的一节。

**核心原则：不要替业务做 SLA 降级的决定。** 工程师最常犯的错是自己判断「慢 10 分钟没关系」然后就调了参数。正确做法是把 trade-off 量化成业务能理解的选项，让业务选。

**他有一个教科书级的一手例子**：Iceberg 的 `commit.interval` 从 60s 拉到 10min，写侧文件数降约 3 倍，代价是端到端可见性变成约 10 分钟。这条是**和业务确认「10 分钟可接受」之后才定的**（src: `interview-6-starrocks-lakehouse.md:60`）`[一手]`。这个细节比任何理论都有说服力，因为它证明他真的走了这个流程。

**对话的四步结构**：
1. **把成本换成业务语言。** 不说「NAT 处理费每月 $X」，说「这笔钱等于一个工程师半个月」或者「等于每笔交易多花 Y 分钱」。
2. **把可靠性代价量化成选项，而不是描述成风险。** 不说「可能会慢」，说「A 方案月省 $X，代价是 p99 从 200ms 到 400ms；B 方案月省 $X/3，p99 不变」。
3. **明确谁有权决定。** SLO 是业务契约，改 SLO 是业务决策；在 SLO 之内怎么省钱是工程决策。**这条边界划清楚，成本对话就不会变成扯皮。**
4. **用 error budget 做共同语言。** 如果一个降本动作会消耗 error budget，那它就有了一个可量化的预算约束：budget 还有余量时可以试，烧完了就停。**这是把成本决策纳入 SRE 框架的正确接口。**（诚实边界：error budget policy 的制度落地在他这里是中环，见 `02_monitoring_slo/README.md`。）

**反过来，也要能守住底线。** 面试如果问「老板要你砍 30% 成本怎么办」，正确答法不是「我努力砍」，是：先归因（这 30% 在哪个科目最可能来）、再排序（架构级 > 弹性 > 折扣 > 清理，按收益/风险比）、把「不能动的部分」明确列出来并说明理由（关键路径的冗余、副本数、跨 AZ 的可用性成本），最后给出一个带风险标注的方案组合让老板选。**能说「有些成本我建议不砍，理由是 X」的人才是 senior。**

---

## §8 反模式清单（面试里主动说出来最有杀伤力）

每条都配一个「正确做法」和「他有没有踩过」。

| 反模式 | 为什么错 | 正确做法 | 他的位置 |
|---|---|---|---|
| **只做一次性清理不建机制** | 浪费会长回来，尤其是每次升级/部署重新制造的那类 | 把检测做成周期性的自动检查，把护栏做进 IaC 和 CI | ✅ **做对了**（S06 三层预防：TTL + 升级 runbook 增加审计步骤 + 舰队级审计），但自我批评是「没做成自动化检测项，仍依赖 runbook 的人工步骤」`[一手]` |
| **为省钱牺牲 SLO 且没有量化依据** | 事后无法辩护，出事时找不到当初的判断依据 | 每个降本动作写清「消耗多少 error budget / 影响哪个 SLI」，并且让业务确认 | ✅ **做对了**（`commit.interval` 是和业务确认后才定的）`[一手]` |
| **只看总额不看单位成本** | 增长期误判恶化、萎缩期误判改善，且没有决策指向 | 至少做一层 unit economics（per request / per tenant / per query） | ✅ **他的强项**（1,240× cost per query）`[一手]` |
| **优化了资源费却被网络费吃掉** | 拆分服务、跨 AZ 打散、多 region 部署都会把成本从 EC2 挪到 data transfer，账单科目变了但总额没降 | 每个架构变更都要问「这会改变哪个计费维度」 | ⚠️ **理论**。但他有一个完美的正面例子：Iceberg 那次是**先问「这个瓶颈在账单上对应哪个计费维度」再动手**（S3 按请求计费 → 治文件数）`[一手]` |
| **跳过 Inform 直接 Optimize** | 只能优化你正好看见的地方 | 先建可见性和归因，再排优先级 | ⚠️ **踩过**（S06：TB 级僵尸存储是 OOM 发现的不是账单发现的）。主动讲这个自我批评 |
| **对着 Compute Optimizer 的建议无脑执行** | 默认只回看 14 天，看不到月度/季度周期性负载；也不知道你的硬约束 | 当输入不当结论，回看窗口必须覆盖最长业务周期 | `[理论]`，但他有 Doris `cpu=8` 那个硬约束的例子说明「利用率不是唯一判据」`[一手]` |
| **买了长期承诺然后去做架构级降本** | 架构降本让 baseline 消失，承诺 utilization 崩掉，两个「优化」互相抵消 | **先架构，后承诺**；承诺只覆盖确定不会消失的 baseline | ⚠️ **理论，但这是他最有资格讲的一条**（§2.4） |
| **在迁移/重构期做长期承诺** | 实例族、节点数、region 分布全在变 | 迁移期用 On-Demand + Compute SP（最灵活），或干脆不承诺 | ⚠️ 理论，但 CH→Doris 迁移期正是这个场景 |
| **把 spot 用在有状态或用户面负载上** | 一次回收等于数据搬迁或 SLA 违约 | 按风险容忍度分池，on-demand 与 spot 不可混 | ✅ **做对了且有明确论证**（S05）`[一手]` |
| **以为 scale-to-zero 一定更省** | 请求间隔比冷启动短的高频负载会被冷启动和最小计费惩罚（业界案例：60s 最小计费 + >1min 冷启动 = 最高 30× 惩罚） | 算 burst 稀疏度和计费粒度，算出弹性/常驻的翻转点 | ✅ **做对了**（S01 的 L5）`[一手/业界]` |
| **认为 idle 资源是免费的** | 零副本不等于零成本，也不等于零风险 | idle 状态要有专门的运维审视 | ✅ **踩过并总结了**（缩到 0 的 compute group 留下 orphan lease 阻塞别人 compaction，src: `p_elastic_compute.md:49`）`[一手]` |
| **用总账单做 KPI 考核团队** | 团队会通过「不做新东西」来达标，抑制业务发展 | 考核单位成本或成本效率，不考核总额 | `[理论]` |

---

## §9 面试前 30 分钟速览卡

**如果只记 12 条：**

1. 账单 = 用量 × 单价 × 时长。用量是架构、时长是弹性、单价是折扣。**我的经历在前两项，第三项是补课项。**
2. AWS 官方现在推荐 **SP 优先于 RI**；RI 剩下的价值是 Marketplace 转售（只能卖 Standard）和 zonal RI 的容量预留。
3. SP 承诺的是 **$/hr 消费额**，RI 承诺的是**实例配置**。SP 有四种：Compute（66%）/ EC2 Instance（72%）/ SageMaker AI（64%）/ **Database（2025-12 新增，12-35%，仅 1 年 No Upfront）**。
4. Coverage 低 = 钱没省够；Utilization 低 = 买多了在付没用的承诺。两者反向拉扯，所以**只承诺 baseline**。
5. **先做架构级降本，再定承诺策略。** 顺序反了会买一堆用不掉的承诺。
6. cost allocation tag **能回溯，窗口 12 个月**，但只能回填标签当时确实存在的时段。
7. **S3 Gateway Endpoint 免费，所以「用它省 NAT」没有盈亏平衡点**；Interface Endpoint 有小时费才需要算。
8. **跨 AZ 流量没有变免费**，仍是 $0.01/GB 单向。2022 年免费的只有 PrivateLink / TGW / Client VPN 的跨 AZ。
9. **S3 PUT 比 GET 贵约 12.5 倍**（$0.005 vs $0.0004 每千请求），所以写侧文件数比读侧请求数更值钱。**Intelligent-Tiering 只对 ≥128KB 对象生效**，小文件场景无效。
10. **gp3 比 gp2 便宜 20%，但更大的收益是可以砍掉「为 IOPS 买的多余容量」**（gp2 是 3 IOPS/GB）。
11. K8s 上：`节点成本 ≥ Σrequests ≥ Σusage`。两个 gap 分别是**调度碎片**和**request 虚高**，治法完全不同。**先压 idle 再做 workload rightsizing。** 他们是 kubeadm 自建不是 EKS，所以 **EKS split cost allocation data 用不了**，只能走 OpenCost。
12. Unit economics 是终局指标。**我做过 cost per query（1,240×），但那是墙钟比不是美元比，美元化需要成本分配标签 + node-hours 摊销，这步我没走完。**

**三条一定要主动说的诚实边界：**
- 承诺折扣的采购决策我没参与过（⚠️ 且这条与 `resume-expand.tex` 上的 "Reserved baseline" 冲突，投简历前必须处理）。
- 日志成本治理我有零散动作没有体系。
- 我们的成本归因停在账单科目层，没有下到 workload 层；Inform 层薄是我最该补的。
