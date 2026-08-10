# 07 AWS Fundamentals：compute / storage / network / IAM

## 这个方向我的一句话定位

我不是 AWS 认证意义上的专家，我是**通过 50 个生产 K8s 集群、6 个 region、600+ 节点的实际运维，以及 Doris 存算分离下 spot 弹性算力架构，反向学 AWS 的 SRE**。我的深度集中在 EC2/EBS/S3/VPC/IAM 与 K8s 的接缝处：这是每天会踩坑、会被 oncall 电话叫醒的地方。我们的集群是 kubeadm 自建控制面（不是 EKS 托管），这意味着我在 CCM、CSI、Cluster Autoscaler、instance profile 这些"别人交给托管服务"的层面上有实操经验，但也意味着我在 AWS 托管服务的广度（Organizations、Direct Connect、WAF/Shield、Lambda 生态）上是明确的补课项。这份材料的目标不是把自己包装成什么都懂，而是知道边界在哪、边界内答得多深、边界外怎么诚实退回理论。

## 三环

### 内核（一手玩过，能扛住多层追问）

| 环 | 能力条目 | 一句话说明 | 场景锚点 / 补课标记 |
|---|---|---|---|
| 内核 | EC2 实例族选型与 spot 完整生命周期 | 中断通知 2 分钟、rebalance recommendation、capacity-optimized 分配策略；存算分离让"杀 spot 安全"这个论证能讲透 | Doris CN heavy 池跑在 spot 上，`replicas:0→N` 靠 ASG 拉起（p_elastic_compute.md） |
| 内核 | EBS 卷类型选型 + snapshot 恢复语义 | gp2/gp3 解耦、snapshot 增量与 lazy load、恢复后 initialization 惩罚 | 5.2B 行 EBS snapshot 恢复演练，count 50s / GROUP BY 83s 验证（content_plan.md, mining_notes.md） |
| 内核 | ASG + Launch Template + Cluster Autoscaler | worker 节点自动伸缩全链路，含 CA 的已知失效模式 | 50 集群 worker 全走 ASG+LT+CA（interview-8-k8s-cluster-build.md）；CA scale-from-zero 两类静默拒绝（p_elastic_compute.md） |
| 内核 | VPC 内 K8s 网络排障 | 分层排障法（Client→DNS→LB→Ingress→Service→Pod），timeout vs refused 分类 | `pattern-aws-k8s-networking-troubleshooting-pattern.md`，50 集群跨 6 region 实战 |
| 内核 | S3 作为存算分离冷存储 | file_cache 命中/未命中的真实性能差异，扇出成本与 S3 带宽的关系 | Doris BE `1.3TB nvme file_cache`；冷读吞吐 ~1MB/s、暖查询仍 1.12s 扇出地板（doris_wide_table_point_query_optimization_survey） |

### 中环（做过但不深，有标准口径即可）

| 环 | 能力条目 | 一句话说明 | 场景锚点 / 补课标记 |
|---|---|---|---|
| 中环 | IAM policy 设计与评估顺序 | 显式 Deny 优先、instance profile vs IRSA 的取舍 | 发现并推动过 jenkins.yaml 明文 AWS key 泄露的修复建议（真实案例，见 fundamentals_iam.md） |
| 中环 | 跨 AZ / NAT 流量 | 知道成本模型和典型陷阱，没有专门做过流量成本审计 | 06 目录（cost/FinOps）覆盖成本量化，这里只覆盖机制 |
| 中环 | ELB/NLB 选型 | apiserver 用 internal NLB（L4 透传），业务入口 ingress-nginx 经业务 NLB | interview-8-k8s-cluster-build.md 步骤 4/5 |
| 中环 | EBS CSI driver 与 PVC | PVC 在线扩容（gp2/gp3 + allowVolumeExpansion）我们生产在用；StatefulSet volumeClaimTemplates 首建后不可变是遇到过的坑类型 | 2026-02-25 daily record 提到 EBS-backed StorageClass 在线扩容 |
| 中环 | SG 设计哲学 | 粗粒度信任边界（VPC/VPN/管理网全放行）+ 端口隔离下放 CNI，是有意识的权衡不是疏忽 | interview-8 `roles/aws/tasks/main.yml:3-37` |

### 外环（明确补课，不装懂）

| 环 | 能力条目 | 一句话说明 | 场景锚点 / 补课标记 |
|---|---|---|---|
| 外环 | Organizations / SCP | 多账号治理体系，没有一手经验 | `[纯理论，无一手经验]` |
| 外环 | Direct Connect / Transit Gateway | 混合云专线与多 VPC 互联，没接触过 | `[纯理论，无一手经验]` |
| 外环 | WAF / Shield | 边缘防护，评估未覆盖 | `[纯理论，无一手经验]` |
| 外环 | IRSA / OIDC provider | 知道机制，但我们 kubeadm 自建集群**没有**配 OIDC provider，走的是 node instance profile，这正是 jenkins.yaml 明文 key 事件的背景 | ⚠️ 待确认：是否任何集群已上线 IRSA |
| 外环 | RDS/Aurora、Lambda 等托管服务广度 | 我们数据层自管（MySQL/CH/Doris/YugabyteDB 都是自己在 K8s 上跑），没有托管数据库实操 | `[纯理论，无一手经验]` |
| 外环 | Route53 高级路由（加权/地理/故障转移健康检查） | 知道 DNS TTL 是故障切换时间的物理下限，也知道生产系统通常把切换点放在 LB/target-group 层，但没有配置过这些路由策略 | 见 fundamentals_network.md 第 7 节的理论分析 |

## 面试前一小时速览清单

1. gp2 vs gp3：gp3 把 IOPS/吞吐与容量解耦，3000 IOPS/125MB/s 基线不随容量走，超出走额外计费。
2. EBS snapshot 恢复后有 lazy load：首次读每个 block 要从 S3 拉取，第一轮全量扫描会比稳态慢，这是 5.2B 行恢复验证要跑 count/GROUP BY 而不是只看恢复"完成"的原因。
3. Spot 中断通知只有 2 分钟，rebalance recommendation 更早但不保证一定会中断。
4. capacity-optimized 分配策略优先选中断率低的池子，不是价格最低（lowest-price 会疯狂追低价高中断风险的池子）。
5. Cluster Autoscaler 从字面 0 节点扩容依赖 ASG 的虚拟节点模板（label/taint tag），缺了就静默 Pending，这是我们真实踩过的坑，不是背书本。
6. SG 有状态、NACL 无状态：SG 只评估一次方向，NACL 双向都要显式放行，这也是为什么改 NACL 更容易忘一侧。
7. Calico IPIP 模式下跨节点 Pod 流量走 IP protocol 4，不是 TCP/UDP 端口，SG 收紧成逐端口时最容易漏放行这个。
8. S3 2020 年后是强一致（写后立即读一致，包括覆盖写和删除），但这不等于"没有传播延迟的其他行为"，跨 region 复制、CDN 缓存仍有各自的时延窗口。
9. NAT Gateway 按小时 + 按处理流量 GB 计费，是常被忽视的隐性成本，S3 Gateway Endpoint 可以把去 S3 的流量完全绕开 NAT。
10. IAM policy 评估顺序：显式 Deny 永远赢；没有显式 Deny 时看是否有显式 Allow；都没有则隐式 Deny；SCP/permission boundary 是"天花板"不是"授权"，必须再叠加 identity/resource policy 才真正放行。
11. IRSA 本质是给 K8s ServiceAccount 一个 OIDC 身份，换成对应 IAM Role 的临时凭证；我们的 kubeadm 自建集群目前没有这层，这是诚实的补课项，也是我能主动提出的改进方向。
12. Launch Template 版本管理：新 AMI 要建新版本（不是改旧版本），ASG 指向 `$Latest` 或固定版本号，回滚就是把 ASG 指回旧版本号，这条我们在真实 AMI/ASG 运维文档里有完整流程。
