# 07 AWS Fundamentals：高频面试题 + 答题骨架

按 compute / storage / network / IAM / 综合场景 分组，共 30 题。每题给出：一句定位（这题到底在考什么）+ 展开结构（怎么组织答案）+ 我的场景锚点或诚实边界。详细理论展开见对应的 `fundamentals_*.md`，这里是压缩版调用索引，面试前一小时刷这份就够。

---

## Compute

### C1. spot 实例中断是怎么发生的，你们怎么保证被杀了不出事？

- **一句定位**：考的不是"spot 便宜"这个常识，是"你有没有真正设计过一个能容忍中断的架构"。
- **展开结构**：中断通知 2 分钟 → rebalance recommendation 更早但不保证 → 中断原因主要是容量不是价格 → capacity-optimized vs lowest-price 分配策略 → 有状态服务上 spot 的前提。
- **我的场景锚点**：Doris heavy 查询池跑在 spot 上，存算分离让节点本地无持久数据，FE 约 2 秒心跳检测失联、约 7 秒释放锁、失败重试一次，全部在 2 分钟回收窗口内完成；决策不是"spot 就是好"的教条，而是权衡了 mid-query 回收浪费已完成工作 + 约 3-4 分钟重扩容的代价后，先用 on-demand、装好中断处理再切 spot-first。中断回退的**实现**不是我写的（git 归属 junhan.ouyang/Runzi Yang），我讲的是架构论证。

### C2. Cluster Autoscaler 从零扩容为什么会失败，怎么排查？

- **一句定位**：考对 scale-from-zero 这个特殊场景的理解深度，不是问"CA 怎么用"。
- **展开结构**：CA 靠调度模拟决定要不要扩某个 node group；字面零节点时没有真实节点可看，只能靠 ASG node-template 标签构造虚拟节点；两类静默失败：kube-reserved 导致的 request 超过 allocatable、虚拟节点缺 label/taint tag 导致 CA 判定"这组永远装不下"且不报任何错误。
- **我的场景锚点**：这两类坑都是我们真实在 Doris CN 弹性池调试中踩过并定位过的（`p_elastic_compute.md`），不是背知识点。

### C3. Cluster Autoscaler 和 Karpenter 有什么区别？

- **一句定位**：考知识面广度，也考"你了解自己工具局限"的诚实度。
- **展开结构**：CA 以预定义 node group 为扩缩单位，选型颗粒度受限；Karpenter 逐 pod 即时算最优实例类型+AZ+计价方式，bin-packing 更优、天然支持 spot 多样化。
- **我的场景锚点**：我们用 CA 不用 Karpenter，CA 的局限（scale-from-zero 依赖 node-template、kube-reserved 坑）我实际处理过；`⚠️ 待确认` 团队是否系统评估过迁移 Karpenter，不编造已有决策。

### C4. 实例族怎么选，你们数据库节点为什么选这个族？

- **一句定位**：考实例族命名规则是否只是背过，还是真能反推架构约束。
- **展开结构**：c/m/r/i 族 vCPU:内存比不同；先画负载曲线再选族和世代。
- **我的场景锚点**：Doris BE/CN 内存密集（agg 状态、sketch 函数）+ 需要本地快盘做 file_cache，天然指向 `r`/`i` 族方向而不是 `c` 族；具体生产实例型号 `⚠️ 待确认`。

### C5. Launch Template 怎么做版本管理，AMI 升级流程是什么？

- **一句定位**：考不可变基础设施的实操理解。
- **展开结构**：LT 是版本化不可变对象，改 AMI 建新版本不改旧版本，ASG 指向具体版本号或 `$Latest`，回滚=指回旧版本号。
- **我的场景锚点**：真实操作序列：Packer 出新 AMI → `create-launch-template-version --source-version` → 验证 → `update-auto-scaling-group --launch-template Version=$Latest`；K8s 升级流程强制"Worker 侧 Launch Template diff 只允许 AMI ID 变化"作为门禁，不是随便改。

### C6. T 族实例的 CPU credit 模型是什么，为什么容易踩坑？

- **一句定位**：纯知识点摸底题，考的是有没有基础常识。
- **展开结构**：baseline 性能 + credit 累积/消耗，Standard 模式耗尽后硬限速，Unlimited 模式允许超支付费突发。
- **我的场景锚点**：`[纯理论，无一手经验]`,我们核心计算节点负载模式不适合 T 族，刻意没选，但没有真实踩坑故事，诚实说清这是常识题不是经验题。

---

## Storage

### S1. EBS snapshot 恢复出来的卷马上就是满血性能吗？

- **一句定位**：本方向含金量最高的一题，专考"懒加载"这个反直觉细节，直接决定能不能讲好 5.2B 行 DR 故事。
- **展开结构**：snapshot 增量存储在 S3 → 恢复卷立即可挂载但默认懒加载 → 首次读每个 block 触发从 S3 拉取 → 全表扫描类查询会顺带把大部分 block 强制预热，比稳态慢 → Fast Snapshot Restore 可以避免这个代价但要额外付费。
- **我的场景锚点**：5.2B 行 EBS snapshot 恢复演练，验证阶段特意跑 `count`(约 50s)和 `GROUP BY`(约 83s)这类全表扫描查询而不是点查，因为点查命中不到懒加载代价，这个查询选择本身就是"理解懒加载"的证据。诚实边界:这是一次性演练，不是制度化 DR,RPO≈24h 是隐含推出不是写死的 SLA。

### S2. gp2 和 gp3 有什么区别？

- **一句定位**：基础但高频，考是否理解"解耦"这个核心变化。
- **展开结构**：gp2 IOPS 与容量强绑定（3 IOPS/GB）+ burst credit;gp3 baseline 独立于容量、可单独加购 IOPS/吞吐。
- **我的场景锚点**：Doris BE 本地缓存盘实际是本地 NVMe instance store 不是 EBS 卷，这个区分本身是加分点：它不需要 EBS 持久性保证，因为权威数据在 S3。

### S3. S3 现在是强一致的吗？这意味着什么？

- **一句定位**：考是否知道 2020 年这个具体变化，以及"强一致"边界在哪。
- **展开结构**：2020 年 12 月起所有操作（含覆盖 PUT、DELETE）读后写强一致;不覆盖跨 region 复制的异步延迟、不覆盖本地/CDN 缓存的 TTL。
- **我的场景锚点**：这条区分直接对应 Doris file_cache：S3 强一致只保证"直接读 S3 拿到最新",不保证 file_cache 本地副本自动失效，缓存失效是引擎自己的机制，两层问题不能混。

### S4. 存算分离架构下，本地缓存解决了什么问题、没解决什么问题？

- **一句定位**：本方向第二强的锚点，考存算分离性能模型的第一性理解，不是"有没有加缓存"这么简单。
- **展开结构**：暖读消除 S3 读但不消除扇出成本;"扇出是地板，S3 是冷路径乘数"这个根因模型。
- **我的场景锚点**：暖查询（缓存全命中，几乎零 S3）仍要 1.12 秒，因为要跨 8 BE 扇出到 566 tablet/6689 segment 逐个开倒排 searcher;冷读到暖读单条链路从约 31.8s 降到约 0.46s;冷读聚合吞吐仅约 1MB/s,瓶颈是 GET 延迟×数量不是带宽。这条我现场验证过一个错误假设（4.0.5 缓存清零）并用三重证据纠正了自己。

### S5. K8s 里 PVC 扩容有什么坑？

- **一句定位**：考 K8s+存储接缝的实操细节。
- **展开结构**：EBS CSI driver 桥接 PVC↔EBS 卷;StatefulSet volumeClaimTemplates 的 size 只在首建生效，改 YAML 不会自动扩容存量 PVC;真正在线扩容要靠 StorageClass `allowVolumeExpansion` + 单独操作 PVC。
- **我的场景锚点**：我们生产确认用 EBS-backed StorageClass、`allowVolumeExpansion:true`,在线扩容不需要重启 StatefulSet,这是运维 runbook 里的真实选项;volumeClaimTemplates 首建不可变这条是通用 K8s 知识`[理论]`,没有素材证明我们踩过这个具体坑，诚实区分两者。

### S6. S3 请求费怎么算，为什么前缀分片以前是个问题现在不是了？

- **一句定位**：考是否知道"过时知识点"的时效性，别背老答案。
- **展开结构**：PUT/GET 分类计费;2018 年后 S3 自动分区，不再强制要求随机前缀，但极高请求速率场景仍建议提前规划。
- **我的场景锚点**：真实冷读数据印证"请求数量是瓶颈"这条：冷读聚合吞吐约 1MB/s,瓶颈是大量小 GET 的延迟串行叠加，不是单请求传输量，这条比理论本身更有说服力。

---

## Network

### N1. K8s on AWS 网络故障怎么排查？

- **一句定位**：本方向排障能力的压轴题，考方法论是否成体系。
- **展开结构**：先按症状分类（timeout vs refused vs 高延迟但 upstream 正常）→ 按 Client→DNS→LB→Ingress→Service→Pod 分层、由外到内、只在第一失败点停;control-plane truth ≠ data-plane truth 的核心原则。
- **我的场景锚点**：这是我们团队在 50 集群 6 region 环境下反复验证过的真实排障语法（`pattern-aws-k8s-networking-troubleshooting-pattern.md`）,不是临时拼凑。

### N2. Security Group 和 NACL 有什么区别？

- **一句定位**：基础高频，考有状态/无状态评估顺序是否清楚。
- **展开结构**：SG 有状态、只需单向放行、只有 Allow;NACL 无状态、双向都要显式放行、支持 Deny、按规则号顺序评估。
- **我的场景锚点**：我们 SG 是刻意的粗粒度信任边界（VPC/VPN/管理网全放行，端口隔离下放 CNI）,这是有意识权衡不是疏忽;真实踩过的坑是 Calico IPIP 模式下跨节点流量走 IP protocol 4 不是端口，SG 逐端口收紧最容易漏放行这个。

### N3. ENI 怎么限制 K8s Pod 密度，你们 600+ 节点怎么应对？

- **一句定位**：考是否理解这个限制**依赖 CNI 模式**,不是无条件成立。
- **展开结构**：VPC 原生 CNI 模式下 Pod 密度 = ENI 数 × 每 ENI IP 数;overlay 封装模式下不受此约束，改受 CNI 自身 IP 池设计约束。
- **我的场景锚点**：我们默认 CNI 是 Calico IPIP(overlay,Pod 走独立 `192.168.0.0/16` 网段),不受 ENI/VPC IP 配额约束;`⚠️ 待确认` 50 集群实际是否全部用 Calico,还是部分启用了 Cilium ENI(repo 支持两种但没有素材证明具体分布)。

### N4. ALB、NLB 怎么选？

- **一句定位**：基础但要讲出"为什么"不是背表格。
- **展开结构**：ALB 理解 L7、做路由决策、终止 TLS;NLB 只做 L4 透传、更低延迟更高吞吐、支持静态 IP。
- **我的场景锚点**：apiserver 用 internal NLB,因为 apiserver 是 TLS+gRPC 需要 L4 透传不终止 TLS;业务入口也走 NLB(`aws-load-balancer-type: nlb`)接 ingress-nginx 做 L7 路由，L7 决策放在 ingress 层而不是 ALB 层。

### N5. Route53 故障转移能做到多快？DNS 层故障切换的物理下限在哪？

- **一句定位**：考是否真的理解 DNS 故障切换的天花板，以及能不能把架构选择和这条理论下限对上。
- **展开结构**：TTL 到期理论上触发重新解析;实际下限是分钟级，因为客户端/中间代理不严格遵守 TTL、连接池不会因 DNS 变了主动断连。
- **答法** `[理论]`：要秒级生效，切换点就得放在 DNS 之后的转发层，例如 ALB target-group 权重、API Gateway 路由指向、Global Accelerator 端点权重、K8s Ingress canary 权重，这些决策在连接建立之后仍然生效，不需要客户端重新解析域名;Global Accelerator 用 Anycast 静态 IP 做入口，更是把"客户端要重新解析"这个变量整个拿掉。DNS 层留给 region 级容灾和可以接受分钟级收敛的场景，判据是目标 RTO 是否宽于 DNS 缓存的现实收敛时间。诚实边界:Route53 的加权/地理路由我没有配置过。

### N6. NAT Gateway 有什么成本和带宽陷阱？

- **一句定位**：考基础但常被忽视的隐性成本模型。
- **展开结构**：按小时+按处理流量 GB 计费，单 NAT Gateway 约 45Gbps 带宽上限;S3/DynamoDB 流量可以用 Gateway Endpoint 完全绕开 NAT。
- **我的场景锚点**：`⚠️ 待确认` 我们的 Doris/VM 到 S3 的流量是否已配置 Gateway Endpoint,还是仍走 NAT：这是我复盘时发现的可能优化点，诚实标注未确认，不假装已做。

---

## IAM

### I1. IAM policy 评估顺序是什么？

- **一句定位**：IAM 最容易被抽查的一段"背诵型"知识，必须逐层讲对不能跳步骤。
- **展开结构**：隐式 Deny 兜底 → 显式 Deny 最高优先级、无条件拒绝 → 显式 Allow(identity 或 resource policy 任一满足，跨账号需两边都过)→ SCP/Permission Boundary 只收窄不授权，是天花板不是授权来源。
- **我的场景锚点**：`⚠️ 待确认` 我们是否使用 Organizations/SCP,`[纯理论，无一手经验]`;评估逻辑本身能讲清楚，没有把它应用到自己账号结构的一手经验。

### I2. 什么是 IRSA？你们怎么落地的？

- **一句定位**：本方向 IAM 部分最诚实也最有判断力的一题。
- **展开结构**：EKS 原生机制，靠集群 OIDC provider 注册进 IAM,ServiceAccount annotation 指向 role ARN,实现 Pod 级别（而非节点级别）最小权限。
- **我的场景锚点**：我们是 kubeadm 自建集群，**没有配 OIDC provider**,没有 IRSA;走的是 node instance profile,节点上所有 Pod 共享节点级权限;我们安全审计清单明确把"改用 IRSA/instance profile"列为 Secret 硬编码问题的修复方向，说明团队知道正确路径但没落地。追问"为什么不上"时，诚实答法是这是我会主动提出的下一步基础设施投入，不是评估后放弃。

### I3. Instance Profile 是什么，和 IRSA 的核心区别是什么？

- **一句定位**：考粒度概念：节点级 vs 工作负载级。
- **展开结构**：Instance Profile 挂在 EC2 实例上，该实例所有进程共享同一权限;IRSA 精确到具体 ServiceAccount/namespace。
- **我的场景锚点**：我们 CCM/EBS CSI/Cluster Autoscaler 这些系统组件目前就是靠 node instance profile 拿 AWS 权限，这个模型的代价（业务 Pod 也能拿到节点级权限）是当前真实存在的风险面，不是假设。

### I4. 你们发现过密钥管理的真实问题吗？怎么处理的？

- **一句定位**：这是本方向唯一的行为面素材题，考"发现问题并推动改进"的具体案例，答不出真实案例这题就白问了。
- **展开结构**：先讲发现过程（整理材料时主动 grep 出来的，不是别人报告）,再讲具体证据（文件+行号+key 前缀）,再讲正确修复路径（rotate → IRSA/instance profile → git 历史清理 → CloudTrail 回溯异常使用）。
- **我的场景锚点**：`infra/jenkins-config/jenkins.yaml` L28-31 明文 AWS AccessKey/SecretKey(`AKIAJQXAV6...`)进 git 历史，以及 `infra-internal` 的 `roles/cilium/templates/values.yaml.j2` 同类硬编码，都是我主动发现并记录修复路径的真实案例。诚实边界:`⚠️ 待确认` 这两处是否已完成实际 rotate 和历史清理，没证据不能说"已修复"。

### I5. AssumeRole 和 instance profile 拿到的凭证有什么共同点？

- **一句定位**：考是否理解"临时凭证"是贯穿多种机制的共同底层设计。
- **展开结构**：两者本质都是通过 STS 颁发有过期时间的临时凭证，区别只在"谁来触发这次颁发"(手动 assume vs 实例自动关联)。
- **我的场景锚点**：`[纯理论，无一手经验]`,AssumeRole 跨账号场景没有一手经验，能讲清机制原理。

### I6. 为什么长期 access key 是反模式？

- **一句定位**：基础但常考，考是否理解"风险窗口"这个核心论证，而不只是"不安全"这种空话。
- **展开结构**：长期 key 没有内置过期，泄露后风险窗口无限直到被发现;临时凭证过期时间明确，泄露风险窗口受限;临时凭证的获取路径通常不需要把密钥写在任何地方，从根源减少泄露入口。
- **我的场景锚点**：jenkins.yaml/cilium values.yaml.j2 两个真实案例正是长期 key 硬编码进代码的反面教材，可以直接引用作为论证的实证支撑。

---

## 综合场景

### G1. 设计一个能在 AWS 上缩到零的 OLAP 计算池（他的满分题）

- **一句定位**：这是把 compute/storage/network/IAM 四块知识串成一个系统设计答案的题，也是他能打满分的题，面试官如果给这个开放性问题，要主动往自己真实做过的架构上带。
- **展开结构（按面试官期待的系统设计节奏组织）**：
  1. **先讲经济账，不要先讲技术**：测算负载分布（点查 vs 重查询的执行次数/成本比）,证明"常驻重池"的钱大部分花在空转;
  2. **架构前提**：只有存算分离（计算和数据解耦，tablet 在对象存储）才能让计算节点"随便杀",这是能缩到零的地基，不是可选项;
  3. **弹性层**：ASG + Launch Template + Cluster Autoscaler 从 Pending pod 拉起节点，控制面收敛成对一个 CR 字段的 patch(而不是自己建部署逻辑，平台已经管理了这份状态);
  4. **路由层**：查询进来先做 heavy/light 判定（基于逐算子资源估算）,轻查询留常驻池，重查询才触发弹性池;
  5. **就绪链路要假设每个信号都会说谎**：`SELECT 1` 会被常量折叠不代表真探活，pod RUNNING 不代表 backend 已注册，必须用 `SHOW BACKENDS` Alive + canary 查询做真正的数据面探活;
  6. **spot 的位置**：只放在无状态、可重试、能在中断窗口内完成"检测+释放+重试"的计算层，不放在有状态服务;
  7. **失败模式提前想清楚**：scale-from-zero 的两类静默拒绝（kube-reserved、虚拟节点缺 tag）、探针说谎、"缩到零"在监控面板上显红但其实是设计生效。
- **我的场景锚点**：这几乎是我真实做过的系统原样复述：Doris CN heavy 池，`p_elastic_compute.md` 全文都是这题的标准答案来源，包括成本数字（静态池 92-97% 是空转）、冷启动时间（约 66s 节点+约 2min 注册）、幂等控制面设计。这题不需要编，是我最强的一张牌。

### G2. 一次跨 50 集群、6 region 的 K8s 大版本升级你会怎么设计？

- **一句定位**：考大规模变更管理的方法论，不是问 kubeadm 命令本身。
- **展开结构**：check→plan(dry-run)→apply+evidence 三段流水线;blast radius 用 quorum 数学在执行前封顶（3 master 容忍 1、serial:1、20% batch）;evidence chain 把隐式资深经验转成任何人可操作的显式门禁;分层回滚（etcd snapshot 恢复数据不恢复二进制、worker 回滚是回退 Launch Template、addon 回滚是 rollout undo）。
- **我的场景锚点**：`p_k8s_upgrade.md` 全文，18-21h→6-8h(自动化目标 3-4h),两套生产集群零客户可感知停机零回滚，支撑模式是双集群流量前置切换。

### G3. 一次生产数据的完整恢复演练你会怎么验证"真的恢复成功"？

- **一句定位**：考验证方法论而不是恢复步骤本身：很多人会漏掉"完成"和"性能达标"是两回事。
- **展开结构**：恢复完成（挂载成功）不等于性能稳态（EBS snapshot 懒加载）;验证要选择会触发全表扫描的查询（而不是点查）才能暴露懒加载代价;要分清"一次性演练"和"制度化 DR"：RPO 是从 snapshot 频率隐含推出的，不是写死的 SLA。
- **我的场景锚点**：5.2B 行 EBS snapshot 恢复，验证用 `count`(约 50s)和 `GROUP BY`(约 83s),两个数字本身就是懒加载代价的实测证据。诚实边界:一次性演练非制度，RPO≈24h 是隐含推断。

### G4. 你们的监控平台怎么从 Prometheus Federation 迁移到 VictoriaMetrics 的，AWS 这层扮演什么角色？

- **一句定位**：这题看起来是纯监控题，但面试官如果懂行会追问"600 节点 1.2M series 这个容量数字你是怎么算出来的",这是 compute(节点数)和 storage(热/冷存储分层)交叉的题。
- **展开结构**：federation 的可靠性问题（head block 内存、每周 OOM）和延迟问题（两层 scrape 叠加 45s）都是架构属性不是配置问题;容量测算从实测输入反推（50 集群×约 12 节点×约 2000 series/节点）;热存储 SSD、冷存储 S3 降采样分层。
- **我的场景锚点**：`p_vm_platform.md` 全文，1.2M active series、80K samples/s、热存储 3 月约 250GB(4x 压缩)、冷存储 S3 180 天约 25GB。这题的 AWS 层落点是"S3 当冷存储归档"这个具体决策，`⚠️ 待确认` 这部分 S3 数据是否配置了生命周期策略。

### G5. 如果你要把这套 kubeadm 自建集群的权限模型现代化，你会怎么排优先级？

- **一句定位**：考安全改进的优先级判断，不是列一堆理论清单。
- **展开结构**：先处理"正在流血"的（已知硬编码 key,立即 rotate+清历史）;再处理"结构性但影响面广"的（node instance profile→IRSA 迁移，需要先给集群配 OIDC provider,这是跨 50 集群的基础设施投入，不是一次性脚本）;最后处理"治理层"的（是否需要 SCP/Organizations,取决于账号结构现状）。
- **我的场景锚点**：这题直接复用 jenkins.yaml/cilium key 泄露案例（立即项）+ IRSA 缺失现状（结构性项）,两条都是真实识别出的问题，不是凭空列理论清单;诚实标注 SCP/Organizations 现状 `⚠️ 待确认`,不假装知道优先级里那部分该怎么排。

### G6. 你们 50 集群、6 region 的架构里，AWS 层面最大的运维复杂度来自哪里？

- **一句定位**：开放性总结题，考有没有一个自己的"骨架观点"而不是罗列知识点。
- **展开结构**：复杂度不来自单个 AWS 服务本身，而来自"自建控制面（kubeadm）+ 托管服务（CCM/CSI/CA）+ 业务架构（存算分离/spot 弹性）"三层耦合在一起时，任何一层的假设被打破，故障现象会在另一层表现出来：比如 CA 的静默拒绝表现为"pod 一直 Pending"而不是"AWS 报错",SG 端口收紧表现为"跨节点 Pod 不通"而不是"网络配置错误提示"。
- **我的场景锚点**：这个"故障在 A 层但现象在 B 层"的模式，在 spot scale-from-zero(表现层:调度)、SG+IPIP(表现层:CNI 连通性)、EBS snapshot 懒加载（表现层:查询变慢）三个真实案例里反复出现，值得作为总结性观点讲出来，证明这不是巧合而是自建基础设施的结构性特征。
