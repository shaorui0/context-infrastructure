# 04 IaC / CI-CD / K8s 升级：基础回顾（Q&A）

> 标记规则：`[一手]` = 我的真实场景，有 evidence 出处；`[理论]` = 通用知识，用来补答题深度，**面试时不许说成「我做过」**。混合条目标 `[一手 + 理论]`，并在文内分清哪半是哪半。
> Terraform 生态的版本与时间事实来自 2026-07-29 的一次定向网络调研，标 `(src: web 2026-07)`，重要结论附了确信度。

---

# 第一部分：Kubernetes 升级机制深度

## Q1. `kubeadm upgrade` 的实际步骤是什么？[一手 + 理论]

`[理论]` 官方的单集群升级步骤（每个 minor 重复一次）：

1. **控制面第一台**：`apt-mark unhold kubeadm && apt install kubeadm=<ver>` → `kubeadm upgrade plan`（读集群状态，输出可升到哪些版本、有哪些手动动作）→ `kubeadm upgrade apply <ver>`（这一步做真正的活：拉新控制面组件镜像、更新静态 pod manifest、轮转证书、升级 etcd、更新 kube-proxy 与 CoreDNS 的 addon）→ 然后才升 kubelet 与 kubectl 二进制并重启 kubelet。
2. **控制面其余台**：`kubeadm upgrade node`（不是 `apply`）。它不重复做集群级动作，只更新本机的静态 pod manifest 和本地 etcd 成员。
3. **每个 worker**：`kubectl drain <node> --ignore-daemonsets` → `kubeadm upgrade node` → 升 kubelet → `kubectl uncordon <node>`。

一个容易答错的点：**`kubeadm upgrade apply` 只负责控制面，不动 kubelet**。kubelet 是单独升的，这也是为什么 version skew 会成为一个需要理解的约束，kubeadm 的设计假定这两件事分开发生。

`[一手]` 我的实际做法在两处偏离这个默认流程，而且偏离的理由都是可靠性：

- **控制面**：原地 in-place 升级，但用 Ansible `serial: 1` 包起来、每台人工确认，前面挂了 etcd 三项健康检查加强制 snapshot 的门禁 (src: `work-contexts/career/interview/interview-1-k8s_upgrade.md:68`)。
- **worker**：我不 drain + 原地升 kubelet，走**不可变替换**：Packer 出新 AMI（kubelet 版本 = 目标版本）→ 更新 Launch Template（只允许 AMI ID 变）→ ASG Instance Refresh，20% batch，pause-on-failure (src: `interview-1-k8s_upgrade.md:69`)。选 Instance Refresh 不选 Ansible 手动 drain 的理由：Instance Refresh 天然支持 batch size 和 pause-on-failure，并与 ASG lifecycle hook 集成，Ansible 只做 drain 协调和升级后验证 (src: `work-contexts/career/interview/interview-1-k8s_upgrade_reference.md:310`)。

## Q2. 控制面组件与 kubelet 的 version skew policy 具体是什么？[一手 + 理论]

`[一手]` 我实际依赖的三条 (src: `interview-1-k8s_upgrade_reference.md:100-108`)：

| 组件 | 允许偏差 |
|---|---|
| kube-apiserver | N（基准） |
| controller-manager / scheduler | N 或 N-1 |
| kubelet（worker） | N-2 |

这三条的直接后果，也是我升级顺序的机制依据：**kubelet 允许落后 apiserver，反过来不成立**，所以「控制面先行、数据面跟随」在机制上天然安全，不是习惯问题 (src: `interview-1-k8s_upgrade_reference.md:108`；`adhoc_jobs/dynamic_resume_site/content/projects/p_k8s_upgrade.md:47`)。

`[理论]` 补充几条被追问时能加分的细节：

- **HA 控制面内部的 apiserver 之间**允许 1 个 minor 偏差（因为逐台升级期间必然共存），但这个窗口应该尽量短。
- **kubectl** 允许与 apiserver 相差一个 minor（前后都行）。这条在实操里很实际：跳好几个 minor 之后，本地 kubectl 太旧会出现奇怪的字段丢失。
- kubelet 的 N-2 是 1.28 起放宽的（此前是 N-1）。所以「kubelet 能落后两个 minor」这个答案要看目标版本，1.24 时代的严格答案是 N-1。⚠️ 我的 evidence 里写的是 N-2 (src: `interview-1-k8s_upgrade_reference.md:106`)，被追问「1.24 时代也是 N-2 吗」时，诚实答法是「我们的实操从不利用这个余量，逐 minor 推进时 kubelet 落后从不超过一个 minor，所以这个边界对我们不是约束」。这个答法是真的，因为逐 minor 执行本身就把偏差压到了 1。

## Q3. etcd 在升级里的角色：备份、恢复、以及备份救不了什么？[一手]

`[一手]` 健康判定查三件事，缺一不可 (src: `interview-1-k8s_upgrade_reference.md:12-30`)：

| 检查项 | 命令 | 判断标准 | 为什么单独看不够 |
|---|---|---|---|
| member list | `etcdctl member list` | 成员数奇数、全部在线 | 在线不等于同步健康 |
| raft index lag | `etcdctl endpoint status --write-out=table` | follower 落后 leader **> 1000 即 fail** | 这是核心洞察：quorum 名义存在但复制不健康时，升级让一个 member 短暂不可用就会真丢 quorum |
| leader 唯一 | 同上 | 有且只有一个 leader | 脑裂或选举中都不该开始升级 |

fail 条件的完整清单：etcd member < 3 或有 unhealthy 或无 leader、raft lag > 1000、node Ready 低于预期、kube-system 有 CrashLoop/Pending、外部监控有 active alert (src: `interview-1-k8s_upgrade_reference.md:24-30`)。

**备份**：`etcdctl snapshot save` 是升级前的强制动作 (src: `interview-1-k8s_upgrade_reference.md:32`)。

**备份救不了什么**（这是被追问时最能显示深度的一条）：**snapshot 恢复的是数据，不是二进制** (src: `interview-1-k8s_upgrade_reference.md:32`；`p_k8s_upgrade.md:55`)。所以控制面回滚是两个动作的组合：snapshot 恢复 + 二进制降级。`[理论]` 再往下一层：snapshot 恢复会丢掉 snapshot 时点之后的所有写入（也就是 RPO 等于「从 snapshot 到故障」这段时间的所有集群变更），而且 `etcdutl snapshot restore` 会生成一个**新的集群 ID**，所以三个成员都必须一起从同一个 snapshot 恢复，不能只恢复一台再让它加回去。这两条加起来解释了为什么我的真实策略排序是「靠门禁不进坏状态 > 前滚修复 > 回滚」。

`[一手]` 升级期间 **etcd leader 转移是预期行为**，Raft 选举 1-2 秒完成；`serial: 1` 保证 quorum 始终维持。真正的风险是**成员升级后起不来**导致 quorum 丢失、集群不可写 (src: `interview-1-k8s_upgrade_reference.md:63-67`)。这个失效模式是唯一一个 `serial: 1` 也救不了的，因为它不是「同时动了两台」造成的。

## Q4. 1.24 → 1.29 之间的重大 API 变更与移除有哪些？[一手 + 理论]

`[一手]` 我实际处理过、有 evidence 的两条：

- **PodSecurityPolicy 在 1.25 移除** (src: `interview-1-k8s_upgrade_reference.md:110`)。替代是 Pod Security Admission（PSA），语义相反：PSP 是「不配就不管」，PSA 是「namespace 打了 label 就强制」。真实故障形态：Fluentd、node-exporter 这类 DaemonSet 合法需要 privileged，namespace 被草率打成 `enforce: restricted` 会直接被拦死。我的处理是把它当独立问题线：升级前扫存量 workload 并迁移、PSA 先上 `warn`/`audit` 观察、确认零违规才切 `enforce`、infra namespace 显式保持 `privileged` (src: `p_k8s_upgrade.md:47`)。
- **in-tree cloud provider 的交接**：kubelet 的 `--cloud-provider` 从 `aws`（in-tree）改成 `external`（CCM 接管），我们的 Ansible 用条件分支表达 `<1.27` vs `>=1.27`，不分叉代码库 (src: `work-contexts/career/interview/interview-8-k8s-cluster-build.md:66`)。失效形态很脏：CCM 没起来，新 worker 卡在 `uninitialized` taint，节点看着 join 了但排不上 pod (src: `interview-1-k8s_upgrade.md:76`)。这也是 addon 顺序里 CCM 必须第一个的原因。

`[理论]` 其余 minor 的重要变更（用来展示我知道整个地形，**不声称都踩过**）：

| 版本 | 变更 | 影响面 |
|---|---|---|
| 1.24 | dockershim 移除 | 必须换 containerd/CRI-O。**我的起点是 1.24，容器运行时早已是 containerd**（Packer AMI 直接装 containerd + kubeadm，src: `interview-8-k8s-cluster-build.md:16`），所以这个坑不在我这一轮 |
| 1.24 | `ServiceAccount` 不再自动创建长期 token Secret | 依赖 SA Secret 取 token 的外部集成会断 |
| 1.25 | PSP 移除 → PSA；`batch/v1beta1 CronJob`、`policy/v1beta1 PDB` 等 beta API 移除 | manifest 需要批量改 apiVersion |
| 1.26 | CRI v1alpha2 移除（要求 containerd 1.6+）；`autoscaling/v2beta2 HPA` 移除；in-tree AWS/Azure/GCE provider 逐步下线 | 老 containerd 会直接跑不起来 |
| 1.27 | in-tree cloud provider 默认关闭（kubelet 需 `--cloud-provider=external`）；`seccompDefault` 稳定 | **CCM 成为硬依赖** |
| 1.28 | kubelet skew 放宽到 N-3（apiserver 侧看是允许 kubelet 落后 3）；sidecar container（`restartPolicy: Always` 的 initContainer）alpha | 升级窗口更宽松 |
| 1.29 | `flowcontrol.apiserver.k8s.io/v1beta2` 移除；in-tree cloud provider 代码正式删除；`ReadWriteOncePod` 稳定 | 自定义 APF 配置需要迁移 |

被问「你怎么知道要改哪些」时的答法见 Q5。

## Q5. 升级前的兼容性检查怎么做？[一手 + 理论]

`[一手]` 我的做法是**把它当独立问题线，不当升级的一个步骤** (src: `p_k8s_upgrade.md:47`)。流程是：升级前完成存量 workload 扫描与迁移 → 分级 rollout（PSA 先 warn/audit）→ 零违规才 enforce → infra namespace 显式例外。加上 `kubeadm upgrade plan` 会输出该 minor 需要的手动动作，这是官方给的一手检查点 (src: `interview-1-k8s_upgrade_reference.md:43`)。

`[理论]` 完整工具箱（面试里能列出来就够）：

- **API server 侧的实测数据**：`apiserver_requested_deprecated_apis` 指标直接告诉你「现在还有谁在用即将移除的 API」，比扫 manifest 准，因为它抓的是运行时真实调用（包括 controller 和外部集成）。审计日志同理。
- **静态扫描**：`kubent`（kube-no-trouble）扫集群里的资源和 Helm release、`pluto` 扫 chart 和 manifest 仓库。局限：扫不到运行时才发生的调用。
- **CRD 与 addon 的版本矩阵**：CCM 版本必须匹配 K8s minor、Cluster Autoscaler 版本必须 >= K8s 版本 (src: `interview-1-k8s_upgrade_reference.md:193, 200`)。这类约束扫描工具查不到，必须查每个组件的兼容表。
- **client 侧**：老 client-go 的应用可能用了被移除的 API 组；这一类只能靠 `apiserver_requested_deprecated_apis` 加 user-agent 归因。

⚠️ 待确认：我的 evidence 里没有提到 kubent/pluto 或 `apiserver_requested_deprecated_apis` 的使用。这一条以 `[理论]` 讲，被问「你用什么扫的」时诚实答法是「我们的做法是人工扫存量 workload 加 PSA 的 warn/audit 模式作为运行时探测，warn/audit 本质上就是在用 API server 自己做扫描器；如果重做我会加上 `apiserver_requested_deprecated_apis` 的指标监控，因为它覆盖了 manifest 扫描漏掉的运行时调用」。这个答法既诚实又显示我知道更好的做法。

## Q6. 50 个集群的配置差异怎么管？[一手]

`[一手]` 两层加一条原则 (src: `interview-1-k8s_upgrade_reference.md:118-141`)：

第一层，按用途分类 `cluster_type`：`workload`（标准生产，配置高度一致）/ `management`（CI/CD、monitoring，额外 addon）/ `dev-staging`（版本可能落后，PDB 宽松）。

第二层，`feature flag` 解决同类中的少数例外，写在 `group_vars/<cluster>/all.yaml`：`skip_calico_upgrade`、`custom_pdb_override`、`drain_timeout_seconds: 600`（默认 300，用于已知驱逐慢的集群）。

原则：**override 字段越少，集群越标准；flag 数量增长本身被当作分类失准的信号，应该新增一个 cluster_type 而不是继续加 flag** (src: `interview-1-k8s_upgrade_reference.md:139`)。

对 drift 的态度：**不追求消灭，追求在升级前变得可见、可决策**。check 阶段的 baseline snapshot 显式化 current state (src: `interview-1-k8s_upgrade_reference.md:141`；`p_k8s_upgrade.md:51`)。

---

# 第二部分：Kubernetes 核心机制（senior 必问）

## Q7. 调度器怎么工作？亲和性有哪几种，什么时候用？[理论 + 一手]

`[理论]` 调度分两个阶段：**Filter**（predicate，把不可行节点排除：资源不够、taint 不容忍、nodeSelector 不匹配、端口冲突、volume 拓扑不满足）→ **Score**（priority，给可行节点打分：`LeastAllocated`/`BalancedAllocation` 资源均衡、`ImageLocality` 镜像已在本地、亲和性偏好加分）→ 选最高分 → **Bind**。1.19 起可以用 Scheduling Framework 的扩展点（PreFilter/Filter/PostFilter/PreScore/Score/Reserve/Permit/PreBind/Bind）插自定义插件。

四种放置约束，按硬/软和对象分：

| 机制 | 对象 | 硬/软 | 典型用途 |
|---|---|---|---|
| `nodeSelector` | 节点 label | 硬 | 最简单的「必须在这类机器上」 |
| `nodeAffinity` | 节点 label | `required`（硬）/ `preferred`（软，带权重） | 「优先 spot，没有就 on-demand」 |
| `podAffinity` | 同拓扑域内的其他 pod | 硬/软 | 把有网络亲和的服务凑近 |
| `podAntiAffinity` | 同上 | 硬/软 | **散开副本**，最常用 |
| `topologySpreadConstraints` | 拓扑域 + `maxSkew` | `DoNotSchedule` / `ScheduleAnyway` | 比 antiAffinity 更精细的均匀分布（能表达「每个 AZ 最多差 1 个」） |

一个常考的坑：`requiredDuringSchedulingIgnoredDuringExecution` 里的 `IgnoredDuringExecution` 意味着**已调度的 pod 不会因为条件后来不满足而被驱逐**。想要「运行期也维持」需要 descheduler 之类外部组件。

`[一手]` 我的真实关联场景：3 台 master 必须跨 3 AZ，否则单 AZ 挂会丢掉 2 个 etcd、失去多数派、集群变只读 (src: `interview-8-k8s-cluster-build.md:231`)。这条是「单 AZ 改跨 AZ 为生产必改项」的根因，而 repo 现状确实是单 AZ、public/private 子网复用，是明确列出的待改项 (src: `interview-8-k8s-cluster-build.md:150-157`)。

## Q8. requests/limits 与 QoS class 的关系，limits 设不设？[理论]

`[理论]` 三个 QoS class 由 requests 和 limits 的关系推导，不能直接指定：

| QoS | 条件 | 后果 |
|---|---|---|
| `Guaranteed` | 每个容器每种资源都设了 limits，且 requests == limits | 最后被驱逐；能拿到独占 CPU（配合 static CPU manager policy） |
| `Burstable` | 至少设了一个 requests，但不满足 Guaranteed | 中间 |
| `BestEffort` | 完全没设 requests 和 limits | 节点压力下第一个被驱逐 |

两种资源的行为根本不同，这是最容易答错的地方：

- **CPU 是可压缩的（compressible）**：超过 limit 会被 cgroup **throttle**（`cpu.cfs_quota_us`），pod 不死但变慢。所以 CPU limit 的真实成本是 P99 延迟，`container_cpu_cfs_throttled_seconds_total` 是必须看的指标。这也是很多团队主张「CPU 只设 requests 不设 limits」的理由。
- **内存是不可压缩的（incompressible）**：超过 limit 直接 **OOMKill**（cgroup 的 memory.max）。内存必须设 limit，否则一个泄漏的容器会把整个节点拖进 node-level OOM，那时被杀的可能是无辜的邻居。

requests 决定**调度**（scheduler 只看 requests 的总和 vs 节点 allocatable），limits 决定**运行时约束**。所以 requests 设得远低于实际用量会导致节点超卖后被驱逐；设得远高于实际用量会浪费容量并让 Cluster Autoscaler 扩出多余节点（这是一条真实的成本泄漏路径）。

节点侧还有一层：`allocatable = capacity - kube-reserved - system-reserved - eviction-threshold`。所以「节点有 16G 内存」和「pod 能用 16G」永远不相等。

## Q9. 驱逐（eviction）有几种？PDB 到底保护什么？[一手 + 理论]

`[理论]` 两类驱逐，机制完全不同，**只有一类受 PDB 保护**：

- **主动 / voluntary**：`kubectl drain`、node 维护、Cluster Autoscaler 缩容、descheduler。走 **Eviction API**（`pods/eviction` 子资源），**受 PDB 约束**。
- **被动 / involuntary**：kubelet 的节点压力驱逐（内存/磁盘/PID 压力）、preemption、节点直接挂、OOMKill。**不受 PDB 约束**，PDB 在这里只是不存在。

kubelet 的节点压力驱逐顺序：先看 QoS class（BestEffort → Burstable → Guaranteed），同 class 内比「超出 requests 的程度」，再考虑 pod priority。内存压力是硬驱逐（有 grace period 但很短），磁盘压力会先尝试回收镜像和死容器。

PDB 的语义：`minAvailable` 或 `maxUnavailable`，作用是让 Eviction API 在会违反约束时**返回 429 拒绝驱逐**。所以 PDB 不「保护」pod 不死，它只是让主动操作被卡住。

`[一手]` 我踩过的一个反直觉细节：**PDB 在 dark cluster 上依然诚实**。双集群模式下流量已切走，那个集群没有业务流量，PDB violation 不会伤害任何用户，但 drain 还是会被卡住。处理方式是等 PDB 满足或显式调低 `minAvailable`，**绝不强制驱逐** (src: `interview-1-k8s_upgrade_reference.md:84`；`p_k8s_upgrade.md:49`)。这个细节值得讲，因为它说明 PDB 是一个纯语法约束，它不知道也不该知道流量状态。

`[一手]` 分层保护模型，以及**明确列出不覆盖的场景** (src: `interview-1-k8s_upgrade_reference.md:86-94`)：

| 机制 | 保护什么 | 覆盖场景 |
|---|---|---|
| PDB | 主动操作期间的最低副本数 | 升级、节点替换 |
| HPA | 按负载自动扩缩 | 流量突增、节点减少 |
| readiness probe | 新 pod 就绪前不接流量 | 滚动更新 |

不覆盖：硬件故障（involuntary）、应用自身 bug。靠多 AZ 布局 + liveness probe + 监控兜底，而不是假装不存在 (src: `p_k8s_upgrade.md:49`)。

`[一手]` liveness probe 的一个真实反直觉结论：对**基于 quorum 的有状态系统**，liveness 必须保守（高失败阈值、长周期），readiness 保持敏感用于摘流量。KRaft 模式的 Kafka broker 轮流重启，每次都对齐 `Liveness probe failed` 而非任何崩溃信号，每次误杀又强制一轮 controller 重选举，不稳定被层层放大；探针不再抢在系统自愈之前动手，重启风暴即停 (src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md:44`)。

## Q10. controller 模式与 reconcile loop 的本质是什么？[一手 + 理论]

`[理论]` 结构：`for { observe(actual) ; diff(desired, actual) ; converge() }`。实现上是 informer（watch + 本地 cache + resync）→ workqueue（去重 + rate limit + 重试退避）→ `Reconcile(key)` 函数。三条硬要求：

1. **幂等**：`Reconcile` 可能被同一个 key 调用任意多次，包括没有实际变化时（resync）。所以它必须是「读现状 → 算差异 → 只做必要动作」，不能是「执行一串步骤」。
2. **level-triggered 而非 edge-triggered**：它收到的是「这个对象需要检查」而不是「发生了什么事件」。所以丢事件不致命，重新入队就修好了。这是 K8s 可靠性的一个核心设计选择。
3. **不能假设自己是唯一的 writer**：`status` 用 subresource 更新，冲突用 optimistic concurrency（resourceVersion）+ 重试。

`[一手]` 这个模式我在两个地方主动用过它的思想：

- **BKC daemon**（Intel）：把一份文档编译成一个 control loop，desired state 从 prose 和人脑搬到 git，机器可执行、被持续 enforce (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_bkc.md:120`)。而且是两层嵌套 reconcile：systemd 保证 agent 进程活着，agent 保证节点配置不漂移，与 kube-controller-manager 管 pod 同构，只是 target 换成 Linux 加硬件 (src: `p_bkc.md:163`)。**⚠️ 认领边界：只有审计/监控这一半是我构建并跑起来的，完整的风险分级修复模型是设计口径** (src: `p_bkc.md:187`)。
- **反面的一手洞察**：声明式的 reconcile 天生幂等，命令式的 Jenkins pipeline 天生不是，模型里没有任何东西保证一个 job 跑两遍收敛到同一状态 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_jenkins.md:84`)。所以工具不给你的幂等性要自己构造，我构造的三种形态是 skip-if-exists、checkpoint 文件、备份加校验 (src: `adhoc_jobs/dynamic_resume_site/content/integration/jenkins_facts.md:110-113`)。

## Q11. CRD / operator 什么时候值得做？[理论]

`[理论]` CRD 给你的是「一个新的 API 类型 + etcd 里的存储 + kubectl 支持 + RBAC」，operator 给你的是「针对这个类型的领域运维知识的自动化」。判据：

**值得做**：运维动作有**领域特定的顺序或前置条件**，而通用工具（Deployment/StatefulSet）表达不了。典型是有状态系统：数据库的扩容要先加节点再 rebalance 再改路由；升级要按角色顺序（先 follower 后 leader）；备份要 quiesce。这些是「知识」，写在 operator 里就变成了可执行的知识。

**不值得做**：只是想把一堆 YAML 打包 → 用 Helm/Kustomize。只是想在创建时改字段 → 用 mutating webhook。只是想跑一次初始化 → 用 Job 或 initContainer。

CRD 的工程细节里最容易被追问的两个：**版本化与 conversion webhook**（CRD 改字段时怎么让老版本对象还能读，`storage: true` 只能有一个版本），以及 **finalizer 与删除**（finalizer 会让 `DELETE` 只是设 `deletionTimestamp`，控制器必须做完清理再摘掉 finalizer，忘了摘会导致对象永久卡在 Terminating，这是生产上非常常见的一类「删不掉」）。

## Q12. 准入控制（admission）的链路是什么？webhook 出问题会怎样？[一手 + 理论]

`[理论]` API server 的请求链：**认证 → 鉴权 → 准入（mutating admission → schema/OpenAPI 校验 → validating admission）→ 持久化到 etcd**。注意 mutating 在 validating 之前，且 schema 校验夹在两者之间。

两类 webhook 配置对象：`MutatingWebhookConfiguration`（改对象：注入 sidecar、填默认值、加 label）和 `ValidatingWebhookConfiguration`（只能接受或拒绝）。关键字段：

- **`caBundle`**：API server 用它验证 webhook 服务端证书。这是 API server 单向信任 webhook 的唯一凭据。
- **`failurePolicy`**：`Fail`（webhook 不可用则拒绝请求，安全优先，但把 webhook 变成集群写入路径上的单点）/ `Ignore`（放过，可用性优先，但策略被静默绕过）。
- **`timeoutSeconds`**、**`namespaceSelector`/`objectSelector`**（缩小作用面，也是防止 webhook 拦住自己所在 namespace 的手段）、**`reinvocationPolicy`**。
- 一条运维铁律：**webhook 绝不能拦到自己的依赖**（kube-system、webhook 自身的 namespace 要排除），否则 webhook 挂了就永远起不来了。

`[一手]` 我处理过一次这个的生产事故：一次 ingress-nginx 的 helm upgrade 重建了 `ValidatingWebhookConfiguration` 但丢了 `caBundle`，API server 无法验证 webhook 的 TLS，于是所有包含 Ingress 的 helm install 全部报 `x509: certificate signed by unknown authority` 失败 (src: `oncall_track_record.md:20`)。定位关键是路由判断：多个租户在同一分钟以同一机制失败 = 集群级基础设施信号，所以直接跳过应用层。修复是从 Secret 把 CA patch 回去；长期方案是让 webhook 证书脱离一次性 helm hook 管理 (src: `oncall_track_record.md:20`)。

这个故事的机制价值：它是 `failurePolicy: Fail` 的代价的实证，也是「把长生命周期状态（证书）托付给短生命周期机制（helm 的一次性 hook）」这个反模式的实证。

## Q13. CSI 与 PVC 的生命周期？[一手 + 理论]

`[理论]` 链路：`StorageClass`（provisioner + parameters + `reclaimPolicy` + `volumeBindingMode` + `allowVolumeExpansion`）→ 用户建 `PVC` → external-provisioner 看到 PVC 调 CSI `CreateVolume` → 生成 `PV` 并绑定 → pod 调度到某节点 → external-attacher 调 `ControllerPublishVolume`（云侧 attach）→ kubelet 调 `NodeStageVolume`（格式化 + 挂到全局路径）→ `NodePublishVolume`（bind mount 进容器）。删除时按 `reclaimPolicy`：`Delete` 会真删云盘，`Retain` 只解绑。

两个必须知道的点：

- **`volumeBindingMode: WaitForFirstConsumer`**：默认的 `Immediate` 会在 PVC 创建时就 provision 一个卷，而 EBS 是 AZ 局部资源，卷一旦落在 AZ-a，pod 就再也不能调度到 AZ-b。`WaitForFirstConsumer` 把 provision 推迟到调度决定之后，是多 AZ 集群的必需配置。这是最常见的「pod 永久 Pending」根因之一。
- **`accessModes` 的真实含义**：`ReadWriteOnce` 是「单节点可读写」，同一节点上的多个 pod 是可以共享的；想要「只有一个 pod」需要 1.29 稳定的 `ReadWriteOncePod`。EBS 只支持 RWO（多挂载是特例），要 RWX 得用 EFS/NFS。

`[一手]` 我的一手关联：EBS CSI driver 是我们集群 AWS 集成三件套之一，含 retain StorageClass；链路是 PVC 触发 → 建 EBS → attach 到 pod 所在 EC2 → mount (src: `interview-8-k8s-cluster-build.md:122`)。另外「drain 承载数据库 pod 的节点是升级最容易伤到租户的地方」这条一手结论本质上就是 CSI 的 attach/detach 成本：做法是提前测绘数据库节点分布、在每个波次排最前、逐节点推进、每个服务验证通过才走下一个 (src: `p_k8s_upgrade.md:49`)。

## Q14. Service / Ingress / CNI 的分层怎么讲？[一手 + 理论]

`[一手]` 从三个 CIDR 讲起，这是我实际的心智模型 (src: `interview-8-k8s-cluster-build.md:24-30`)：

| 平面 | 谁负责 | 走哪 |
|---|---|---|
| Node 网络 | AWS VPC（我们是 `172.233.0.0/16`） | EC2 ENI 真实网卡 |
| Pod 网络 | CNI（`podSubnet=192.168.0.0/16`） | 隧道或 VPC 原生 |
| Service 网络 | kube-proxy + CoreDNS（`serviceSubnet=10.96.0.0/16`） | 虚拟 IP / iptables |

三者绝不能重叠。Service 网络最特殊：ClusterIP 是一个**不存在的 IP**，没有任何网卡持有它，它只是 iptables/IPVS 规则里的一个匹配目标。理解这一点就能解释为什么 ping ClusterIP 不通但 curl 通。

`[一手]` CNI 的两种哲学与取舍（我能对着真实配置讲）(src: `interview-8-k8s-cluster-build.md:98-112`)：

- **Calico IPIP**（我们的默认）：Pod 用 VPC 不认识的 `192.168.x.x`，跨节点走 IPIP 隧道再包一层。优点：不依赖 AWS、onsite 与 AWS 通用、Pod IP 不占 VPC 地址。代价：封装 MTU 开销（IPIP 头 20B，MTU 降到 1440）、Pod IP 在 VPC 不可见（SG 和 flow log 看不到）、少量 CPU 与延迟开销。
- **Cilium ENI**：不封装，从 VPC 子网给 Pod 分配真实 VPC IP（多 ENI + 前缀委派），eBPF 替掉 kube-proxy（`kubeProxyReplacement=strict`）。优点：无封装开销、SG 能直接作用于 Pod、大规模 Service 转发更快。代价：**消耗 VPC IP**（子网不够大 Pod 起不来，最常见的 ENI 事故）、ENI/IP 上限限制单节点 pod 密度、强耦合 AWS、需要 AWS 凭据。
- 选型判据：默认 Calico 是因为我们有 onsite 交付约束（一套代码要能装云上和客户机房）；换 Cilium 的前置条件是**先算清子网 IP 容量**。

`[一手]` 一个能显示深度的耦合点：IPIP 模式下跨节点 Pod 流量走 **IP protocol 4**，不是 TCP/UDP 端口。SG 从「VPC 内全放行」收紧成逐端口最小化时忘了放行 IPIP proto 4，跨节点 Pod 会完全不通 (src: `interview-8-k8s-cluster-build.md:197`)。这是安全加固和网络可用性之间的真实耦合。

`[一手]` Service 平面：kube-proxy 用 **iptables 模式**（ipvs 配置存在但未启用）。Calico 安装顺手把 conntrack 表调大（`maxPerCore`/`min` → 524288），防高并发下 conntrack 打满丢包 (src: `interview-8-k8s-cluster-build.md:114`)。换 ipvs/eBPF 的条件是 Service 数极大（数千以上）(src: `interview-8-k8s-cluster-build.md:243`)。

`[一手]` 入口分两层：控制面入口是 internal NLB(L4) 挂 3 台 master 的 TCP 6443（选 NLB 不选 ALB 是因为 apiserver 是 TLS + gRPC，需要 L4 透传不做 TLS 终止）(src: `interview-8-k8s-cluster-build.md:200-202`)；业务入口是 `type=LoadBalancer` + `aws-load-balancer-type: nlb` annotation，CCM 建业务 NLB → ingress-nginx → 按 Host/Path 路由，有 internal/external 两套；onsite 用 MetalLB L2 模式（给一段局域网 IP，ARP 广播认领）(src: `interview-8-k8s-cluster-build.md:204-206`)。

`[理论]` Ingress 与 Gateway API 的关系：Ingress 的表达力止于 Host/Path，厂商差异全靠 annotation，所以它事实上不可移植。Gateway API 用 `GatewayClass`/`Gateway`/`HTTPRoute` 分离了「基础设施提供者」「集群运维」「应用开发」三个角色的关注点，并把流量拆分、header 匹配、跨 namespace 引用做成一等公民。2026 年的正确答法是：Ingress 仍是存量主流，新建应该看 Gateway API。

## Q15. CCM / Cluster Autoscaler 这类云集成组件的失效形态？[一手]

`[一手]` 三个 addon 的影响窗口与最坏情况 (src: `interview-1-k8s_upgrade_reference.md:185-200`)：

| Addon | 核心功能 | 升级影响窗口 | 最坏情况 |
|---|---|---|---|
| Calico | Pod 网络 / NetworkPolicy | `calico-node` DaemonSet rolling restart | Pod 间网络中断 |
| AWS CCM | node lifecycle、LB 创建更新、EBS attach | controller pod restart | 新 LB 无法 provision，存量不受影响 |
| Cluster Autoscaler | node scale-out/in | pod restart | scale 请求堆积，不影响已有节点 |

升级顺序 CCM → Calico → CA，每个有独立 gate (src: `interview-1-k8s_upgrade.md:74-78`)：

- **CCM**（第一个，因为 CCM 不健康会让新 worker 卡在 `uninitialized` taint）：验 pod Running + **所有 node 都有 `spec.providerID`** + 存量 LB Target Group 有 healthy instance。CCM 重启后会重新 reconcile node 的 providerID，缺失的话该 node 不会被注册到 LB Target Group，ASG 也可能误判节点状态 (src: `interview-1-k8s_upgrade_reference.md:193-196`)。TG 为空的常见原因：CCM 未运行 / IAM 权限不足 / node 缺 cluster tag / node 缺 providerID / `externalTrafficPolicy: Local` 的瞬态 (src: `interview-1-k8s_upgrade_reference.md:198`)。
- **Calico**：先 `calico-kube-controllers`（不影响数据面）再 `calico-node`（`maxUnavailable: 1`），验跨节点 pod-to-pod ping。BGP 模式下 `calico-node` 重启会导致 BGP session 断开约 5-30s，缓解是 graceful restart 或切 VXLAN overlay (src: `interview-1-k8s_upgrade_reference.md:191`)。
- **CA**：版本必须 >= K8s 版本；验证方式是 drain 一个节点触发 scale-out 成功 (src: `interview-1-k8s_upgrade_reference.md:200`)。

`[一手]` CA 的完整闭环与真实时延：Pod Pending → CA 调 AWS 扩 ASG → 新 EC2（Packer AMI）启动 → userdata `kubeadm join` → 成为 worker (src: `interview-8-k8s-cluster-build.md:124`)。我实测过 spot 节点冷启动约 9 分钟，分解是 CA 扩 spot ASG 约 70s、kubeadm join 约 80s、init container 约 50s、镜像拉取约 200s (src: `rules/skills/workflow_dcluster_starrocks_cn_deployment.md`「等待 pod 就绪」节)。这个分解很有用：最大项是镜像拉取，所以优化杠杆在镜像层而不在扩容速度。

---

# 第三部分：IaC 原理

## Q16. 声明式 vs 命令式，真正的区别是什么？[一手 + 理论]

`[理论]` 教科书答案是「声明式描述 what，命令式描述 how」。这个答案在面试里不够，因为它不产生任何可操作的结论。更好的答法是从三个可观测性质切入：

| 性质 | 声明式 | 命令式 |
|---|---|---|
| 重跑第二遍 | 收敛到同一终态（no-op） | 无保证，可能叠加副作用 |
| 「现在是否符合期望」 | 可以随时算（有 desired 可比） | 无法回答，只有「上次跑成功了」 |
| 中途失败 | 重跑即可 | 需要人判断进行到哪一步 |

`[一手]` 我的一手判断，也是最能拉开档次的一句：**声明式的 reconcile 天生幂等，命令式的 pipeline 天生不是，模型里没有任何东西保证一个 job 跑两遍收敛到同一状态**。这不是回避命令式工具的理由，恰恰是「熟悉 Jenkins」成为一项可靠性工程能力的原因：工具不给你的幂等性，要靠你自己构造出来 (src: `p_jenkins.md:84`；`work-contexts/career/interview/interview-5-cicd_reliability.md:33`)。

`[一手]` 一个重要的补充：**声明式工具也可能骗你**。我们 Ansible 里大量 role 直接 `shell` 调 `helm upgrade --install` 或 `kubectl apply` 兜底，结果是不真正幂等、`--check` 失效（也就是 dry-run 会骗人）、错误埋在 shell 输出里。这是我们 codebase 最大的技术债之一 (src: `interview-8-k8s-cluster-build.md:74`)。所以「用了声明式工具」不等于「拿到了声明式的性质」，判据要落在实际行为上。

## Q17. 幂等性的真实含义是什么？[一手]

`[一手]` 这是我有一手洞察的地方，答案分三层。

**第一层，形状**：我的修复脚本全部遵循同一个形状 `guard → 备份 → 收敛 → verify` (src: `p_jenkins.md:34, 92`)。apt 修复脚本先确认自己确实跑在 Buster 上，否则空操作退出；带时间戳备份现有配置；然后**整体覆写**配置而不是逐行打补丁；依赖修复脚本结尾是显式的 verify 函数，断言制品此刻确实存在，而不是假设成功。

**覆写而不是打补丁**这个选择是关键：覆写到已知良好状态是收敛的，第二次运行产生和第一次相同的终态，跑两遍安全、断在中间没有代价。反例是追加行或假设初始状态干净的脚本：跑两遍，一个事故变成两个 (src: `p_jenkins.md:92`)。

**第二层，判定权的位置**：幂等的判定必须基于**目标状态的实测**，不能基于调用者的记忆。两个一手实证：
- FORCE_BUILD 参数逐层透传到叶子 job，由叶子 job 自己查镜像 tag 是否已存在再决定跳过 (src: `jenkins_facts.md:110-111`)。判定权留在唯一知道真相的那一层。
- K8s 升级里判断「这一步到底完成了没有」用的是**镜像版本 × health 四象限**的集群实测，不信 `state.yaml` (src: `interview-1-k8s_upgrade_reference.md:69-76`)。

**第三层，幂等不等于可重入，这是我算错过的地方**：Ansible 的幂等只覆盖 module 级。drain 是幂等的（已 drain 的节点再跑无 pod 可驱逐，直接成功），但 kubelet 的中间状态超出 idempotency 范围：master 原地升级或 worker 换节点失败在中途，都需要人工介入；`state.yaml` 只告诉你从哪步接手，不告诉你集群的真实状态 (src: `interview-1-k8s_upgrade_reference.md:154-157, 55-56`)。所以更准确的抽象是两个独立问题：**从头重跑安全吗**（幂等），以及**我怎么从实测判断这一步是否完成**（可判定）。第二个才是恢复的入口。

`[一手]` 诚实边界：我做的是**操作级幂等**（skip-if-exists、checkpoint 文件、备份加校验），不是声明式 reconcile；而且修复脚本大多 `set -e` 快速失败但没有事务回滚，dry-run 只存在于诊断脚本里、修复脚本没有 (src: `jenkins_facts.md:116`)。

## Q18. drift 检测与收敛怎么做？[一手 + 理论]

`[理论]` drift 的来源三类：人手改（`kubectl edit`、控制台点、SSH 上机）、其他自动化改（另一个 controller、云厂商的自动行为）、以及**外部世界变了而配置没变**（上游仓库下线、base image EOL、证书过期）。第三类最难，因为配置本身没动，是它的假设过期了。

检测手段：`terraform plan` 类的 diff、controller 的持续 reconcile（一直在检测所以不需要单独的检测）、以及独立的审计器（读现状 vs 读期望）。

收敛的三种态度：**自动收敛**（controller 模式）、**报告不收敛**（审计器，让人决定）、**阻止漂移**（策略引擎 + 权限收紧，让人改不了）。三者不是替代关系，成熟体系三者都有。

`[一手]` 我在三个地方处理过 drift，三种态度都用过：

- **报告不收敛**：50 集群升级里的 drift 处理。**不试图消灭所有 drift，而是让 drift 在升级前变得可见、可决策**：check 阶段的 baseline snapshot 显式化 current state；残余差异用 `cluster_type` 分类加 per-cluster feature flag 表达；**flag 数量增长本身被当作分类失准的信号** (src: `interview-1-k8s_upgrade_reference.md:141`；`p_k8s_upgrade.md:51`)。
- **自动收敛 + 报告，按风险分档**：BKC daemon 的核心设计就是这个。⚠️ 认领边界：审计与报告这一半是我构建并跑起来的；带 drain、维护窗口、重启协调的完整风险分档（🟢 在线可逆立即改 / 🟡 需先 drain / 🟠 需维护窗口加重启 / 🔴 只审计绝不自动改）是设计口径 (src: `p_bkc.md:169-172, 187`)。**这个项目最有价值的一条结论是：audit 独立于 update 就有独立价值**。即便某项 controller 从不改，持续产出每节点 compliance 加 drift 时间戳本身就点亮了「静默降级」这个盲区，还成了交付合规的凭证 (src: `p_bkc.md:185`)。
- **第三类 drift 的实证**：Jenkins 迁移时暴露的东西全是「配置没动但假设过期」：上游 Maven 仓库失联、Debian Buster EOL、只活在运行中 pod 里的手工 Maven 配置 (src: `jenkins_facts.md:36-38`；`p_jenkins.md:112`)。这类 drift 的检测手段不是 diff，是**定期真的重跑一遍**（重建镜像、清缓存重新拉依赖）。这也是我认为「能从零重建」是比「能维持运行」更强的可靠性属性的原因。

## Q19. 不可变基础设施与 Packer 的定位是什么？边界在哪？[一手]

`[一手]` **分层判据是变更频率**：Packer 固化「慢且稳定」的部分（装包），Ansible 做「快且多变」的部分（配集群）。所以 AWS 部署能跳过装 containerd/k8s（AMI 已含），onsite 必须现装 (src: `interview-8-k8s-cluster-build.md:51`)。AMI 内容是 OS + containerd + kubeadm (src: `interview-8-k8s-cluster-build.md:16`)。

`[一手]` 不可变带来的三个具体好处，我都用到过：

1. **升级退化成换机器**：worker 的「升级」不是「改一台机器」而是「新 AMI → 更新 LT → Instance Refresh」，失败路径从「修一台半死的节点」变成「回退一个 LT 版本」(src: `interview-1-k8s_upgrade.md:69`)。
2. **回滚路径就是日常路径**：容量受损时的操作规则是先回滚到已知良好的 launch template 或 AMI 恢复容量，再追根因 (src: `oncall_track_record.md:56`)。这和升级的回滚动作是同一个动作。**回滚路径应该是日常已经在走的路径，而不是只在应急计划书里存在的路径**。
3. **plan 的可验证性**：worker 侧的 plan 就是 AMI diff（kubelet 必须等于目标版本）加 LT diff（只允许 AMI ID 变化）(src: `interview-1-k8s_upgrade_reference.md:43`)。变更集小到可以逐项确认。

`[一手]` 边界两处：

- **有状态节点**。承载数据库 pod 的节点不能随便换，drain 它就是在动数据面。所以数据库节点要提前测绘、在每个波次排最前、逐节点推进、每个服务验证通过才走下一个 (src: `p_k8s_upgrade.md:49`)。不可变的成本随节点的状态量线性上升。
- **反馈周期**。不可变意味着任何一行配置改动都要重新出镜像，反馈周期从秒级变成分钟到小时级。所以把高频变更的东西塞进 AMI 是最常见的分层错误。我实测过这个代价的另一面：spot 节点冷启动 9 分钟里镜像拉取占 200s，是最大单项 (src: `workflow_dcluster_starrocks_cn_deployment.md`)。镜像层的成本既出现在构建端也出现在启动端。

## Q20. 配置管理（Ansible）与编排（K8s）的边界在哪？[一手]

`[一手]` 我的分层就是这条边界的答案，四层 (src: `interview-8-k8s-cluster-build.md:12-17`)：

```
Layer 3  集群内组件   CNI / CCM / CSI / Ingress / 监控日志   ← K8s 编排（声明式 API + controller）
Layer 2  K8s 控制面   kubeadm init/join + etcd              ← Ansible（一次性建立，之后由 K8s 自己维持）
Layer 1  AWS 基础设施  SG / EC2 / NLB / TG / ASG / LT        ← Ansible（VPC/Subnet/NAT/IAM 是 repo 外手动预建）
Layer 0  机器镜像     Packer AMI（OS + containerd + kubeadm）← Packer（不可变）
```

边界的判据是**谁在持续维持这个状态**。Layer 3 的期望状态由 K8s 的 controller 持续维持（我只需要 apply 一次，之后它自己收敛）；Layer 0/1/2 没有任何东西在持续维持，所以需要一个外部的 agent 在需要的时候跑一遍。

`[一手]` 这条边界的一个真实推论：**Ansible 的角色是「建立」而不是「维持」**。它没有 state 文件、没有 plan 预演、没有 drift detection、没有安全的 destroy、没有并发锁，它靠每个 module 自己查 AWS API 判断幂等，缺全局视图 (src: `interview-8-k8s-cluster-build.md:46`)。承认这一点是回答「为什么不用 Terraform」的前提，见 `terraform_honest_answer.md`。

`[一手]` Ansible 侧的组织哲学三句话 (src: `interview-8-k8s-cluster-build.md:57-60`)：Role 即组件（58 个 role，一个 role 等于一个可独立装的组件，标准结构 `tasks/{main,prepare,install,configure}.yml` + `templates/` + `defaults/`）；Playbook 即编排顺序（`00-install-all-aws` 就是依赖拓扑的线性化：CNI 必须在 master join 之后、业务组件必须在 CCM/CSI 之后）；Jinja2 模板即配置生成（`kubeadm_config.yaml.j2` 是整个体系的枢纽）。

需要掌握的 Ansible 概念清单（自查用）：inventory / group_vars / host_vars、变量优先级（defaults < inventory < vars < extra-vars）、Jinja2、handler、tags（局部重跑）、`--check --diff`、`delegate_to` / `run_once`、`async` / `serial` (src: `interview-8-k8s-cluster-build.md:76`)。

`[一手]` 我实际依赖的五个 Ansible 特性及其用途 (src: `interview-1-k8s_upgrade_reference.md:254-262`)：`--check` 做 plan 阶段 dry-run、`--diff` 把 before/after 写进 evidence、module 幂等支持中断后重入、`serial: 1` 逐节点控制 blast radius、tags 单独跑某阶段。

---

# 第四部分：Terraform（重点补课）

> **这一整部分全部是 `[理论]`。我没有 Terraform 的生产经验。** 面试口径见 `terraform_honest_answer.md`。
> 版本与生态事实来自 2026-07-29 的定向调研 `(src: web 2026-07)`。

## Q21. 核心工作流 init / plan / apply / destroy 的语义分别是什么？[理论]

| 命令 | 干了什么 | 容易答错的地方 |
|---|---|---|
| `init` | 下载 provider 与 module、初始化 backend、写 `.terraform.lock.hcl` | 它**不**读远程 state 的内容做任何决策，只是建立连接。改 backend 需要 `init -migrate-state`；改 provider 版本约束需要 `init -upgrade`（否则会沿用 lock 文件里的版本） |
| `plan` | 刷新 state（读真实资源）→ 与配置 diff → 输出 CRUD 动作图 | plan 是**只读**的，但它默认会做 refresh，也就是会调很多云 API（大 state 慢就慢在这里，`-refresh=false` 可以跳过但会用陈旧数据）。plan 的结果可以 `-out=tfplan` 保存，`apply tfplan` 才是「所见即所执行」；不保存直接 `apply` 会重新 plan 一遍，中间世界可能变了 |
| `apply` | 按依赖图执行，默认并发 10（`-parallelism`），每完成一个资源就写 state | **apply 中途失败 state 是部分更新的**，不是全有或全无。所以「apply 失败了怎么办」的正确答案是「再 plan 一次看现在差什么」，而不是「回滚」，Terraform 没有回滚 |
| `destroy` | 反向遍历依赖图删除 | `-target` 可以只删一部分，但用 `-target` 本身是个警告信号（说明模块边界划错了） |

一条常被追问：**Terraform 没有回滚**。「回滚」在 TF 语境里的真实含义是「把配置改回上一个 git commit 然后 apply」，而这在有不可逆动作时（删了数据库、换了不能原地改的资源）不等价于恢复。这一点和我在 K8s 升级里的结论是一样的：真正的策略是靠 plan 门禁不进入坏状态，前滚修复优先于回滚。

## Q22. state 文件是什么？为什么它是唯一真相源？[理论]

state 是「TF 管理的资源」与「云上真实资源」之间的**映射表加最近一次已知属性快照**。它至少承担四个职责：

1. **身份映射**：配置里的地址 `aws_instance.web[0]` ↔ 云上的 `i-0abc123`。没有这个映射，TF 无法知道「这个配置块对应的东西是否已存在」，就只能每次都创建。这是它「唯一真相源」的核心含义：**云上资源不携带「我属于哪个 TF 配置块」的信息，只有 state 知道**。
2. **属性缓存**：用于 diff，也用于把一个资源的输出喂给另一个资源。
3. **依赖记录**：`dependencies` 字段记录创建时的依赖关系，destroy 时按它反向删（因为配置可能已经删掉了那些引用）。
4. **元数据**：serial（版本号）、lineage（血统 ID）、provider 配置引用。

**为什么它这么危险**：state 丢了不等于资源丢了，但等于 TF 失忆，下一次 apply 会试图重新创建一切（对已存在的资源会报 already exists，或者更糟，创建了重复资源）。state 被两个人同时写会互相覆盖，导致部分资源脱管。

**secret 进 state**：这是必须知道的一条。TF 会把资源的属性原样存进 state，包括 RDS 密码、私钥、`aws_secretsmanager_secret_version` 的值。`sensitive = true` 只影响 CLI 输出的显示，**不影响 state 里的存储**。所以后果是 state 文件必须当作 secret 对待：backend 必须加密、访问必须受限、绝不进 git。缓解手段：S3 backend 开 SSE-KMS + bucket policy、把 secret 改成 `ephemeral`/write-only（见 Q29）、或者干脆让 TF 只管 secret 的**引用**而不管它的值（TF 创建一个空的 Secrets Manager secret，值由别的流程写入）。

## Q23. remote backend 与 state locking 怎么工作？[理论]

**为什么要 remote**：本地 state 无法多人协作、笔记本丢了 state 就丢了、也没有锁。

**S3 backend 的现代形态** `(src: web 2026-07)`：Terraform **1.10** 引入了 S3 原生锁（基于 S3 的条件写，`use_lockfile = true`），**DynamoDB 锁表已被弃用**（1.15 时还没移除但已标记未来移除）。所以 2026 年的正确答案是「S3 backend + `use_lockfile = true`，不再需要 DynamoDB 锁表」，而经典的「S3 存 state + DynamoDB 做锁」是历史形态。OpenTofu 在 1.10+ 也独立实现了等价能力。

推荐的 S3 backend 配置要素：`bucket` + `key`（每个环境/组件独立 key）+ `region` + `encrypt = true` + `kms_key_id` + `use_lockfile = true` + bucket 开版本控制（这是 state 损坏时的救命绳）。

**锁的语义**：TF 在 `plan`（会 refresh 所以也要锁）和 `apply` 期间持有锁。锁没释放（进程被 kill）会导致后续操作报 `Error acquiring the state lock`，`force-unlock <LOCK_ID>` 是逃生门，但**用它之前必须确认没有别的 apply 真的在跑**，否则就是双写。

**HCP Terraform**（原 Terraform Cloud）`(src: web 2026-07)`：托管 backend + 远程执行 + 状态版本历史 + 策略（Sentinel/OPA）+ 团队权限。2026 年的现状是：IBM 于 2025-02-27 完成对 HashiCorp 的收购（$6.4B），2025-09-01 起产品线改名（HCP Terraform Plus/Premium → IBM Terraform Standard/Premium），**免费层已停止，legacy Free plan 在 2026-03-31 EOL**，计费按 RUM（resource under management）每资源每月计（2026-02 公布的档位是 Essentials $0.10 / Standard $0.47 / Premium $0.99）。BUSL 许可在收购后**没有**回退到 MPL。

## Q24. state 损坏或资源脱管怎么救？import 怎么用？[理论]

按「问题的形状」分四类，这也是被追问时最好的组织方式：

**1. 资源存在于云上但不在 state 里**（手工建的、或者 TF 之前失败了但资源已创建）→ **import**。
- 老形态：`terraform import aws_instance.web i-0abc123`，命令式、一次一个、且**只改 state 不生成配置**，你得自己把 HCL 写对（写不对下一次 plan 就要改真实资源）。
- 现代形态 `(src: web 2026-07)`：Terraform **1.5** 引入了 `import` **block**（config-driven import，可以进 plan、可以被 review、支持 `-generate-config-out=generated.tf` 自动生成配置骨架）。OpenTofu 1.7 更进一步支持 loopable import block（`for_each`）。这是 2026 年该给的答案：import 应该是 PR 里一个可 review 的声明，不是某人本地敲的一条命令。

**2. 资源在 state 里但云上已经没了** → `terraform state rm`（老）或 `removed` block（TF **1.7** 引入，config-driven，能进 plan 被 review）`(src: web 2026-07)`。区分 `removed` 和 `destroy`：`removed` 是「TF 不再管它」，不删真实资源。

**3. 资源地址变了但东西没变**（重命名、搬进 module）→ **`moved` block**（TF **1.1** 引入）`(src: web 2026-07)`。这是关键：如果不用 `moved`，改名会被 plan 解读为「销毁旧的 + 创建新的」，对数据库就是灾难。`moved` 让重构变成纯 state 操作。老办法是 `terraform state mv`，命令式、不可 review。

**4. state 文件本身坏了/丢了** → 逃生路径按代价排序：
- S3 bucket 版本控制回滚到上一个版本（**这就是为什么必须开版本控制**）。
- `terraform state pull > backup.tfstate` 手工编辑再 `terraform state push`（危险，serial 要对，lineage 不能变）。
- 最坏情况：从零 import 全部资源。这就是「大 state 是风险」的具体含义：state 越大，这条路越不可能走完。

**一条被问到就能加分的纪律**：任何直接改 state 的操作之前先 `terraform state pull` 存一份，以及优先用 config-driven 的 `import`/`moved`/`removed` block 而不是 `terraform state` 子命令，因为前者留在 git 里、能被 review、能被 plan 验证。这条纪律和我在 K8s 那边的做法同构：把隐式的人工操作变成显式的、可评审的声明。

## Q25. resource vs data source 的区别与陷阱？[理论]

`resource` 是「我负责它的生命周期」，`data` 是「我只读它」。三个陷阱：

1. **data source 在 plan 期求值**，所以如果它依赖的东西是同一次 apply 里才创建的，plan 时读不到（表现为 "value not known until apply" 或直接失败）。解法是显式 `depends_on`，或者干脆用 resource 的输出属性而不是绕一圈 data source。
2. **data source 让 plan 变得不确定**：`data "aws_ami" "latest"` 配 `most_recent = true` 意味着上游发新 AMI 你的 plan 就变了，可能在你完全没改代码时触发实例替换。生产上应该 pin 具体 AMI ID（这正好回到我的一手观点：AMI 应该是版本化的不可变工件，见 Q19）。
3. **用 data source 引用另一个 state 的输出**（`terraform_remote_state`）会造成跨 state 的隐式耦合，而且要求读方有对方 state 的读权限（state 里有 secret，等于扩大了泄露面）。更好的解法是通过一个显式的契约层传递（SSM Parameter Store / Secrets Manager / 云资源的 tag 与命名约定）。

## Q26. module 怎么设计？版本约束怎么写？[理论]

**module 的边界应该按什么划**：按「生命周期 + blast radius + 所有权」，不是按「技术分层」。一个好的判据是：**放在同一个 module 里的资源应该总是一起被 apply，且失败时影响同一批人**。把 VPC 和应用放同一个 module 是经典错误，因为 VPC 的变更频率是年级、应用是天级，而 VPC 的 blast radius 是全账号。

**接口设计**：变量要有 `type`、`description`、`default`（或显式无默认表示必填）、`validation` block（早失败胜过 apply 时失败）；输出只暴露下游真正需要的，暴露越多耦合越强。不要让 module 内部资源名成为事实上的公共接口（那会让重构必须配 `moved` block）。

**版本约束**：
- module source 用 git tag 或 registry 版本，**`version = "~> 3.1"`（允许 3.1.x）比 `>= 3.1` 安全**，生产环境的根 module 建议直接 pin 精确版本。
- provider 用 `required_providers` 里的 `version` 约束 + **`.terraform.lock.hcl` 提交进 git**（这是 provider 的 lock 文件，锁到精确版本加 hash，作用等同于 `package-lock.json`）。`required_version` 约束 TF 自身版本。
- 一条纪律：**module 不应该自己声明 provider 配置**（provider block），只声明 `required_providers`；provider 实例由根 module 传入。否则 module 无法在多 region/多账号场景复用。

**反模式**：过早抽象出「万能 module」（参数比资源多）、module 嵌套超过两层（调试时定位地址变成噩梦）、以及用 module 包装单个资源（除了增加一层地址什么也没得到）。

## Q27. count 与 for_each 的区别？为什么这个区别很重要？[理论]

这是 TF 面试最经典的问题之一，因为它直接暴露对 state 的理解深度。

- `count` 产生的地址是**索引**：`aws_instance.web[0]`、`[1]`、`[2]`。
- `for_each` 产生的地址是**键**：`aws_instance.web["us-west-2a"]`。

**为什么重要**：从 list 中间删掉一个元素，`count` 会让后面所有元素的索引往前挪一位，于是 TF 认为 `[1]` 的内容变了、`[2]` 的内容变了、`[3]` 不再存在，一次删除引发**一连串的 destroy/create**。`for_each` 的键是稳定的，删掉一个键只影响那一个资源。

所以规则是：**只在「这些东西完全同质且只有数量意义」时用 count（例如 `count = var.enabled ? 1 : 0` 做条件创建），一旦元素有身份就用 for_each**。

配套知识：`for_each` 的 key 必须在 plan 时已知（不能依赖另一个尚未创建资源的属性，否则报 "Invalid for_each argument"）；修正历史遗留的 `count` → `for_each` 迁移正是 `moved` block 的典型用例。

## Q28. lifecycle 的几个 meta-argument 分别解决什么问题？[理论]

| 参数 | 解决的问题 | 陷阱 |
|---|---|---|
| `prevent_destroy = true` | 给数据库、S3 bucket 这类不可逆资源上保险栓，任何会删它的 plan 直接报错 | 它会让 `terraform destroy` 整体失败（包括你真想删的时候）；也无法阻止「先改一个 force-new 的属性导致 replace」这条路径 |
| `ignore_changes = [tags, desired_capacity]` | 承认某些字段会被外部合法修改（自动打的 tag、被 ASG/autoscaler 改的容量），不要每次 plan 都想改回去 | 它是**放弃对该字段的管理**，不是「不检测」。用它意味着这个字段的真相源不再是 TF。滥用会让配置慢慢变成小说 |
| `create_before_destroy = true` | 需要替换的资源先建新的再删旧的，避免中断 | 同时存在两个会撞名字/撞唯一约束（安全组名、IAM role 名），所以通常要配 `name_prefix` 而不是 `name` |
| `replace_triggered_by = [...]` | 显式声明「那个东西变了就重建我」 | TF 1.2+；用它之前先想清楚是不是模块边界划错了 |
| `precondition` / `postcondition` | 在 plan/apply 时断言假设（TF 1.2+） | 这是 IaC 里最接近「单元测试」的东西，被问「你怎么保证配置正确」时是个好答案 |

一个跨领域的连接：`create_before_destroy` 就是 blue/green，`ignore_changes` 就是承认双写真相源，`prevent_destroy` 就是不可逆操作设人工闸门。这三个和我在 K8s 与 CI/CD 里的判据是同一套。

## Q29. workspace vs 目录隔离，多环境怎么组织？[理论]

**`terraform workspace`**：同一份配置、同一个 backend、多个 state（S3 key 变成 `env:/<workspace>/<key>`）。适合「完全同构、只有参数不同」的环境。

**它的三个致命问题**（这是为什么业界主流不用 workspace 做环境隔离）：
1. **共享同一个 backend 和同一套凭据**，所以 dev 和 prod 的 state 在同一个 bucket、同一个权限域里。真正的环境隔离应该连账号都分开。
2. **配置无法差异化**：prod 要 3 个 AZ、dev 要 1 个，只能靠 `count = terraform.workspace == "prod" ? 3 : 1` 这种条件，配置很快变成条件语句的森林。
3. **切错 workspace 就完蛋**：`terraform apply` 前忘了 `workspace select`，没有任何东西提醒你。目录隔离下 prod 在 `envs/prod/` 里，路径本身就是提示。

**推荐形态**：目录隔离 + 共享 module。
```
modules/            # 可复用组件，带版本
  vpc/  eks/  rds/
envs/
  dev/    main.tf backend.tf terraform.tfvars   # 独立 backend key（甚至独立账号）
  stage/  ...
  prod/   ...
```
每个环境目录一个独立 backend key、独立的 provider（可以指向不同 AWS 账号）、独立的 CI 流水线与审批策略。代价是有重复（每个环境一份 `main.tf`），但这个重复换来的是**环境之间没有共享的失败面**，值得。

进一步的现代选项 `(src: web 2026-07)`：**Terraform Stacks** 在 **TF 1.13** GA，专门解决「多个相关组件作为一个可部署单元」的编排问题（此前要靠 Terragrunt 之类的 wrapper）。它把多 workspace 编排折进主 CLI。注意计费：Stacks 的资源也计入 RUM。被问到「多环境怎么做」时提一句 Stacks 能显示知识是新鲜的，但要诚实说「我没有用过」。

## Q30. Terraform 与 Ansible 的职责边界？[理论 + 一手]

`[理论]` 标准分工：**Terraform 做 provisioning（创建和管理资源的存在与形态），Ansible 做 configuration（管理机器内部的状态）**。判据是「这个东西的期望状态是不是云 API 能表达的」。

三条实操纪律：
1. **不要用 `provisioner "remote-exec"` 跑配置**。它不幂等、失败会把资源标 tainted、且不出现在 plan 里。官方自己把 provisioner 列为最后手段。要配机器就用 user-data 引导（云原生）或者 TF apply 完之后由独立流水线跑 Ansible。
2. **不要让 Ansible 去建云资源**（`amazon.aws` 那些 module），除非你接受没有 plan、没有 drift detection、没有安全 destroy。
3. **交接面用显式契约**：TF 输出资源信息（到 SSM Parameter / tag / 或者 Ansible 的动态 inventory 插件直接查云 API），Ansible 消费它。不要靠人肉复制 IP。

`[一手]` 我的真实场景恰好是这条边界的**反例**，而且我能讲清它为什么在我们的场景下成立：我们用 Ansible 管 AWS 资源（Layer 1）而不是 TF。优点是一套工具同时「建资源 + 配机器」，不用在 TF（建）和 Ansible（配）之间传 state 和 IP。具体到代码，`roles/aws/tasks/main.yml:189` 用 `sed -i` 把新建 NLB 的 DNS 直接回写进 `hosts-aws` 的 `controlPlaneEndpoint`，建完即用 (src: `interview-8-k8s-cluster-build.md:44-45`)。代价我也清楚：**没有 state 文件，所以没有 plan 预演、没有 drift detection、没有安全 destroy、没有并发锁**；Ansible 靠每个 module 自己查 AWS API 判幂等，缺全局视图 (src: `interview-8-k8s-cluster-build.md:46`)。结论：适合「少量长生命周期集群 + 建机器配机器一体化」；集群数量爆炸、或者要 PR-based review 加 drift detection 时，应该改成 TF 管 Layer 1、Ansible 管 Layer 0/2/3 (src: `interview-8-k8s-cluster-build.md:47`)。

**这个「我知道我们的选择的代价」才是这道题的高分答案**，完整展开见 `terraform_honest_answer.md`。

## Q31. Terraform 的常见生产问题有哪些？[理论]

| 问题 | 机制 | 缓解 |
|---|---|---|
| **大 state 变慢** | `plan` 默认 refresh 全部资源，每个资源至少一次云 API 调用；一个几千资源的 state 的 plan 可能要十几分钟，还会撞云 API 限流 | 拆 state（按 blast radius 和变更频率拆 module/目录）、`-refresh=false` 配合定期完整 refresh、`-target` 应急（但它是设计问题的信号） |
| **plan 与实际不符** | ① provider 的 diff 逻辑有 bug 或字段是 computed；② 有外部东西在改资源（另一个自动化、云厂商自动行为）；③ plan 与 apply 之间世界变了；④ data source 求值出了变化 | 用 `plan -out` 保存计划再 apply（消除 ③）、`ignore_changes` 承认外部真相源（②）、升级 provider（①） |
| **"perpetual diff"（永远有 diff 但改不掉）** | 云返回的属性格式与配置不一致（大小写、JSON 空白、默认值被云填上）、或字段是 write-only | 通常是 provider issue；短期用 `ignore_changes`，但要留注释说明原因 |
| **跨 module / 跨 state 依赖** | `terraform_remote_state` 造成隐式耦合 + 需要对方 state 的读权限（state 里有 secret） | 通过显式契约层传递（SSM/Secrets Manager/tag 约定）；或者用 Stacks 那类正式的组件编排 |
| **secret 进 state** | TF 原样存储资源属性，`sensitive = true` 只影响显示不影响存储 | backend 加密 + 严格权限；用 ephemeral / write-only 参数（TF **1.10** ephemeral values、**1.11** write-only arguments）`(src: web 2026-07)`；或让 TF 只管 secret 的引用不管值 |
| **依赖图不对导致偶发失败** | 隐式依赖靠引用推导，没有引用关系的顺序依赖（IAM policy 生效延迟、DNS 传播）图里看不到 | 显式 `depends_on`；对最终一致性的云 API 加重试或 `time_sleep`（丑但诚实） |
| **并发 apply 互相覆盖** | 锁没配或被 force-unlock | S3 `use_lockfile = true`；CI 里串行化同一 state 的 apply |
| **不可逆变更被误 apply** | 改了 force-new 字段导致 destroy/create | `prevent_destroy`、CI 里对 plan 输出做策略检查（有 destroy 就要额外审批） |

## Q32. Terraform vs CloudFormation vs CDK？[理论]

| | Terraform / OpenTofu | CloudFormation | CDK（AWS CDK） |
|---|---|---|---|
| 语言 | HCL（声明式 DSL） | JSON/YAML | 真实编程语言（TS/Python/Go/Java），**编译成 CFN 模板** |
| 状态 | 自己管 state 文件 | AWS 托管 stack 状态，**你不持有 state 文件** | 同 CFN |
| 多云 / 多 provider | 是，3000+ provider（也能管 K8s、GitHub、Datadog、Cloudflare） | 仅 AWS | 仅 AWS（CDK for Terraform 见下） |
| 回滚 | 无回滚（改配置再 apply） | **stack 级自动回滚**，失败自动回到上一个稳定状态 | 同 CFN |
| drift | `plan` | `drift detection`（较弱，不覆盖所有资源类型） | 同 CFN |
| 抽象能力 | module，表达力有限（无循环外的逻辑、无类型系统） | 弱（nested stack + macro） | 强（类、继承、单测、L2/L3 construct 内置最佳实践） |
| 主要代价 | state 是你的责任、HCL 表达力有限 | 只锁 AWS、模板冗长、更新失败的恢复体验差 | 生成的 CFN 不透明（`cdk diff` 之后还有一层）、抽象泄漏时很难 debug |

**判据式答法**（比列表更能拿分）：
- 只在 AWS 且团队接受托管 state、想要自动回滚 → CFN/CDK。
- 多云或者要管非云资源（K8s、SaaS、DNS）→ Terraform。**这一条通常是决定性的**，因为现代基础设施很少只有一个 provider。
- 团队是软件工程师而非运维、要复用抽象和写单测 → CDK。但要提醒：CDK 的强抽象在小团队会变成「只有作者看得懂的基础设施」。

`(src: web 2026-07)` **CDK for Terraform（CDKTF）已于 2025-12-10 被 HashiCorp/IBM 正式弃用并归档**，官方说法是「没有在规模上找到 product-market fit」，推荐迁回原生 HCL 或（AWS 强绑定时）直接用 AWS CDK。这是个很好的面试谈资：它说明 HashiCorp 把投资收回到核心 HCL，也说明「用通用编程语言写 IaC」这条路在 TF 生态里没走通。

## Q33. 2026 年的 Terraform 生态现状，被问到要能答什么？[理论]

全部 `(src: web 2026-07)`，按被问到的概率排序：

1. **许可与分叉**：HashiCorp 2023-08 把 Terraform 从 MPL 2.0 改成 BUSL 1.1；社区分叉出 **OpenTofu**，进 Linux Foundation。OpenTofu **2025-04-23 进入 CNCF Sandbox**，到 2026 年中**仍在 Sandbox**，没有 Incubating/Graduated。BUSL 在 IBM 收购后**没有**回退。
2. **OpenTofu 独有的能力**（Terraform OSS 没有）：**state 加密**（AES-GCM，可插拔 key provider：passphrase/PBKDF2、AWS KMS、GCP KMS、OpenBao，OpenTofu 1.7）、provider-defined functions（1.7；TF 在 1.8 有自己的版本）、**early variable evaluation**（可在 backend/provider 配置里用输入变量，1.8）、`.tofu` 文件覆盖扩展（1.8，让同一份代码同时兼容两边）、OCI registry、OpenTelemetry tracing、S3 原生锁（1.10+）。**「state 加密」是最值得记住的一条**，因为它直接回应了 Q22 里 secret 进 state 这个真实痛点。
3. **IBM 收购**：2024-04-24 宣布，**2025-02-27 完成**（$6.4B），2025-09-01 业务并入 IBM 并改名（HCP Terraform → IBM Terraform Standard/Premium 等）。免费层停止，legacy Free plan **2026-03-31 EOL**，按 RUM 计费。
4. **Terraform 版本线**：2026 年中最新是 **1.15.x**。1.5 以来的关键特性见 Q24/Q28/Q31 的引用；**Stacks 在 1.13 GA**。
5. **Crossplane 2025-10-28 从 CNCF 毕业**（Graduated，与 Kubernetes/Prometheus 同级）。这是这个周期最重要的「K8s 原生 IaC」信号，也是 Terraform 在平台工程方向最强的挑战者：它把云资源变成 CRD，由 controller 持续 reconcile，也就是**把 IaC 从「plan/apply 的一次性动作」变成「持续收敛的控制循环」**。
6. **CDKTF 2025-12-10 归档**（见 Q32）。
7. **Pulumi** 仍是强势第二（用真实编程语言），但 Terraform 在职位描述和市场份额上仍然是默认选项（具体百分比来自厂商营销材料，可信度低，面试里不要报数字）。
8. **2026 年的新话题**：AI 生成的 IaC 让 review 跟不上变更速度，推动 policy-as-code（OPA/Sentinel/Conftest）在 CI 里更早介入。这是一个能主动抛出去、显示我在看趋势的话题。

**我讲这一节的目的**要说清楚：这些是我作为一个没有 TF 生产经验的人做的功课，用来证明我能快速进入一个生态并抓住它的结构性事实，不是用来假装我用过。

---

# 第五部分：CI/CD 理论

## Q34. 流水线怎么设计？快慢分离是什么意思？[一手 + 理论]

`[理论]` 快慢分离的原则：**开发者每次 push 都要等的东西必须快，慢的东西移到不阻塞人的地方**。典型分层：

| 阶段 | 目标时间 | 内容 | 失败语义 |
|---|---|---|---|
| pre-commit / pre-push | 秒级 | format、lint、单元测试的子集 | 本地拦住 |
| PR 门禁 | < 10 分钟 | 编译、单测全量、静态扫描、`terraform plan` | fail-fast，阻塞合并 |
| 主干构建 | 分钟级 | 构建不可变工件、打 digest、推 registry | 阻塞发布 |
| 集成 / E2E | 十分钟到小时 | 起真实依赖跑端到端 | 不阻塞合并，阻塞晋级 |
| nightly / 周期 | 小时 | 全矩阵、性能回归、依赖更新扫描 | 只报警 |

`[一手]` 我实际建过 nightly 这一层：cron 驱动的 nightly 生产镜像构建编排器，跨 4 条生产分支 × 3 类服务，编排下游 pre-process → build-image job 链 (src: `jenkins_facts.md:17`)。它的四个属性正好对应「把 pipeline 当生产系统」：参数持久化（cron 触发时参数会回落 default，我把上次人工触发的参数写到持久卷的 properties 文件，cron 时读回）、下游状态收集（结果收进 `BUILD_RESULTS` JSON，失败前先落盘保存 partial results）、失败归因加 oncall 路由（`FAILED_SERVICE`/`FAILED_BRANCH` 归因，按服务映射到对应 oncall 在 Slack @ 到人，Slack + email 双通道，通知本身 try/catch 不阻塞）、FORCE_BUILD 幂等门贯穿全链 (src: `jenkins_facts.md:20-23`)。

## Q35. 构建可重现性（reproducibility）怎么做？[一手 + 理论]

`[理论]` 三个层次，由弱到强：

1. **可重复运行**（re-runnable）：同一个输入跑两遍都成功。
2. **产出稳定**（deterministic output）：同一个 commit 构建两次得到字节相同的工件。需要：pin 所有依赖版本（lock 文件进 git）、消除时间戳与随机顺序（`SOURCE_DATE_EPOCH`）、固定构建环境（容器化的 builder + pin base image 到 digest 而不是 tag）。
3. **可验证**（verifiable）：别人能独立重建出相同工件并比对（SLSA 的 provenance、reproducible-builds）。

`[一手]` 我付过不可重现的税，而且能讲清税从哪来：Jenkins 跨集群迁移后构建大面积失败，根因是三件事叠加：外部仓库失效（maven.twttr.com 超时、repo.spring.io 认证失败）、迁移时 `.m2` 缓存没带过去、以及 Maven 的 `.lastUpdated` 失败记录会阻止重试 (src: `jenkins_facts.md:36`)。

这个故障链的方法论价值有两条：
- **缓存掩盖了「依赖已死」这个事实好几年**。构建一直绿是因为缓存里有，不是因为它可重现。所以「能从零重建」是比「能维持运行」更强的属性，而唯一验证方式是**定期真的从零重建一次**。
- **系统的失败缓存本身成了故障的一部分**：`.lastUpdated` 让 Maven 在上游恢复后仍然不重试。同一个形状我在 K8s 侧也遇到过：`imagePullPolicy: IfNotPresent` 会让相同 tag 的新镜像不生效，所以我的部署纪律是**每次用不同 tag** (src: `workflow_dcluster_starrocks_cn_deployment.md`「踩过的坑」表)。

## Q36. artifact 不可变与晋级（promotion）怎么做？[理论 + 一手]

`[理论]` 核心规则：**一次构建，多次部署**（build once, deploy many）。工件在第一次构建后就不可变，晋级只是改「它被贴的标签/它出现在哪个环境的清单里」，绝不重新构建。

- 镜像用 **digest（`@sha256:...`）而不是 tag** 引用，因为 tag 可以被重新指向，digest 不能。
- 环境差异必须外置（配置、secret、环境变量），否则「同一个工件」是假的。
- 晋级链路：`build → 存 registry（immutable tag + digest）→ dev 部署这个 digest → 验证 → stage 部署同一个 digest → prod 部署同一个 digest`。每次晋级留记录（谁批的、基于哪次验证）。
- 反模式：每个环境重新构建一次（那你在 prod 部署的东西从未被测过）、用 `latest`（不可追溯也不可回滚）。

`[一手]` 我的一手关联：`imagePullPolicy: IfNotPresent` 加相同 tag 会导致新镜像不生效，所以我的纪律是每次部署用不同 tag (src: `workflow_dcluster_starrocks_cn_deployment.md`)。这是「tag 可变」这个问题的一个具体表现形态。另外我的 nightly pipeline 里的幂等门就是建立在「镜像 tag 是否已存在」这个判定上（存在且非 FORCE_BUILD 就跳过构建）(src: `jenkins_facts.md:110`)，这等于把「工件不可变」当成了幂等的实现基础。

`[一手]` AMI 是同一个模式在机器层的实例：AMI 是版本化的不可变工件，Launch Template 引用它，回滚就是指向旧版本 (src: `interview-1-k8s_upgrade.md:69`；`oncall_track_record.md:56`)。

## Q37. 部署策略与 CI/CD 的关系？[一手 + 理论]

`[理论]` 四种策略与判据：

| 策略 | 机制 | 何时用 | 代价 |
|---|---|---|---|
| rolling | 逐批替换（`maxSurge`/`maxUnavailable`） | 默认，无状态服务 | 新旧共存，需要向后兼容；回滚也要滚一遍 |
| blue/green | 两套完整环境，切流量 | 需要快速完整回滚、或新旧不能共存 | 双倍资源；有状态层不好复制 |
| canary | 小比例真实流量 + 指标对比 | 需要用真实流量验证 | 需要可观测性支撑（否则 canary 只是「先发一部分」） |
| 影子 / shadow | 复制流量到新版本但不返回结果 | 高风险变更的读路径验证 | 副作用要隔离 |

与 CI/CD 的连接点是**幂等和不可变**：不幂等就不敢自动重试、不敢自动回滚，只能叫人 (src: `interview-5-cicd_reliability.md:35`)。所以部署策略的可行性由流水线的属性决定，不是反过来。

`[一手]` 我实际用的模式在两个层次：
- **集群层的 blue/green**：双集群 + 流量前置切换。流量全切到对侧 → 暂停跨集群复制 → 升级已 dark 的一侧 → 恢复复制并等 lag 回落 → 验证 → 切回 (src: `p_k8s_upgrade.md:59`)。这个模式下 worker 的 20% batch 语义从「保护用户」变成「节奏控制」。
- **节点层的 rolling + 不可变替换**：ASG Instance Refresh 20% batch，pause-on-failure (src: `interview-1-k8s_upgrade.md:69`)。

`[理论]` fail-fast vs fail-safe 的区分（这条是高级信号）：什么时候「停在原地不回滚、保留现场」比自动回滚更对？答案是**疑似数据损坏时**，因为回滚会盖掉证据 (src: `interview-5-cicd_reliability.md:43`)。判据是「回滚动作本身是否覆盖状态」：LT 回滚不覆盖（版本并存，diff 随时可看），数据回滚覆盖。

## Q38. Jenkins 的架构：master/agent、JCasC、pipeline as code？[一手]

`[一手]` 我们的形态：Jenkins 跑在 Kubernetes 上，用 kubernetes plugin **动态起 agent pod**；`.m2` 缓存挂 PVC（`jenkins-m2` claim）；agent 镜像我维护（Dockerfile 我 touch 50 次，是主要维护者）：基础镜像升级、Debian 源切 Bookworm、Java 8/17 多版本构建环境、Maven 3.3 + Java 8 组合 (src: `jenkins_facts.md:47`)。

`[一手]` 动态 agent 的可靠性含义：agent 是无状态的（pod 起来就干活，完事就销毁），所以**所有需要跨构建存活的状态都必须显式外置**（缓存挂 PVC、凭据在 Jenkins credential store、工件推 registry）。迁移时暴露的问题恰恰是这条没做干净：agent pod 里有手工调过的 Maven 配置，只活在运行中的系统里 (src: `p_jenkins.md:112`)。

`[一手]` **pipeline as code**：交付逻辑约 275 个 pipeline 定义文件加 16 个 shared library groovy 步骤，全部活在 git 里，可 review、可 diff、以及决定性的一点，**可迁移** (src: `p_jenkins.md:112, 139`)。这次迁移就是对这个属性的审计：repo 里的东西全部干净地搬了过去，只活在运行中系统里的东西全部以故障形式浮出。这就是 pipeline-as-code 和「点 UI 攒出来的雪花 Jenkins」在运维意义上的差别：**雪花在定义上不可恢复**。

`[一手]` **JCasC 的诚实边界**：我们 repo 里**没有** JCasC。`jenkins.yaml` 这个文件实际是捕获的 agent pod spec 快照，不是 Jenkins Configuration as Code (src: `p_jenkins.md:145`；`jenkins_facts.md:133`)。所以「用 JCasC 管 controller 配置」我只能以「我会对任何自己拥有的 Jenkins 采用的标准」口径讲 (src: `p_jenkins.md:112`)。另一个弱项：`@Library('jenkinsconfig@east-mgt-rui')` 长期指向个人分支，shared library 的分支治理是弱项，**不能声称做到了 configuration-as-code 治理** (src: `jenkins_facts.md:133`)。

`[理论]` JCasC 的价值与边界：它把 controller 的插件列表、全局工具、凭据引用、安全域、agent 模板写成 YAML，从而让 controller 本身可重建。边界是插件版本仍需单独 pin（`plugins.txt` 或 `plugin-installation-manager-tool`），以及 job 的构建历史与 secret 本体仍是运行时状态。

`[一手]` `[理论]` 顺带一个我付过的税：我那段时间有 91 个 Debug/test commit，说明当时没有 pipeline 的本地验证或 staging 环境，只能靠生产 Jenkins push-and-run 反复试 (src: `jenkins_facts.md:68, 132`)。这是「命令式 CI 的可测试性差」这个论点的一手证据，我用它当自嘲式论据而不是成就。现代解法是 `Jenkinsfile Runner` / `jenkins-pipeline-unit` 做本地验证，或者干脆选一个原生支持本地执行的 CI。

## Q39. 供应链安全的基础是什么？[理论 + 一手]

`[理论]` 按攻击面组织，四层：

1. **源码到构建的完整性**：分支保护 + 必需 review + 签名 commit；CI 的触发条件不能让 fork 的 PR 拿到 secret。
2. **依赖**：lock 文件进 git（精确版本 + hash）、私有 mirror/proxy 隔离上游消失与投毒（typosquatting、依赖混淆）、SCA 扫描已知 CVE。
3. **构建过程**：构建环境隔离且无状态、**provenance**（SLSA 的 attestation：谁在什么环境用什么源码构建了这个工件）、构建器本身的权限最小化。
4. **工件与部署**：镜像签名（Sigstore/cosign）、**SBOM**（SPDX/CycloneDX，用于事后回答「哪些镜像里有这个 CVE 的库」）、部署时验签（admission webhook 拦未签名镜像）。

`[一手]` 我的一手关联全部在「反面教材」这一侧，而这恰好让答案可信：

- **凭据集中在流水线够得着的地方是自动化打开的新故障面** (src: `p_jenkins.md:120`)。实证：我们 repo 里 `jenkins.yaml` 意外捕获了明文 AWS AccessKey + SecretKey，而且进了 git 历史 (src: `jenkins_facts.md:142`)；`roles/cilium/templates/values.yaml.j2` 里也硬编码过明文 AWS Access Key/Secret，同样进了 git 历史 (src: `interview-8-k8s-cluster-build.md:254`)。修复路径三步：IAM rotate/disable 该 key、改用 **IRSA 或 instance profile**、用 `git filter-repo`/BFG 清历史 (src: `interview-8-k8s-cluster-build.md:254`)。
- **插件供应链**是我明确列出的自动化新增故障面之一 (src: `p_jenkins.md:120`)。
- **上游依赖消失**不是理论风险，是我修过的生产故障（maven.twttr.com 失联、Debian Buster 源下线）(src: `jenkins_facts.md:36-38`)。正确的长期解是内部 mirror，我把它写成了文档建议但**没有落地** (src: `jenkins_facts.md:131`)。
- **`COPY .git-credentials` 进镜像**这种做法在我们的 agent Dockerfile 里存在过，是我明确标为不该展示的内部实现 (src: `jenkins_facts.md:143`)。

⚠️ 待确认 / 明确的外环：镜像签名（cosign）、SBOM 生成与消费、SLSA provenance、admission 层验签，这些我**没有实践证据**，只能作为「我知道的标准做法」讲。这是这个方向外环里最该补的一块，因为 senior SRE 面试问到供应链安全的概率在上升。

---

# 自查清单（面试前一天过一遍）

**K8s 升级**：能不看笔记说出 kubeadm upgrade 的三层顺序、version skew 三行表、etcd 三项健康检查加 raft lag 1000 这个阈值、PSP→PSA 的迁移四步、回滚三层路径加「snapshot 恢复数据不恢复二进制」、以及零事故的三个来源拆分（结构性/门禁/我算错的）。

**K8s 核心**：QoS 三档与 CPU throttle vs 内存 OOMKill 的区别、两类驱逐只有主动受 PDB 约束、`WaitForFirstConsumer` 为什么是多 AZ 必需、admission 链的顺序与 `failurePolicy` 的两难、三个 CIDR 与 Calico IPIP vs Cilium ENI 的取舍加 IPIP proto 4 那个坑。

**IaC**：声明式的三个可观测性质、幂等的三层（形状/判定权位置/幂等≠可重入）、drift 的三类来源与三种态度、不可变的两处边界、四层分层判据是「谁在持续维持」。

**Terraform**：state 的四个职责与「云资源不携带归属信息」这个核心、S3 原生锁（1.10）取代 DynamoDB、`import`/`moved`/`removed` 三个 block 各解决什么、count vs for_each 的地址稳定性、workspace 的三个致命问题、大 state 慢在 refresh、secret 进 state 与 ephemeral/write-only、OpenTofu 的 state 加密、Crossplane 2025-10 CNCF 毕业。

**CI/CD**：快慢分离的五层、build once deploy many + digest 而非 tag、fail-fast vs fail-safe 的判据是「回滚是否覆盖状态」、Jenkins 的 JCasC 边界（我们没有）、供应链四层加我手上的三个反面实证。
