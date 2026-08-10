# 04 IaC / CI-CD / K8s 升级：Story Bank

> 每个故事结构固定：Headline → 适用题型 → 情境 → 动作 → 结果（数字带出处）→ 5 层追问防线 → 归属边界 → 可复用到。
> `(src: 路径)` 都是相对 workspace 根 `/Users/rshao/work/context-infrastructure`。
> `[一手]` = 有 evidence 支撑的我的经历；`[理论]` = 通用知识，用来补答题深度，不声称是我做的。

## 数字口径与已知漂移

| 数字 | 口径 | 出处 |
|---|---|---|
| 50 集群 / 6 region / 600+ 节点 | 统一口径 | `work-contexts/career/profile/resume.tex:91` |
| 1.24 → 1.29，逐 minor 执行 | kubeadm 只支持一次升一个 minor | `work-contexts/career/interview/interview-1-k8s_upgrade.md:6`；`interview-1-k8s_upgrade_reference.md:96-98` |
| Before：单集群 18-21h，必须 2 人 pair | 一手 | `work-contexts/career/interview/interview-1-k8s_upgrade.md:20, 98-99` |
| After：6-8h，1 人 + system | **已达成值** | `adhoc_jobs/dynamic_resume_site/content/projects/p_k8s_upgrade.md:33, 89`；`interview-1-k8s_upgrade.md:99` |
| 3-4h | **自动化成熟后的目标值，不是已达成值** | `p_k8s_upgrade.md:33`（"targets 3-4 hours"）；`resume.tex:93` 直接写成 3-4h |
| 零事故、零回滚 | 一手 | `interview-1-k8s_upgrade.md:100`；`p_k8s_upgrade.md:59` |

> ⚠️ **口径漂移（最重要的一条，进面试前必须自己定死）**：`resume.tex:93` 写的是 `18–21h to 3–4h`，但 7 月的 `p_k8s_upgrade.md:33` 明确区分了「6-8 小时 = 已达成」和「3-4 小时 = 自动化路线图目标，预期降幅 60-80%」。按「冲突以 7 月为准」的规则，**面试口述必须说 6-8h**，并把 3-4h 讲成 roadmap。如果按简历字面说 3-4h，被追问「这 3-4 小时里你具体在干什么、哪几步还需要人」时会答不上来，因为那三项自动化（外部告警门控 / synthetic health check / canary 自动放行）在 evidence 里明确是「路线图」而非已实施 (src: `interview-1-k8s_upgrade_reference.md:177`)。建议：要么口述改 6-8h，要么把简历改成 `18–21h to 6–8h, with automation roadmap to 3–4h`。

---

## S01. K8s 1.24 → 1.29 跨 50 集群零事故升级（主力故事）

**Headline（一句话，先给结论）**：我把一个「只存在于资深工程师脑子里」的 18-21 小时双人手工升级仪式，重构成一条 check → plan → apply 的证据链流水线，然后用它把 50 个自管理集群从 1.24 逐 minor 推到 1.29，两套生产 fleet 零客户可感知停机、零回滚，单集群成本降到 6-8 小时单人操作。

**适用题型**：讲一个你主导的最复杂的变更 / 大规模变更管理怎么做 / 你怎么定义「安全」 / K8s 升级怎么升 / 怎么在 50 个异构环境里保持一致性 / 你怎么证明一件事没出问题。

**情境**：50 个 AWS 上的自管理集群，kubeadm 控制面 + ASG worker，跨 6 region、600+ 节点 (src: `work-contexts/career/profile/resume.tex:91`)。1.24 即将脱离支持窗口，每落后一个 minor，CVE 暴露面与合规风险都在累积 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_k8s_upgrade.md:15`)。存量做法是单集群 18-21 小时纯手工、必须两人结对，因为真正的风险模型只存在于资深工程师的脑子里 (src: `work-contexts/career/interview/interview-1-k8s_upgrade.md:20`)。kubeadm 一次只能升一个 minor，1.24 到 1.29 意味着每个中间版本都要走一遍，每一跳都覆盖 control plane / worker / addon 三层，每集群至少 3 轮操作 (src: `interview-1-k8s_upgrade.md:6-8`)。

**动作**：我做的第一件事不是写脚本，是重新定义问题。根本矛盾不是「手动 vs 自动」，而是系统可解释性缺失：在任何一步，没人能回答「我凭什么确信现在可以进入下一步」(src: `interview-1-k8s_upgrade.md:11, 23`)。所以我设计的是一个 Upgrade Safety System，形态是 `check → plan(dry-run) → apply + evidence` 三段流水线，实现为一个 Python CLI，编排 Ansible、boto3 和 kubectl，所有 stdout/stderr 全量落进 evidence 存储 (src: `p_k8s_upgrade.md:21`；`interview-1-k8s_upgrade.md:39-46`)。

check 把健康基线显式化。etcd quorum 查三件事：member list 奇数且全部在线、raft index lag（follower 落后 leader 超过 1000 直接 fail）、leader 唯一性 (src: `interview-1-k8s_upgrade_reference.md:12-30`)。这三件事的设计意图是同一个：quorum 名义存在不代表复制健康，而升级本身会让一个 member 短暂不可用，「刚好够」等于升级期间会丢 quorum。node Ready 数、kube-system pod 状态、外部活跃告警同样走硬编码的 fail 条件。任何变更之前，etcd snapshot 是强制动作。

plan 是真 dry-run 不是文档。master 侧 `kubeadm upgrade plan` 加 `ansible --check --diff`；worker 侧做 AMI diff（kubelet 必须等于目标版本）和 Launch Template diff（只允许 AMI ID 变化）(src: `interview-1-k8s_upgrade_reference.md:38-46`)。blast radius 在执行前用 quorum math 量化：3 master 恰好容忍 1 台不可用，`serial: 1` 保证每次只动一台，最坏情况被封在单节点。

apply 按严格顺序、逐层设门：control plane 原地 in-place 升级、`serial: 1`、每台 master 人工确认；worker 走不可变替换（新 AMI → 更新 LT → ASG Instance Refresh，20% batch，失败即暂停）；addon 按依赖顺序 CCM → Calico → Cluster Autoscaler，各有独立 gate (src: `interview-1-k8s_upgrade.md:50-78`)。fleet 推进顺序 dev → preprod → prod 金丝雀 → 其余 prod → 管理集群最后，任何一个集群失败全局暂停，人工批准才继续 (src: `interview-1-k8s_upgrade.md:58`)。

生产执行的关键使能条件是双集群流量前置切换：流量全切到对侧集群，暂停跨集群复制，升级已变 dark 的一侧，恢复复制并等 lag 降回阈值，按 checklist 验证后再切回 (src: `p_k8s_upgrade.md:59`)。

**结果**：
- 操作人数 2 人 pair → 1 人 + system；单集群 18-21h → 6-8h (src: `interview-1-k8s_upgrade.md:98-99`；`p_k8s_upgrade.md:33`)
- 两套生产 fleet（East / West）的 master、控制面组件、worker 全部升级完成，零客户可感知停机、零回滚 (src: `contexts/fy2026_self_assessment.md:5`；`interview-1-k8s_upgrade.md:100`)
- 升级前后验证覆盖 infra 健康与**业务层正确性**两层，不只是 infra 绿 (src: `contexts/fy2026_self_assessment.md:19`)
- 沉淀物不是工具：checklist 与 evidence 模式外溢成日常 infra health check (src: `interview-1-k8s_upgrade.md:101`)
- 这是我 FY2026 自评里写的最大成就，公司内部口径一致 (src: `contexts/fy2026_self_assessment.md:19`)
- 自动化路线图目标 3-4h、预期降幅 60-80%，**未达成，是 roadmap** (src: `p_k8s_upgrade.md:33`)

**5 层追问防线**：

- **L1 面试官问「1.24 到 1.29 你是怎么升的，讲一下流程」** → 答：三句话给骨架，再按层展开。骨架是 check → plan → apply + evidence，逐 minor 跳（kubeadm 硬约束，不是我保守），每跳三层（control plane / worker / addon）。然后我会主动给出顺序的理由：control plane 先行是因为 version skew policy 允许 kubelet 落后 apiserver 两个 minor，反过来不成立，所以「控制面先、数据面后」在机制上天然安全，不是习惯 (src: `interview-1-k8s_upgrade_reference.md:100-108`)。worker 我不 in-place 升 kubelet，走不可变替换：Packer 出新 AMI、更新 Launch Template、ASG Instance Refresh 20% batch。这样 worker 的「升级」退化成「换机器」，失败路径从「修一台半死的节点」变成「回退一个 LT 版本」。
- **L2 追问「哪一跳最危险？为什么？」** → 答：1.24 → 1.25，因为它是唯一一跳里有**移除类破坏性变更**的：PodSecurityPolicy 在 1.25 被移除 (src: `interview-1-k8s_upgrade_reference.md:110`)。危险不在 API 本身，在它的替代品语义相反：PSP 是「不配就不管」，Pod Security Admission 是「namespace 打了 label 就强制」。日志和监控类 DaemonSet（Fluentd、node-exporter）合法需要 privileged，一个 namespace 被草率打成 `enforce: restricted`，这些组件直接被拦死，而且是升级后才发作。我的处理是把它当独立问题线而不是升级的一个步骤：升级前先扫存量 workload 并迁移，PSA 先上 warn/audit 观察，确认零违规才切 enforce，infra namespace 显式保持 privileged (src: `p_k8s_upgrade.md:47`；`interview-1-k8s_upgrade_reference.md:110`)。
  次危险的是 1.26 → 1.27 那一段的 cloud provider 交接：in-tree AWS cloud provider 被移除，kubelet 从 `--cloud-provider=aws` 改成 `--cloud-provider=external`，由 CCM 接管。这条我们的 Ansible 是用条件分支表达的，`<1.27` 走 in-tree、`>=1.27` 走 external，不分叉代码库 (src: `work-contexts/career/interview/interview-8-k8s-cluster-build.md:66`)。这一跳的失效形态很脏：CCM 没起来，新 worker 会卡在 `uninitialized` taint 上，节点看着 join 了但排不上 pod，所以 addon 顺序里 CCM 必须第一个 (src: `interview-1-k8s_upgrade.md:76`)。
  顺带一个诚实点：dockershim 的坑不在这一轮。dockershim 是 1.24 移除的，我们的起点就是 1.24，容器运行时早就是 containerd（Packer AMI 里直接装 containerd + kubeadm）(src: `interview-8-k8s-cluster-build.md:16`)。所以我可以讲 dockershim 的机制，但不会声称是我这次踩的坑。
- **L3 追问「回滚方案是什么？真的回滚过吗？」** → 答：先给分层答案，再给诚实边界。回滚按层设计，触发条件事前写死。control plane 回滚 = etcd snapshot 恢复 + 二进制降级；worker 回滚 = 停止 Instance Refresh + LT 回退旧 AMI；addon 回滚 = `kubectl rollout undo` 或 reapply 旧 manifest (src: `interview-1-k8s_upgrade.md:68-70`；`p_k8s_upgrade.md:55`)。触发条件：master 升级失败、超过 50% pod 非 Running、关键服务不可达、告警洪水 (src: `p_k8s_upgrade.md:55`)。
  诚实边界：**实际执行零回滚**，所以我没有「回滚成功过」的战绩，我有的是「回滚路径被设计过并且被 dry-run 检验过」(src: `interview-1-k8s_upgrade.md:100`)。而且我会主动说出这个设计里最脆的一环：etcd snapshot 恢复的是数据，不是二进制 (src: `interview-1-k8s_upgrade_reference.md:32`)。也就是说控制面「回滚」实际是两个动作的组合，而且 snapshot 恢复会丢掉 snapshot 之后的所有写入，kubeadm 的降级路径本身也不是一等公民 `[理论]`。所以我的真实策略排序是：第一优先靠 gate 不进入坏状态，第二优先前滚修复（fix-forward），回滚是最后手段。这也是为什么门禁密度那么高、为什么 `serial: 1` 是不可协商的。
- **L4 追问「为什么不用 EKS 或 Cluster API？自管理控制面这个选择本身对吗？」** → 答：这个选择我不为它辩护，我为它的成因和代价负责。成因是历史债务加成本考量：自管理省掉 EKS 控制面费用（$0.10/cluster/hr × 50 ≈ $3,600/month）(src: `interview-1-k8s_upgrade_reference.md:161`)。代价是我这整个项目本身：省下来的 infra 钱远不如工程师时间值钱，一个 50 集群的跨版本升级项目的人力成本量级远超那个数字。如果重做，我上 EKS：master 升级退化成一次 API 调用，我的精力能放到上层（addon 兼容性、业务层验证、发布节奏），而不是花在 kubeadm 的逐跳编排上 (src: `interview-1-k8s_upgrade_reference.md:163`)。
  但我会补一句区分：自管理控制面在两个场景下仍然是对的选择，一是 onsite / 客户裸机交付（没有云托管可用，我们的同一套 Ansible 就要能装 onsite 集群，MetalLB 替代云 LB）(src: `interview-8-k8s-cluster-build.md:206`)；二是需要改 apiserver / etcd 参数到托管服务不开放的深度。不属于这两类而还在自管理，就是纯技术债。
- **L5 追问（最深）「你说零事故。这里面有多少是设计，有多少是运气？你算错过什么？」** → 答：我把零事故拆成三个来源，其中只有两个是我的功劳。
  第一，**结构性来源，也是最大的那一份**：双集群流量前置切换。升级时那个集群是 dark 的，没有业务流量 (src: `p_k8s_upgrade.md:59`；`interview-1-k8s_upgrade_reference.md:80`)。在这个前提下 20% batch 的语义变了，它不再是保护用户的机制，而是节奏控制机制，小到出问题能快速暂停 (src: `p_k8s_upgrade.md:59`)。承认这一点很重要：如果没有双集群这个架构条件，同样的操作纪律不可能拿到零事故，我会需要真正的 canary + 逐 AZ 推进 + 更长的观察窗口。
  第二，**门禁设计**：版本 × 健康四象限（目标版本且健康则继续、旧版本且健康则直接重跑、任何不健康一律人工）(src: `interview-1-k8s_upgrade_reference.md:69-76`)，加 post-verify 对比落盘 baseline 而不是工程师记忆，加 check 结果与外部监控交叉验证以防「baseline 本身就是错的」(src: `interview-1-k8s_upgrade_reference.md:171-175`)。
  第三，**我算错过的地方**：我最初把「Ansible 幂等」当成了可重入的充分条件。它不是。drain 是幂等的（已 drain 的节点再跑无 pod 可驱逐，直接成功），但 kubelet 的中间状态超出 idempotency 的覆盖范围：master 原地升级或 worker 换节点失败在中途，都需要人工介入，state.yaml 只告诉你从哪一步接手，不告诉你集群的真实状态 (src: `interview-1-k8s_upgrade_reference.md:154-157, 55-56`)。这个认知差直接导致了设计上的修正：evidence 不能只有 state 文件，必须有全量执行日志，而且判定「这一步到底完成了没有」必须回到集群实测（镜像版本 × health），不能信 state 文件。同类的第二个盲区是 evidence 本身的边界：网络层抖动 kubectl 和 boto3 都看不见，需要 metrics 时间轴对齐才能发现 (src: `interview-1-k8s_upgrade_reference.md:58`)。
  ⚠️ **待确认**：「最接近出事的一次」我目前**没有可讲的真实案例**。evidence 里明确记录了这一点：reference 文件把它列为面试预设问题，但无实际事件素材 (src: `p_k8s_upgrade.md:160`；`interview-1-k8s_upgrade_reference.md:206`)。这是这个故事**最可能被问穿的地方**。面试前必须回忆并落盘一个真实的「gate 把我拦下来了」的实例（候选：某个集群 raft lag 超 1000 被 check 拦住、某个集群 PDB 卡住 drain 等了很久、某个 cluster 的 drain timeout 要从 300s 调到 600s 这件事本身就是从一次卡住里学来的 (src: `interview-1-k8s_upgrade_reference.md:136`)）。**在确认之前，不许编。** 没有案例时的诚实答法：「我没有 near-miss 的戏剧性案例，因为这套流程的设计目标就是让 near-miss 在 check 阶段就变成一次 fail 而不是一次事故。我能讲的是 check 真的拦过东西：<待确认的实例>。如果你想问的是我认为最危险的未被覆盖的场景，我的答案是 etcd 成员升级后起不来导致 quorum 丢失，这是唯一一个 serial:1 都救不了的情况，只能靠 snapshot 加人工。」

**归属边界**：Upgrade Safety System 的设计与实现、check/plan/apply 的门禁规则、evidence 结构、fleet 推进顺序都是我的 (src: `interview-1-k8s_upgrade.md:10-13`)。双集群 + 跨集群复制这个架构本身不是我建的，我是在这个既有架构上设计升级流程并利用它做流量前置切换；讲的时候用「我们的架构是双集群，我把它变成升级的安全前提」而不是「我设计了双集群」。worker AMI 的构建（kernel、OS patch 的测试）归 AMI builder 负责，我的 plan 只验证 kubelet/kubeadm/kubectl 版本等于目标版本 (src: `interview-1-k8s_upgrade_reference.md:46`)。3-4h 不能说成已达成。

**可复用到**：05 blue/green（dark cluster 切换是 blue/green cluster 的完整实例）、02 监控（baseline 与外部监控交叉验证、告警门控）、06 成本（EKS vs 自管理的 $3,600/月对比与「工程师时间更贵」的论证）、90 行为面（重新定义问题：从「手动 vs 自动」到「可解释性缺失」）。

---

## S02. 自研 Upgrade Safety System：18-21h 是怎么变成 6-8h 的

**Headline**：省下来的时间不是敲命令的时间，是「等待、核对、取证、以及两个人互相确认」的时间；我把这四类工作变成了一条命令加一份可复盘的证据链，人从执行者变成了审批者。

**适用题型**：讲一个你写的工具 / 你怎么衡量自动化的价值 / 自动化该做到什么程度 / 你怎么把隐性知识显性化 / 用什么标准判断一个流程可以自动化。

**情境**：18-21 小时 / 双人 pair 这个成本结构里，真正耗时的不是命令本身。命令是分钟级的。耗时的是：升级前巡检要人肉逐项看 etcd、node、pod、告警并判断「够不够健康」；每一步之后要人肉核对状态并截图/记录以备复盘；两个人 pair 的一半价值是互相 review 判断，也就是用人力冗余替代显式规则；出问题时要重建时间线，而证据是散落的，事后连复盘都做不了 (src: `work-contexts/career/interview/interview-1-k8s_upgrade.md:19-22`)。

**动作**：三段流水线对应三类工作的消除。

check 消除的是「人肉巡检 + 主观判断」。我把 fail 条件写成规则而不是临场判断：etcd member 数 < 3 或有 member unhealthy 或无 leader、raft lag > 1000、node Ready 低于预期、kube-system 有 CrashLoop/Pending、外部监控有 active alert (src: `work-contexts/career/interview/interview-1-k8s_upgrade_reference.md:24-30`)。这一步的产物是一份 JSON 健康快照，同时是门禁输入和 post-verify 的 baseline。

plan 消除的是「靠经验预判影响面」。`kubeadm upgrade plan` + `ansible --check --diff` 让 master 侧的变更集可读；AMI diff + LT diff 让 worker 侧的变更集只剩一个允许项（AMI ID）(src: `interview-1-k8s_upgrade_reference.md:38-46`)。blast radius 从「资深工程师的直觉」变成 quorum math 的算术结果。

apply 消除的是「人肉取证与状态记录」。Python 直接 `subprocess` 调 `ansible-playbook`，`--diff` 常开，stdout/stderr 全量写进 `evidence/{cluster}/apply/{playbook}.log`，返回码决定通过与否 (src: `interview-1-k8s_upgrade_reference.md:266-286`)。落盘四类东西：结构化 JSON 快照、plan diff、执行日志、以及记录每步 completed / in_progress / pending 的 `.state.yaml` (src: `interview-1-k8s_upgrade_reference.md:50-54`)。

被消除的第四类是 pair 的冗余判断。人工签核从「全程两人」压缩到四个位置：check、plan、每一台 master、最终 post-verify (src: `p_k8s_upgrade.md:59`)。人还在，但角色从执行者变成审批者。

**结果**：18-21h / 2 人 → 6-8h / 1 人 + system (src: `interview-1-k8s_upgrade.md:98-99`)。中断可恢复：state.yaml 说明从哪步接手，幂等步骤直接重跑 (src: `p_k8s_upgrade.md:29`)。剩余的 6-8 小时里最大的成分是等待（Instance Refresh 滚动、addon 滚动、复制 lag 回落）和人工签核点之间的观察窗口，这也是为什么 roadmap 的下一步是外部告警门控、synthetic health check、canary 通过后同 region 自动放行，目标 3-4h (src: `interview-1-k8s_upgrade_reference.md:177`；`p_k8s_upgrade.md:33`)。

**5 层追问防线**：

- **L1「这个工具具体是什么形态？」** → 答：一个 Python CLI，三个子命令 check / plan / apply，底下编排三样东西：Ansible（真正的执行与幂等）、boto3（AWS 侧的 ASG / LT / AMI 操作与动态 inventory 生成）、kubectl（集群侧读状态）(src: `interview-1-k8s_upgrade.md:39-46`)。Ansible 侧是 inventory per cluster、playbook 分 preflight/control_plane/workers/addons、role 拆到 drain_node / upgrade_kubelet / verify_node 这个粒度 (src: `interview-1-k8s_upgrade_reference.md:236-252`)。Python 只做三件 Ansible 不擅长的事：门禁判定、evidence 归档、跨 AWS API 与集群 API 的联合判断。
- **L2「为什么不全用 Ansible，或者反过来全用 Python？」** → 答：分工是按「谁天然给我幂等和 dry-run」划的。Ansible 的 module 幂等 + `--check` 天然 dry-run + `--diff` 天然产出 before/after + `serial: 1` 天然控制 blast radius，这四个属性我自己写 Python 都要重新实现一遍 (src: `interview-1-k8s_upgrade_reference.md:254-262`)。反过来，Ansible 不擅长「读多源状态做一个复合判定」和「把证据组织成可复盘的目录结构」，那是 Python 的部分。这条分工线的一般化表述是：声明式工具负责收敛，命令式代码负责判定与编排。
- **L3「你怎么知道 6-8 小时里省的是对的东西？会不会只是把人的判断变成了脚本的盲区？」** → 答：这是我认真处理过的风险，而且我承认它没被完全消除。我用三层验证测这套系统本身：dev 集群跑功能 happy path、每次 prod 升级前的 plan dry-run 作为只读预演、第一个 prod 集群作 canary 做真实验证 (src: `interview-1-k8s_upgrade_reference.md:167`)。我明确没做的是 Molecule 那类单测：playbook 重度依赖 kubeadm / kubectl / ASG，mock 成本远超收益 (src: `interview-1-k8s_upgrade_reference.md:169`)。留下的盲区我能点出来：`check` 判定的是我想到的那些失效模式，网络层抖动这类 kubectl 和 boto3 都看不到的东西它看不到 (src: `interview-1-k8s_upgrade_reference.md:58`)。缓解手段是 check 与外部监控交叉验证、check 产出 diff 与上次 baseline 对比、check 定期运行让「normal 长什么样」平时就知道，人工 review 作为最后一道门 (src: `interview-1-k8s_upgrade_reference.md:171-175`)。
- **L4「设计权衡：为什么保留四个人工签核点？为什么不做成全自动？」** → 答：因为在这个操作的频率与可逆性象限里，人工闸门是更可靠的组件而不是缺陷。我的排序规则是：高频且可逆的自动化，低频且不可逆的设闸 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_jenkins.md:62`)。跨 minor 的控制面升级是典型的低频不可逆：一年几次、失败要靠 snapshot + 二进制降级两步组合才能退。四个签核点的位置也不是随手放的，它们卡在四个「状态判定成本最高」的地方：升级前（baseline 对不对）、plan 后（变更集是不是只有预期项）、每台 master（quorum 边界）、post-verify（业务层是否真的正常）。同时我给了自动化的演进路径而不是拒绝自动化：先用外部告警门控替掉 check 后的人工、再用 synthetic health check 替掉 post-verify 的一部分、最后让 canary 通过后同 region 自动放行 (src: `interview-1-k8s_upgrade_reference.md:177`)。
- **L5（最深）「如果让你做 V2，你会改什么？」** → 答：三件，按杠杆排序。
  第一，**把问题消灭掉而不是优化它**：上 EKS，控制面升级退化成一次 API 调用 (src: `interview-1-k8s_upgrade_reference.md:163`)。这条会让我这个工具的 60% 变成无用代码，我认为这是它应该有的命运。工具的价值不是被长期维护，是被它证明的标准。
  第二，**把 check 从「升级前跑」改成「一直在跑」**。现在的形态里 baseline 是升级那天现采的，所以「baseline 本身是错的」这个失效模式一直存在。持续运行的 check 会让 drift 变成一条时间序列而不是一个快照，也就顺便把 baseline 的可信度问题解决了。实际上这件事已经部分发生了：checklist 和 evidence 模式在项目结束后外溢成了日常 infra health check (src: `interview-1-k8s_upgrade.md:101`)。V2 是把这个外溢正式化。
  第三，**把「幂等」这个词从设计文档里删掉，换成「可重入 + 可判定」**。我踩过的认知坑就在这里：Ansible 的幂等只覆盖 module 级，kubelet 的中间状态不在覆盖范围内 (src: `interview-1-k8s_upgrade_reference.md:154-157`)。V2 的正确抽象是每一步都要能回答两个问题：从头重跑安全吗，以及我怎么从集群实测判断这一步到底完成了没有。第二个问题比第一个更重要，因为它才是恢复的入口。

**归属边界**：工具的设计与实现是我的。evidence 目录结构、Ansible 目录结构、Python 调 Ansible 的核心逻辑都在 reference 里有具体形态 (src: `interview-1-k8s_upgrade_reference.md:216-286`)，可以细讲。Ansible 的 install-k8s 那套 role 体系是团队既有资产（58 个 role，见 S03），升级用的 playbook 是我在这个体系上加的，讲的时候要分清「既有的 role 库」和「我加的升级编排」。3-4h 是目标不是结果。

**可复用到**：02 监控（check 演化成常态 health check）、03 AIOps（门禁 + 证据链 + 人在环路，与 agent harness 的 Spec/Hook 同构）、90 行为面（把隐性知识变成可操作标准）。

---

## S03. kubeadm 自建生产集群：四层叠加与自管理控制面的运维负担

**Headline**：一个生产 K8s 集群是四层叠加起来的（Packer AMI → AWS 资源 → kubeadm 控制面 → 集群内组件），我能从任一层的故障反推到该层的设计决策；而选择自建控制面的真实代价，是这四层的每一层都变成我的 oncall 范围。

**适用题型**：从零搭一个生产集群你怎么做 / 讲讲你的 IaC 分层 / 为什么不用托管 K8s / K8s 网络怎么规划 / 控制面 HA 怎么做 / 你 codebase 里最大的技术债是什么。

**情境**：公司的 K8s 集群是自管理的，交付形态有两种：AWS 上的自管理集群，以及 onsite（客户机房，没有云 LB 可用）(src: `work-contexts/career/interview/interview-8-k8s-cluster-build.md:206`)。配套代码是 Packer（AMI）+ Ansible（资源编排 + 配置）+ kubeadm（控制面）(src: `interview-8-k8s-cluster-build.md:4`)。

**动作 / 我能讲到的深度**：

四层心智模型 (src: `interview-8-k8s-cluster-build.md:12-17`)：Layer 0 机器镜像（Packer AMI，含 OS + containerd + kubeadm）；Layer 1 AWS 基础设施（SG / EC2 / NLB / TG / ASG / LT 由 Ansible 建，VPC / Subnet / NAT / IAM Role 是 repo 外手动预建，vars 里只引用 ID）；Layer 2 K8s 控制面（kubeadm init/join + stacked etcd）；Layer 3 集群内组件（CNI / CCM / CSI / Ingress / 监控 / 日志）。

分层的判据是变更频率：Packer 固化「慢且稳定」的部分（装包），Ansible 做「快且多变」的部分（配集群）。所以 AWS 部署能跳过装 containerd/k8s（AMI 已含），onsite 必须现装 (src: `interview-8-k8s-cluster-build.md:51`)。

控制面 HA 的落点是网络：Ansible 建一个 internal NLB + Target Group（TCP 6443，健康检查 10s / 阈值 3）挂 3 台 master，然后把 NLB 的 DNS 回写进 `controlPlaneEndpoint`，kubeadm 配置引用它 (src: `interview-8-k8s-cluster-build.md:200`)。任一 master 挂，NLB 自动摘除，控制面不中断。选 NLB(L4) 不选 ALB(L7)，因为 apiserver 是 TLS + gRPC，需要 L4 透传不做 TLS 终止；`scheme=internal` 让控制面只在 VPC 内可达 (src: `interview-8-k8s-cluster-build.md:202`)。

首 master 与后续不对称：`master[0]` 跑 `kubeadm init --upload-certs`，`master[1:]` 跑 `kubeadm join --control-plane` 下载证书并加入 etcd，实现 stacked etcd HA (src: `interview-8-k8s-cluster-build.md:69`)。

三个 CIDR 绝不能重叠：Node 网络走 VPC（EC2 ENI 真实网卡）、Pod 网络走 CNI、Service 网络是 kube-proxy + iptables 的虚拟 IP (src: `interview-8-k8s-cluster-build.md:24-30`)。

**结果 / 我能拿出来的判断**：我不是「装过集群」，我能对每个决策说出替代方案和切换条件 (src: `interview-8-k8s-cluster-build.md:239-248`)：Ansible 管 AWS 资源 vs Terraform（集群多、要 drift detection / PR review 时换）；Calico IPIP vs Cilium ENI（要高性能 / 大规模 Service / Pod 进 VPC 且子网 IP 够时换）；kube-proxy iptables vs ipvs/eBPF（Service 数到数千时换）；单 AZ vs 跨 3 AZ（生产必须改）；SG 粗粒度信任边界 vs 逐端口最小化（安全合规要东西向隔离时换）；3 master vs 5（超大规模，但 etcd 写性能会降）。

**5 层追问防线**：

- **L1「你们的集群是怎么建起来的？」** → 答：直接上四层模型，然后说清边界：VPC / Subnet / NAT / IAM 是手动预建在 repo 外的，Ansible 从 SG 开始接手 (src: `interview-8-k8s-cluster-build.md:20-22`)。这个边界本身值得讲：它是「谁的生命周期更长」划出来的，VPC 是账号级长生命周期资产，集群是可以被销毁重建的。
- **L2「Ansible 的设计哲学是什么？58 个 role 怎么组织？」** → 答：三句话。Role 即组件，一个 role 等于一个可独立装的组件，标准结构 `tasks/{main,prepare,install,configure}.yml` + `templates/` + `defaults/`。Playbook 即编排顺序，`00-install-all-aws` 就是依赖拓扑的线性化（CNI 必须在 master join 之后、业务组件必须在 CCM/CSI 之后）。Jinja2 模板即配置生成，`kubeadm_config.yaml.j2` 把变量渲染成 K8s 实际配置，是整个体系的枢纽 (src: `interview-8-k8s-cluster-build.md:57-60`)。版本兼容用条件分支不分叉代码库：kubeadm API 版本 `<1.22` 用 v1beta2 / `>=1.22` 用 v1beta3，cloud-provider `<1.27` in-tree / `>=1.27` external (src: `interview-8-k8s-cluster-build.md:65-66`)。
- **L3「这套 codebase 最大的技术债是什么？」** → 答：大量 role 直接用 `shell` / `script` 调 `helm upgrade --install` 或 `kubectl apply` 兜底。务实，但反范式：不真正幂等、`--check` 失效（dry-run 骗人）、错误埋在 shell 输出里。这是这个 codebase 最大的技术债之一 (src: `interview-8-k8s-cluster-build.md:74`)。第二个是安全：`roles/cilium/templates/values.yaml.j2` 里硬编码过明文 AWS Access Key/Secret，而且已进 git 历史；修复路径是三步（IAM rotate/disable 该 key、改用 IRSA 或 instance profile、用 git filter-repo/BFG 清历史）(src: `interview-8-k8s-cluster-build.md:254`)。第三个是 join token 落盘且默认 24h 过期，扩容/重装要注意重新生成 (src: `interview-8-k8s-cluster-build.md:70`)。
  我讲这个的方式很重要：这些是我读代码读出来并且能给修复路径的，不是我造成的也不都是我修掉的。诚实说法是「我做过这套 repo 的系统性审计，这三条是我列出来的待修项」。
- **L4「设计权衡：Calico IPIP 还是 Cilium ENI？为什么默认 Calico？」** → 答：两种哲学，不是好坏。Calico IPIP：Pod 用 VPC 不认识的 `192.168.x.x`，跨节点走 IPIP 隧道再包一层。好处是不依赖 AWS、onsite 和 AWS 通用、Pod IP 不占 VPC 地址；代价是封装 MTU 开销（IPIP 头 20B，MTU 降到 1440）、Pod IP 在 VPC 不可见（SG 和流日志看不到）、少量 CPU 和延迟开销 (src: `interview-8-k8s-cluster-build.md:100-104`)。Cilium ENI：不封装，从 VPC 子网给 Pod 分配真实 VPC IP，eBPF 替掉 kube-proxy。好处是近裸金属性能、SG 能直接作用于 Pod、大规模 Service 转发更快；代价是消耗 VPC IP（子网不够大 Pod 起不来，这是最常见的 ENI 事故）、ENI/IP 上限限制单节点 Pod 密度、强耦合 AWS、需要 AWS 凭据 (src: `interview-8-k8s-cluster-build.md:106-110`)。
  默认 Calico 的真实原因是我们有 onsite 交付这个约束，一套代码要同时能装云上和客户机房 (src: `interview-8-k8s-cluster-build.md:112`)。切换到 Cilium 的前置条件是先算清子网 IP 容量，这个算不清就上是自找事故。
  这里我还有一个能显示深度的细节：IPIP 模式下跨节点 Pod 流量走的是 IP protocol 4，不是 TCP/UDP 端口。所以如果有人把 SG 从「VPC 内全放行」收紧成逐端口最小化，忘了放行 IPIP proto 4，跨节点 Pod 会完全不通 (src: `interview-8-k8s-cluster-build.md:197`)。这是安全加固和网络可用性之间一个真实的耦合点。
- **L5（最深）「自建控制面的运维负担具体是什么？如果只能保留一层自建，你保留哪层？」** → 答：负担可以精确列举，因为它就是我 oncall 的范围。Layer 0：AMI 的 kernel/OS patch 回归风险要我兜（升级项目里 worker 的 AMI diff 只验 kubelet 版本，其他差异由 AMI builder 测，这条分工线本身就是负担被转移的证据 (src: `interview-1-k8s_upgrade_reference.md:46`)）。Layer 1：ASG 扩出来的节点起不来或 join 不上是真实发生过的 oncall（见 S07）(src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md:56`)。Layer 2：etcd 的备份、quorum、证书轮转、逐 minor 升级全是我的，这就是 S01 那个项目存在的原因。Layer 3：addon 的版本矩阵（CCM 版本必须匹配 K8s minor、CA 版本必须 >= K8s 版本）(src: `interview-1-k8s_upgrade_reference.md:193, 200`)，以及 addon 升级打断部署这类事故（见 S08）。
  如果只能保留一层自建，我保留 Layer 0（AMI）。理由是：AMI 是我唯一真正需要控制的层，因为节点上的内核参数、containerd 配置、安全加固（osharden）、以及不可变替换这个能力全在这一层，而托管服务的节点镜像给不了我这些。反过来，Layer 2 是最应该外包的：etcd 和 apiserver 的运维知识密度极高、出错代价极大、而且和业务差异化零相关。这个排序其实就是 EKS + 自定义 AMI/自管理节点组这个组合，也是我说「如果重做上 EKS」时脑子里的形态 (src: `interview-1-k8s_upgrade_reference.md:163`)。

**归属边界**：这套 `install-k8s` repo 是团队既有资产，我不是它的原作者。我能声称的是：我基于真实代码做过系统性梳理与审计（结论到 `file:line` 级别）、我能对每个设计决策给出替代方案与切换条件、我在升级项目里在这套体系上加了升级编排。最近的 `[ONCALL-20941] K8S support 1.32` 这类版本适配 commit 是这个 repo 的持续演进 (src: `interview-8-k8s-cluster-build.md:68`)，⚠️ 待确认：这条 commit 是否是我的。不确认就不要说「我加了 1.32 支持」。

**可复用到**：07 AWS fundamentals（VPC/子网/SG/NLB/ASG 的全部一手场景）、02 监控（Layer 3 的监控日志组件）、05 blue/green（不可变替换与 LT 回滚）。

---

## S04. Jenkins 跨 K8s 集群迁移与 CI/CD 稳定化

**Headline**：把一套 Jenkins 从旧 K8s 集群搬到新集群，等于对它体内每一条隐含假设做一次全量审计；进 git 的东西全部干净迁走，只活在运行中系统里的东西全部在迁移当天以故障形式浮出来，我修的就是后者，并且修完把前人留下的 workaround 一起删了。

**适用题型**：讲一个你处理过的复杂故障 / CI/CD 你做过什么 / 配置即代码为什么重要 / 迁移怎么做 / 根因分析讲一个 / 你怎么处理技术债。

**情境**：公司把 Jenkins 从旧 K8s 集群迁到新 K8s 集群，两套 Jenkins 都跑在 Kubernetes 上、用 kubernetes plugin 动态起 agent pod (src: `adhoc_jobs/dynamic_resume_site/content/integration/jenkins_facts.md:9`)。迁移后构建大面积失败。我在这个共享 pipeline 库里是第一贡献者，306 commits，时间跨度 2025-03 到 2025-08 (src: `jenkins_facts.md:6`)。

**动作**：三类故障，我做的是系统性根因定位加修复 (src: `jenkins_facts.md:34-41`)。

第一类，**Maven 依赖链断裂**。根因是三件事叠加：外部仓库失效（maven.twttr.com 超时、repo.spring.io 认证失败）、迁移时 `.m2` 缓存没带过去、以及 Maven 的 `.lastUpdated` 失败记录会阻止重试。受影响的包有 hadoop-lzo、内部 SNAPSHOT、joda-time、ua-parser、hibernate-validator。修复三手：mirror 重定向到 Maven Central 并排除内部仓库、跨集群 `kubectl cp` 迁移包（带 SHA1 校验、权限修复、`_remote.repositories` 重写）、清理 `.lastUpdated` (src: `jenkins_facts.md:36`)。

第二类，**Debian Buster EOL**。构建镜像基于 Debian Buster，官方源下线导致 apt 全面失败。修复是切 `archive.debian.org` 加 `Check-Valid-Until false`；后续把 agent 镜像升到 Bookworm (src: `jenkins_facts.md:38`)。

第三类，**Arcanist / PHP 兼容性**。land-code pipeline 里 2019 年版 Arcanist/libphutil 与 PHP 8 不兼容（`Phobject::rewind()` 返回类型错），强制所有 arc 命令走 PHP 7.1；另外修了 pipeline 内 git credential 问题（`@Library` 语法错误 + credential helper 配置）(src: `jenkins_facts.md:40`)。

治理动作是这个故事的第二个亮点：制品正式迁移到位之后，我把 Jenkinsfile 里前人留下的 workaround 代码删掉了（3 个 "Remove workaround codes of mvn package install" commit）(src: `jenkins_facts.md:36`)。构建用的 Jenkinsfile 在上游仓库陆续失联那段时间长出了一批 workaround stage：元数据修复、依赖调试、直接下载兜底；根因修完这些 stage 就是死代码，遮蔽信号、拖长构建、并且保证会迷惑下一个读 pipeline 的人 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_jenkins.md:118`)。

**结果**：迁移后 CI/CD 稳定化完成 (src: `jenkins_facts.md:9`)。方法论产出是一条判据：pipeline-as-code 和「点 UI 攒出来的雪花 Jenkins」在运维意义上的差别是，雪花在定义上不可恢复；这次迁移就是对这个属性的审计，repo 里的东西（约 275 个 pipeline 定义文件 + 16 个 shared library groovy 步骤）全部干净地搬了过去，只活在运行中系统里的东西全部以故障形式浮出 (src: `p_jenkins.md:112`；`p_jenkins.md:139`)。

**5 层追问防线**：

- **L1「讲一下那次故障你怎么定位的」** → 答：入口信号是构建大面积失败，第一个判断是「大面积同时失败 = 共享依赖层的问题，不是各 pipeline 各自的问题」，所以我不从单个 pipeline 查，从共享层查：agent 镜像、.m2 缓存、外部仓库可达性。三条线分别落到三个根因。这个「多租户同一分钟以同一机制失败就是共享层信号」的路由判断我在别的事故里也用过 (src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md:20`)。
- **L2「Maven 那条为什么修了还是失败？」** → 答：因为 `.lastUpdated` 这个机制。Maven 拉不到包会写一个失败标记，之后即使上游恢复也不再重试，直接用缓存的失败结论。所以「修好源」和「构建能过」之间还有一步「清理失败标记」。这是我特别喜欢讲的一类根因：**系统的失败缓存本身成了故障的一部分**。同一个形状在别的地方也出现过，比如 K8s 的 `imagePullPolicy: IfNotPresent` 会让相同 tag 的新镜像不生效，所以我的部署纪律是每次用不同 tag (src: `rules/skills/workflow_dcluster_starrocks_cn_deployment.md`「踩过的坑」表)。
- **L3「你的修复脚本长什么样？为什么这么写？」** → 答：所有修复脚本一个形状：guard → 备份 → 收敛 → verify。apt 修复脚本先确认自己确实跑在 Buster 上，否则直接空操作退出；对现有配置做带时间戳的备份；然后**整体覆写**配置而不是逐行打补丁；依赖修复脚本结尾是一个显式的 verify 函数，断言制品此刻确实存在，而不是假设成功 (src: `p_jenkins.md:34, 92`；`jenkins_facts.md:113`)。
  为什么覆写而不是打补丁：覆写到已知良好状态是收敛的，第二次运行产生和第一次相同的终态，跑两遍安全、断在中间没有代价、从头重跑即可。反例是追加行或假设初始状态干净的脚本：跑两遍，一个事故变成两个 (src: `p_jenkins.md:92`)。
  还有一个结构性动作：每个 fix 脚本配对一个只读的 diagnose 脚本（采集系统版本、源清单、`apt-get update --dry-run`、对已知 EOL 代号告警，全程不改任何东西）。诊断作为独立于修复的 artifact 存在，把「先确认故障模式再动手」固化成了结构而不是依赖纪律 (src: `p_jenkins.md:96`；`jenkins_facts.md:114`)。
- **L4「设计权衡：为什么不干脆搭一个内部 Maven mirror？」** → 答：这是正确的长期解，我在文档里写成了建议，但**没有落地证据**，所以我不会说我做了 (src: `jenkins_facts.md:131`)。我诚实的自我评价是：`fix-*.sh` 系列本质是 `kubectl exec` 包装的 runbook 自动化，作用对象是单个 agent pod 的 `.m2` 缓存，不是平台级修复 (src: `jenkins_facts.md:131`)。当时的权衡是止血优先：构建全挂是在阻塞发布，而搭 mirror 是一个需要容量、权限、和跨团队协调的项目。正确的说法是「我做的是止血 + 根因文档化 + workaround 清理，平台级修复我给了方案没有落地」。
- **L5（最深）「这次迁移暴露的最根本问题是什么？如果你重新设计这套 Jenkins，第一件改什么？」** → 答：最根本的问题是**状态活在运行中的系统里而不是 git 里**，而且这个状态是隐式的、没人知道它存在，直到搬家。具体标本有三个：上游早已失联的缓存制品（缓存掩盖了依赖已死这个事实好几年）、agent pod 里手工调过的 Maven 配置、以及 `jenkins.yaml` 这个东西本身，它其实是捕获的 agent pod spec 快照，不是 JCasC，也就是说 controller 配置根本没进代码 (src: `p_jenkins.md:145`；`jenkins_facts.md:133`)。
  所以第一件改的是把 controller 配置也纳入 JCasC，让「配置即代码」这个判据延伸到 Jenkins 本体，而不是只覆盖 pipeline 定义 (src: `p_jenkins.md:112`)。第二件是 shared library 的分支治理：`@Library('jenkinsconfig@east-mgt-rui')` 长期指向个人分支，这是弱项，我不会声称我们做到了 configuration-as-code 治理 (src: `jenkins_facts.md:133`)。第三件是可测试性：我那段时间有 91 个 Debug/test commit，说明当时没有 pipeline 的本地验证或 staging 环境，只能靠生产 Jenkins push-and-run 反复试 (src: `jenkins_facts.md:68, 132`)。这个我当自嘲式论据用，它正好证明「命令式 CI 的可测试性差」不是抽象论点，我付了这个税。

**归属边界**：三类故障的定位与修复、修复脚本、workaround 清理、agent 镜像现代化（Dockerfile 我 touch 50 次，是主要维护者）都是我的 (src: `jenkins_facts.md:47`)。**不能声称的**：`vars/*.groovy` 的 signoff 系列和 `pipelines/release/` 是团队既有资产，我不是主要作者；`docs/release-process-analysis.md` 是我做的**流程分析文档**（读懂了整个 release 状态机），可以作为背景知识讲，不可写成「我建了 release 系统」(src: `jenkins_facts.md:72`)。JCasC 一律用「我会采用的标准」口径，repo 里没有 JCasC (src: `p_jenkins.md:145`)。

**可复用到**：05 blue/green（迁移即环境切换，新旧双环境并行期）、90 行为面（修完顺手删 workaround = 主动治理）、01 数据库运维（`.lastUpdated` 这类失败缓存的思维模式可迁移）。

---

## S05. nightly 生产镜像流水线：把 pipeline 当系统设计的四个属性

**Headline**：我从零写了一个 cron 驱动的 nightly 生产镜像构建编排器，跨 4 条生产分支 × 3 类服务，它同时具备参数持久化、下游状态收集、失败归因加 oncall 路由、和贯穿全链的幂等重跑门，这四个属性就是「把 pipeline 当生产系统」的具体含义。

**适用题型**：CI/CD 你做过什么最有系统性的东西 / 幂等性怎么落地 / 流水线的可观测性怎么做 / 告警怎么路由 / 讲一个你的设计而不是你的修复。

**情境**：需要每天 nightly 构建生产 Docker 镜像，覆盖 4 个生产分支 × 3 类服务（FP Services / API Server / NGSC），并编排下游 pre-process → build-image 的 job 链 (src: `adhoc_jobs/dynamic_resume_site/content/integration/jenkins_facts.md:17`)。

**动作**：四个设计点，每个都对着一个真实的失效模式。

**参数持久化**，对着「cron 构建用错分支」。Jenkins declarative pipeline 的参数在 cron 触发时会回落到 default 值。我把上次人工触发的参数写到持久卷上的 properties 文件，cron 触发时读回、人工触发时保存并动态更新 job 的参数定义 (src: `jenkins_facts.md:20`；`jenkins_facts.md:112`)。这条消除的是「cron 重跑用了 default 参数」这种静默走错的不一致。

**下游状态收集**，对着「链式 pipeline 状态不可见」。逐个下游 job 收集 service / branch / job / number / result / console url 到一个 `BUILD_RESULTS` JSON，并且**失败前先落盘保存已有结果**，partial results 不丢 (src: `jenkins_facts.md:21, 122`)。

**失败归因加 oncall 路由**，对着「谁该看这条告警」。`FAILED_SERVICE` / `FAILED_BRANCH` 归因，异常路径也回填（catch 里从 buildGroups 提取服务名）；失败按服务名映射到对应 oncall 在 Slack @ 到人；成功失败双通道（Slack + email）；通知发送本身 try/catch 不阻塞 pipeline (src: `jenkins_facts.md:22, 123-124`)。通知内容包含每分支每服务的明细，以及「因前序失败未执行」的剩余项 (src: `jenkins_facts.md:125`)。

**FORCE_BUILD 幂等开关贯穿全链**，对着「重跑会不会重复产出」。参数从顶层编排器逐层透传到叶子 job（production-build → pre-process → base build），底层 build job 先查镜像 tag 是否已存在，存在且非 force 就跳过构建 stage (src: `jenkins_facts.md:23, 110-111`)。这个设计显式区分了两种语义：「重跑补齐」和「强制重建」。

**结果**：859 行的 nightly production-build 编排器，我创建的 (src: `jenkins_facts.md:26`)。在这个共享 pipeline 库里我是第一贡献者，306 commits (src: `jenkins_facts.md:6`)。四个属性齐全，直接对上我自己的 CI/CD 可靠性框架里的幂等和错误处理两条 (src: `jenkins_facts.md:30`)。

**5 层追问防线**：

- **L1「Jenkins 你熟到什么程度？」** → 答：我不用「会写 Jenkinsfile」回答这个问题。我的回答是：熟悉 Jenkins 应该读作「能把一条交付流水线当生产系统来拥有」：它的故障模式、它的状态、它的恢复路径，而不是它的语法 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_jenkins.md:124`)。然后我给三个判据（幂等可重入、状态可观测可诊断、配置即代码）和这个 859 行编排器作为实物。
- **L2「幂等在 Jenkins 里怎么落地？Jenkins 本身不是不幂等吗？」** → 答：对，这正是重点。声明式的 reconcile 天生幂等，命令式的 Jenkins pipeline 天生不是，模型里没有任何东西保证一个 job 跑两遍收敛到同一状态 (src: `p_jenkins.md:84`；`work-contexts/career/interview/interview-5-cicd_reliability.md:33`)。所以工具不给你的幂等性，要靠你自己构造。我构造的方式是三类：skip-if-exists（查镜像 tag 是否存在）、checkpoint 文件（参数持久化、partial results 落盘）、备份加校验（修复脚本的 SHA1 verify）(src: `jenkins_facts.md:110-113`)。
  诚实边界我会主动给：这是**操作级幂等**，不是声明式 reconcile (src: `jenkins_facts.md:116`)。而且我的修复脚本大多 `set -e` 快速失败但没有事务回滚，dry-run 只在诊断脚本里有、修复脚本没有 dry-run 模式 (src: `jenkins_facts.md:116`)。
- **L3「你的 pipeline 有 SLI 吗？可观测性做到什么程度？」** → 答：这里我必须分清做到的和主张的。做到的是**事件通知层**：构建级 Slack/email、失败归因、按服务路由到 oncall、partial results 落盘 (src: `jenkins_facts.md:127`)。**没做到的**是 metrics 化：没有 Prometheus 指标、没有构建时长趋势、没有 DORA 指标采集 (src: `jenkins_facts.md:127`)。
  「pipeline 应该有自己的 SLI（成功率、时长、排队时间）」是我衡量一套成熟设施的标准，我以判据口径讲它，不声称已实施 (src: `p_jenkins.md:50, 108`)。这个区分我认为比多讲一个功能更有价值：面试官要的是知道我能分清 aspiration 和 implementation。
- **L4「设计权衡：为什么 FORCE_BUILD 要一路透传，不在顶层判断完就好？」** → 答：因为幂等的判定点必须在**产出物的所有者**那里，不能在编排器。编排器不知道叶子 job 的产出物存不存在，它只知道自己调了谁。如果顶层判断，就要把「镜像 tag 命名规则」这个知识复制到顶层，两处规则会漂移。透传参数、叶子自查，是把判定权留在唯一知道真相的那一层。这个设计的一般化表述是：**幂等的判定必须基于目标状态的实测，不能基于调用者的记忆**，这和 S01 里「判断一步是否完成必须回到集群实测镜像版本 × health，不能信 state 文件」是同一条原则 (src: `work-contexts/career/interview/interview-1-k8s_upgrade_reference.md:69-76`)。
  代价我也讲：参数逐层透传是一种耦合，加一个参数要改三层。更干净的做法是叶子 job 从一个共享配置读，但那需要 shared library 的配置治理，而我们的 shared library 分支治理本身就是弱项 (src: `jenkins_facts.md:133`)。
- **L5（最深）「自动化到这个程度之后，你怎么知道自动化本身没有变成新的问题？」** → 答：我有一个明确的反论，而且有标本。自动化不是目的，程度更高也不是单调更好。标本就是 S04 里那批 workaround stage：上游仓库陆续失联的时候 Jenkinsfile 长出了元数据修复、依赖调试、直接下载兜底这些 stage，等制品正式迁移到位它们全变成死代码，遮蔽信号、拖长构建、迷惑下一个读者，我的修复动作之一就是删掉它们 (src: `p_jenkins.md:118`)。
  一般化：自动化的老化方式和告警规则一模一样，每一段都编码着会静默过期的假设；而一条没人看的自动化路径会在无人察觉中腐化，人工闸门里至少有一个会察觉异常的人 (src: `p_jenkins.md:118`)。自动化还会打开新的故障面：凭据集中在流水线够得着的地方、插件供应链、脚本本身的腐化 (src: `p_jenkins.md:120`)。我们 repo 里就有这个故障面的实证：`jenkins.yaml` 里意外捕获了明文 AWS 凭据 (src: `jenkins_facts.md:142`)。
  所以我把生产 release 流程里那个人工 review 与 approval 环节读作**设计决策而不是缺陷**：对低频且爆炸半径大的操作，一道有意保留的人工闸门往往是更可靠的那个组件 (src: `p_jenkins.md:62, 120`)。我为之辩护的排序是：可运行、可观测、可恢复在前，配得上的部分再自动化。高频且可逆的自动化，低频且不可逆的设闸。

**归属边界**：production-build 编排器（859 行）是我创建的，参数持久化 / 下游状态收集 / 失败归因 / FORCE_BUILD 透传四个设计点都有 commit 可证 (src: `jenkins_facts.md:26-28`)。`pipelines/release/` 和 signoff 系列不是我的 (src: `jenkins_facts.md:72`)。DORA 指标只能讲框架不能报数字：`interview-5` 里的简历 bullet 明确标着「待填真实数字」，说明我手上**没有**真实的 change failure rate / rollback MTTR (src: `interview-5-cicd_reliability.md:91-93`)。⚠️ 被问到「你们的 change failure rate 是多少」时，正确答法是「我们没有系统性采集，这正是我说 metrics 化是缺口的意思」，不许估一个数字出来。

**可复用到**：02 监控（告警路由到 owner、告警治理）、03 AIOps（幂等 + 门禁 + 证据是 agent harness 的同构结构）、90 行为面（发现摩擦并系统性消除）。

---

## S06. jenkins-mgt：Jenkins 藏起了自己的状态，所以我把它抽出来

**Headline**：Jenkins 的 UI 一次只给你看一个 job、一个 build、一组参数，而我们的链式 pipeline 有四跳且横跨迁移前后两套环境，所以我写了一个聚合面板把 job 状态变成可提取的数据，而不是靠翻页面拼出来的印象。

**适用题型**：讲一个你自己造的工具 / 你怎么发现问题 / 主动性的例子 / 可观测性的理解。

**情境**：Jenkins 原生 UI 是单 job 视角，链式 pipeline（entrypoint → pre-process → build-image → deploy）没有统一视图；迁移期还要跨新旧两套 Jenkins 环境对比构建结果；参数难追溯、replay 麻烦 (src: `adhoc_jobs/dynamic_resume_site/content/integration/jenkins_facts.md:55`；`adhoc_jobs/dynamic_resume_site/content/projects/p_jenkins.md:50`)。

**动作**：Flask 应用，通过 Jenkins JSON API 抓取，按真实 pipeline 执行顺序组织 Folder → Job → 最近 5 次 build 三层视图；新旧两套 Jenkins 环境一键切换；一键用上次成功构建的参数 replay、参数追溯与复制；`ThreadPoolExecutor` 并发抓取（max_workers 8/10）；凭据不落 repo（走 `.env`）；有单元测试；Docker 加 K8s 部署清单齐全 (src: `jenkins_facts.md:55-62`)。

**结果**：`jenkins_manager.py` 1088 行、`app.py` 10 个 REST 端点、454 行测试 (src: `jenkins_facts.md:62`)。并发抓取实测总耗时 8.31s → 5.79s（30.3%），吞吐 1.20 → 1.73 jobs/s (src: `jenkins_facts.md:59`)。

**5 层追问防线**：

- **L1「为什么要自己写，不用现成插件？」** → 答：需求是迁移期特有的：**同时**看两套 Jenkins 环境并对比同一个 pipeline 在两边的构建结果。这是一个临时且局部的需求，值得一个小工具不值得一个平台。我对这个工具的定位很清楚，它体现的是一个判据（job 状态应该是可提取的数据），不是一个平台级交付 (src: `p_jenkins.md:50`)。
- **L2「30% 的提升是怎么来的？」** → 答：Jenkins JSON API 是 per-job 的，页面要展示 N 个 job × 最近 5 次 build，串行抓就是 N 次往返，全是 IO 等待。`ThreadPoolExecutor` 并发（max_workers 8/10）把等待重叠起来，8.31s → 5.79s (src: `jenkins_facts.md:59`)。我会主动说明这个数字的性质：这是一个本地实测的页面加载时间，不是生产 SLI，样本很小。
- **L3「这个工具算你的工程能力还是你的个人爱好？」** → 答：我把它明确标注为**个人工具项目（personal tooling）**，不冒充团队交付 (src: `jenkins_facts.md:64`)。它的价值点是「发现工作流摩擦 → 自己造工具消除」，加上有量化数字、有单测、有部署清单，说明我做个人工具也用工程标准。
- **L4「设计权衡：为什么是拉取式展示，不做成告警？」** → 答：因为它解决的是「诊断时的信息聚合」问题，不是「异常时的通知」问题，这两件事的正确形态不同。通知那一半我在 production-build pipeline 里做了（失败归因加 oncall 路由，见 S05）。诚实边界：jenkins-mgt 补的是状态可见性，但也是拉取式展示，不是告警系统 (src: `jenkins_facts.md:127`)。所以我们在 CI/CD 上真正缺的那一块是 metrics 化和趋势，这两个工具都不覆盖。
- **L5（最深）「一个更成熟的团队应该怎么做这件事？」** → 答：不做这个工具。链式 pipeline 需要一个外部聚合器，本身就是「Jenkins 的模型和我们的交付模型不匹配」的症状。成熟形态有两条路：一条是把交付逻辑收敛成一个真正的 pipeline 对象（Jenkins 的 multibranch / pipeline-as-code 加上 stage 级可视化，或者干脆换声明式 CD），另一条是把 build/deploy 状态推到统一的可观测平面（构建事件打成 metrics 和 Grafana annotation，让部署竖线出现在所有业务图表上）。第二条其实是我在监控体系那边的做法，机制是 Grafana annotation API (src: `work-contexts/career/interview/interview-3-monitoring_reference.md:140`)。我写这个面板是在既有约束下的局部最优，不是我认为的终态。

**归属边界**：个人项目，personal tooling，独立于工作 repo 的事实 (src: `jenkins_facts.md:53, 64`)。

**可复用到**：02 监控（状态可提取 vs 印象）、03 AIOps（工具化的自驱力）、90 行为面。

---

## S07. ASG 扩出来的节点起不来：分层隔离定位，先回滚到 known-good

**Headline**：自动扩容拉起的 EC2 要么立即被终止要么起来后永远 join 不上集群，我用严格的分层隔离定位（ASG 活动 → launch template → user-data/cloud-init → kubeadm join → kubelet 日志），因为「启动失败」和「加入失败」的归属完全不同；沉淀的操作规则是容量受损时先回滚到已知良好的 LT 或 AMI 恢复容量，再追根因。

**适用题型**：讲一个 AWS 加 K8s 的故障 / 不可变基础设施的实际好处 / 你怎么在压力下决定「先恢复还是先定位」/ 自动扩容出问题怎么查。

**情境**：Autoscaling 拉起的 EC2 实例要么立即死掉，要么启动后始终无法加入 Kubernetes 集群 (src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md:56`)。

**动作**：严格分层隔离：先看 ASG 活动记录与 launch template，再查 user-data 与 cloud-init 结果，然后是 kubeadm join 路径，最后是 kubelet 日志 (src: `oncall_track_record.md:56`)。这个顺序的理由是归属：启动失败（ASG/LT/AMI/容量/权限）和加入失败（user-data/join token/网络/kubelet 配置）是完全不同的两个 owner 和两套修复动作，混着查会来回横跳。

**结果**：沉淀成一条操作规则：**容量受损时先回滚到已知良好的 launch template 或 AMI 恢复容量，然后再追根因** (src: `oncall_track_record.md:56`)。

**5 层追问防线**：

- **L1「怎么查的？」** → 答：给分层顺序和每层的判据。ASG 活动记录会直接告诉你实例是「被 ASG 终止的」（健康检查失败/容量策略）还是「起来了但没注册」，这一条就把问题分成两个完全不同的分支。
- **L2「为什么先回滚 LT 再查根因？这不是丢证据吗？」** → 答：因为回滚 LT 不丢证据。这是不可变基础设施的一个具体好处：LT 是版本化的，回滚是「指向旧版本」而不是「改回来」，旧版本和新版本同时存在，diff 随时可看。而且没起来的实例日志我可以先取，实例本身可以保留一台不终止。这和我在数据类事故里的判断不同：疑似数据损坏时不能自动回滚，因为回滚会盖掉证据 (src: `work-contexts/career/interview/interview-5-cicd_reliability.md:43`)。区分点是**回滚动作本身是否覆盖状态**：LT 回滚不覆盖，数据回滚覆盖。
- **L3「和 K8s 升级里的 worker 替换是同一套机制吗？」** → 答：是同一套，而且这次故障就是那套机制的日常压力测试。升级时 worker 走的是新 AMI → 更新 LT → ASG Instance Refresh 20% batch，回滚路径是停止 Instance Refresh 加 LT 回退旧 AMI (src: `work-contexts/career/interview/interview-1-k8s_upgrade.md:69`)。也就是说升级的回滚方案和这次 oncall 的恢复动作是同一个动作。这一点我很在意：**回滚路径应该是日常已经在走的路径，而不是只在应急计划书里存在的路径。**
- **L4「设计权衡：为什么 worker 用 ASG Instance Refresh，不用 Ansible 直接 drain 加原地升 kubelet？」** → 答：Instance Refresh 天然支持 batch size 和 pause-on-failure，并且与 ASG lifecycle hook 集成，比手动 drain 更安全；Ansible 只负责 drain 协调和升级后验证 (src: `work-contexts/career/interview/interview-1-k8s_upgrade_reference.md:310`)。更根本的理由是可变 vs 不可变：原地升 kubelet 会产生「半升级的节点」这种中间状态，而中间状态是 Ansible 的幂等覆盖不到的地方 (src: `interview-1-k8s_upgrade_reference.md:154-157`)。换机器把「修一台半死的节点」变成「删掉它再要一台」。
- **L5（最深）「不可变基础设施的边界在哪？什么时候它反而是负担？」** → 答：两处。第一，**有状态节点**。承载数据库 pod 的节点不能随便换，因为 drain 它就是在动数据面。所以升级里数据库节点是提前测绘、排在每个波次最前、逐节点推进、每个服务验证通过才走下一个 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_k8s_upgrade.md:49`)。不可变的成本随节点的状态量线性上升。第二，**镜像构建的反馈周期**。不可变意味着任何一行配置改动都要重新出 AMI，反馈周期从秒级变成分钟到小时级。所以分层的判据是变更频率：Packer 固化慢且稳定的部分，Ansible 做快且多变的部分 (src: `work-contexts/career/interview/interview-8-k8s-cluster-build.md:51`)。把高频变更的东西塞进 AMI，是我见过的最常见的分层错误。

**归属边界**：这是 oncall 处理过的真实生产事故，来自我的事故库 (src: `oncall_track_record.md:106`)。事故库共 21 份完整调查记录，其中 20+ 为生产 P1/P2 (src: `oncall_track_record.md:88`)。这一条属于 infra 域。ASG / LT / AMI 这套体系不是我建的（团队既有的 `install-k8s` 资产），我是它的运维者和升级路径的设计者。

**可复用到**：07 AWS fundamentals（ASG / LT / user-data / cloud-init 全链）、05 blue/green（LT 版本化即不可变发布）、01 数据库运维（有状态节点的替换约束）。

---

## S08. 一次 helm upgrade 阻断了全集群的部署

**Headline**：一次 ingress-nginx 的 helm upgrade 重建了 ValidatingWebhookConfiguration 但丢了 caBundle，于是所有带 Ingress 的 helm install 全部因为 x509 失败；定位关键是「多个租户同一分钟以同一机制失败 = 集群级基础设施信号」，所以我直接跳过了应用层。

**适用题型**：讲一个升级/变更引起的事故 / 准入控制 webhook 你理解到什么程度 / 你怎么快速判断故障层级 / helm 的坑。

**情境**：一次 ingress-nginx 的 helm upgrade 之后，所有包含 Ingress 的 helm install 全部报 `x509: certificate signed by unknown authority` 失败 (src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md:20`)。

**动作**：路由判断先行：多个租户在同一分钟以同一机制失败，这是集群级基础设施信号，所以调查直接跳过应用层 (src: `oncall_track_record.md:20`)。根因是 helm upgrade 重建了 ValidatingWebhookConfiguration 但没有带上 caBundle，API server 无法验证 webhook 的 TLS，于是所有触发该 webhook 的请求全部被拒。修复是从 Secret 把 CA patch 回去；长期方案是让 webhook 证书脱离一次性 helm hook 管理 (src: `oncall_track_record.md:20`)。

**结果**：修复恢复；长期动作是把 webhook 证书的生命周期从 helm hook 里搬出来 (src: `oncall_track_record.md:20`)。

**5 层追问防线**：

- **L1「怎么定位的？」** → 答：先给路由判断（多租户同机制同时失败 → 共享层），再给证据链（错误是 x509 而不是业务错误 → TLS 信任问题 → 谁在验谁的证书 → API server 在验 webhook 的 → caBundle）。
- **L2「准入控制 webhook 的机制讲一下」** → `[理论]` 答：API server 的请求处理链是认证 → 鉴权 → 准入（mutating → schema 校验 → validating）→ 持久化。ValidatingWebhookConfiguration 告诉 API server「符合这些规则的请求要转发给这个 webhook 服务，并且用这个 caBundle 验它的证书」。所以 caBundle 是 API server 单向信任 webhook 的唯一凭据，丢了它，API server 无法建立到 webhook 的可信连接，请求就按 `failurePolicy` 处理。这里的关键设计参数是 `failurePolicy`：`Fail` 意味着 webhook 不可用时拒绝请求（安全优先，但把 webhook 变成了集群写入路径上的单点），`Ignore` 意味着放过（可用性优先，但准入策略会被静默绕过）。这次事故的形态说明它是 `Fail`。
- **L3「这是 helm 的问题还是 chart 的问题？」** → 答：是「把证书生命周期绑到一次性 hook 上」这个设计的问题，helm 只是暴露了它。一次性 hook 的语义是「安装时跑一次」，而 upgrade 会重建资源；证书这种需要跨 upgrade 存活的状态放在一次性 hook 里，就是把长生命周期状态托付给短生命周期机制。所以长期修复是让 webhook 证书脱离 helm hook 管理 (src: `oncall_track_record.md:20`)，比如交给 cert-manager 的 CA injector 这类专门管证书生命周期的控制器 `[理论]`。
- **L4「设计权衡：那你们为什么还大量用 helm？」** → 答：我们确实大量用，而且是以一种我明确认为是技术债的方式用：Ansible 的很多 role 直接 `shell` 调 `helm upgrade --install`，不真正幂等、`--check` 失效、错误埋在 shell 输出里 (src: `work-contexts/career/interview/interview-8-k8s-cluster-build.md:74`)。所以我对 helm 的定位是：它是一个模板渲染 + release 记账工具，不是一个 reconcile 控制器。把它当控制器用（指望它维持期望状态）就会踩这次这种坑，因为它只在你执行命令的那一刻收敛，之后不再看。
  我的 helm 深度边界我会主动画清：我写过 chart（dcluster 的 starrocks-cn chart，含 values / configmap / deployment）(src: `rules/skills/workflow_dcluster_starrocks_cn_deployment.md`「关键路径」表)，我处理过 chart 引起的生产事故，但我没有做过大规模的 chart 库治理（library chart、umbrella chart 的依赖策略、chart 的测试与发布流水线）。那部分是我的中环。
- **L5（最深）「怎么让这类事故在下一次升级前就被发现？」** → 答：这正好落回 S01 的门禁体系，而且暴露了它的一个缺口。addon 升级在我的升级流程里是有 gate 的，但 gate 的形式是组件级验证：CCM 验 pod Running + 所有 node 有 providerID + 存量 LB TG healthy；Calico 验跨节点 pod-to-pod ping；CA 验 drain 触发 scale-out 成功 (src: `work-contexts/career/interview/interview-1-k8s_upgrade.md:74-78`)。这三个 gate 有一个共同点：它们验的是**该组件自己还活着**。而这次事故的形态是「组件活着，但它对集群写入路径的副作用坏了」。
  所以正确的补法是加一类 gate：**功能性 synthetic 验证**，也就是升级后真的 `helm install` 一个带 Ingress 的最小 workload，看它能不能成功。这和我升级 roadmap 里写的 synthetic health check（主动 deploy test pod）是同一个东西 (src: `work-contexts/career/interview/interview-1-k8s_upgrade_reference.md:177`)。这个故事对我最大的价值就是它证明了那条 roadmap 不是为了自动化省时间，而是为了覆盖一整类「组件健康但功能坏了」的失效模式。

**归属边界**：oncall 处理的真实生产事故，来自我的事故库 (src: `oncall_track_record.md:20, 106`)。⚠️ 待确认：这次 helm upgrade 是不是我自己执行的（是我做变更踩的坑，还是我作为 oncall 接手别人的变更）。这个区别在面试里会被问到（「那次升级是你做的吗」），答错方向会显得在抢功或在推责。evidence 只说是 oncall 处理的事故，没说执行者是谁。安全说法：「这是我 oncall 期间处理的一次 addon 升级引发的事故」。

**可复用到**：02 监控（假信号 vs 真影响、多租户同时失败的路由判断）、01 数据库运维（同一事故库）、05 blue/green（变更后回归）。

---

## S09. Intel BKC daemon：把一份文档编译成 control loop（真实性边界最严的一个故事）

> ⚠️ **这个故事的真实性分栏是硬约束**，来源 `adhoc_jobs/dynamic_resume_site/content/projects/p_bkc.md` 的 SOURCES 节（第 209-238 行）。**只有第一栏能说「我做了」，第二栏只能用设计口径讲（「这类 controller 必须如何构建」）。** 说错会被问穿，因为设计口径的东西一追细节就没有一线痕迹。

**Headline**：Intel 5G vRAN 的 Best Known Configuration 原本只是一份 doc 里的 prose 加复制粘贴的 shell，我把它变成了 git 里声明式、被持续审计的 desired state，做法是每台机器一个 systemd 层的 daemon，跑在 K8s 之下，覆盖约 30 台裸金属服务器。

**适用题型**：IaC 你做过什么 / 声明式的本质是什么 / reconcile 你理解到什么深度 / 讲一个你的设计而不是运维 / 配置漂移怎么处理 / 一个不 crash 只降级的故障怎么发现。

**情境（可声称）**：Intel 5G 云化把无线接入网的 L1/L2 从专用芯片搬到通用 Xeon 服务器加标准 NIC 加软件（FlexRAN 参考架构）。这套软件能否跑出认证性能，完全取决于底层硬件、固件、内核是否被精确调到 Intel 验证过的那组值，即 BKC (src: `p_bkc.md:116-117`)。我做的是 IaC 这一层：这批 fleet 的硬件层配置管理 (src: `p_bkc.md:118`)。规模约 30 台服务器，分布在多个 cluster，场景是多个内部测试集群加交付客户的裸机集群 (src: `p_bkc.md:223-224`)。NIC 是 Intel E810 100GbE (src: `p_bkc.md:225`)。

起点（可声称）：在这个系统之前 BKC 从没被编译成任何可执行的东西，它以三种形式存在：doc 里的 prose 加几段复制粘贴的 shell、工程师脑子里的部落知识、以及每台机器上「当初装的时候大概是对的」这个假设。排一台机器就是打开 doc 一段段复制命令、肉眼看输出，没有 enforcement、没有审计、没有 drift 检测。这比 Ansible 更原始：不是 Ansible 不够好，而是当时连 Ansible 这一级都没有 (src: `p_bkc.md:120, 222`)。

**动作（严格分两栏）**：

**可声称为「我构建并运行了」的部分** (src: `p_bkc.md:215-226`)：
- 一个持续运行的自研 machine-level controller，daemon 形态，跑在 systemd 层，一台节点一个 (src: `p_bkc.md:220`)
- **审计与监控能力**：daemon 持续巡检每台节点并上报 compliance 加 drift 时间戳。采集面是 BIOS 走 Redfish/BMC 与带内厂商工具、kernel 读 `/proc/cmdline`、tuning 读 sysctl 和 tuned、NIC 用 ethtool 和 devlink (src: `p_bkc.md:187, 221`)
- 范围刻意停在 systemd 层，不做成 K8s Node Operator，因为场景恰恰是「K8s 之下、客户裸机、可能根本没有 K8s」(src: `p_bkc.md:202, 226`)

**只能用设计口径讲的部分**（说成「这类 controller 必须如何构建」，不说「我做了」）(src: `p_bkc.md:228-238`)：
- 完整的风险分级 reconcile（🟢 在线可逆立即改 / 🟡 需先 drain / 🟠 需维护窗口加重启 / 🔴 只审计绝不自动改）(src: `p_bkc.md:169-172, 233`)
- pull-based 架构、只读 aggregator、无反向命令通道 (src: `p_bkc.md:161, 238`)
- reboot token 按 failure domain 限流的分布式 lease (src: `p_bkc.md:195, 236`)
- 跨重启状态机、隔离核 CPUAffinity 不扰动被监控对象、签名 profile 与信任边界 (src: `p_bkc.md:193-196, 234-237`)
- 具体服务器/加速卡 SKU 一律用代际说法（Ice Lake 代、100G NIC、FEC 加速卡），不落型号 (src: `p_bkc.md:232, 244`)

**结果**：把硬件层的盲区点亮成每节点 compliance 加 drift 时间戳。这一条我可以完整声称，因为它就是 L1 审计能力的产出 (src: `p_bkc.md:221`)。

**5 层追问防线**：

- **L1「这个项目是做什么的？」** → 答：一句话，把一份文档编译成一个 control loop。desired state 从散落在 prose 和人脑里，变成 git 里声明式、机器可执行、被持续 enforce 的形式 (src: `p_bkc.md:120`)。
- **L2「为什么 BKC 天生就是 desired state？」** → 答：BKC 是一份被验证过、能交付认证性能的完整栈配方：BIOS（C-state / P-state 策略、Turbo、SR-IOV、VT-d/IOMMU、NUMA、电源 profile）、kernel（RT / low-latency 版本，isolcpus、nohz_full、hugepages 等启动参数）、NIC（ice 驱动加一个 DDP profile 版本）、firmware、OS tuning (src: `p_bkc.md:124`)。它在结构上已经是一个 desired state，只差一个持续 enforce 它的控制器。这个观察本身是这个项目的立论：reconcile 是通用思想，不是 Kubernetes 的特性。
- **L3「为什么必须做在 systemd 层？做成 K8s Operator 不是更省事吗？」** → 答：两个事实逼出这个形态 (src: `p_bkc.md:163`)。第一，不能假设 K8s 起得来：裸机交付、测试床重装、节点刚开机这三个场景下 K8s 都不在；而且漂移发生在 K8s 看不到的层（BIOS、kernel cmdline、NIC 固件、sysctl）；再加上交付给客户的方案必须自包含，一个 systemd unit 加一个 agent 二进制，不能依赖客户先跑一套编排。第二，两层嵌套 reconcile：systemd 保证 agent 进程活着，agent 保证节点配置不漂移，这和 kube-controller-manager 管 pod 是同构的，只是 target 换成了 Linux 加硬件。
  所以往 K8s Operator 走反而背离了项目存在的理由 (src: `p_bkc.md:202`)。把 compliance 暴露成 Node label 给调度器用（NFD 那类方向）是可想象的相邻方向，明确不在范围内 (src: `p_bkc.md:103`)。
- **L4「设计权衡：为什么第一天做 audit 而不是 auto-remediation？」** → 答：因为这个场景的核心失效模式是**静默降级**。偏离 BKC 的节点通常不报错，而是抖动、丢包、突破 fronthaul 时序预算；最难查的失效恰恰是所有健康检查全绿、性能就是差的那一种 (src: `p_bkc.md:131`)。而且 provisioning 完成不等于认证性能就位：一台机器装好、能起 K8s、能跑 pod，完全不代表 C-state 关了、NIC 固件对了、DDP profile 是对的版本、hugepages 和 isolcpus 真的落地了 (src: `p_bkc.md:132`)。
  在这个前提下，audit 独立于 update 就有独立价值：即便某项 controller 从不改，持续产出每节点 compliance 加 drift 时间戳本身就点亮了这个盲区，而且成了交付合规的凭证 (src: `p_bkc.md:185`)。这也是我认领的边界所在：**审计和监控这一半是我构建并跑起来的，完整的风险分级修复模型是我作为设计口径陈述的** (src: `p_bkc.md:187`)。我会主动把这句话说出来，因为它比含糊地说「我做了一个 reconciler」更可信。
- **L5（最深）「如果要往 auto-remediation 走，最难的是什么？」** → 设计口径答：三个问题，任何诚实的版本都必须回答 (src: `p_bkc.md:193-196`)。
  第一，**监控者不能扰动被监控对象**。开了 isolcpus 的节点，隔离核跑的是 RT 的 RAN 负载；审计 agent 被调度到这些核上，或它派生的子进程逃逸上去，就变成噪声邻居，亲手制造出它本该保护的那种 jitter。agent 必须钉死在 housekeeping 核、拒绝在隔离核上运行，子进程受同一个 cpuset 约束。
  第二，**跨重启状态机**。只有重启才生效的改动（BIOS、kernel）意味着 agent 得活过它自己触发的那次重启：落盘的状态机加开机读取的 intent marker、有上限的重试来打破 boot loop、bootloader 的 last-known-good 兜底，让一个坏 cmdline 不至于把客户节点变砖。
  第三，**按 failure domain 限流的 reboot token**。pull 模型下 git 里一次 BKC bump 会被每台节点在下一个 poll 周期同时看到；没有分布式 lease 限制同一域内同时中断的节点数，它们会一起重启，造成自己制造的 correlated failure。fail-safe 默认是 token 服务不可达就不重启。
  加一条信任边界：agent 在每台机器上以 root 运行、能刷固件，desired state 来自 git，所以必须验签（fail-closed）、每次 mutation 有审计日志、protected branch 带 review、最高危类别（固件 flash）人工审批 (src: `p_bkc.md:196`)。
  最后我会做一个跨项目的收束：这和 K8s 升级项目里的 `serial: 1`、quorum math、PodDisruptionBudget 是同一套 blast-radius 纪律，同一个脑子、两个层 (src: `p_bkc.md:198`)。

**归属边界（本故事最关键的一节）**：
- 能说「我做了」：Intel 5G 云化背景下的 IaC / 硬件层配置管理是我的；构建并运行了持续运行的自研 machine-level controller（systemd 层 daemon）；审计/监控能力（持续巡检 + compliance + drift + 那四个采集面）；before 现状（doc 加 prose 加人肉执行，连 Ansible 这级都没有）；场景（多个内部测试集群 + 交付客户裸机集群）；规模约 30 台、多 cluster；NIC = E810 100GbE；范围刻意不做 K8s Operator (src: `p_bkc.md:215-226`)
- **不能说「我做了」**：L2/L3/L4 能力分层（在线 tuning 收敛、traffic-aware 破坏性收敛、GitOps 闭环）；隔离核 jitter「我踩过这个坑」；跨重启状态机；reboot token 限流的实现；签名 profile 的实现；「我压测过 pull 架构的抗分区」。这些全部只能用设计口径 (src: `p_bkc.md:230-238`)
- 具体 SKU 不落型号，用代际说法 (src: `p_bkc.md:232`)
- ⚠️ 待确认：`work-contexts/career/profile/resume-expand.tex:108` 有一句 `Built Kubernetes platform tooling using operator-style controllers, IaC (GitOps/Ansible) cluster management`。这里的 **GitOps** 在其他任何 evidence 里都没有支撑（全库搜不到 ArgoCD/Flux 的一手证据）。如果这条指的是 BKC 的 git-as-source-of-truth，那措辞应该是「git-declared desired state」而不是「GitOps」，因为 GitOps 在业界语境里默认指 ArgoCD/Flux 那类 pull-based CD。**面试前建议改简历措辞**，否则被问「你们用 ArgoCD 还是 Flux」时会尴尬。

**可复用到**：03 AIOps（reconcile / 控制原语 / 人在环路）、07 AWS fundamentals（对比：云上的不可变 AMI vs 裸机的收敛 reconcile 是同一问题的两种解）、90 行为面（把部落知识变成系统）。

---

## S10. dcluster StarRocks CN：一套自己写下来的部署与 E2E 验证流程

**Headline**：我把「改代码到确认生产行为正确」这条路径写成了一份有 11 个测试点的可执行 checklist，其中包含幂等语义的显式验证和一个 spot 冷启动 9 分钟的真实时间分解，这份东西的价值在于它让部署验证从「我看着像好了」变成「11 个断言全过」。

**适用题型**：你怎么验证一次部署 / 你怎么写 runbook / 讲一个你做的开发加运维闭环 / 幂等性怎么测 / 弹性伸缩的真实时延是多少。

**情境**：dcluster 的 StarRocks CN tier + warehouse 功能开发（CRE-6630），改完代码需要部署到 dev 集群做 E2E 验证 (src: `rules/skills/workflow_dcluster_starrocks_cn_deployment.md` 元数据节)。

**动作**：五步流程写成 skill：构建（Maven 打包 + `docker buildx --platform linux/amd64` 交叉编译推镜像）→ 部署（`set image` + `rollout status --timeout=120s` + 确认新 pod）→ port-forward → E2E 验证（11 个测试点）→ 清理（终止测试集群 + 回滚镜像到 production tag）(src: 同上，步骤 1-5)。

11 个测试点覆盖了正常路径、输入校验、资源正确性、和幂等：T1 launch 返回正整数 ID；T2/T3 输入校验（缺 tier、未知 tier 都返回 -1）；T4 status；T5 验证 pod 资源真的按 tier 分配（small → 2cpu/8Gi）；T6 验证 ConfigMap 里 feAddress 自动构造正确、warehouse 正确传递；T7/T8 scale up/down；T9 scale down 到底应该被拒（"Cannot scale below 1 CN"）；T10 terminate；**T11 terminate 幂等（重复 terminate 应返回 "already terminated" 而不是报错或重复执行）** (src: 同上，步骤 4)。

**结果**：一份可复用的部署验证 skill。附带产出是一张「踩过的坑」表，每条都是根因加解决 (src: 同上，「踩过的坑」表)：Mac 构建 arm64 镜像但 K8s 要 amd64 → `buildx --platform`；相同 tag 新镜像不生效（`imagePullPolicy: IfNotPresent` 缓存）→ 每次用不同 tag；feAddress 用错 namespace → 改用 `getPodNamespace()` 读 service account；**`CREATE WAREHOUSE` 失败被 `|| true` 吞掉导致整个分支静默失败 → 改为检查返回码，失败 fallback 到 default 注册**。

一个可以直接报出来的容量数字：spot 节点冷启动约 9 分钟，分解为 CA 扩 spot ASG 约 70s、kubeadm join 约 80s、init container 约 50s、镜像拉取约 200s (src: 同上，「等待 pod 就绪」节)。

**5 层追问防线**：

- **L1「你怎么验证一次部署是对的？」** → 答：我不用「看 pod Running 和日志没报错」回答。我的答案是：部署验证要有断言清单，而且断言要覆盖四类：正常路径、输入校验的负例、资源与配置的实际落地、以及幂等。举例就是那 11 个测试点，特别是 T5/T6（验证 pod 真的按 tier 分到资源、ConfigMap 里的地址真的构造正确）和 T11（重复 terminate 的语义）。
- **L2「T11 为什么要单独测？」** → 答：因为幂等是自动化的前提，而幂等在 API 层的正确形态不是「不报错」，是「返回一个明确的、可判定的已完成状态」。T11 期望的是 `"This cluster is already terminated."` 而不是 500 也不是静默成功 (src: 同上，T11)。这个区别在编排层很关键：调用方要能区分「我刚做完」和「早就做完了」，否则重试逻辑没法写。这和 S05 里 FORCE_BUILD 区分「重跑补齐」和「强制重建」是同一件事。
- **L3「那个 `|| true` 吞掉错误的坑，你怎么看？」** → 答：这是我最喜欢举的一个例子，因为它是 **fail-open 的教科书标本**。`CREATE WAREHOUSE` 失败被 `|| true` 吞掉，导致整个 CN 注册分支静默失败，结果是 CN pod 起来了、看着健康、但根本没注册到 FE (src: 同上，「踩过的坑」表)。修复是检查返回码，失败时显式 fallback 到 default 注册。
  一般化：`|| true` 是把「我不想让脚本停」这个便利，换成了「我永远不知道它失败过」这个代价。我在自己的自动化方法论里把这一条写成了硬原则：**fail closed**，如果前置条件不能被证明成立就带明确错误退出，而不是继续 (src: `rules/skills/bestpractice_automation_path_hygiene.md:13`)。
- **L4「设计权衡：为什么手工 checklist 而不是自动化测试？」** → 答：因为这个阶段的瓶颈不是执行速度，是**知识的可传递性**。11 个 curl 加断言的清单可以被自动化，但先要有人把「该断言什么」想清楚；把它写成人可读的 checklist 是一个中间产物，它同时是自动化的规格说明。这和我在 K8s 升级里的做法完全一致：先把 fail 条件写成规则（人可读），然后才是 Python 去执行它 (src: `work-contexts/career/interview/interview-1-k8s_upgrade_reference.md:24-30`)。诚实边界：这份 checklist 目前是手工执行的 skill，不是 CI 里跑的自动化测试套件。
- **L5（最深）「那个 9 分钟的冷启动，你会怎么优化？」** → 答：先看分解，因为分解决定杠杆在哪。200s 镜像拉取是最大项，占一半以上，杠杆最大：可选项是 AMI 里预热基础镜像层（回到 Packer 那一层，把慢且稳定的东西固化进镜像，正是分层判据）、或者用镜像 lazy pulling。70s 的 CA 扩 spot ASG 和 80s 的 kubeadm join 是链路上的固定成本，能省的方式不是加速而是**提前**：保留一个小的 warm pool，或者用 over-provisioning pod 占位让 CA 提前扩容。
  但我会先问一个更前置的问题：这 9 分钟对谁是问题？如果是交互式查询在等，9 分钟不可接受，那正确的解不是优化冷启动而是保底常驻容量；如果是批量负载，9 分钟完全可接受，优化它是浪费。这个判断决定了要不要花这个钱，而 spot 弹性算力的整个价值前提是「可以接受冷启动」。

**归属边界**：这份 skill 是我写的（一手，来源 CRE-6630 开发过程）。dcluster 平台的可靠性那批工作（spot 中断回退、容量准入、多集群锁修复）不是我的，按 `contexts/resume_highlights_doris_dcluster.md` §0 的归属边界，git 作者是别人，**不入主线故事**。所以这个故事只讲「StarRocks CN tier + warehouse 的开发与部署验证流程」，不碰 dcluster 的弹性可靠性机制。

**可复用到**：01 数据库运维（StarRocks CN 部署）、06 成本（spot 冷启动是弹性降本的时间代价）、02 监控（部署后验证与 synthetic check）。

---

## S11. 自动化脚本的 fail-closed 设计（方法论型小故事）

**Headline**：任何跨机器、跨 cron、跨嵌套 repo 运行的自动化，第一件事不是干活而是证明自己站在正确的位置上；证不出来就带明确错误退出，绝不静默降级成一次「什么都没扫到但报成功」的运行。

**适用题型**：你写自动化有什么原则 / 静默失败怎么防 / 一个脚本在别人机器上跑不起来怎么办 / 你怎么让自动化可审计。

**情境**：自动化脚本的一类高频失效是位置错误导致的静默无操作：cwd 漂移把输出写到错误目录、submodule 的 repo root 与 workspace root 不一致导致数据缺失、期望目录不存在导致扫描静默空转但报告成功 (src: `rules/skills/bestpractice_automation_path_hygiene.md:49-52`)。

**动作**：五条原则 (src: `bestpractice_automation_path_hygiene.md:9-14`)：代码里不写硬编码绝对路径；运行时从当前文件位置或显式 env var 推导 workspace root；干活前 preflight 校验期望的目录和文件存在；**root 证不出来就 fail closed，带清晰错误中止**；把解析出的 root 和目标全部记日志，让操作者能审计发生了什么。

root 推导用 sentinel-dir 搜索而不是 `git rev-parse`，因为嵌套 git 会让 `git rev-parse` 给出错误答案 (src: `bestpractice_automation_path_hygiene.md:16-17`)。

Preflight 清单：确认每个扫描 root 存在（缺失是错误，除非显式标为可选）、确认每个写入目标在 root 之内（没有 `..` 逃逸）、确认持久化目标存在或用一条有 guard 的代码路径显式创建 (src: `bestpractice_automation_path_hygiene.md:38-43`)。

Drift 处理：扫描 root 缺失时不许静默跳过，要么中止（写路径推荐），要么在运行输出里显式记 `missing_paths=[...]` (src: `bestpractice_automation_path_hygiene.md:45-47`)。

**结果**：这是我的一手方法论沉淀，形态是可复用的 skill。

**5 层追问防线**：

- **L1「你写自动化有什么原则？」** → 答：一句话，让自动化可移植，并且在即将读写错误位置时大声失败而不是静默继续 (src: `bestpractice_automation_path_hygiene.md:7`)。
- **L2「为什么不用 `git rev-parse` 找根目录？」** → 答：嵌套 git 场景下它会给出错误答案（submodule 或嵌套 repo 里，rev-parse 返回的是最近的那个 repo root，不是我想要的 workspace root）。sentinel-dir 搜索的语义更精确：我要的不是「某个 git repo 的根」，是「同时包含这几个特征目录的那个目录」(src: `bestpractice_automation_path_hygiene.md:17`)。这个区别的一般化是：定位应该基于**结构特征**而不是基于**工具的默认答案**。
- **L3「fail closed 和 fail open 怎么选？」** → 答：按「错误的后果是否可逆」选。读路径证不出来最坏是数据不全，可以记 `missing_paths` 继续；写路径证不出来会往错误位置写，不可逆，必须中止 (src: `bestpractice_automation_path_hygiene.md:46`)。所以我的规则不是「一律 fail closed」，是「写路径一律 fail closed，读路径允许显式记录后继续」。
  反例我手上有实证：`CREATE WAREHOUSE` 失败被 `|| true` 吞掉导致 CN 静默不注册（见 S10）。那就是一个写路径上的 fail open。
- **L4「设计权衡：preflight 会不会太重？」** → 答：preflight 的成本是常数（几次 stat），自动化的运行次数是变量，所以它的边际成本趋零；而它防的是一整类难以事后诊断的失效（「为什么这次跑完什么都没有？」）。真正的成本不在运行时，在写的时候要显式列出期望，也就是要求作者把隐含假设写下来。这个成本我认为应该付，因为它和我在 K8s 升级里做的是同一件事：把隐式的前提条件变成显式的 fail 条件 (src: `work-contexts/career/interview/interview-1-k8s_upgrade_reference.md:24-30`)。
- **L5（最深）「这和 K8s 的 admission control 是一回事吗？」** → `[理论]` + 一手 答：是同一个模式在不同层。admission webhook 的 `failurePolicy: Fail` 就是 fail closed，`Ignore` 就是 fail open，而选哪个取决于「webhook 不可用时，放过一个未经校验的请求」和「拒绝所有写入」哪个后果更糟。我在 S08 那次 caBundle 事故里见过 `Fail` 的代价：webhook 变成了集群写入路径上的单点。所以更完整的表述是：fail closed 提高正确性但把自己变成了可用性上的单点，因此它适用于低频、不可逆的路径（我的写路径、生产 release 的人工闸门），fail open 适用于高频、可逆、且有其他补偿机制的路径。这个判据和我在 Jenkins 那边的排序是同一条：高频可逆的自动化，低频不可逆的设闸 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_jenkins.md:62`)。

**归属边界**：一手方法论，我自己的 skill。

**可复用到**：全部方向（这是通用的自动化纪律）、03 AIOps（agent 的 fail-closed 与工具边界）。

---

## 故事到题型的快速索引

| 题型 | 首选故事 | 备选 |
|---|---|---|
| 最复杂的变更 / 大规模变更管理 | S01 | S04 |
| 你写的工具 / 自动化的价值 | S02 | S05, S06 |
| 从零建集群 / IaC 分层 | S03 | S09 |
| 为什么不用托管 K8s | S03 (L4/L5) | S01 (L4) |
| 复杂故障根因分析 | S04 | S08, S07 |
| 幂等性 | S05 | S10, S11, S02 |
| CI/CD 可靠性 | S05 | S04, S06 |
| 变更引发的事故 | S08 | S04 |
| AWS + K8s 集成故障 | S07 | S03 |
| 声明式 / reconcile 的本质 | S09 | S03, S11 |
| 部署验证方法论 | S10 | S02 |
| 自动化的边界与反论 | S05 (L5) | S11, S02 (L4) |
| Terraform | **无故事，走 `terraform_honest_answer.md`** | S03 (L4) 讲 Ansible vs TF 的取舍 |
