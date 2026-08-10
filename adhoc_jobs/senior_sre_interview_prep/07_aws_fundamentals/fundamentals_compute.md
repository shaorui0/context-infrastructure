# AWS Fundamentals：Compute (EC2)

这一节的考点在哪：面试官很少直接问"EC2 有哪些实例族"，而是把这个知识点包在一个场景里问，"你们的 OLAP 计算池怎么设计成可以缩到零"、"spot 中断了业务会不会炸"、"Cluster Autoscaler 和 Karpenter 有什么区别，你为什么没换"。这些问题的标准答案都是通用知识，但追问到第三层一定会问到我的具体架构；这节把每个知识点都锚回 Doris CN 弹性池和 50 集群 worker 管理的真实形态。

## 1. 实例族命名规则与选型

**面试官会怎么问**：EC2 实例族怎么分类？c/m/r/i 族怎么选，你们的数据库节点用哪个？

**标准答案（理论骨架）**
- 实例族字母前缀代表优化方向：`c`（compute-optimized，高 vCPU:内存比，约 1:2）、`m`（general purpose，均衡，约 1:4）、`r`（memory-optimized，约 1:8）、`i`（storage-optimized，本地 NVMe instance store，高 IOPS）。
- 数字代表世代（如 m5 → m6i → m7i），世代越新通常性价比越高、支持更新的处理器特性（如 Nitro）。
- 字母后缀表示处理器/网络变体：`i`=Intel、`a`=AMD、`g`=Graviton(ARM)、`n`=增强网络、`d`=本地 NVMe。
- 选型第一原则：先画负载的 vCPU:内存需求曲线，再从对应族里挑世代和处理器变体，不要反过来"先选便宜的再凑合"。

**我的场景锚点**
- Doris BE/CN 节点的核心瓶颈是内存（聚合状态、join build 侧、agg 状态模型里 sketch 函数按 8KB/group 计算，见 `resume_highlights_doris_dcluster.md` §3），同时需要本地 NVMe 做 file_cache（BE 本地 `1.3TB nvme`）。这个组合天然指向 `r` 族（内存优化）或 `i`/`d` 变体（本地存储），而不是纯 `c` 族。
- 我们的存算分离架构把"存储"这个维度已经挪到 S3，BE/CN 节点本地盘的角色降级成缓存而不是持久层，这让实例族选型的约束从"要不要本地大盘"变成"要不要本地快盘"，这是一个值得在面试里讲清楚的架构推理链，而不是单纯背概念。

**如果被追问到边界**：具体生产环境里 Doris BE/CN 节点用的确切实例类型（比如 r6i.4xlarge 还是别的型号），我没有一手确认的型号清单，`⚠️ 待确认：Doris BE/CN 生产实例类型`。

---

## 2. vCPU 与 burstable（T 族 credit 模型）

**面试官会怎么问**：T 族实例的 CPU credit 是怎么回事？为什么有的团队线上用 T 族会踩坑？

**标准答案（理论骨架）**
- T 族（t2/t3/t3a/t4g）是低基线性能 + 可突发的实例，靠 CPU credit 机制：每小时按基线性能（比如 t3.medium 基线 20% vCPU）累积 credit，突发使用时消耗 credit。
- Credit 耗尽后，`Standard` 模式实例被硬限制回基线性能（突然变慢，且没有告警默认触发），`Unlimited` 模式允许持续突发但超额部分按小时计费。
- 陷阱：把 T 族当成廉价通用实例长期跑高 CPU 负载，credit 耗尽后性能断崖式下降，且这个下降本身不容易在监控里第一时间定位到"是 CPU throttle 不是应用变慢"。

**我的场景锚点**
- 我们的 K8s worker 和 Doris BE/CN 节点都是持续负载或 spike 到高利用率的角色，不适合 T 族的 burstable 模型；`[理论，无一手 T 族踩坑经验]`：这条我知道的是标准知识，团队目前没有在生产上因为 T 族 credit 耗尽栽过跟头（或者说没有素材佐证）。
- 如果被问"你们用 T 族吗"，诚实答法是：我们的核心计算节点（K8s worker、Doris BE/CN）负载模式不匹配 T 族的假设，所以刻意没有选它；这本身是一个正确的选型判断，即便没有踩坑故事支撑。

**如果被追问到边界**：`[纯理论，无一手经验]`，没有真实的 credit 耗尽故障可讲。

---

## 3. Placement Group（cluster / spread / partition）

**面试官会怎么问**：Placement Group 三种模式的区别？什么场景需要？

**标准答案（理论骨架）**
- **Cluster**：同一 AZ 内物理临近，追求极低延迟/高带宽（如 HPC、tightly-coupled 分布式计算），代价是同时故障风险集中（一个机架级故障可能影响一整组）。
- **Spread**：每个实例放在不同的底层硬件（最多 7 个实例/AZ），追求故障隔离，典型场景是少量关键实例（如几个 master 节点）互相不共享故障域。
- **Partition**：把实例分成多个分区，每个分区独立的机架集合，分区间故障隔离，分区内可以临近，典型场景是大规模分布式系统（Kafka、HDFS、Cassandra 这类需要"跨分区容错"的系统）。

**我的场景锚点**
- 我们的 3 台 master 节点做 stacked etcd HA，理论上是 spread placement group 的经典适用场景（避免两台 master 落在同一物理机架，交叉扣掉 quorum）。`⚠️ 待确认：我们的 master 节点是否实际配置了 spread placement group`：我确认的是"3 master 必须跨 3 AZ"这条硬约束（etcd quorum 数学，见 `p_k8s_upgrade.md`），AZ 级隔离已经覆盖了大部分 placement group 想解决的问题，机架级的 spread placement group 是否额外配置了，没有素材可以确认。

**如果被追问到边界**：能讲清楚为什么"跨 AZ"已经覆盖了 placement group 想解决的大部分问题（AZ 本身就是独立的数据中心，故障域比机架大得多），placement group 是在同一 AZ 内做更细粒度隔离，我们的 HA 设计优先级放在 AZ 这一层，没有证据表明进一步做了机架级隔离。

---

## 4. Spot 完整生命周期（本节最重）

**面试官会怎么问**：Spot 实例中断是怎么发生的？你们怎么保证 spot 上跑的服务被杀了不出事？

**标准答案（理论骨架）**
- **中断通知**：AWS 在实际中断前 **2 分钟** 发送 interruption notice（通过实例元数据 `/latest/meta-data/spot/instance-action` 或 EventBridge），这是唯一保证的最短窗口。
- **Rebalance recommendation**：更早的信号（不保证给、也不保证真的会中断），提示"这个容量池风险变高了"，是比 2 分钟通知更早但不确定的预警。
- **中断原因**：价格超过出价（如果设了 max price）、容量不足（AWS 需要把容量还给 on-demand）、约束变化。绝大多数中断是容量原因，不是价格原因（on-demand 定价模型下 spot 价格已经不会超过 on-demand）。
- **分配策略**：`capacity-optimized`（从历史中断率最低的池子分配，优先稳定性）vs `lowest-price`（从最便宜的池子分配，可能持续追向高中断率的池子）。多实例类型 + capacity-optimized 是生产推荐组合。
- **spot 与有状态服务的边界**：spot 天然适合无状态、可重试、可容忍 2 分钟内优雅退出的工作负载；有状态服务（数据库、需要本地持久数据的角色）如果一定要上 spot，必须先解决"节点没了数据怎么办"，这正是我们架构的关键论证点。

**我的场景锚点（这条要讲透）**
- Doris heavy 查询计算池（CN/BE）跑在 spot 上，`replicas:0` 空闲缩零，靠 ASG + Launch Template + Cluster Autoscaler 弹起（`p_elastic_compute.md`）。
- **"杀 spot 安全"的完整论证链**：存算分离架构下 BE/CN 节点本地没有持久数据（tablet 全部在 S3），所以一个节点被 spot 回收，等价于"少了一台计算力"而不是"丢了一份数据"；FE 通过 ~2 秒心跳检测到 backend 失联，锁在 ~7 秒内释放，失败查询重试一次，整个探测+释放+重试链条都发生在 spot 2 分钟回收窗口之内。
- **决策不是教条**：即便spot 中断在架构上是安全的，一个执行到一半的 60-500 秒查询被回收仍然浪费已完成的工作，加上约 3-4 分钟的重新扩容；所以实际决策是"先用 on-demand，装好 node-termination handler 之后再切 spot-first 混合 ASG"，锚定的是实测 node-hours 而不是"spot 便宜"的教条。这条决策论证本身是一个很强的面试素材：懂得权衡而不是无脑上 spot。
- **成本数字**：该节点档位 spot 比 on-demand 便宜约 62%；heavy 池静态 2 节点 on-demand 约 $772/月，实测 burst 模式（日均 2 节点跑约 2 小时）on-demand 约 $63/月、spot 约 $24/月（约 92%/97% 节省）。

**Cluster Autoscaler 的两类 scale-from-zero 静默拒绝（真实踩过的坑，是本节最好的追问防线）**
1. **kube-reserved 差距**：BE 请求 `cpu=8` 在 8 vCPU 节点上，扣除 kube-reserved 后 allocatable 只有约 7.9，调度模拟永远报 `Insufficient cpu`，没有任何事件指向那 0.1 核的差距；改成 `cpu=7` 立即扩出。"request 严格小于节点 vCPU"是我们的 P0 checklist 项。
2. **字面零节点时的虚拟节点构造**：ASG 处于 0 节点时，CA 没有真实节点可查看，只能靠 ASG 的 node-template label/taint tag 在内存构造一个 virtual node；缺 tag 时 CA 判定这个组永远装不下该 pod 并跳过，pod 永远 Pending，且没有报错提到缺失的 tag。

**如果被追问到边界**：spot 中断回退逻辑的具体代码实现（比如 dcluster 里的中断处理、多集群锁）不是我写的，git 归属是 junhan.ouyang / Runzi Yang（见 `resume_highlights_doris_dcluster.md` §0）；我能讲的是**架构论证**（为什么杀 spot 安全）和**Cluster Autoscaler 层的坑**（因为 scale-from-zero 是我实际调过的），不越界到平台可靠性实现细节。

---

## 5. ASG（Auto Scaling Group）

**面试官会怎么问**：ASG 的扩缩策略有哪些？健康检查怎么配？lifecycle hook 是干什么的？

**标准答案（理论骨架）**
- **Scaling policy 类型**：Target tracking（追踪某个指标到目标值，如 CPU 50%）、Step scaling（按告警幅度分档调整）、Simple scaling（单一阈值触发单一动作，带冷却）、Scheduled scaling（定时）。
- **健康检查**：EC2 状态检查 + 可选 ELB 健康检查；ASG 健康检查失败会自动终止并替换实例，两者可以叠加（`HealthCheckType=ELB` 时同时看 ELB 判定）。
- **Lifecycle hook**：在实例进入 `InService` 前（`Pending:Wait`）或终止前（`Terminating:Wait`）插入等待窗口，让自定义逻辑（比如 join K8s 集群、下线前 drain）有机会完成，默认超时后走 heartbeat 续期或 abandon/continue。
- **Warm pool**：预先启动并保持在 stopped/running 状态的实例池，减少扩容时的冷启动延迟，代价是要为待命实例付费（stopped 状态省计算费但保留 EBS 费用）。

**我的场景锚点**
- 我们 50 集群的 worker 节点全部走 ASG + Launch Template + Cluster Autoscaler 的组合（`interview-8-k8s-cluster-build.md`）：Pod Pending → CA 触发 ASG 扩容 → 新 EC2（Packer AMI）启动 → userdata 跑 `kubeadm join` → 成为 worker。这条闭环我完整维护过。
- ASG Instance Refresh 是 K8s 版本升级里 worker 替换的机制：20% batch 滚动、失败自动暂停，在双集群流量前置切换的模式下，20% batch 从"保护用户"降级为"节奏控制"（因为流量已经切走，batch size 只影响能多快发现异常并暂停），见 `p_k8s_upgrade.md`。
- Lifecycle hook：`⚠️ 待确认` 我们的 worker 加入/退出流程是否显式用了 lifecycle hook，还是完全靠 kubelet 的 graceful shutdown + PDB 处理；素材里没有看到 lifecycle hook 的直接证据，谨慎不编造。
- Warm pool：`[纯理论，无一手经验]`，我们没有用 warm pool，heavy 池的策略是完全 scale-to-zero + 接受约 66 秒(节点) + 约 2 分钟(BE 注册)的冷启动，这是刻意的成本取舍而不是没想到 warm pool。

---

## 6. Launch Template 版本管理

**面试官会怎么问**：Launch Template 怎么做版本管理？升级 AMI 是改现有版本还是建新版本？

**标准答案（理论骨架）**
- Launch Template 是不可变的版本化对象：每次改动（比如换 AMI）都创建一个新版本号，不修改旧版本；ASG 可以指向固定版本号或 `$Latest`/`$Default`。
- 回滚 = 把 ASG 指回旧版本号，或者把 `$Default` 改回旧版本，不需要"撤销"操作。
- 最佳实践：AMI ID 是 Launch Template 版本间唯一应该变化的字段（其余实例类型、安全组等尽量稳定），这样 diff 一目了然。

**我的场景锚点**
- 真实操作流程（`docs/aws_ami_asg_guide.md`）：Packer 构建新 AMI → `aws ec2 create-launch-template-version --source-version 1 --launch-template-data "ImageId=<new-ami-id>"` 创建新版本 → 验证新版本 → `aws autoscaling update-auto-scaling-group --launch-template LaunchTemplateId=...,Version='$Latest'` 让 ASG 指向新版本。
- K8s 升级流程里明确要求"Worker 侧只允许 AMI ID 变化"作为 Launch Template diff 的门禁（`p_k8s_upgrade.md`：`kubeadm upgrade plan` 加 AMI diff + Launch Template diff，只允许 AMI ID 变），这是把上面的最佳实践变成了强制流程门禁，而不只是知道概念。

---

## 7. AMI 与 Packer 的关系

**面试官会怎么问**：AMI 是怎么构建出来的？Packer 在这里做什么角色？

**标准答案（理论骨架）**
- AMI 是 EC2 实例的镜像模板（OS + 预装软件 + 配置），Packer 是声明式构建 AMI 的工具：定义 builder（用哪个 base AMI、哪个 region）+ provisioner（怎么装软件，通常是 shell script 或 Ansible），跑起来产出一个新 AMI ID。
- 好处是把"机器长什么样"变成可版本化的代码（Packer 模板进 git），而不是手工登录改一台机器再打镜像。

**我的场景锚点**
- 我们的四层 IaC 里，Packer 负责 Layer 0（机器镜像：OS + containerd + kubeadm 预装），Ansible 负责 Layer 1-3（AWS 资源、K8s 控制面、集群内组件）。这个分层背后的设计原则是"慢且稳定的装包动作固化进 AMI，快且多变的配置动作留给 Ansible"，AWS 部署能跳过装 containerd/k8s（AMI 已含），只有 onsite（无云环境）才需要现装，这是分层解耦的具体体现（`interview-8-k8s-cluster-build.md` §1(b)）。

---

## 8. Cluster Autoscaler vs Karpenter

**面试官会怎么问**：Cluster Autoscaler 和 Karpenter 有什么区别？你们为什么用 CA 不用 Karpenter？

**标准答案（理论骨架）**
- **Cluster Autoscaler**：以 ASG（或等价 node group）为扩缩单位，逻辑是"看 Pending pod 需要什么，找到能满足的 node group，把这个 group 的 desired count +1"；一个 node group 内实例规格通常同质，选择实例类型的粒度是"提前配置好的 node group"，不是逐 pod 动态选型。
- **Karpenter**：不依赖预先定义好的 node group，直接根据 Pending pod 的资源请求即时算出"最省的实例类型+可用区+计价方式"组合并直接调用 EC2 API 创建，弹性粒度更细、bin-packing 更优、扩缩速度通常更快，且原生支持 spot 多样化实例类型的自动选择。
- CA 的局限：受限于 node group 的规格颗粒度（不能逐 pod 精算最优实例）、scale-from-zero 依赖 node-template 元数据（这正是我们踩过的坑）、多 node group 时扩容决策的"选哪个 group"逻辑不如 Karpenter 灵活。

**我的场景锚点**
- 我们用的是 **Cluster Autoscaler**，不是 Karpenter（`interview-8-k8s-cluster-build.md` 明确：`Cluster Autoscaler + ASG` 闭环）。CA 的两个已知局限我们都踩过：kube-reserved 导致的 `Insufficient cpu` 静默失败、scale-from-zero 时虚拟节点构造依赖 ASG tag（见上面 spot 小节）。
- 诚实分析"为什么没换 Karpenter"：素材里没有一手证据说明这是团队主动评估后放弃 Karpenter 的决策，还是历史遗留没有重新评估过。诚实答法是"我们目前用 CA，CA 的局限我很清楚且实际处理过；Karpenter 在更细粒度 bin-packing 和更快扩容速度上有优势，如果要迁移，代价是要重新设计 node group 抽象和验证与我们 kubeadm 自建、多 region 的兼容性，这个评估目前还没做"。`⚠️ 待确认：团队是否评估过 Karpenter 迁移`。

---

## 9. Nitro / 虚拟化基础

**面试官会怎么问**：Nitro 系统是什么？为什么现在的 EC2 实例都基于 Nitro？

**标准答案（理论骨架）**`[理论]`
- Nitro 是 AWS 自研的虚拟化卸载架构：把网络、存储、安全监控这些原本由 hypervisor 软件处理的功能卸载到专用硬件（Nitro Card），hypervisor 本身变得极薄（接近裸金属性能），CPU/内存几乎全部让渡给客户实例。
- 现代实例族（c5/m5/r5 及以后）基本都基于 Nitro，带来的直接影响：EBS 性能上限更高（Nitro 网络带宽更大）、支持更细粒度的 EBS 优化默认开启、部分实例支持 Nitro Enclaves（隔离计算环境）。

**我的场景锚点**：`[纯理论，无一手经验]`，没有素材支撑我们对 Nitro 底层机制的直接观测或依赖，这条纯粹是背景知识，用于回答"为什么新世代实例网络/存储性能更好"这类问题时的解释框架。

---

## 10. 预留容量家族（计算语义，成本策略见 06 目录）

**面试官会怎么问**：On-Demand Capacity Reservation、Reserved Instance、Savings Plans 有什么区别？

**标准答案（理论骨架）**
- **On-Demand Capacity Reservation (ODCR)**：只保证容量（这个 AZ 里这个实例类型一定有位置给你），不自动打折，按 on-demand 价计费（不用也计费），常和 RI/Savings Plans 叠加使用来同时锁定容量和价格。
- **Reserved Instance (RI)**：承诺使用量换折扣，绑定实例类型+region（regional RI 可跨 AZ 灵活，zonal RI 锁 AZ 但保证容量），1年/3年期，standard/convertible 两种（convertible 允许换实例族）。
- **Savings Plans**：承诺一段时间内的**美元消费额**（而不是具体实例类型）换折扣，Compute Savings Plans 覆盖跨实例族/region/计算服务（EC2/Fargate/Lambda）的弹性最大，EC2 Instance Savings Plans 折扣更高但锁定实例族。
- 三者可以组合：RI/Savings Plans 管价格，ODCR 管容量确定性，这是两个正交的问题（"这笔钱花多少"vs"这个位置一定有没有"）。

**我的场景锚点**：这部分是**纯计算语义**，具体的降本策略、我们实际用了哪种组合、dcluster 弹性池的成本论证属于 06 目录（AWS cost/FinOps）的范围，这里不重复展开数字。`⚠️ 待确认：我们生产是否购买了 RI/Savings Plans，还是完全 on-demand+spot`：从目前素材看，heavy 池明确是 on-demand/spot 的讨论，没有看到 RI/Savings Plans 的直接证据。
