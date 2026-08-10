# AWS Fundamentals：IAM 与安全基础

这一节的考点在哪：IAM 这块我最强的锚点不是"我设计过多精巧的 policy"，而是**我在自己工作的 repo 里真实发现过明文 AWS key 泄露进 git 历史的案例，并且能讲清楚正确的修复路径应该是什么**。这是一个天然的"发现问题并推动改进"的行为面素材，同时又能自然带出最小权限、密钥轮换、IRSA/instance profile 的技术讨论。诚实的部分同样重要：我们 kubeadm 自建集群目前**没有** IRSA/OIDC 这层，这个补课项本身也是一个可以主动提出的改进方向。

## 1. IAM 实体（user / group / role / policy）

**面试官会怎么问**：IAM 的基本实体有哪些，各自的作用是什么？

**标准答案（理论骨架）**
- **User**：代表一个长期身份（人或应用），可以有长期凭证（密码、access key）。
- **Group**：User 的集合，用来批量挂 policy，group 本身不能被 assume，只是权限管理的容器。
- **Role**：不绑定到具体身份的临时身份容器，通过"assume"获得，颁发的是**临时凭证**（有过期时间），是现代 AWS 权限设计的核心（相比长期 user access key，role 从根本上避免了凭证泄露后长期有效的风险）。
- **Policy**：JSON 文档，描述"谁能对什么资源做什么操作，在什么条件下"，可以挂在 user/group/role 上（identity-based policy），也可以挂在资源上（resource-based policy，如 S3 bucket policy）。

**我的场景锚点**：K8s 世界的 RBAC 和这套模型是结构同构的：ServiceAccount(身份) → Role/ClusterRole(权限定义) → RoleBinding(绑定) → API Server 裁决，这个类比我在自己的知识笔记里系统整理过（`2026-02-25_1651_k8s-rbac-and-iam-model.md`）：K8s 的 SA 对应 AWS 的 IAM User/Role，K8s 的 Role/ClusterRole 对应 AWS 的 IAM Policy，K8s 的 RoleBinding 对应 AWS 的"attach policy / assume role"，两边的作用域概念（namespace vs account/org）也能对上。这个同构关系是我在面试里能主动讲出来的一个"体系化理解"证据，不是临场现凑的类比。

---

## 2. Policy 结构与评估逻辑（高频考点，必须讲清评估顺序）

**面试官会怎么问**：一个请求同时受多个 policy 约束时，AWS 怎么决定最终允许还是拒绝？

**标准答案（理论骨架，这条必须逐层说清楚）**
1. 默认是**隐式 Deny**（没有任何显式 Allow，一律拒绝）。
2. 如果任何一层出现**显式 Deny**，直接拒绝，其他任何 Allow 都救不回来：显式 Deny 优先级最高。
3. 没有显式 Deny 的情况下，需要看是否存在**显式 Allow**：identity-based policy（挂在 user/group/role 上）和 resource-based policy（挂在资源上，如 S3 bucket policy）任何一边给出 Allow 都可能放行，取决于是否跨账号访问（同账号内 identity policy 单独就够，跨账号需要两边都 Allow）。
4. **SCP（Service Control Policy，Organizations 层级）和 Permission Boundary（针对某个 role/user 的权限上限）都只能收窄权限，不能授予权限**：它们是"天花板"，真正的权限授予必须来自 identity/resource policy，SCP/boundary 只是划定这个授予结果不能超过的范围。
5. 完整心智模型：最终允许 = (SCP 允许) AND (Permission Boundary 允许，如果设置了) AND (identity policy 允许 OR resource policy 允许) AND (没有任何显式 Deny)。

**我的场景锚点**：`⚠️ 待确认`：具体到我们公司是否使用了 Organizations/SCP/Permission Boundary，素材里没有证据，`[纯理论，无一手经验]`；这是外环补课项，评估逻辑本身我能讲清楚（这是 AWS IAM 最容易在电话面试里被抽查的一段"背诵型"知识），但没有把它应用到我们自己账号结构的一手经验。

---

## 3. AssumeRole 与信任策略

**面试官会怎么问**：AssumeRole 是怎么工作的？信任策略和权限策略有什么区别？

**标准答案（理论骨架）**`[理论]`
- Role 有两类策略：**权限策略**（这个 role 能做什么，等价于普通 identity policy）和**信任策略**（trust policy，规定"谁能 assume 这个 role"，本质是一个特殊的 resource-based policy，`Principal` 字段指定可信主体）。
- AssumeRole 调用 STS，验证请求方是否匹配信任策略里的 Principal，验证通过后颁发一组临时凭证（AccessKeyId/SecretAccessKey/SessionToken），默认有效期可配置（15 分钟到最长通常 12 小时，具体上限由 role 的 `MaxSessionDuration` 决定）。
- 常见用途：跨账号访问（账号 A 的 role 信任账号 B 的某个身份）、EC2/Lambda 等计算服务通过 instance profile/execution role 获得临时凭证、联合身份（SAML/OIDC）登录换取 AWS 临时凭证。

**我的场景锚点**：`[纯理论，无一手经验]`，没有素材证明我直接设计过跨账号的 AssumeRole 信任关系。能讲清机制，讲不出真实故事。

---

## 4. Instance Profile

**面试官会怎么问**：EC2 实例怎么拿到 IAM 权限？

**标准答案（理论骨架）**
- Instance Profile 是 IAM Role 的一个容器，附加到 EC2 实例上；实例内的进程通过 IMDS（Instance Metadata Service，`169.254.169.254`）拿到该 role 的临时凭证，AWS SDK 默认会自动尝试这个来源，不需要在实例里硬编码任何密钥。
- 这是"实例级别"的权限粒度：挂在这台实例上的**所有**进程/容器共享同一个 role 的权限，无法在实例内部对不同进程做更细的权限区分：这正是 IRSA 想解决的问题（见下一节）。

**我的场景锚点**：我们 kubeadm 自建的集群里，CCM（cloud-controller-manager）、EBS CSI Driver、Cluster Autoscaler 这些组件要调 AWS API（建 ELB、建/挂载 EBS 卷、查询/调整 ASG），在没有 IRSA 的前提下，最合理的权限模型就是**node instance profile**：EC2 worker 节点挂一个有相应权限的 role，节点上所有 Pod（包括这些系统组件）共享节点级别的 AWS 权限。这个模型的代价是权限粒度粗：业务 Pod 理论上也能拿到节点级别的 AWS 权限，这正是下一节 IRSA 缺失要解决的问题，也是 jenkins.yaml key 泄露事件背后的权限设计背景（当时选择硬编码 key 而不是走 instance profile，本身就是这层权限模型没有被严格执行的一个症状）。

---

## 5. IRSA（K8s ServiceAccount 到 IAM Role，本节最诚实的一段）

**面试官会怎么问**：什么是 IRSA？你们 50 个集群怎么管这个的？

**标准答案（理论骨架）**
- IRSA（IAM Roles for Service Accounts）是 EKS 生态原生支持的机制：给集群配一个 **OIDC identity provider**（集群的 OIDC issuer 注册进 AWS IAM），K8s ServiceAccount 上打一个 annotation 指向某个 IAM Role 的 ARN，这个 role 的信任策略里限定"只有来自这个 OIDC provider、且 subject 匹配这个具体 namespace/ServiceAccount 的联合身份才能 assume"。
- 效果：同一个节点上不同 Pod 可以按各自的 ServiceAccount 拿到**不同**、**权限最小化到具体工作负载**的 IAM 权限，而不是像 instance profile 那样节点上所有 Pod 共享一个粗粒度权限。
- 这是从"节点级别权限"进化到"工作负载级别权限"的关键机制，是现代 AWS+K8s 最小权限实践的标准做法。

**诚实的场景锚点（这条必须诚实）**
- 我们是 **kubeadm 自建的集群**，不是 EKS 托管，**没有为集群配置 OIDC identity provider**，也就没有 IRSA 这层。素材里能确认的是：我们的安全审计清单里，"Secret 明文硬编码"这一项的修复建议明确写的是"改用 IRSA / instance profile"（`interview-8-k8s-cluster-build.md`"关键权衡速查表"），这条建议本身说明团队**知道** IRSA 是正确方向，但目前**没有落地**，走的是 instance profile 这条更粗粒度但至少不硬编码密钥的路径。
- `⚠️ 待确认：是否任何一个集群已经实验性配置了 OIDC provider / IRSA`，没有更进一步的素材可以确认，不编造。

**如果被追问到边界（这条答法本身是加分项）**：如果面试官追问"为什么不上 IRSA"，诚实且体现判断力的答法是：自建 kubeadm 集群配 OIDC provider 是可行的（不是 EKS 专属能力，社区有标准做法），但这是一项要跨 50 个集群统一落地的基础设施投入，目前团队的权限模型停留在 instance profile + 部分硬编码这个更原始的阶段，这正是我会主动提出的下一步改进方向，而不是我们判断过 IRSA 不适合而放弃。这个答法把"补课项"转成了"我看得清改进路径"的信号。

---

## 6. 跨账号访问

**面试官会怎么问**：跨账号访问怎么设计？

**标准答案（理论骨架）**`[理论]`
- 标准模式：账号 A 建一个 role，信任策略里 `Principal` 指定账号 B（或账号 B 的某个具体 role/user），账号 B 的身份调用 `sts:AssumeRole` 拿到账号 A 的临时凭证；可以叠加 `ExternalId` 防止"混淆代理人"问题（第三方场景下防止别人拿着同一个 role ARN 冒充）。
- 组织级替代方案：AWS Organizations + 资源共享（RAM）+ SCP，用于大规模多账号治理，而不是逐个手写跨账号 role。

**我的场景锚点**：`[纯理论，无一手经验]`。我们是否有多账号结构（比如不同 region/环境是否分账号），素材没有明确信息，`⚠️ 待确认：我们的账号结构是单账号多 region 还是多账号`。

---

## 7. 临时凭证与 STS

**面试官会怎么问**：临时凭证和长期凭证（access key）有什么本质区别？为什么长期 key 是反模式？

**标准答案（理论骨架）**
- STS（Security Token Service）颁发的临时凭证包含一个 SessionToken，且有明确过期时间；泄露后风险窗口有限（过期后自动失效），且大多数临时凭证的获取路径（instance profile/IRSA/AssumeRole）不需要把密钥写在任何地方，从根源上减少了"密钥被意外提交进代码"的攻击面。
- 长期 access key（IAM User 的 key）没有内置过期机制（除非手动轮换/设置密码策略强制轮换），一旦泄露且未被发现，风险窗口是无限的，直到有人主动发现并禁用。

**我的场景锚点（真实案例，本节的核心证据）**
- 我在梳理 Jenkins 迁移相关素材时，发现工作 repo `infra/jenkins-config/jenkins.yaml` 里存在**明文硬编码的 AWS AccessKey + SecretKey**（`AKIAJQXAV6...`开头，L28-31，加上 L23 的 JENKINS_SECRET），且这份文件已经进了 git 历史。同一批排查里，`infra-internal` 的 `roles/cilium/templates/values.yaml.j2` 也发现了另一处硬编码的明文 AWS Access Key/Secret，同样已进 git 历史。这两处是我在做面试材料/知识库梳理时**主动发现**的真实安全债，不是别人报告给我的。
- 正确的修复路径（我在自己的笔记里写清楚过）：① 立即 rotate/disable 泄露的 IAM key；② 把这类组件迁移到 IRSA/instance profile，从根源上不需要在任何 YAML 里出现长期 key；③ 用 `git filter-repo` 或 BFG Repo-Cleaner 把敏感内容从 git 历史彻底清除（普通 `git rm` 不够，历史提交里的内容仍然可追溯）；④ 排查这个泄露的 key 在事件发现前是否被异常使用过（CloudTrail 审计）。
- 这个案例同时是一个**很好的行为面素材**："发现问题并推动改进"：我不是在写一份技术评审报告，而是在整理自己过往工作痕迹时主动识别出一个真实的安全隐患，并且能提出结构化的修复步骤（不只是"改一下"，而是 rotate + 架构性修复 + 历史清理 + 审计回溯 四步都想到了）。

**如果被追问到边界**：这两处发现目前状态是"识别并记录了修复建议"，`⚠️ 待确认：这两个 key 是否已经完成了实际的 rotate 和历史清理`，如果面试官追问"后续处理结果如何"，诚实答法是我在整理材料时发现并记录了这个问题和修复路径，具体的轮换/清理动作是否已经执行完成需要回去确认，不能在没有证据的情况下声称"已经修复"。

---

## 8. 密钥管理反模式（延伸）

**面试官会怎么问**：除了硬编码，还有哪些常见的密钥管理反模式？

**标准答案（理论骨架）**`[理论，部分有真实印证]`
- 硬编码进代码/配置文件并提交 git（我们真实踩过，见上）。
- 长期 key 从不轮换（没有密钥轮换策略/自动化）。
- 把权限过大的 key 用在权限需求很小的场景（比如给一个只读脚本配了管理员权限的 key）。
- 密钥通过非加密渠道传递（Slack 消息、邮件明文粘贴）。
- kubectl describe/日志输出里意外包含明文密码环境变量，粘贴进工单前没有脱敏：这条我们的实际运维材料里也有过提醒（`case_cards.json` 提到"kubectl describe 输出可能含明文密钥，贴进 ticket 前必须脱敏"），说明这不是纯假设的风险，是团队内部实际会强调的操作纪律。

**我的场景锚点**：除了上面 jenkins.yaml/cilium values.yaml.j2 这两处 hardcode 案例，"kubectl describe 输出脱敏"这条操作纪律是我们运维知识库里真实存在的提醒项，证明团队在这个问题上不是零意识，只是没有把 IRSA 这类结构性修复落地。

---

## 9. 最小权限的实操落地路径

**面试官会怎么问**：最小权限原则在实践中怎么落地，而不只是一句口号？

**标准答案（理论骨架）+ 我的场景锚点**
- 落地路径通常是：① 先用宽松权限（甚至临时 admin）跑通功能，② 收集 CloudTrail 里这个角色实际调用过的 API，③ 用 IAM Access Analyzer 或手工比对生成"实际用到的权限最小集"，④ 收紧 policy 到这个最小集，⑤ 持续监控是否有权限不足的报错、迭代调整。
- 这个"先宽松验证、再收紧"的模式，和我们 K8s RBAC 权限落地的实际做法是结构一致的：我们有 dapp(控制面：审批/角色映射) + JumpServer(网关：凭证托管+审计) + K8s RBAC(裁决层) 三层的访问控制架构（`2026-02-25_1651_k8s-rbac-and-iam-model.md`），新增一个角色时的标准四步是"建 ClusterRole/Role → 建 SA → Binding → `kubectl auth can-i --as` 验收"，这个"先定义、再用 `auth can-i` 验证边界"的做法和 AWS 侧的"先宽松、用 CloudTrail 反推最小集"是同一种"用可验证的方式代替猜测"的工程纪律，只是工具链不同。
- 这套三层架构还带来一个诚实的观察值得讲：K8s audit 只能看到 ServiceAccount 级别的身份，看不到具体是哪个人操作的，真正到"人"的审计粒度在 JumpServer 层(会话审计/录屏),这是当前架构的一个已知局限，升级方向是 JumpServer 侧用 impersonation 或每人一个 OIDC 身份，让 K8s 审计能直接看到人。

---

## 10. 常见 IAM 面试题（快速问答補充，主干题目见 questions.md）

- **Q: root 账号应该怎么用？** `[理论]` 只用于账号创建初期和极少数只有 root 能做的操作（关闭账号、改支持计划），日常操作应该用 IAM User/Role，root 应该开 MFA 且不生成 access key。
- **Q: MFA 在 IAM 里怎么强制？** `[理论]` 可以在 policy 里用 `aws:MultiFactorAuthPresent` condition key 强制"必须带 MFA 的会话才能执行某些操作"。
- **Q: Policy 里的 `Condition` 块能做什么？** `[理论]` 基于请求上下文做细粒度限制，比如限制来源 IP（`aws:SourceIp`）、限制时间窗口、限制必须走加密连接（`aws:SecureTransport`）、限制资源 tag 匹配。这类条件是把静态的"谁能做什么"进一步收窄成"谁在什么条件下能做什么"，是最小权限里经常被忽视的一层。
