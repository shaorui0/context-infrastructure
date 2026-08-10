# Terraform：一套既诚实又能加分的答法

> **这份文件的前提**：我没有 Terraform 的生产经验。我的栈是 Packer + Ansible + kubeadm。
> 这份文件的目标不是把「没经验」藏起来，而是把这个话题从**记忆题**（你会不会用 TF）转成**判断题**（你怎么想 IaC）。后者我有真实的一手材料，而且比很多有 5 年 TF 经验的候选人更成体系。
> 所有关于我的经历的引用都带 `(src: 路径)`；所有 TF 知识标 `[理论]`；2026 年生态事实标 `(src: web 2026-07)`，来自 2026-07-29 的定向调研。

---

## 0. 三条心态铁律（先定死，否则会答歪）

1. **绝不说「我用过 Terraform」，也绝不说「我不懂 Terraform」。** 正确的自我定位是：「我们的 IaC 是 Ansible-centric，我很清楚它换来了什么、代价是什么，而那个代价恰好就是 Terraform 存在的理由。」这句话本身就是懂 TF 的证明。
2. **不要为「没用 TF」道歉，也不要辩解成「TF 不好」。** 这个选择在我们的场景下有成立的理由，我能讲出所以然；同时它有明确的失效条件，我也能讲出来。既不防御也不谄媚。
3. **主动把话题引向我的强项：幂等、drift、blast radius、状态的真相源。** 这四个概念在 TF 里的名字叫 idempotency、drift detection、blast radius、state。我在 Ansible/K8s 侧对每一个都有一手洞察。TF 只是同一组问题的另一种解法。

---

## 1. 「你们用 Terraform 吗？」的直接答法

### 30 秒版本（先给结论，等追问）

> 「不用。我们的 IaC 是 Ansible-centric：Packer 做机器镜像、Ansible 建 AWS 资源并配置机器、kubeadm 起控制面。这个组合在我们的场景下是有原因的，因为我们的集群是少量长生命周期的资产，而且我们同时要交付 onsite 环境，一套代码得能装云上也能装客户机房。代价我很清楚：**没有 state 文件，所以没有 plan 预演、没有 drift detection、没有安全的 destroy、没有并发锁**。Ansible 靠每个 module 自己查 AWS API 判断幂等，缺全局视图。这四条缺失恰好就是 Terraform 的核心价值，所以我的结论是：集群数量继续涨、或者要 PR-based review 加 drift detection 的时候，正确形态是 Terraform 管 AWS 资源那一层、Ansible 管镜像和集群内部那三层。」

出处：Ansible-centric 而非 Terraform (src: `work-contexts/career/interview/interview-8-k8s-cluster-build.md:40`)；四条缺失与「缺全局视图」(src: `interview-8-k8s-cluster-build.md:46`)；分工结论 (src: `interview-8-k8s-cluster-build.md:47`)；onsite 交付约束 (src: `interview-8-k8s-cluster-build.md:206`)。

### 2 分钟版本（讲清所以然）

分四段，按「这不是落后，是权衡」的结构组织。

**第一段，说清我们的分层，让对方知道我脑子里有结构不是有习惯。**

四层叠加 (src: `interview-8-k8s-cluster-build.md:12-17`)：Layer 0 机器镜像（Packer AMI，含 OS + containerd + kubeadm）；Layer 1 AWS 基础设施（SG / EC2 / NLB / Target Group / ASG / Launch Template 由 Ansible 建，而 VPC / Subnet / NAT Gateway / IAM Role 是 repo 外手动预建，vars 里只引用 ID）；Layer 2 K8s 控制面（kubeadm init/join + stacked etcd）；Layer 3 集群内组件（CNI / CCM / CSI / Ingress / 监控日志）。

这里有一个可以主动送出去的洞察：**Layer 1 内部还有一条边界，而这条边界的划法本身就是 TF 思维**。VPC / Subnet / NAT / IAM 我们没有用任何 IaC 管，是手动预建的，理由是它们的生命周期是账号级、以年计；集群是可以被销毁重建的。也就是说我们已经在按「生命周期长度」切分状态的所有权了，只是切完之后长生命周期那一半直接交给了人工而不是交给 TF。**这是这套体系最该被 TF 接管的地方**，而不是集群那一层。

**第二段，说清 Ansible 换到了什么。**

一套工具同时「建资源 + 配机器」，不用在 TF（建）和 Ansible（配）之间传 state 和 IP。具体到代码：`roles/aws/tasks/main.yml:189` 用 `sed -i` 把新建的 NLB 的 DNS 直接回写进 `hosts-aws` 的 `controlPlaneEndpoint`，建完即用，`kubeadm_config.yaml.j2` 直接引用它 (src: `interview-8-k8s-cluster-build.md:44-45, 200`)。在 TF + Ansible 的分工下，这个动作要跨两个工具传值（TF output → SSM/inventory → Ansible），多一个交接面就多一处失败点。

对于「少量长生命周期集群」这个场景，这个一体化是真便宜的：新建集群是低频事件，而每次新建都要建机器加配机器，一体化省掉的是交接成本。

**第三段，说清代价，而且要说得比对方问得更深。**

四条缺失 (src: `interview-8-k8s-cluster-build.md:46`)，我按「痛的程度」重排：

| 缺失 | 具体后果 | 我实际感受到的形态 |
|---|---|---|
| 没有 plan 预演 | 无法在执行前看到「将要改什么」的完整清单 | 我在 K8s 升级里不得不**自己造一个 plan**：`ansible --check --diff` + AMI diff + LT diff，还要写规则限定「只允许 AMI ID 变化」(src: `work-contexts/career/interview/interview-1-k8s_upgrade_reference.md:43`)。这等于手工重建了 TF 免费给的东西 |
| 没有 drift detection | 无法回答「现在的云资源是否符合期望」 | 我的处理是**不追求消灭 drift，而是让它在升级前变得可见**：check 阶段的 baseline snapshot + `cluster_type` 分类 + per-cluster feature flag (src: `interview-1-k8s_upgrade_reference.md:141`；`adhoc_jobs/dynamic_resume_site/content/projects/p_k8s_upgrade.md:51`)。这是一个诚实的降级方案，不是等价替代 |
| 没有安全的 destroy | 没有依赖图，不知道删除顺序，也不知道「删这个会连带影响谁」 | 这一条我们靠「基本不 destroy」规避，也就是用流程限制替代工具能力 |
| 没有并发锁 | 两个人同时跑同一个 playbook 没有任何阻止机制 | 靠「集群数量少 + 团队小 + 约定」规避 |

再加一条我自己补的、比 evidence 更狠的：**Ansible 里大量 role 直接 `shell` 调 `helm upgrade --install` 或 `kubectl apply` 兜底，导致不真正幂等、`--check` 失效（也就是 dry-run 会骗人）、错误埋在 shell 输出里。这是这个 codebase 最大的技术债之一** (src: `interview-8-k8s-cluster-build.md:74`)。这一条特别值得主动说，因为它证明我不只是「知道工具的理论局限」，我知道**这套代码在哪里连它自己的承诺都没做到**。

**第四段，给切换条件，把答案落成判据。**

集群数量爆炸、或者要 PR-based review 加 drift detection 时，应该改成 Terraform 管 Layer 1、Ansible 管 Layer 0/2/3 (src: `interview-8-k8s-cluster-build.md:47`)。

我会补一句更精确的判据：**当「云资源的变更频率」超过「人能记住上次改了什么」的时候，就必须上 TF。** 因为 plan 的本质价值不是自动化，是**让变更集变成可评审的对象**。这和我在别的地方反复做的事情是同一件：把隐式的东西变成显式的、可评审的声明 (src: `work-contexts/career/interview/interview-1-k8s_upgrade.md:11-13`)。

### 如果对方追问「那你是不是就没做过真正的 IaC？」

这是一个需要顶住的问题，答法：

> 「取决于你把 IaC 定义成什么。如果定义成 Terraform，那我没有。如果定义成『desired state 声明式、机器可执行、被持续 enforce』，那我做过一个比 TF 更底层的版本：在 Intel，我把 5G vRAN 的 Best Known Configuration 从一份 doc 里的 prose 加复制粘贴 shell，变成 git 里声明式、被持续审计的 desired state，形态是每台机器一个 systemd 层的 daemon，覆盖约 30 台裸金属服务器。那之前连 Ansible 这一级都没有 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_bkc.md:120, 222-224`)。我认领的是审计与监控这一半：持续巡检每台节点、上报 compliance 和 drift 时间戳；完整的风险分级修复模型我是作为设计口径讲的，不声称跑起来了 (src: `p_bkc.md:187`)。所以我的 IaC 经验的形状是：我理解 reconcile 是与 target 无关的，我自己实现过一个 target 是 BIOS 和 NIC 固件的版本。Terraform 是这个思想在云 API 上的实例，我需要补的是它的具体工程约定，不是它的思想。」

---

## 2. 「如果让你引入 Terraform，你怎么做？」（这道题是主战场）

> **为什么这道题答好了比有 5 年 TF 经验的候选人更亮眼**：5 年经验的候选人会讲他们公司怎么做的；这道题问的是「在一个已有存量、有 Ansible、有 50 个集群的环境里从零引入」，这考的是迁移设计、blast radius 控制、和组织落地，而这三件事我有真实的一手方法论（K8s 升级本身就是一次高风险存量改造的成功案例）。

### 总纲：一句话

> 「我不会从『把现有基础设施 import 进 TF』开始，我会从『新建的、生命周期最长的、爆炸半径最大的那一层』开始，先让 TF 在一个低风险高价值的位置证明自己，再逐层接管。整个过程我按四个阶段推，每个阶段有明确的退出条件，任何一个阶段失败可以停在那里而不是必须回退。」

这个总纲的骨架直接来自我做 K8s 升级的方法（分阶段、每阶段有 gate、失败暂停而不是回滚）(src: `interview-1-k8s_upgrade.md:58`)。

### 阶段 0：先做不改任何东西的功课（1-2 周）

三件事，全部只读：

1. **盘清「谁是真相源」的现状地图。** 每一类 AWS 资源现在由什么管：Ansible 的哪个 role、手工、还是云厂商自动行为。这一步的产出是一张表，行是资源类型，列是「谁创建 / 谁修改 / 变更频率 / blast radius」。**没有这张表就上 TF 是在制造双写。**
2. **定 state 的切分方案**（见下方「state 怎么组织」）。这个决定最难改，所以必须在写第一行 HCL 之前定。
3. **定 review 与执行流程**（见下方「review 流程」）。同理，先定流程再写代码，否则第一个 apply 就会是某人在本地跑的。

退出条件：三份文档 review 通过，并且团队对「TF 管哪些、Ansible 管哪些」这条线有共识。

### 阶段 1：绿地先行，用 TF 管**新建的**长生命周期资源（1 个月）

**先管什么**：VPC / Subnet / 路由 / NAT Gateway / IAM Role / SG。

理由三条，每条都能顶住追问：

- **这一层现在是手工预建的，也就是完全没有 IaC**，所以 TF 进来是纯增量，不和 Ansible 抢地盘，不产生双写 (src: `interview-8-k8s-cluster-build.md:20`)。**这是整个方案里最重要的一个洞察**：引入新工具的最佳落点是「现在没有任何工具管的地方」，而不是「现有工具管得不好的地方」。
- 这一层生命周期最长、变更最低频，所以 plan 的评审价值最高、apply 的频率最低（风险敞口小）。
- 这一层的 blast radius 最大（改错子网路由能打穿整个集群），所以它最需要 plan 这个「变更集可评审」的能力。

**做法**：下一个新建的集群（或者新 region）的网络层用 TF 建，老的一律不动。这一步是纯绿地，零风险，而且立刻产出一个可 review 的 PR 作为团队的样板。

顺手解决一个真实的安全债：SG 现在是「粗粒度信任边界」策略（可信来源全协议放行，端口级隔离下放给 CNI NetworkPolicy），东西向零隔离，安全审计过不了 (src: `interview-8-k8s-cluster-build.md:177-179`)。在 TF 里把 SG 规则写成显式的、逐端口的、可 review 的声明，正好是收紧它的最佳时机。**但必须记得放行 Calico IPIP 的 IP protocol 4，否则跨节点 Pod 完全不通** (src: `interview-8-k8s-cluster-build.md:197`)。这个细节我一定会讲，因为它证明我不是在纸上做迁移设计。

退出条件：一个新集群的网络层完全由 TF 管、plan 干净（无 drift）、团队有人独立跑过一次完整流程。

### 阶段 2：把存量 import 进来（2-3 个月，一次一个 blast radius 域）

**这是最危险的阶段，所以规则要最硬。**

**import 的现代做法** `[理论]` `(src: web 2026-07)`：用 `import` **block**（TF 1.5 引入，config-driven），配 `-generate-config-out=generated.tf` 生成配置骨架，而不是用命令式的 `terraform import`。理由是决定性的：block 形式**进 plan、进 git、可以被 review**；命令式 import 是某人在本地敲的一条命令，没人能审。这和我在 K8s 那边坚持「把隐式的人工操作变成显式的可评审声明」是同一条原则 (src: `interview-1-k8s_upgrade.md:11-13`)。

**import 的安全流程，五步，任何一步不过就停**：

1. 写 `import` block + 用 `-generate-config-out` 生成配置骨架。
2. **`terraform plan` 必须是「零变更」**。这是唯一可接受的通过标准。任何一个字段的 diff 都意味着我写的 HCL 与云上现状不一致，而 apply 会**按 HCL 去改真实资源**。这是 import 唯一真正危险的地方，也是我会花最多时间讲的地方。
3. 零变更达成后再 apply（此时 apply 只写 state，不动任何资源）。
4. 立刻验证：`terraform state list` 确认对象在、再跑一次 plan 确认仍然零变更。
5. **把对应的 Ansible 代码路径关掉**（把 `auto_create_*` 开关置 false，或删掉那段 task）。我们的 Ansible 本来就是开关驱动的（`auto_create_master_instance` / `auto_create_master_loadbalance` / `auto_create_autoscaler_group`）(src: `interview-8-k8s-cluster-build.md:53`)，这些开关正好是 import 的天然交接点。**这是我们既有设计给这次迁移留下的礼物，我会主动指出来**。

**双写是这个阶段唯一不可接受的状态。** 一个资源同时被 TF 和 Ansible 管，等于两个 controller 抢同一个 desired state，结果是每次跑谁就赢谁，而 drift 永远存在。所以第 5 步不是可选的收尾，它和第 3 步是同一个原子操作的两半。

**顺序**：按 blast radius 从小到大，和我做集群升级的顺序逻辑一致但方向相反（升级是从小 blast radius 开始建立信心，import 也一样）：dev 集群的 SG → dev 的 ASG/LT → preprod → prod 的一个集群作 canary → 其余 prod → 管理集群最后 (src: `interview-1-k8s_upgrade.md:58`)。

**明确不 import 的东西**：Layer 2 的 kubeadm 控制面和 Layer 3 的集群内组件。理由是这两层的期望状态不是云 API 能表达的，而 Layer 3 已经有一个持续 reconcile 的东西在管了（K8s 自己）。硬要用 TF 的 kubernetes/helm provider 管 Layer 3，就是把 K8s 的声明式 API 套一层 TF 的 state，多一个真相源、多一处 drift 来源。**这是一个我会主动划清的边界，因为很多人会犯这个错。**

退出条件：每个域 import 完之后连续一周 plan 零 drift。

### 阶段 3：把 TF 接进流水线并加治理（与阶段 2 并行推进）

- **CI 里 `plan`，人工审批后 `apply`**，apply 一定用 `plan -out` 保存的计划文件，保证「所见即所执行」`[理论]`。
- **对 plan 输出做策略检查**：任何包含 `destroy` 或 `replace` 的 plan 需要额外审批。这是 policy-as-code（OPA/Conftest/Sentinel）最有价值的一个用法。
- **给不可逆资源上 `prevent_destroy`**（数据库、state bucket 本身、生产 VPC）`[理论]`。
- **`.terraform.lock.hcl` 进 git**，provider 用 `~>` 约束，根 module pin 精确版本 `[理论]`。
- **secret 不进 state**：backend 开 SSE-KMS，把敏感参数改用 ephemeral values（TF 1.10）/ write-only arguments（TF 1.11）`(src: web 2026-07)`，或者让 TF 只管 secret 的引用不管值。这一条我会主动提，因为它是 TF 最常被忽略的安全问题，而我们已经有过明文凭据进 git 的历史教训（`jenkins.yaml` 的明文 AWS key、`values.yaml.j2` 里硬编码的 Access Key，两处都进了 git 历史）(src: `adhoc_jobs/dynamic_resume_site/content/integration/jenkins_facts.md:142`；`interview-8-k8s-cluster-build.md:254`)。**用同一个组织已经犯过的错来论证一条 TF 纪律，比引用最佳实践有说服力。**

### state 怎么组织（这个子问题会被单独追问）

**结论：目录隔离 + 共享 module，不用 `terraform workspace` 做环境隔离。**

三条理由 `[理论]`：workspace 共享同一个 backend 和同一套凭据（dev 和 prod 的 state 在同一个 bucket、同一个权限域，而真正的环境隔离应该连 AWS 账号都分开）；配置无法差异化（prod 要 3 AZ、dev 要 1 AZ 只能靠 `terraform.workspace == "prod" ? 3 : 1` 这种条件，很快变成条件语句森林）；切错 workspace 没有任何东西提醒你，而目录隔离下路径本身就是提示。

**切分维度按三条，从粗到细**：

1. **环境**（dev / preprod / prod / mgt）：这一条不可协商，因为它是权限和 blast radius 的边界。而且它和我们既有的 `cluster_type` 分类天然对齐（workload / management / dev-staging）(src: `interview-1-k8s_upgrade_reference.md:120-127`)。
2. **生命周期长度**（network / platform / cluster）：网络是年级、平台组件是季度级、集群是月级。混在一个 state 里意味着改集群要 refresh 整个网络，plan 变慢而且 blast radius 被人为放大。
3. **region**（我们有 6 个 region）：天然的故障隔离边界，也天然限制 state 大小。

结构：

```
modules/
  network/  security-groups/  cluster-nodes/   # 共享，带版本
live/
  us-west-2/
    prod/
      network/        # 独立 state：backend key = us-west-2/prod/network
      platform/       # 独立 state
      cluster-a/      # 独立 state
    dev/  ...
  eu-west-1/ ...
```

**为什么要拆这么细**：因为 state 的大小直接决定三件事的成本 `[理论]`：plan 的时长（refresh 要调云 API，几千资源的 plan 可能十几分钟还会撞限流）、锁的争抢（一个大 state 意味着任何人 apply 时所有人都得等）、以及**灾难恢复的可行性**（state 丢了要重新 import，state 越大这条路越不可能走完）。

**backend 配置**：S3 + `encrypt = true` + `kms_key_id` + **`use_lockfile = true`**（TF 1.10 的 S3 原生锁，DynamoDB 锁表已弃用）+ **bucket 开版本控制**（这是 state 损坏时唯一的救命绳）`(src: web 2026-07)`。

### 怎么和现有 Ansible 分工

**交接线画在 Layer 1 和 Layer 0/2/3 之间** (src: `interview-8-k8s-cluster-build.md:47`)：

| 层 | 归谁 | 理由 |
|---|---|---|
| Layer 0 机器镜像 | **Packer**（不变） | 不可变工件的构建，TF 不该碰 |
| Layer 1 AWS 资源 | **Terraform**（接管） | 需要 plan / drift / 依赖图 / destroy 顺序 |
| Layer 2 K8s 控制面 | **Ansible + kubeadm**（不变） | 期望状态不是云 API 能表达的；需要在机器内部执行 |
| Layer 3 集群内组件 | **K8s 自己 + Helm/Ansible**（不变） | 已经有一个持续 reconcile 的 controller 在管了 |

**交接面的具体实现**（这是最容易做烂的地方，要给出方案而不只是原则）：
- TF 的输出**不要**靠人肉复制。三种可接受的形态：写进 SSM Parameter Store（Ansible 用 `aws_ssm` lookup 读）、打成资源 tag（Ansible 的动态 inventory 按 tag 发现）、或者 Ansible 直接用 `amazon.aws.aws_ec2` 动态 inventory 插件查云 API。
- **优先选「Ansible 直接查云 API」而不是「TF 传值给 Ansible」**。理由是它消除了一个状态副本：云本身就是真相源，Ansible 去问云，不需要问 TF。这条判断很关键，它同时解决了「NLB DNS 怎么传给 kubeadm 配置」这个我们现在靠 `sed -i` 解决的问题 (src: `interview-8-k8s-cluster-build.md:45`)。改成 Ansible 按 tag 查 NLB 的 DNS，比在两个工具之间传字符串更干净。
- **绝不用 TF 的 `provisioner "remote-exec"` 跑 Ansible** `[理论]`：它不幂等、失败会把资源标 tainted、且不出现在 plan 里。正确形态是 TF apply 完成后由流水线的下一个 stage 跑 Ansible。

### blast radius 怎么控（六条，从强到弱）

1. **state 切分本身就是最强的 blast radius 控制**：一个 state 里的资源就是一次 apply 的最大影响面。这和我在 K8s 升级里的 `serial: 1` 是同一个思想，**blast radius 是设计输入而不是执行结果** (src: `p_k8s_upgrade.md:64`)。
2. **`prevent_destroy`** 给不可逆资源上保险栓 `[理论]`。
3. **CI 对 plan 做策略检查**：含 destroy/replace 的 plan 需要额外审批。
4. **环境和 region 分账号 / 分权限**：让 prod 的凭据在 dev 的流水线里根本不存在。
5. **`create_before_destroy`** 用于必须替换的资源（配 `name_prefix` 避免名字冲突）`[理论]`。
6. **不用 `-target`**。用它是模块边界划错了的信号，而且它会让 state 处于「部分 apply」的不一致状态。应急可以用，但每次用完要开一个修边界的 issue。

### review 流程怎么设计

- PR 必须带 **plan 输出**（CI 自动贴到 PR comment）。review 的对象是 plan 不是 HCL。**这是整个 TF 治理里最重要的一条文化规则**，因为 HCL 看起来对不代表 plan 是对的。
- **零变更是 import PR 的唯一通过标准**（见阶段 2）。
- **destroy / replace 需要第二个 reviewer**，且 PR 描述里必须写清「为什么这个资源可以被替换 / 它有没有状态」。
- prod 的 apply 保留**人工审批闸门**。这一条我不是照抄最佳实践，我有自己的论证：对低频且爆炸半径大的操作，一道有意保留的人工闸门往往是更可靠的那个组件；我为之辩护的排序是「可运行、可观测、可恢复」在前，配得上的部分再自动化，也就是高频可逆的自动化、低频不可逆的设闸 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_jenkins.md:62, 120`)。
- **定期跑 drift 检测**（每天 plan 一次，有 diff 就开 issue）。这一条是我从 BKC 项目学到的最有价值的一条：**audit 独立于 update 就有独立价值**，即便你什么都不自动修，持续产出 compliance 和 drift 时间戳本身就点亮了静默降级这个盲区 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_bkc.md:185`)。TF 的每日 plan 就是云资源层的这个东西。

### 一句话收尾（面试里说出来）

> 「这个方案的核心不是 Terraform 的技术细节，是三条判断：新工具应该落在『现在没人管』的地方而不是『管得不好』的地方；双写是唯一不可接受的中间态，所以 import 和关掉 Ansible 那一半必须是同一个原子操作；以及 state 的切分就是 blast radius 的切分，所以它必须在写第一行 HCL 之前定死。这三条我不是从 TF 文档里学的，是从做 50 集群跨版本升级里学的。」

---

## 3. 「Terraform 的坑你知道哪些？」的答法

**策略**：每个坑都用「TF 的机制 → 我在 Ansible/K8s 侧的同构经验」两段式讲。这样每个答案都自带可信度，因为它不是背的，是迁移过来的。

### 坑 1：state 是唯一真相源，而它可以和现实脱节

`[理论]` 机制：**云上的资源不携带「我属于哪个 TF 配置块」这个信息，只有 state 知道这个映射**。所以 state 丢了不等于资源丢了，但等于 TF 失忆，下一次 apply 会试图重新创建一切。两个人同时写 state 会互相覆盖，导致部分资源脱管。

**我的同构经验**：我在 K8s 升级里踩过完全同形的坑，而且它改变了我的设计。我的 `state.yaml` 记录每步 completed / in_progress / pending，但我很快发现**它只告诉你哪步失败了，不告诉你集群的真实状态**；步骤完整失败可以直接重跑，执行到一半就必须回到集群实测（镜像版本 × health 四象限）才能判断 (src: `interview-1-k8s_upgrade_reference.md:55-56, 69-76`)。

所以我对 TF state 的第一直觉不是「怎么保护它」，是「**它是缓存而不是真相，真相在云上**」。这个视角直接给出正确的纪律：refresh 是必须的、drift 检测是必须的、任何直接改 state 的操作之前先 `terraform state pull` 存一份、以及 bucket 必须开版本控制。

### 坑 2：`terraform apply` 中途失败不是全有或全无

`[理论]` 机制：TF 按依赖图并发执行（默认 parallelism 10），每完成一个资源就写 state。所以 apply 失败时 state 是**部分更新**的，云上也是部分改变的。TF **没有回滚**。「回滚」的真实含义是「把配置改回上一个 commit 再 apply」，而这在有不可逆动作时不等价于恢复。

**我的同构经验**：这和 etcd snapshot 的边界完全同形。我在 K8s 升级里给自己写的第一条硬结论是「**snapshot 恢复的是数据，不是二进制**」，所以控制面回滚是两个动作的组合，而不是一个按钮 (src: `interview-1-k8s_upgrade_reference.md:32`；`p_k8s_upgrade.md:55`)。由此我的真实策略排序是：**靠门禁不进入坏状态 > 前滚修复 > 回滚**，回滚是最后手段而不是安全网。

搬到 TF：正确的反应不是找回滚方案，是（a）把 plan 门禁做严（plan 保存后 apply、含 destroy 就要额外审批），（b）apply 失败后的标准动作是「再 plan 一次看现在差什么」而不是「回滚」，（c）用 state 切分把「部分失败」的影响面限制在一个小 state 内。

### 坑 3：`count` 的索引不稳定，一次删除引发连环重建

`[理论]` 机制：`count` 的资源地址是索引（`web[0]`、`web[1]`），从 list 中间删一个元素会让后面所有索引前移，TF 于是认为多个资源的内容都变了，一次删除引发一连串 destroy/create。`for_each` 的地址是键，稳定。修正历史遗留的 `count` → `for_each` 正是 `moved` block 的典型用例（TF 1.1）`(src: web 2026-07)`。

**我的同构经验**：这就是「身份 vs 位置」的问题，我在生产上见过它的另一个形态并且修过。一个 OLAP 引擎的 frontend 陷入 CrashLoopBackOff 重启 285 次，根因是内部元数据库用**旧 Pod IP** 注册了节点，重启后 IP 变了，节点角色停在 UNKNOWN、查询端口不开、liveness probe 每 60 秒杀一次；永久修复是 headless Service 加 FQDN 注册，**让身份不随 IP 漂移** (src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md:38`)。

一般化成一条我能随时复用的原则：**任何需要长期稳定的引用，都不能用「位置」（索引、IP、序号）当身份，必须用「名字」（键、FQDN、稳定 ID）。** TF 的 `for_each` vs `count` 就是这条原则在 IaC 里的实例。

### 坑 4：`ignore_changes` 是放弃管理，不是「不检测」

`[理论]` 机制：`ignore_changes` 让 TF 不再把该字段纳入 diff，也就是**这个字段的真相源不再是 TF**。它有正当用途（被 autoscaler 改的 `desired_capacity`、外部系统打的 tag），但滥用会让配置慢慢变成小说：文件里写着 A，现实是 B，而 plan 是干净的。

**我的同构经验**：这正是我在 50 集群 drift 管理里做的取舍，而且我有一条自己的护栏。我用 per-cluster feature flag 表达残余例外（`drain_timeout_seconds: 600` 覆盖默认 300），但配了一条规则：**override 字段越少集群越标准；flag 数量增长本身被当作分类失准的信号，应该新增一个 cluster_type 而不是继续加 flag** (src: `interview-1-k8s_upgrade_reference.md:136-139`)。

搬到 TF：每个 `ignore_changes` 必须带注释说明「谁是这个字段的真相源」，并且**统计它的数量当成健康指标**。数量上升说明抽象错了，不是说明配置灵活。

### 坑 5：大 state 让 plan 变慢，慢到没人愿意跑

`[理论]` 机制：`plan` 默认 refresh 全部资源，每个资源至少一次云 API 调用。几千资源的 state 可能要十几分钟，还会撞云 API 限流。`-refresh=false` 能跳过但会基于陈旧数据做决策，`-target` 是应急且会造成部分 apply。

**我的同构经验**：这是一个我很熟悉的失效模式：**验证成本太高会导致验证被跳过，而不是导致验证变慢**。我在 CI/CD 侧有一手证据：我那段时间有 91 个 Debug/test commit，因为当时没有 pipeline 的本地验证手段，只能靠生产 Jenkins push-and-run 反复试 (src: `jenkins_facts.md:68, 132`)。反馈慢的直接后果不是「大家耐心等」，是「大家绕过它」。

搬到 TF：plan 的时长是一个必须监控的指标，它变慢就是 state 该拆了。这也是我把「按生命周期长度切 state」放进方案的原因之一，不只是为了 blast radius。

### 坑 6：secret 进 state

`[理论]` 机制：TF 原样存储资源属性，包括 RDS 密码、私钥、secret 版本的值。`sensitive = true` **只影响 CLI 输出的显示，不影响 state 里的存储**。缓解：backend 加密 + 严格权限、ephemeral values（TF 1.10）/ write-only arguments（TF 1.11）、或让 TF 只管 secret 的引用不管值。OpenTofu 从 1.7 起有原生的 **state 加密**（AES-GCM，可插拔 key provider），这是它相对 Terraform OSS 的一个实质优势 `(src: web 2026-07)`。

**我的同构经验**：这个坑我们组织已经用另一种形态踩过两次，都是明文凭据进 git 历史：`jenkins.yaml` 里的明文 AWS AccessKey + SecretKey (src: `jenkins_facts.md:142`)，以及 `roles/cilium/templates/values.yaml.j2` 里硬编码的 AWS Access Key/Secret (src: `interview-8-k8s-cluster-build.md:254`)。修复路径都是三步：IAM rotate/disable 该 key、改用 IRSA 或 instance profile、`git filter-repo`/BFG 清历史。

结论：**任何会持久化的东西都要假设它会泄露**，git 是，state 也是。所以我的纪律是让 secret 从来不进入这些系统，而不是加密之后放进去（加密是第二道防线，不是第一道）。

### 坑 7：`provisioner` 与「用 TF 做配置管理」

`[理论]` 机制：`provisioner "remote-exec"` 不幂等、失败会把资源标 tainted（下次 apply 会销毁重建）、且不出现在 plan 里。官方自己把 provisioner 列为最后手段。

**我的同构经验**：这就是我们 codebase 最大技术债的镜像。我们 Ansible 里大量 role 直接 `shell` 调 `helm upgrade --install` / `kubectl apply` 兜底，结果是不真正幂等、`--check` 失效、错误埋在 shell 输出里 (src: `interview-8-k8s-cluster-build.md:74`)。**两边是同一个病：在一个声明式工具里开一个命令式后门，然后就失去了那个工具的全部保证。** 所以我对 TF provisioner 的态度和对 Ansible `shell` 的态度完全一致：能用就说明抽象选错了，用了就必须承认这一段没有 dry-run 也没有幂等。

### 坑 8：`plan` 干净不等于 apply 会成功

`[理论]` 机制三类：plan 与 apply 之间世界变了（所以要 `plan -out` 保存计划）；依赖图里看不到的顺序依赖（IAM policy 生效延迟、DNS 传播这类最终一致性，需要显式 `depends_on` 或重试）；provider 的 diff 逻辑与云的实际行为不一致（perpetual diff / computed 字段）。

**我的同构经验**：这就是「dry-run 会骗人」，我有直接实证：Ansible 用 `shell` 兜底的地方 `--check` 完全失效 (src: `interview-8-k8s-cluster-build.md:74`)。所以我对任何 dry-run 的态度是：**dry-run 的可信度等于最不可信的那一步的可信度**，要显式知道哪些步骤是 dry-run 覆盖不到的。在 TF 里那些步骤是：provisioner、`null_resource` 加 local-exec、以及依赖最终一致性的资源。

---

## 4. 面试前的最小自学实验清单

> 目标不是「学会 TF」，是**能在面试里说出「我上周自己做过这个实验，观察到 X」**。一个亲手做过的小实验的可信度远高于十页笔记。
> 全部可以在个人 AWS 账号里用免费或近免费资源做（VPC、SG、S3、IAM 都免费；ASG 用 t4g.nano 或 `desired_capacity = 0`）。

### 实验 1（必做，2 小时）：state 的生死实验

这是最高价值的一个，因为它直接对应我要讲的「state 是缓存不是真相」。

1. `terraform init` 用 S3 backend（`encrypt = true` + `use_lockfile = true`，bucket 开版本控制）建一个 VPC + 2 个 subnet + 1 个 SG。
2. **看一眼 state 文件的实际内容**：`terraform state pull | jq`。找到 `lineage`、`serial`、resource 的 `dependencies` 数组。这三个字段能讲出来就说明真读过 state。
3. **破坏它**：`terraform state rm aws_security_group.x`，然后 `plan`，观察 TF 想创建一个已经存在的 SG。
4. **救回来**：写一个 `import` block（不是 `terraform import` 命令），跑 `plan -generate-config-out=gen.tf`，看它生成什么，然后**把 plan 调到零变更**再 apply。记录「零变更」花了几轮、哪几个字段一开始不一致。**这一段的观察就是我在面试里要讲的具体细节。**
5. **更狠一点**：手工在控制台删掉 state 文件（或者上传一个空的），然后从 bucket 版本历史里恢复。记录恢复的具体步骤。
6. **锁实验**：开两个终端同时 `apply`，观察第二个报 `Error acquiring the state lock`，记下 LOCK_ID 的样子；然后 `force-unlock`。

**要带走的可讲细节**：state 里的 `dependencies` 字段长什么样、import 到零变更花了几轮、锁报错的具体形态。

### 实验 2（必做，1 小时）：`count` vs `for_each` 的连环重建

1. 用 `count` 建 3 个 SG（名字来自一个 list）。
2. 删掉 list 的**中间**那个元素，`plan`，**数一下有几个 destroy/create**。
3. 用 `for_each` 重做同一件事，删中间元素，`plan`，对比。
4. 加分项：用 `moved` block 把 `count` 版本迁移到 `for_each` 版本，观察 plan 变成纯 state 操作、零资源变更。

**要带走的可讲细节**：具体的重建数量（例如「删中间一个引发 2 个 replace」），以及 `moved` block 让它变成零变更。

### 实验 3（建议，1.5 小时）：lifecycle 与不可逆保护

1. 给一个资源加 `prevent_destroy = true`，试 `destroy`，看报错。
2. 给一个 ASG 加 `ignore_changes = [desired_capacity]`，手工在控制台改容量，`plan` 观察它不再想改回去；然后去掉 `ignore_changes` 再 plan，对比。
3. 建一个带 `name` 的 SG，改一个 force-new 的属性触发 replace，观察名字冲突导致失败；改成 `name_prefix` + `create_before_destroy = true` 再试。

**要带走的可讲细节**：`create_before_destroy` 必须配 `name_prefix` 这个具体约束，这是「读文档」和「做过」的分界线。

### 实验 4（建议，1 小时）：VPC + ASG，对着我的真实场景做

用 TF 建 VPC + 2 个 subnet（跨 AZ）+ SG + Launch Template + ASG（`desired_capacity = 0` 省钱）。这个实验的价值是它**正好是我方案里阶段 1 要 TF 管的那一层**，做完之后我讲阶段 1 就不是纸上设计。

顺手验证一件事：在 SG 里显式放行 **IP protocol 4（IPIP）**，看 TF 的 `ingress` block 怎么表达非 TCP/UDP 协议。这个细节对应我一手的 Calico IPIP 坑 (src: `interview-8-k8s-cluster-build.md:197`)，能连起来讲会很亮。

### 实验 5（可选，30 分钟）：module 与版本约束

把实验 4 抽成一个 module，从 `live/dev/` 和 `live/prod/` 两个目录用不同参数各 apply 一次，观察两个独立 state。验证「目录隔离」是什么手感，以及为什么它比 workspace 好。

### 实验 6（可选，30 分钟）：TF 与 Ansible 交接

TF 建资源并打 tag，然后用 `amazon.aws.aws_ec2` 动态 inventory 让 Ansible 按 tag 发现它。这个实验验证的是我方案里那条判断：**让 Ansible 直接查云 API 而不是从 TF 传值**，因为它消除了一个状态副本。

### 读的部分（不动手也要过一遍）

- `terraform plan` 的输出符号：`+` create、`-` destroy、`~` update in-place、`-/+` destroy then create、`+/-` create then destroy（`create_before_destroy`）。**看到 `-/+` 要条件反射地警觉**，这是面试里最实用的一个反应。
- Q33 那一节的生态事实（OpenTofu / IBM / 版本线 / Stacks / Crossplane 毕业 / CDKTF 归档），能说出年份和版本号。
- 至少扫一遍 AWS provider 里 `aws_security_group` 和 `aws_autoscaling_group` 的文档，感受一下「provider 文档的信息密度」和「哪些字段是 computed」。

---

## 5. 三个必背的口径（原话级别）

**问「你们用 TF 吗」**：
> "We don't. Our IaC is Ansible-centric. Packer for machine images, Ansible for both AWS resources and machine configuration, kubeadm for the control plane. That combination made sense for us: a small number of long-lived clusters, plus we ship onsite deployments, so one codebase has to build both on AWS and in a customer data center. But I'm very clear about what it costs us: no state file means no plan preview, no drift detection, no safe destroy, and no concurrency lock. Ansible judges idempotency per-module by querying the AWS API, so it never has a global view. Those four gaps are exactly what Terraform exists to provide, so my position is that the moment the cluster count grows or we need PR-based review with drift detection, the right shape is Terraform owning the AWS resource layer and Ansible owning image, control plane, and in-cluster components."

**问「你没用过 TF，我怎么知道你能上手」**：
> "Fair question. I'd point at the shape of what I've done rather than the tool. I built an upgrade system for 50 self-managed clusters whose entire job was making a high-risk change reviewable: an explicit health baseline, a real dry-run producing a diff, a quantified blast radius, and an evidence chain. That is functionally what `plan` plus remote state plus a review flow gives you. I had to build it by hand because Ansible doesn't give it to me. So Terraform isn't a new mental model for me, it's a better-engineered version of one I already had to implement. What I'd need to learn is its specific conventions: state layout, import semantics, the `count` versus `for_each` addressing trap, lifecycle meta-arguments. I've been working through those hands-on. For example, I deliberately corrupted a state file and imported the resource back to see exactly what 'zero-change plan' takes."

**问「如果让你引入 TF」**（30 秒开头，之后按第 2 节展开）：
> "I wouldn't start by importing what we already have. I'd start with the layer nobody currently manages with any tooling at all. Our VPCs, subnets, NAT gateways and IAM roles are hand-built outside the repo. That's pure greenfield, so Terraform proves itself with zero risk of double-writing, and it happens to be the layer with the longest lifecycle and the largest blast radius, which is where a reviewable plan is worth the most. Then I'd import the existing resources one blast-radius domain at a time, and the hard rule is that importing a resource and disabling the Ansible code path that used to create it are one atomic change. Double-write is the only state I won't accept."

---

## 6. ⚠️ 待确认 / 不许说的清单

- **不许说**「我用过 Terraform」「我们在迁移到 Terraform」「我写过 TF module」。零 evidence。
- **不许说**「我们用 GitOps」。全库没有 ArgoCD/Flux 的一手证据。⚠️ `work-contexts/career/profile/resume-expand.tex:108` 有一句 `IaC (GitOps/Ansible) cluster management`，**建议改掉措辞**，否则被追问「ArgoCD 还是 Flux」会尴尬。如果那句指的是 BKC 的 git-as-source-of-truth，正确措辞是 "git-declared desired state"。
- **不许报** DORA 数字（change failure rate、rollback MTTR）。`interview-5-cicd_reliability.md:91-93` 的简历 bullet 明确标着「待填真实数字」，说明手上没有。被问到就答「我们没有系统性采集，这正是我说 CI/CD 的 metrics 化是缺口的意思」。
- **不许说**镜像签名 / SBOM / SLSA provenance 我们做过。零 evidence，只能作为「我知道的标准做法」。
- ⚠️ **待确认（面试前问自己）**：TF 我是否已经真的动手做过实验？如果没有，第 5 节第二个口径里「I deliberately corrupted a state file and imported the resource back」这句**不能说**。做完实验 1 再说。这是这份文件里唯一一句依赖未来行动的话，标在这里防止自己顺口说出去。
