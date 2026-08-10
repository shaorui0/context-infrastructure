# 04 IaC / CI-CD / K8s 升级：高频面试题与答题骨架

> 每题三段：**一句定位**（开口第一句，先给结论或立场）→ **展开结构**（按什么顺序讲，讲几层）→ **挂载**（挂哪个 story / fundamentals 条目 / 或者诚实边界在哪）。
> 故事编号见 `story_bank.md`，Q 编号见 `fundamentals.md`，TF 口径见 `terraform_honest_answer.md`。
> 难度标记：`★` 常规 · `★★` 需要一手细节 · `★★★` 会被钻到底，答案必须有取舍和自我批评。
> 本文件里出现的所有数字都不带出处，因为它们全部溯源到 `story_bank.md` 顶部的「数字口径与已知漂移」表和各 story 的正文引用；口述之前以那张表为准，尤其是 `18-21h → 6-8h`（已达成）与 `3-4h`（roadmap）这条漂移。

---

## A. K8s 升级与运维（8 题）

### A1. 「讲一下你做过的 Kubernetes 升级」★★

**一句定位**：我把一个只存在于资深工程师脑子里的 18-21 小时双人手工仪式，重构成一条 check → plan → apply 的证据链流水线，然后用它把 50 个自管理集群从 1.24 逐 minor 推到 1.29，两套生产 fleet 零客户可感知停机、零回滚。

**展开结构**：四段，每段一句话给结论再展开。（1）**问题的重新定义**：根本矛盾不是手动 vs 自动，是「我凭什么确信现在可以进入下一步」这个问题没人能答。（2）**系统形态**：三段流水线 + evidence 存储 + 四个人工签核点。（3）**执行纪律**：逐 minor（kubeadm 硬约束）、控制面先行（version skew 决定的）、worker 不可变替换、addon 依赖顺序、fleet 推进顺序。（4）**结果与诚实边界**：6-8h / 1 人（**不是 3-4h，那是 roadmap**）、零事故要拆成三个来源。

**挂载**：S01 全篇。数字口径必须用 story_bank 顶部那张表，⚠️ 特别注意 6-8h vs 3-4h 的口径漂移。

---

### A2. 「1.24 到 1.29，哪一跳最危险？」★★★

**一句定位**：1.24 → 1.25，因为它是唯一一跳里有移除类破坏性变更的，而且它的替代品语义是相反的。

**展开结构**：（1）PSP 1.25 移除 → PSA 接管，语义从「不配就不管」翻转成「打了 label 就强制」。（2）真实失效形态：Fluentd / node-exporter 这类 DaemonSet 合法需要 privileged，namespace 被草率打成 `enforce: restricted` 直接被拦死，而且是升级后才发作。（3）我的处理是把它当独立问题线：先扫存量并迁移 → PSA 上 warn/audit 观察 → 零违规才 enforce → infra namespace 显式 privileged。（4）次危险的是 1.26→1.27 的 cloud provider 交接（in-tree → external，CCM 接管），失效形态是新 worker 卡在 `uninitialized` taint。（5）**主动给一个诚实点**：dockershim 的坑不在这一轮，1.24 已经移除了它，我们的起点就是 1.24、运行时早就是 containerd。

**挂载**：S01 的 L2；fundamentals Q4（含其余 minor 的 `[理论]` 变更表，用来展示知道整个地形）。

---

### A3. 「回滚方案是什么？你真的回滚过吗？」★★★

**一句定位**：回滚按层设计、触发条件事前写死，但我要先说清一件事：实际执行是零回滚，所以我有的是被 dry-run 检验过的回滚路径，不是回滚成功的战绩。

**展开结构**：（1）三层路径：控制面 = etcd snapshot 恢复 + 二进制降级；worker = 停 Instance Refresh + LT 回退旧 AMI；addon = `rollout undo`。（2）触发条件预写：master 升级失败 / >50% pod 非 Running / 关键服务不可达 / 告警洪水。（3）**主动指出最脆的一环**：snapshot 恢复的是数据不是二进制，而且会丢 snapshot 之后的所有写入，三个成员必须一起从同一个 snapshot 恢复（restore 会生成新的集群 ID）。（4）由此得出真实策略排序：靠门禁不进坏状态 > 前滚修复 > 回滚。（5）反过来给一条正面结论：worker 的回滚路径是我们日常 oncall 已经在走的路径（容量受损先回滚 LT/AMI 恢复容量再追根因），**回滚路径应该是日常路径而不是只在应急计划书里存在的路径**。

**挂载**：S01 的 L3 + S07 的 L3；fundamentals Q3。

---

### A4. 「你说零事故。这里面有多少是设计，有多少是运气？」★★★

**一句定位**：我把零事故拆成三份，其中只有两份是我的功劳，最大的那一份是架构给的。

**展开结构**：（1）**结构性来源，最大的一份**：双集群流量前置切换，升级时那个集群是 dark 的、没有业务流量；在这个前提下 20% batch 的语义从「保护用户」变成「节奏控制」。承认这一点：没有双集群这个条件，同样的操作纪律拿不到零事故，我会需要真 canary + 逐 AZ + 更长观察窗口。（2）**门禁设计**：版本 × 健康四象限、post-verify 对比落盘 baseline 而不是记忆、check 与外部监控交叉验证以防 baseline 本身是错的。（3）**我算错过的**：把「Ansible 幂等」当成了可重入的充分条件，而 kubelet 的中间状态在覆盖范围外；这个认知差直接改了设计（判定必须回到集群实测，不能信 state 文件）。

**挂载**：S01 的 L5。⚠️ 这题会连着问 A5，提前准备。

---

### A5. 「那最接近出事的一次是什么？」★★★ ⚠️ 最危险的一题

**一句定位（在待确认项落定之前的安全答法）**：我没有戏剧性的 near-miss 案例，因为这套流程的设计目标恰好是让 near-miss 在 check 阶段变成一次 fail 而不是一次事故；我能讲的是 gate 真的拦过东西，以及我认为最危险的未覆盖场景是什么。

**展开结构**：（1）先说流程意图（fail 而非事故），不要显得在回避。（2）给一个 gate 真的生效的实例。（3）给「我认为最危险的未覆盖场景」：etcd 成员升级后起不来导致 quorum 丢失，这是唯一一个 `serial: 1` 也救不了的情况（因为它不是「同时动两台」造成的），只能靠 snapshot 加人工。（4）给一个已经被我系统化的次级案例：PDB 在 dark cluster 上依然卡 drain，处理是等 PDB 满足或显式调低 `minAvailable`，绝不强制。

**挂载**：S01 的 L5 的 ⚠️ 待确认段。**面试前必须落盘一个真实实例**，候选：某集群 raft lag 超 1000 被 check 拦住 / 某集群 PDB 卡住 drain 等了很久 / `drain_timeout` 从 300s 调到 600s 这个 feature flag 本身就是从一次卡住里学来的。**在确认之前不许编。**

---

### A6. 「50 个集群的差异怎么管？drift 怎么办？」★★

**一句定位**：我不试图消灭 drift，我让它在每次升级前变得可见、可决策；差异用两层结构表达，而且我给了一条判断「结构本身是不是错了」的信号。

**展开结构**：（1）第一层 `cluster_type` 分类（workload / management / dev-staging）。（2）第二层 per-cluster feature flag 表达残余例外（`drain_timeout_seconds: 600` 覆盖默认 300）。（3）**护栏**：override 越少集群越标准，flag 数量增长本身当成分类失准的信号，应该新增 cluster_type 而不是继续加 flag。（4）drift 的态度：check 阶段的 baseline snapshot 显式化 current state，让 drift 进入决策而不是被消灭。

**挂载**：S01；fundamentals Q6 + Q18。可以顺势连到 TF 的 `ignore_changes` 是同一个取舍（见 D6）。

---

### A7. 「PDB / 驱逐 / QoS 讲一下」★★

**一句定位**：关键是先分清两类驱逐，因为只有一类受 PDB 约束，而很多人把 PDB 当成通用保护伞。

**展开结构**：（1）主动（drain / CA 缩容 / descheduler，走 Eviction API，**受 PDB 约束**）vs 被动（节点压力驱逐 / preemption / 节点挂 / OOMKill，**不受约束**）。（2）QoS 三档由 requests/limits 关系推导，且 CPU 超限是 throttle（可压缩，代价是 P99）、内存超限是 OOMKill（不可压缩，所以内存必须设 limit）。（3）**一手反直觉点**：PDB 在 dark cluster 上依然诚实：没有流量、违规不伤用户，但 drain 照样被卡；处理是等或显式调低，绝不 force。因为 PDB 是纯语法约束，它不知道也不该知道流量状态。（4）分层保护 PDB + HPA + readiness，并**明确列出不覆盖的场景**（硬件故障、应用 bug），靠多 AZ 兜底。（5）加分项：对 quorum 系统 liveness 必须保守、readiness 保持敏感（Kafka KRaft 被 liveness 反复误杀、每次误杀又触发 controller 重选举的实例）。

**挂载**：fundamentals Q8 + Q9；S01（数据库节点先升的排序）。

---

### A8. 「为什么不用 EKS？」★★

**一句定位**：这个选择我不为它辩护，我为它的成因和代价负责；如果重做我上 EKS。

**展开结构**：（1）成因：历史债务 + 成本（自管理省掉 EKS 控制面费用，$0.10/cluster/hr × 50 ≈ $3,600/月）。（2）代价就是我这整个升级项目：省下的 infra 钱远不如工程师时间值钱。（3）重做的形态：上 EKS，master 升级退化成一次 API 调用，精力放到上层（addon 兼容性、业务层验证、发布节奏）。（4）**但要给区分，否则显得只会跟随托管**：自管理在两个场景仍然对：onsite / 客户裸机交付（没有云 LB，我们用 MetalLB），以及需要改 apiserver/etcd 到托管服务不开放的深度。不属于这两类还在自管理就是纯技术债。（5）加分：如果只能保留一层自建，我保留 Layer 0（AMI），因为内核参数、containerd 配置、安全加固和不可变替换能力都在这一层，而 Layer 2（etcd/apiserver）是最该外包的：知识密度极高、出错代价极大、和业务差异化零相关。

**挂载**：S01 的 L4 + S03 的 L5；06 方向的成本对比可以复用。

---

## B. IaC 设计（6 题）

### B1. 「讲讲你的 IaC 分层」★★

**一句定位**：一个生产 K8s 集群是四层叠加起来的，而分层的判据只有一条：谁在持续维持这个状态。

**展开结构**：（1）四层：Packer AMI → AWS 资源 → kubeadm 控制面 → 集群内组件。（2）**判据**：Layer 3 的期望状态由 K8s 的 controller 持续维持（apply 一次就够），Layer 0/1/2 没有任何东西在持续维持，所以需要外部 agent 按需跑一遍。（3）第二条判据是变更频率：Packer 固化慢且稳定的（装包），Ansible 做快且多变的（配集群）；所以 AWS 部署能跳过装 containerd/k8s，onsite 必须现装。（4）主动指出层内还有一条边界：VPC / Subnet / NAT / IAM 是 repo 外手动预建的，因为它们是账号级、年为单位的生命周期，而集群是可销毁重建的。**这层已经在按生命周期切所有权了，只是长生命周期那一半交给了人工**。

**挂载**：S03；fundamentals Q20。（4）这一点直接是 TF 引入方案的阶段 1 落点，可以顺势接 D3。

---

### B2. 「幂等性到底是什么意思？」★★★

**一句定位**：幂等不是「跑两遍不报错」，它有三层含义，而第三层是我算错过的地方。

**展开结构**：（1）**形状**：guard → 备份 → 收敛 → verify。关键选择是**覆写到已知良好状态而不是逐行打补丁**，因为覆写是收敛的：第二次运行产生相同终态，断在中间没有代价。反例是追加行或假设初始状态干净的脚本，跑两遍一个事故变两个。（2）**判定权的位置**：幂等的判定必须基于目标状态的实测，不能基于调用者的记忆。两个实证：FORCE_BUILD 逐层透传由叶子 job 自查镜像 tag；K8s 升级里判断一步是否完成用集群实测的镜像版本 × health 而不信 state 文件。（3）**幂等 ≠ 可重入**：Ansible 的幂等只覆盖 module 级，drain 是幂等的但 kubelet 的中间状态不在覆盖范围内；所以正确抽象是两个独立问题：从头重跑安全吗（幂等），我怎么从实测判断这一步完成了没有（可判定），**第二个才是恢复的入口**。（4）诚实边界：我做的是操作级幂等（skip-if-exists / checkpoint / 备份加校验），不是声明式 reconcile；修复脚本 `set -e` 快速失败但没有事务回滚，dry-run 只在诊断脚本里有。

**挂载**：fundamentals Q17；S05 的 L2、S02 的 L5、S04 的 L3。这题是这个方向最能拉开档次的一题。

---

### B3. 「声明式和命令式的区别是什么？」★★

**一句定位**：教科书答案（what vs how）不产生任何可操作结论，我用三个可观测性质回答。

**展开结构**：（1）三个性质：跑第二遍是否收敛、能不能随时回答「现在是否符合期望」、中途失败能不能直接重跑。（2）**一手论点**：声明式 reconcile 天生幂等，命令式 pipeline 天生不是；这不是回避命令式工具的理由，恰恰是「熟悉 Jenkins」成为可靠性工程能力的原因：工具不给你的幂等性要自己构造。（3）**反面补充，这一条很关键**：用了声明式工具不等于拿到了声明式的性质。我们 Ansible 里大量 role 用 `shell` 调 `helm upgrade` / `kubectl apply` 兜底，结果不真正幂等、`--check` 失效（dry-run 骗人）、错误埋在 shell 输出里，这是我们 codebase 最大的技术债之一。**在一个声明式工具里开命令式后门，就失去了那个工具的全部保证。**

**挂载**：fundamentals Q16；S03 的 L3。TF 的 `provisioner` 是同一个病（见 D6 坑 7）。

---

### B4. 「不可变基础设施的好处和边界？」★★

**一句定位**：不可变最大的好处不是「干净」，是把「修一台半死的机器」变成「回退一个版本」，而它的成本随节点的状态量线性上升。

**展开结构**：（1）三个具体好处：升级退化成换机器；**回滚路径就是日常路径**（容量受损先回滚 LT/AMI，和升级的回滚是同一个动作）；plan 可验证（worker 的 plan 就是 AMI diff + LT diff，只允许 AMI ID 变化）。（2）边界一：有状态节点。承载数据库 pod 的节点不能随便换，drain 它就是在动数据面；所以数据库节点提前测绘、每波次排最前、逐节点验证。（3）边界二：反馈周期。任何一行配置改动都要重新出镜像，秒级变成分钟到小时级；把高频变更的东西塞进 AMI 是最常见的分层错误。（4）实测数据支撑：spot 冷启动 9 分钟里镜像拉取占 200s 是最大单项。镜像层的成本既出现在构建端也出现在启动端。

**挂载**：fundamentals Q19；S07 的 L4/L5、S10 的 L5。

---

### B5. 「configuration as code 为什么重要？」★★★

**一句定位**：重要性的判据只有一个：能不能从零重建。而验证这个属性的唯一方式是真的搬一次家。

**展开结构**：（1）Jenkins 跨集群迁移就是对这个属性的一次全量审计：进 git 的东西（约 275 个 pipeline 定义 + 16 个 shared library 步骤）全部干净搬走，只活在运行中系统里的东西全部以故障形式浮出。（2）三个标本：上游早已失联的缓存制品（缓存掩盖了「依赖已死」好几年）、agent pod 里手工调过的 Maven 配置、以及 `jenkins.yaml` 这个文件本身其实是 agent pod spec 快照而不是 JCasC。（3）**结论**：pipeline-as-code 和点 UI 攒出来的雪花 Jenkins 的运维差别是：雪花在定义上不可恢复。（4）**诚实边界主动给**：我们没有 JCasC，controller 配置没进代码；shared library 长期指向个人分支，分支治理是弱项，我不声称做到了 configuration-as-code 治理。（5）延伸出一条更强的属性：「能从零重建」比「能维持运行」更强，而验证它的唯一方式是定期真的重建一次。

**挂载**：S04 的 L5；fundamentals Q35 + Q38。这题的加分点全在（4）的诚实边界上。

---

### B6. 「你怎么防自动化脚本静默失败？」★★

**一句定位**：任何跨机器、跨 cron 的自动化，第一件事不是干活，是证明自己站在正确的位置上；证不出来就带明确错误退出。

**展开结构**：（1）五条原则：不硬编码绝对路径、运行时推导 root、preflight 校验、**fail closed**、记日志让操作者能审计。（2）root 推导用 sentinel-dir 搜索而不是 `git rev-parse`，因为嵌套 git 会给错答案。**定位应该基于结构特征而不是工具的默认答案**。（3）fail closed vs fail open 的判据是「错误的后果是否可逆」：写路径一律 fail closed，读路径允许显式记 `missing_paths` 后继续。（4）反例实证：`CREATE WAREHOUSE` 失败被 `|| true` 吞掉，导致 CN pod 起来了、看着健康、但根本没注册到 FE。（5）加分连接：这和 admission webhook 的 `failurePolicy: Fail` 是同一个模式：fail closed 提高正确性但把自己变成可用性单点，所以它适用于低频不可逆的路径。

**挂载**：S11 全篇；S10 的 L3；fundamentals Q12。

---

## C. CI/CD 与发布（6 题）

### C1. 「熟悉 Jenkins 吗？熟到什么程度？」★★

**一句定位**：我不用「会写 Jenkinsfile」回答这个问题。「熟悉 Jenkins」应该读作「能把一条交付流水线当生产系统来拥有」：它的故障模式、它的状态、它的恢复路径，而不是它的语法。

**展开结构**：（1）先给立场：绝大多数线上事故由变更引起，所以交付流水线是 SRE 手里可靠性杠杆最高的一个面，也是头号事故源。（2）三个判据：流程幂等可重入 / 状态可观测可诊断 / 配置即代码。（3）每个判据挂一个实物：幂等挂 859 行的 nightly production-build 编排器（FORCE_BUILD 逐层透传 + 镜像存在性检查）；可观测挂 diagnose/fix 脚本配对 + jenkins-mgt 聚合面板；配置即代码挂 275 个 pipeline 文件进 git 加那次迁移的审计。（4）结构性事实：命令式 Jenkins 天生不幂等，工具不给你的幂等性要自己构造。

**挂载**：S05 + S04 + S06；fundamentals Q38。

---

### C2. 「讲一个 CI/CD 的故障」★★

**一句定位**：迁移后构建大面积失败，根因是三件事叠加，而最有意思的一条是「系统的失败缓存本身成了故障的一部分」。

**展开结构**：（1）路由判断先行：大面积同时失败 = 共享依赖层的问题，所以不从单个 pipeline 查，从 agent 镜像 / `.m2` 缓存 / 外部仓库可达性查。（2）三条线三个根因：外部仓库失效（maven.twttr.com 超时、repo.spring.io 认证失败）+ 迁移时 `.m2` 没带过去 + Maven `.lastUpdated` 阻止重试；Debian Buster EOL 官方源下线；Arcanist/libphutil 与 PHP 8 不兼容。（3）**重点讲 `.lastUpdated`**：修好源和构建能过之间还有一步「清理失败标记」，因为系统缓存了失败结论。同一形状在 K8s 侧是 `imagePullPolicy: IfNotPresent` 让相同 tag 的新镜像不生效，所以我的部署纪律是每次用不同 tag。（4）修复脚本形状：guard → 备份 → 收敛 → verify，每个 fix 配一个只读 diagnose。（5）治理动作：根因修完把前人留下的 workaround stage 删掉。

**挂载**：S04；fundamentals Q35。

---

### C3. 「自动化程度是不是越高越好？」★★★

**一句定位**：不是。自动化不是目的，程度更高不是单调更好，而我有一个干净的标本。

**展开结构**：（1）标本：上游仓库陆续失联那段时间，Jenkinsfile 长出了元数据修复、依赖调试、直接下载兜底这些 workaround stage；制品正式迁移到位后它们全变成死代码，遮蔽信号、拖长构建、保证会迷惑下一个读者。我的修复动作之一就是删掉它们。（2）一般化：**自动化的老化方式和告警规则一模一样**，每一段都编码着会静默过期的假设；没人看的自动化路径会在无人察觉中腐化，人工闸门里至少有一个会察觉异常的人。（3）自动化打开的新故障面：凭据集中在流水线够得着的地方（我们 repo 里就有明文 AWS 凭据进 git 的实证）、插件供应链、脚本腐化。（4）**我为之辩护的排序**：可运行、可观测、可恢复在前，配得上的部分再自动化。高频且可逆的自动化，低频且不可逆的设闸。（5）所以生产 release 流程里那个人工 review/approval 我读作设计决策而不是缺陷。

**挂载**：S05 的 L5；S02 的 L4；fundamentals Q17。这题是这个方向第二个最能拉开档次的题。

---

### C4. 「部署策略你怎么选？blue/green 还是 canary？」★★

**一句定位**：策略的可行性由流水线的属性决定，不是反过来。不幂等就不敢自动重试、不敢自动回滚，只能叫人。

**展开结构**：（1）四种策略的判据表（rolling / blue-green / canary / shadow），各自的代价。（2）我实际用的是两个层次：集群层 blue/green（双集群 + 流量前置切换 + 暂停复制 + lag 回落 + 验证 + 切回），节点层 rolling + 不可变替换（Instance Refresh 20% batch, pause-on-failure）。（3）在 blue/green 前提下 20% batch 的语义变了：不是保护用户，是节奏控制。（4）**fail-fast vs fail-safe 的判据**：什么时候停在原地保留现场比自动回滚更对？疑似数据损坏时，因为回滚会盖掉证据。判据是「回滚动作本身是否覆盖状态」：LT 回滚不覆盖（版本并存，diff 随时可看），数据回滚覆盖。

**挂载**：S01；S07 的 L2；fundamentals Q37。**这题的完整版属于 05 方向**，这里给到能接住追问的深度即可。

---

### C5. 「你们的 change failure rate / rollback MTTR 是多少？」★★ ⚠️ 陷阱题

**一句定位**：我们没有系统性采集，这正是我说 CI/CD 的 metrics 化是我们的缺口的意思。

**展开结构**：（1）**先诚实**：不许估一个数字出来。evidence 里明确写着简历 bullet 的数字「待填」，说明手上没有。（2）**然后把它变成一个我懂这件事的证明**：说清我做到的那一层和没做到的那一层。做到的是事件通知层（构建级 Slack/email、失败归因、按服务路由到 oncall、partial results 落盘），没做到的是 metrics 化（无 Prometheus 指标、无构建时长趋势、无 DORA 采集）。（3）说清如果要补会怎么补：pipeline 的 SLI 是成功率、时长、排队时间；构建事件打成 metrics + Grafana annotation，让部署竖线出现在所有业务图表上（这个机制我在监控侧用过）。（4）**反问对方**（这是这题最好的收尾）：你们的 change failure rate 大概多少？一个 bad deploy 从发现到回滚要多久？有 progressive delivery 还是全量推？生产部署谁 approve、紧急旁路怎么审计？

**挂载**：S05 的归属边界段；fundamentals Q34。⚠️ 这题答歪（编数字）会毁掉整场面试的可信度。

---

### C6. 「供应链安全你们怎么做？」★★ ⚠️ 外环

**一句定位**：诚实说，我们在这块的成熟度不高，我能讲的是四层框架加我手上三个真实的反面教材。

**展开结构**：（1）四层框架：源码到构建的完整性 / 依赖 / 构建过程（provenance）/ 工件与部署（签名、SBOM、admission 验签）。（2）**三个反面实证，这是这题的可信度来源**：`jenkins.yaml` 里明文 AWS AccessKey + SecretKey 进了 git 历史；`values.yaml.j2` 里硬编码 AWS Access Key/Secret 同样进了 git 历史（修复三步：IAM rotate/disable、改用 IRSA 或 instance profile、`git filter-repo`/BFG 清历史）；上游依赖消失不是理论风险，是我修过的生产故障。（3）**明确边界**：镜像签名（cosign）、SBOM、SLSA provenance、admission 层验签我没有实践证据，只能作为我知道的标准做法讲。（4）加一条我的一手论点：凭据集中在流水线够得着的地方本身就是自动化打开的新故障面。

**挂载**：fundamentals Q39。这是这个方向外环里最该补的一块。

---

## D. Terraform（6 题）

> 全部走 `terraform_honest_answer.md`。三条心态铁律：绝不说用过、绝不说不懂、主动把话题引向幂等/drift/blast radius/真相源。

### D1. 「你们用 Terraform 吗？」★★★

**一句定位**：不用。我们的 IaC 是 Ansible-centric，而我很清楚它换来了什么、代价是什么，那个代价恰好就是 Terraform 存在的理由。

**展开结构**：（1）我们的形态：Packer + Ansible + kubeadm，四层。（2）Ansible 换到的：一套工具同时建资源加配机器，不用在两个工具之间传 state 和 IP（举 `sed -i` 把 NLB DNS 回写进 `controlPlaneEndpoint` 的实例）。成立条件是「少量长生命周期集群 + onsite 交付要求一套代码通吃」。（3）**代价四条**：没有 state 文件 → 没有 plan 预演、没有 drift detection、没有安全 destroy、没有并发锁；Ansible 靠每 module 查 AWS API 判幂等，缺全局视图。（4）**加一条比 evidence 更狠的自我批评**：大量 role 用 `shell` 调 helm/kubectl 兜底，连它自己承诺的幂等和 `--check` 都没做到。（5）切换判据：集群数爆炸、或要 PR-based review 加 drift detection 时，TF 管 Layer 1、Ansible 管 Layer 0/2/3。更精确的判据是「当云资源的变更频率超过人能记住上次改了什么的时候」，因为 plan 的本质价值是**让变更集变成可评审的对象**。

**挂载**：`terraform_honest_answer.md` §1；S03 的 L4。

---

### D2. 「你没用过 TF，我怎么知道你能上手？」★★★

**一句定位**：我指的不是工具，是我做过的事情的形状。我为 50 集群的高风险变更手工造了一套 plan + 证据链 + 评审门禁，而那正是 TF 免费给你的东西。

**展开结构**：（1）把 K8s 升级系统翻译成 TF 的词汇：显式健康基线 = refresh，真 dry-run 产出 diff = plan，量化 blast radius = state 切分，evidence chain = plan 保存 + PR review。**我是因为 Ansible 不给我这些才手工实现的。**（2）所以 TF 不是新的心智模型，是我已经不得不实现过一遍的东西的更好工程版。（3）需要补的是具体约定：state 布局、import 语义、`count` vs `for_each` 的地址陷阱、lifecycle meta-argument。（4）给一个动手证据（**做完实验 1 之后才能说**）：我故意破坏了一个 state 文件再 import 回来，看「零变更 plan」到底要几轮。

**挂载**：`terraform_honest_answer.md` §1 追问 + §5 第二个口径。⚠️ 第（4）点在实验做完之前不许说。

---

### D3. 「如果让你引入 Terraform，你怎么做？」★★★ 主战场

**一句定位**：我不会从「把现有基础设施 import 进 TF」开始，我会从「新建的、生命周期最长、爆炸半径最大、而且现在压根没人管」的那一层开始。

**展开结构**：四阶段，每阶段有退出条件。（0）**只读功课**：画「谁是真相源」的现状地图、定 state 切分、定 review 流程。这三件事必须在写第一行 HCL 之前定。（1）**绿地先行**：管 VPC / Subnet / NAT / IAM / SG。三条理由：这层现在完全没有 IaC（纯增量、零双写风险，**引入新工具的最佳落点是「现在没人管」的地方而不是「管得不好」的地方**）、变更最低频所以 plan 的评审价值最高、blast radius 最大所以最需要可评审的变更集。顺手收紧 SG 的东西向零隔离，但**记得放行 Calico IPIP 的 IP protocol 4**。（2）**import 存量**：用 `import` block（config-driven，可 review）而不是命令式 `terraform import`；五步流程，**`plan` 零变更是唯一通过标准**；第五步「关掉对应的 Ansible 代码路径」和 apply 是同一个原子操作，因为**双写是唯一不可接受的中间态**；我们的 Ansible 本来就是开关驱动的（`auto_create_*`），这些开关是天然交接点。顺序按 blast radius 从小到大。明确不 import Layer 2/3。（3）**接流水线加治理**：CI plan、人工审批 apply、`plan -out` 保证所见即所执行、对 plan 做策略检查（含 destroy 要额外审批）、`prevent_destroy`、lock 文件进 git、secret 不进 state。（4）**每日 drift 检测**：这条来自 BKC 项目最有价值的一条结论：audit 独立于 update 就有独立价值。

**收尾一句**：这个方案的核心不是 TF 的技术细节，是三条判断：新工具落在没人管的地方、双写是唯一不可接受的中间态、state 的切分就是 blast radius 的切分。这三条我不是从 TF 文档学的，是从做 50 集群跨版本升级学的。

**挂载**：`terraform_honest_answer.md` §2 全篇。

---

### D4. 「state 怎么组织？workspace 还是目录？」★★★

**一句定位**：目录隔离 + 共享 module，不用 workspace 做环境隔离。

**展开结构**：（1）workspace 的三个致命问题：共享同一 backend 和凭据（真正的环境隔离应该连账号都分）、配置无法差异化（很快变成条件语句森林）、切错 workspace 没有任何提醒（目录隔离下路径本身就是提示）。（2）切分三个维度：环境（不可协商，是权限和 blast radius 的边界，且和我们既有的 `cluster_type` 分类天然对齐）、生命周期长度（network 年级 / platform 季度 / cluster 月级）、region（6 个 region 天然是故障隔离边界）。（3）**为什么要拆细**：state 大小直接决定 plan 时长（refresh 撞云 API 限流）、锁争抢（一个大 state 意味着一人 apply 全员等）、以及灾难恢复的可行性（state 丢了要重新 import，越大越走不完）。（4）backend：S3 + `encrypt` + KMS + **`use_lockfile = true`**（TF 1.10 原生锁，DynamoDB 已弃用）+ bucket 版本控制（state 损坏时唯一的救命绳）。

**挂载**：`terraform_honest_answer.md` §2「state 怎么组织」；fundamentals Q23 + Q29。

---

### D5. 「state 文件是什么？为什么它这么重要？」★★

**一句定位**：state 是「TF 管的资源」和「云上真实资源」之间的映射表，而它之所以是唯一真相源，是因为**云上的资源不携带「我属于哪个配置块」这个信息**。

**展开结构**：（1）四个职责：身份映射、属性缓存（用于 diff 和传值）、依赖记录（destroy 时反向删）、元数据（serial / lineage）。（2）危险性：state 丢了不等于资源丢了，但等于 TF 失忆，下一次 apply 会试图重建一切；两人同写会互相覆盖导致部分资源脱管。（3）**secret 进 state**：TF 原样存储属性，`sensitive = true` 只影响显示不影响存储；所以 state 必须当 secret 对待。缓解是 backend 加密 + ephemeral/write-only（TF 1.10/1.11）+ 让 TF 只管引用不管值。OpenTofu 从 1.7 起有原生 state 加密。（4）**我的视角**：我对 state 的第一直觉不是「怎么保护它」，是「**它是缓存而不是真相，真相在云上**」，因为我在 K8s 升级里踩过同形的坑，`state.yaml` 只告诉我哪步失败，判断一步是否完成必须回到集群实测。

**挂载**：fundamentals Q22 + Q24；`terraform_honest_answer.md` §3 坑 1。

---

### D6. 「TF 的坑你知道哪些？」★★★

**一句定位**：我讲八个，每个都用「TF 的机制 + 我在 Ansible/K8s 侧的同构经验」两段式讲，因为这些坑我不是背的，是迁移过来的。

**展开结构**（按可讲价值排序，面试里挑 3-4 个展开）：
1. **state 是缓存不是真相** ↔ K8s 升级的 `state.yaml` 只说哪步失败、判定要回到集群实测。
2. **apply 中途失败不是全有或全无，TF 没有回滚** ↔ etcd snapshot 恢复数据不恢复二进制，所以真实策略是「门禁 > 前滚 > 回滚」。
3. **`count` 的索引不稳定引发连环重建** ↔ 「身份 vs 位置」问题；生产实证是 OLAP frontend 用旧 Pod IP 注册导致 285 次 CrashLoop，修复是 headless Service + FQDN 让身份不随 IP 漂移。**一般化：任何需要长期稳定的引用都不能用位置当身份。**
4. **`ignore_changes` 是放弃管理不是不检测** ↔ 50 集群的 feature flag 取舍，配套护栏是「flag 数量增长本身是分类失准的信号」，所以每个 `ignore_changes` 要注释真相源并统计数量。
5. **大 state 让 plan 慢到没人跑** ↔ 验证成本太高会导致验证被跳过而不是变慢；实证是我 91 个 Debug commit（没有本地验证手段只能 push-and-run）。
6. **secret 进 state** ↔ 我们组织两次明文凭据进 git 历史的实证。结论：任何会持久化的东西都要假设它会泄露。
7. **`provisioner` 是声明式工具里的命令式后门** ↔ 我们 Ansible 用 `shell` 调 helm/kubectl 是同一个病，用了就失去那个工具的全部保证。
8. **plan 干净不等于 apply 成功** ↔ dry-run 会骗人的实证（`shell` 兜底让 `--check` 完全失效）。**dry-run 的可信度等于最不可信那一步的可信度。**

**挂载**：`terraform_honest_answer.md` §3 全篇；fundamentals Q31。

---

## E. 综合场景（4 题）

### E1. 「你的集群要从 1.29 升到 1.33，你怎么规划？」★★★

**一句定位**：我会先做三件和版本无关的事，因为上一轮教给我的最重要一课是「升级难的不是知道做什么，是用证据证明现在可以做下一步」。

**展开结构**：（1）**先复用已有资产**：check/plan/apply 那套流水线和 evidence 结构可以直接用，这是上一轮真正沉淀下来的东西（它已经外溢成日常 infra health check）。（2）**版本相关的功课**：逐 minor 列出移除类变更（1.29→1.33 之间我会重点查 in-tree 存储插件的彻底移除、`flowcontrol` 与各类 beta API、以及 sidecar container 之类新特性带来的行为变化）；用 `apiserver_requested_deprecated_apis` 指标做**运行时**探测而不只是扫 manifest（这是我上一轮的缺口，明确要补的）；查 addon 版本矩阵（CCM 必须匹配 minor、CA 必须 >= K8s 版本）。（3）**补上一轮的两个缺口**：加一类**功能性 synthetic gate**（升级后真的 helm install 一个带 Ingress 的最小 workload），因为上一轮的 addon gate 只验「组件自己还活着」，而 caBundle 那次事故的形态是「组件活着但它对写入路径的副作用坏了」；把 check 从「升级前跑」改成「一直在跑」，让 drift 变成时间序列而不是一个快照，顺便解决 baseline 可信度问题。（4）**如果我能改架构**：这一轮之前先推 EKS 迁移，让控制面升级退化成一次 API 调用。

**挂载**：S01 + S02 的 L5 + S08 的 L5；fundamentals Q5。这题是把「学到了什么」讲成体系的最好机会。

---

### E2. 「一次变更之后大面积失败，你怎么处理？」★★

**一句定位**：第一个动作不是查，是路由，判断这是共享层还是单点，因为这两个分支的调查路径完全不同。

**展开结构**：（1）**路由判据**：多个租户在同一分钟以同一机制失败 = 集群级基础设施信号，直接跳过应用层（caBundle 那次和 Jenkins 迁移那次都是靠这条判断省掉了大量无效调查）。（2）**分层隔离**：ASG 节点故障那次的做法：ASG 活动记录 → launch template → user-data / cloud-init → kubeadm join → kubelet 日志，因为「启动失败」和「加入失败」的归属完全不同，混着查会来回横跳。（3）**恢复优先还是定位优先**：容量受损时先回滚到已知良好的 LT / AMI 恢复容量再追根因；但疑似数据损坏时相反，停在原地保留现场，因为回滚会盖掉证据。判据是「回滚动作本身是否覆盖状态」。（4）**收尾动作**：根因修完删掉临时 workaround（Jenkins 那次的 3 个 remove-workaround commit），否则死代码会遮蔽下一次的信号。

**挂载**：S08 + S07 + S04；fundamentals Q37。

---

### E3. 「让你从零设计一套 50 集群的基础设施管理体系，你怎么做？」★★★

**一句定位**：我会按「谁在持续维持这个状态」把它切成四层，然后给每层配一个不同的工具和不同的评审强度，而不是找一个统一的工具。

**展开结构**：（1）四层与工具：Layer 0 镜像 = Packer（不可变工件，版本化，回滚就是指向旧版本）；Layer 1 云资源 = **Terraform**（需要 plan / drift / 依赖图 / 安全 destroy）；Layer 2 控制面 = **托管服务（EKS）**，理由是知识密度极高、出错代价极大、和业务差异化零相关，这是最该外包的一层；Layer 3 集群内组件 = K8s 自己 + Helm/声明式 CD。（2）**跨层的三条纪律**：blast radius 是设计输入不是结果（state 切分 / `serial: 1` / batch size / 环境分账号）；高频可逆的自动化、低频不可逆的设闸；audit 独立于 update 就有独立价值（每日 drift 检测 + 常态 health check）。（3）**异构性的处理**：`cluster_type` 分类 + 少量 feature flag，且把 flag 数量当成分类失准的信号。（4）**明确的诚实边界**：Layer 3 的声明式 CD（ArgoCD/Flux）我没有生产经验，这是我会补的一块；Crossplane 那条路（把云资源变成 CRD 由 controller 持续 reconcile，2025-10 从 CNCF 毕业）我认为在方向上更对，它把 IaC 从「plan/apply 的一次性动作」变成「持续收敛的控制循环」，但我只在理论层面理解它。

**挂载**：S03 + S01 + S09；fundamentals Q20 + Q33；`terraform_honest_answer.md` §2。

---

### E4. 「你在这个方向上最大的短板是什么？」★★★

**一句定位**：三块，按对我的实际影响排序：Terraform 的实操、声明式 CD（ArgoCD/Flux）的生产经验、以及交付流水线的 metrics 化。

**展开结构**：（1）**Terraform**：没有生产经验。但我说清代价与切换条件、也做了系统性的功课和动手实验；我不认为这是心智模型的缺失，是具体约定的缺失。（2）**声明式 CD**：我们是 Jenkins 加人工审批的形态，我对「命令式 vs 声明式 reconcile」有一手论点（因为我是在命令式框架里手工补幂等的那个人），但我没有跑过 ArgoCD 的生产环境。**这条尤其要主动说，因为简历里出现过 GitOps 这个词，我不想让它变成一个虚的点。**（3）**metrics 化**：我做到了事件通知层（失败归因 + oncall 路由），没做到 metrics 化和 DORA 采集。所以我报不出 change failure rate，这是缺口不是保密。（4）**加一条我正在补的方向性判断**（把短板讲成成长而不是道歉）：这三块其实是同一件事的三个面：**基础设施的期望状态应该由一个持续运行的控制器维持，而不是由一次成功的执行来保证**。我在硬件层自己实现过这个思想（BKC daemon 的审计半），在 K8s 升级里手工模拟过它（check 外溢成常态 health check），但在云资源层和交付层我还在用「一次性执行」的范式。这是我下一步要补的完整闭环。

**挂载**：`terraform_honest_answer.md` §6 的不许说清单；S05 的归属边界；S09。**这题答好了是整场面试的加分项**，因为它证明我能自己画准边界。

---

## 附：反问清单（面试后半段主动抛出去）

抛这些的效果是从「候选人」变成「同行对话」：

- 你们的 **change failure rate / 回滚率**大概多少？一个 bad deploy 从发现到回滚要多久（rollback MTTR）？
- 有没有 **progressive delivery**（canary / 蓝绿），还是全量推？
- 生产部署谁 approve？**紧急旁路**怎么走、事后怎么审计？（我的判据：旁路使用率是一个反向健康指标，旁路用得越多说明正常路径越不可信，该回头修正常路径而不是修旁路。）
- 你们的集群是托管还是自管理？如果自管理，跨版本升级现在是谁的活、单集群多久？
- 云资源的真相源在哪？有没有每日 drift 检测？drift 发现之后走什么流程？
- 有没有环境之间的账号级隔离？prod 的凭据在 dev 的流水线里存在吗？

出处：反问清单的原型来自 `work-contexts/career/interview/interview-5-cicd_reliability.md:47-56`（旁路反向指标见同文件 :30）。
