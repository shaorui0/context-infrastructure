# 04 IaC / Jenkins / Terraform / Packer / K8s 升级

> 四件套：本文件（核心圈三环）· `story_bank.md`（11 个战 story，各带 5 层追问防线）· `fundamentals.md`（39 条 Q&A 基础回顾）· `questions.md`（30 题答题骨架）· `terraform_honest_answer.md`（TF 专项口径，本目录的特殊交付物）
> 这个方向是**混合性质**：K8s 升级和 Jenkins 是厚素材（做整编），Terraform 是明确的外环补课项（做基础回顾 + 一套诚实答法）。

---

## 这个方向我的一句话定位

我把交付路径和基础设施变更当成生产系统来拥有，而不是当成工具链来使用。我的一手能力集中在**高风险变更的工程化**：把只存在于资深工程师脑子里的风险模型，变成显式的门禁、可执行的 dry-run 和可复盘的证据链，然后用它把 50 个自管理 Kubernetes 集群从 1.24 逐 minor 推到 1.29，两套生产 fleet 零客户可感知停机、零回滚，单集群成本从 18-21 小时双人操作降到 6-8 小时单人加系统。同一套纪律我在三个层次上用过：机器镜像层（Packer 的不可变工件与 LT 回滚）、集群层（quorum math、`serial: 1`、20% batch、addon 依赖顺序）、以及交付流水线层（幂等门、失败归因、按 owner 路由的告警）。

工具选型上我的立场很清楚：我们的 IaC 是 Ansible-centric（Packer + Ansible + kubeadm）而不是 Terraform，这个选择在「少量长生命周期集群 + 同时要交付 onsite 环境」的场景下是成立的，但它的代价我算得很清楚：没有 state 文件就没有 plan 预演、没有 drift detection、没有安全 destroy、没有并发锁。那四条缺失恰好就是 Terraform 存在的理由，所以我在 K8s 升级项目里不得不手工造了一个 plan 加证据链。我没有 Terraform 的生产经验，我有的是它要解决的那组问题的一手经验。

---

## 核心圈三环

### 内核（有一手 evidence，能扛住 5 层追问）

| 能力条目 | 一句话说明 | evidence |
|---|---|---|
| **K8s 跨版本升级工程** | 1.24 → 1.29 逐 minor，50 集群 / 6 region / 600+ 节点，两套生产 fleet 零客户可感知停机、零回滚；升级顺序、etcd 备份恢复、控制面时序、worker 滚动、API 废弃、业务层验证每一环都能展开 | `adhoc_jobs/dynamic_resume_site/content/projects/p_k8s_upgrade.md`；`work-contexts/career/interview/interview-1-k8s_upgrade.md` + `_reference.md`；`contexts/fy2026_self_assessment.md:5,19`；`work-contexts/career/profile/resume.tex:91,93` → **S01** |
| **升级自动化工具开发** | 自研 Upgrade Safety System：Python CLI 编排 Ansible + boto3 + kubectl，三段流水线 check → plan → apply + evidence，四类证据落盘、state 可恢复、四个人工签核点；18-21h 双人 → 6-8h 单人 | `interview-1-k8s_upgrade_reference.md:216-286`；`p_k8s_upgrade.md:21-33` → **S02** |
| **staged dry-run + 门禁 + 证据链方法论** | 「升级难的不是知道做什么，是用证据证明现在可以做下一步」；fail 条件写成规则而非临场判断、版本 × 健康四象限、baseline 与外部监控交叉验证、blast radius 是设计输入不是结果 | `interview-1-k8s_upgrade.md:11,23`；`interview-1-k8s_upgrade_reference.md:24-30,69-76,171-175`；`p_k8s_upgrade.md:64` → **S01/S02** |
| **kubeadm 自建生产集群** | 四层叠加（Packer AMI → AWS 资源 → kubeadm 控制面 → 集群内组件）；三 CIDR 规划、NLB(L4) 做控制面 HA 落点、stacked etcd、Calico IPIP vs Cilium ENI 的完整取舍；每个决策能给替代方案与切换条件；AWS 与 onsite 双形态 | `work-contexts/career/interview/interview-8-k8s-cluster-build.md`（全篇，结论到 `file:line`）→ **S03** |
| **Packer + Ansible 镜像与配置管理** | 分层判据是变更频率：Packer 固化慢且稳定（装包），Ansible 做快且多变（配集群）；worker 走不可变替换（AMI → LT → Instance Refresh 20% batch），回滚路径就是日常 oncall 路径 | `interview-8-k8s-cluster-build.md:16,51`；`interview-1-k8s_upgrade.md:69`；`adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md:56` → **S03/S07** |
| **Jenkins 作为生产系统的三判据** | 幂等可重入 / 状态可观测可诊断 / 配置即代码；含「自动化本身成为熵源」的反论（workaround stage 变死代码这个干净标本）与「高频可逆自动化、低频不可逆设闸」的排序论 | `adhoc_jobs/dynamic_resume_site/content/projects/p_jenkins.md`（全篇）→ **S05** |
| **Jenkins 跨集群迁移与稳定化** | 三类根因（外部 Maven 仓库失联 + `.m2` 未迁移 + `.lastUpdated` 阻止重试 / Debian Buster EOL / Arcanist 与 PHP 8 不兼容），修复脚本形状 guard → 备份 → 收敛 → verify，fix 配对只读 diagnose，根因修完删掉前人 workaround | `adhoc_jobs/dynamic_resume_site/content/integration/jenkins_facts.md:34-43`；`p_jenkins.md:32-38,92-96,118` → **S04** |
| **CI/CD 流水线设计（nightly 编排器）** | 859 行 production-build，跨 4 生产分支 × 3 类服务；cron 参数持久化、下游状态收集与 partial results 落盘、失败归因 + 按服务路由到 oncall、FORCE_BUILD 幂等门贯穿全链；共享 pipeline 库第一贡献者 306 commits | `jenkins_facts.md:6,17-30,110-125` → **S05** |
| **幂等性与 fail-closed 的一手方法论** | 幂等三层（形状 / 判定权的位置 / 幂等≠可重入这个我算错过的地方）；自动化路径卫生五原则（推导 root、preflight、写路径一律 fail closed、日志可审计） | `jenkins_facts.md:110-116`；`interview-1-k8s_upgrade_reference.md:154-157`；`rules/skills/bestpractice_automation_path_hygiene.md` → **S11/S05/S02** |

**内核 9 条。**

### 中环（做过但浅，或归属需要限定；要有标准口径，不许当内核讲）

| 能力条目 | 标准口径（被追问时按这个说） | evidence / 边界依据 |
|---|---|---|
| **Helm** | 「我写过 chart（dcluster 的 starrocks-cn chart，含 values / configmap / deployment），也处理过 chart 引起的生产事故（helm upgrade 重建 ValidatingWebhookConfiguration 丢了 caBundle，全集群带 Ingress 的 install 全挂）。我的 helm 定位是：它是模板渲染加 release 记账工具，不是 reconcile 控制器，把它当控制器用就会踩那种坑。**我没有做过大规模 chart 库治理**（library chart、umbrella chart 的依赖策略、chart 的测试与发布流水线），那部分我只有理论。」 | chart 作者：`rules/skills/workflow_dcluster_starrocks_cn_deployment.md`「关键路径」表；事故：`oncall_track_record.md:20`；技术债：`interview-8-k8s-cluster-build.md:74` → **S08** |
| **GitOps / ArgoCD / Flux** | 「**没有生产经验。** 我们是 Jenkins 加人工审批的形态。我对『命令式 vs 声明式 reconcile』有一手论点，因为我恰好是在命令式框架里手工补幂等的那个人，但我没有跑过 ArgoCD 的生产环境。」 ⚠️ **`resume-expand.tex:108` 出现过 `IaC (GitOps/Ansible)` 这个措辞，建议改掉**，否则被追问「ArgoCD 还是 Flux」会尴尬；如果那句指的是 BKC 的 git-as-source-of-truth，正确措辞是 "git-declared desired state"。 | 全库搜不到 ArgoCD/Flux 的一手证据；唯一提及是 `interview-3-monitoring_reference.md:140`（Grafana annotation 的 webhook 举例）与 `resume-expand.tex:108` |
| **Intel BKC IaC（真实性边界最严）** | **只能声称**：Intel 5G 云化背景下的硬件层配置管理是我的；构建并运行了 systemd 层的自研 machine-level controller（约 30 台裸金属、多 cluster）；**审计与监控这一半**（持续巡检 + compliance + drift 时间戳，采集面 Redfish/BMC、`/proc/cmdline`、sysctl/tuned、ethtool/devlink）；范围刻意不做 K8s Operator。**只能用设计口径**：完整的风险分级 reconcile（🟢🟡🟠🔴）、pull 架构与只读 aggregator、reboot token 限流、跨重启状态机、签名 profile。SKU 一律用代际说法。 | `adhoc_jobs/dynamic_resume_site/content/projects/p_bkc.md:209-238`（SOURCES 的真实性分栏是硬约束）→ **S09** |
| **K8s addon 运维** | 「CCM / Calico / Cluster Autoscaler 三件套我能讲影响窗口、最坏情况、版本矩阵约束（CCM 必须匹配 K8s minor、CA 必须 >= K8s 版本）和各自的验证 gate。**我的 gate 都是验『组件自己还活着』**，caBundle 那次事故让我看到缺一类『功能性 synthetic 验证』的 gate。」 | `interview-1-k8s_upgrade.md:74-78`；`interview-1-k8s_upgrade_reference.md:185-200` → **S08 的 L5** |
| **Ansible 深度** | 「这套 58 role 的 `install-k8s` repo 是团队既有资产，**我不是原作者**。我能声称的是：我基于真实代码做过系统性审计（结论到 `file:line`，含三条待修技术债）、我能对每个设计决策给出替代方案与切换条件、我在升级项目里在这个体系上加了升级编排。」 | `interview-8-k8s-cluster-build.md` 全篇；⚠️ 待确认：`[ONCALL-20941] K8S support 1.32` 那条 commit 是否是我的（`:68`），不确认不许说 |
| **部署验证与 E2E checklist** | 「我把『改代码到确认生产行为正确』写成了一份 11 个断言的可执行 checklist，覆盖正常路径、输入校验负例、资源与配置的实际落地、以及幂等语义（重复 terminate 应返回明确的已完成状态而不是报错）。**它目前是手工执行的 skill，不是 CI 里跑的自动化测试套件。**」 | `rules/skills/workflow_dcluster_starrocks_cn_deployment.md` → **S10** |
| **CI/CD 的 DORA 框架** | 「框架我熟：部署频率 / lead time / change failure rate / MTTR，以及旁路使用率作为反向健康指标。但**我报不出我们的真实数字，因为我们没有系统性采集**。这正是我说 CI/CD 的 metrics 化是我们的缺口的意思。我做到的是事件通知层，没做到 metrics 化。」 | `work-contexts/career/interview/interview-5-cicd_reliability.md:72,91-93`（简历 bullet 明确标「待填真实数字」）；`jenkins_facts.md:127` → **C5 陷阱题** |
| **凭据与 secret 治理** | 「我能讲清失效形态和修复路径（IAM rotate/disable → 改 IRSA 或 instance profile → `git filter-repo`/BFG 清历史），而且我有两个真实的反面实证在自己的 repo 里。**修复路径是我列出来的，不等于都由我落地了。**」 | `jenkins_facts.md:142`（`jenkins.yaml` 明文 AWS key）；`interview-8-k8s-cluster-build.md:254`（cilium values 硬编码 key） |

**中环 8 条。**

### 外环（纯知识，需要补课；不许因为写了 fundamentals 就往里挪）

| 能力条目 | 补课状态 | 对应材料 |
|---|---|---|
| **Terraform（最重要的外环项）** | 零生产经验。已完成系统性基础回顾（工作流语义 / state 四职责 / remote backend 与 S3 原生锁 / import-moved-removed 三个 block / resource vs data / module 与版本约束 / count vs for_each / lifecycle / workspace vs 目录 / 与 Ansible 的边界 / 八类生产问题 / vs CFN vs CDK）+ 一套完整的引入方案 + 六个动手实验清单。**动手实验尚未执行。** | `fundamentals.md` Q21-Q33；**`terraform_honest_answer.md` 全篇**（本目录特殊交付物） |
| **Terraform 生态现状（2026）** | 已调研：BUSL 与 OpenTofu（2025-04 进 CNCF Sandbox，至今仍在 Sandbox；独有 state 加密 / early variable evaluation / `.tofu` 覆盖）、IBM 2025-02-27 完成收购并于 2025-09-01 改名、免费层 2026-03-31 EOL 与 RUM 计费、TF 1.15.x 版本线、Stacks 在 1.13 GA、S3 原生锁在 1.10、CDKTF 于 2025-12-10 归档 | `fundamentals.md` Q33 |
| **GitOps 工具链（ArgoCD / Flux）** | 零经验。需要补：ApplicationSet、sync wave 与 hook、drift 的自动 vs 手动 sync、多集群管理形态、以及「pull-based CD 与 push-based pipeline 的失效模式差异」 | 尚无材料，⚠️ 补课缺口 |
| **Crossplane / Pulumi** | 只有理论。Crossplane 2025-10-28 从 CNCF 毕业（与 K8s/Prometheus 同级），方向上我认为它更对，把 IaC 从「plan/apply 的一次性动作」变成「持续收敛的控制循环」，这和我在 BKC 做的事同构。Pulumi 是强势第二（用真实编程语言）。 | `fundamentals.md` Q33 |
| **Kustomize 深度** | 只会基础用法。需要补：overlay 组织策略、`patchesStrategicMerge` vs JSON patch、component、以及 Kustomize vs Helm 的判据（模板渲染 vs 结构化覆盖） | 尚无材料，⚠️ 补课缺口 |
| **供应链安全（签名 / SBOM / provenance）** | 只有框架，零实践证据。需要补：cosign 签名与 admission 层验签、SBOM（SPDX/CycloneDX）的生成与消费、SLSA provenance 与 attestation、依赖混淆与 typosquatting 的防护 | `fundamentals.md` Q39（四层框架 + 我手上的三个反面实证） |
| **JCasC / Jenkins controller 即代码** | 只有判据没有实践（我们 repo 里的 `jenkins.yaml` 是 agent pod spec 快照，不是 JCasC） | `fundamentals.md` Q38；`p_jenkins.md:145` |
| **policy-as-code（OPA / Sentinel / Conftest）** | 只有理论。2026 年的新话题是 AI 生成的 IaC 让 review 跟不上变更速度，推动策略检查更早进 CI。这是一个可以主动抛出去显示我在看趋势的点 | `fundamentals.md` Q33；`terraform_honest_answer.md` §2 阶段 3 |

**外环 8 条。**

---

## 本方向 3 个最强 headline

**1. 「我把一个只存在于资深工程师脑子里的升级仪式，变成了任何人都能操作的证据链。」**
50 个自管理集群、1.24 逐 minor 到 1.29、6 region、600+ 节点，两套生产 fleet 零客户可感知停机、零回滚，单集群 18-21 小时双人 pair 降到 6-8 小时单人加系统。而真正的产出不是那个工具：checklist 与 evidence 模式在项目结束后外溢成了日常 infra health check。这也是我 FY2026 自评里的最大成就，公司内部口径一致。
（src: `p_k8s_upgrade.md`；`interview-1-k8s_upgrade.md:98-101`；`contexts/fy2026_self_assessment.md:19`；`resume.tex:91,93`）

**2. 「『熟悉 Jenkins』应该读作『能把一条交付流水线当生产系统来拥有』：它的故障模式、它的状态、它的恢复路径，不是它的语法。」**
三判据（幂等可重入 / 状态可观测可诊断 / 配置即代码）加实物：一次跨 K8s 集群迁移的三类根因定位与修复（外部仓库失联 + 缓存未迁移 + `.lastUpdated` 阻止重试的完整故障链）、859 行的 nightly 生产镜像编排器（参数持久化、失败归因、oncall 路由、幂等门贯穿全链）、以及一个反论：**自动化本身会成为熵源**，workaround stage 变成死代码就是干净的标本，所以我为之辩护的排序是「可运行、可观测、可恢复」在前，高频可逆的自动化、低频不可逆的设闸。
（src: `p_jenkins.md`；`jenkins_facts.md:6,17-43`）

**3. 「reconcile 与 target 无关：一份文档一旦让 desired state 变得声明式、机器可执行、被持续 enforce，它就成了一个 control loop，target 可以是容器，也可以是一个 NIC 固件版本。」**
在 Intel，我把 5G vRAN 的 Best Known Configuration 从一份 doc 里的 prose 加复制粘贴 shell，变成 git 里声明式、被持续审计的 desired state，形态是每台机器一个 systemd 层的 daemon，覆盖约 30 台裸金属；起点是连 Ansible 这一级都没有。我认领的是**审计与监控这一半**（持续巡检、compliance、drift 时间戳），完整的风险分级修复模型我作为设计口径讲。这个 headline 的价值是它解释了我为什么能在 IaC 上有判断力却不依赖某个具体工具：**我实现过一个 target 是 BIOS 和固件的 reconciler**，Terraform 是同一思想在云 API 上的实例。
（src: `p_bkc.md:107,120,187,215-226`；真实性边界见 `p_bkc.md:209-238`，**这一条讲的时候必须自己先划边界**）

---

## Terraform 被问到时的诚实答法（摘要，完整版见 `terraform_honest_answer.md`）

### 三条心态铁律

1. **绝不说「我用过 Terraform」，也绝不说「我不懂 Terraform」。** 正确定位是：「我们的 IaC 是 Ansible-centric，我很清楚它换来了什么、代价是什么，而那个代价恰好就是 Terraform 存在的理由。」这句话本身就是懂 TF 的证明。
2. **不为「没用 TF」道歉，也不辩解成「TF 不好」。** 这个选择在我们的场景下有成立的理由，同时它有明确的失效条件，两边我都能讲。既不防御也不谄媚。
3. **主动把话题引向我的强项**：幂等、drift、blast radius、状态的真相源。这四个概念在 TF 里叫 idempotency、drift detection、blast radius、state，而我在 Ansible / K8s 侧对每一个都有一手洞察。

### 30 秒直接答法

> 「不用。我们的 IaC 是 Ansible-centric：Packer 做机器镜像、Ansible 建 AWS 资源并配置机器、kubeadm 起控制面。这个组合在我们的场景下是有原因的，因为我们的集群是少量长生命周期的资产，而且我们同时要交付 onsite 环境，一套代码得能装云上也能装客户机房。代价我很清楚：**没有 state 文件，所以没有 plan 预演、没有 drift detection、没有安全的 destroy、没有并发锁**。Ansible 靠每个 module 自己查 AWS API 判断幂等，缺全局视图。这四条缺失恰好就是 Terraform 的核心价值，所以我的结论是：集群数量继续涨、或者要 PR-based review 加 drift detection 的时候，正确形态是 Terraform 管 AWS 资源那一层、Ansible 管镜像和集群内部那三层。」

（src: `interview-8-k8s-cluster-build.md:40,44-47,206`）

### 「如果让你引入 TF」的四阶段方案（这道题是主战场）

| 阶段 | 做什么 | 关键判断 |
|---|---|---|
| **0 只读功课** | 画「谁是真相源」的现状地图、定 state 切分、定 review 流程 | 这三件事必须在写第一行 HCL 之前定死，因为 state 切分最难改 |
| **1 绿地先行** | 用 TF 管**新建的** VPC / Subnet / NAT / IAM / SG | **引入新工具的最佳落点是「现在没有任何工具管」的地方，不是「管得不好」的地方**。我们这一层现在是手工预建的，所以 TF 进来是纯增量、零双写风险，而且它生命周期最长、blast radius 最大，plan 的评审价值最高 |
| **2 import 存量** | 用 `import` **block**（config-driven，可 review）而不是命令式 `terraform import`；`plan` 零变更是唯一通过标准；**import 与关掉对应 Ansible 代码路径是同一个原子操作** | **双写是唯一不可接受的中间态。** 我们的 Ansible 本来就是开关驱动的（`auto_create_*`），这些开关是天然的交接点。顺序按 blast radius 从小到大。明确不 import Layer 2/3 |
| **3 治理与 drift** | CI plan、人工审批 apply、`plan -out` 保证所见即所执行、对 plan 做策略检查（含 destroy 要额外审批）、`prevent_destroy`、lock 文件进 git、secret 不进 state、**每日 drift 检测** | 每日 drift 那条来自 BKC 项目最有价值的一条结论：**audit 独立于 update 就有独立价值** |

**收尾一句**（面试里说出来）：「这个方案的核心不是 Terraform 的技术细节，是三条判断：新工具落在没人管的地方、双写是唯一不可接受的中间态、state 的切分就是 blast radius 的切分。这三条我不是从 TF 文档里学的，是从做 50 集群跨版本升级里学的。」

### 「TF 的坑你知道哪些」的答法：八个坑，每个都用同构经验背书

| TF 的坑 | 我的同构经验 |
|---|---|
| state 是缓存不是真相 | K8s 升级的 `state.yaml` 只说哪步失败，判定要回到集群实测（镜像版本 × health） |
| apply 中途失败非原子，TF 没有回滚 | etcd snapshot 恢复数据不恢复二进制 → 真实策略是「门禁 > 前滚 > 回滚」 |
| `count` 索引不稳定引发连环重建 | 「身份 vs 位置」：OLAP frontend 用旧 Pod IP 注册导致 285 次 CrashLoop，修复是 headless Service + FQDN |
| `ignore_changes` 是放弃管理 | 50 集群的 feature flag 取舍，护栏是「flag 数量增长本身是分类失准的信号」 |
| 大 state 让 plan 慢到没人跑 | 验证成本太高会导致验证被跳过而不是变慢（我 91 个 Debug commit 的实证） |
| secret 进 state | 我们两次明文凭据进 git 历史的实证 |
| `provisioner` 是声明式工具里的命令式后门 | 我们 Ansible 用 `shell` 调 helm/kubectl 是同一个病 |
| plan 干净不等于 apply 成功 | dry-run 会骗人的实证（`shell` 兜底让 `--check` 完全失效） |

### 面试前必做的最小实验（详见 `terraform_honest_answer.md` §4）

必做两个：**实验 1 state 的生死实验**（S3 backend 建 VPC → 读 state 的 `lineage`/`serial`/`dependencies` → `state rm` 制造脱管 → 用 `import` block 调到零变更 → 从 bucket 版本历史恢复 state → 两个终端同时 apply 观察锁）；**实验 2 `count` vs `for_each`**（删中间元素数一下有几个 destroy/create，再用 `moved` block 迁移）。

⚠️ **在实验做完之前，不许在面试里说「我动手做过」。** 这是 `terraform_honest_answer.md` §6 里唯一一句依赖未来行动的话，标在这里防止自己顺口说出去。

---

## ⚠️ 本方向的口径漂移与待确认清单

**口径漂移（进面试前必须自己定死）**：

- **`18-21h → 3-4h` vs `18-21h → 6-8h`**。`resume.tex:93` 写 3-4h；但 7 月的 `p_k8s_upgrade.md:33` 明确区分「6-8 小时 = 已达成」和「3-4 小时 = 自动化路线图目标，预期降幅 60-80%」。按「冲突以 7 月为准」的规则，**口述必须说 6-8h，3-4h 讲成 roadmap**。风险：按简历字面说 3-4h，被追问「那 3-4 小时里还有哪几步需要人」会答不上来，因为那三项自动化（外部告警门控 / synthetic health check / canary 自动放行）在 evidence 里明确是路线图而非已实施。建议把简历改成 `18–21h to 6–8h, with automation roadmap to 3–4h`。
- **`GitOps` 这个词**。`resume-expand.tex:108` 的 `IaC (GitOps/Ansible) cluster management` 无任何一手支撑，建议改成 "git-declared desired state"。

**待确认（面试前必须自己回答，不许编）**：

1. **「最接近出事的一次」没有可讲案例。** evidence 明确记录了这一点（`p_k8s_upgrade.md:160`：reference 只把它列为面试预设问题，无实际事件素材）。这是这个方向最可能被问穿的点。候选素材：某集群 raft lag 超 1000 被 check 拦住 / 某集群 PDB 卡住 drain 等了很久 / `drain_timeout` 从 300s 调到 600s 这个 feature flag 本身就是从一次卡住里学来的。安全答法见 `questions.md` A5。
2. **`[ONCALL-20941] K8S support 1.32` 那条 commit 是不是我的**（`interview-8-k8s-cluster-build.md:68`）。不确认就不许说「我加了 1.32 支持」。
3. **caBundle 那次 helm upgrade 是我执行的还是我 oncall 接手的**（`oncall_track_record.md:20` 只说是 oncall 处理的事故）。安全说法：「这是我 oncall 期间处理的一次 addon 升级引发的事故」。
4. **kubelet skew 在 1.24 时代是 N-1 还是 N-2**（我的 evidence 写 N-2，`interview-1-k8s_upgrade_reference.md:106`）。安全答法：「我们的实操从不利用这个余量，逐 minor 推进时 kubelet 落后从不超过一个 minor」。
5. **Terraform 动手实验是否已完成**。未完成前不许声称做过实验。

**明确不许说的**（零 evidence）：我用过 Terraform / 我们在迁移到 TF / 我写过 TF module；我们用 GitOps 或 ArgoCD；任何 DORA 数字（change failure rate、rollback MTTR）；镜像签名 / SBOM / SLSA provenance 我们做过；BKC 的风险分级修复、reboot token、跨重启状态机是「我做了」（只能设计口径）；「我建了 release 系统」（`pipelines/release/` 与 signoff 系列不是我的资产，我做的是流程分析文档）。

---

## 跨方向复用

| 本方向的故事 | 可以复用到 |
|---|---|
| S01 K8s 升级 | **05 blue/green**（dark cluster 切换是 blue/green cluster 的完整实例）· 02 监控（baseline 与外部监控交叉验证）· 06 成本（EKS vs 自管理的 $3,600/月与「工程师时间更贵」）· 90 行为面（重新定义问题） |
| S02 Upgrade Safety System | 02 监控（check 外溢成常态 health check）· 03 AIOps（门禁 + 证据链 + 人在环路 = Spec/Hook 同构） |
| S03 kubeadm 自建四层 | **07 AWS fundamentals**（VPC / 子网 / SG / NLB / ASG 的全部一手场景）· 02 监控（Layer 3 组件） |
| S04 Jenkins 迁移 | 05 blue/green（迁移即环境切换）· 90 行为面（修完顺手删 workaround = 主动治理） |
| S05 nightly 编排器 | 02 监控（告警路由到 owner）· 03 AIOps（幂等 + 门禁 + 证据的同构结构） |
| S07 ASG 节点 join 失败 | **07 AWS fundamentals**（ASG / LT / user-data / cloud-init 全链）· 05 blue/green（LT 版本化即不可变发布） |
| S08 helm upgrade 打断部署 | 02 监控（多租户同时失败的路由判断）· 01 数据库运维（同一事故库） |
| S09 BKC daemon | 03 AIOps（reconcile / 控制原语 / 人在环路）· 90 行为面（把部落知识变成系统） |
| S10 dcluster 部署验证 | 01 数据库运维（StarRocks CN）· 06 成本（spot 冷启动 9 分钟是弹性降本的时间代价） |
| S11 fail-closed 方法论 | 全部方向 · 03 AIOps（agent 的 fail-closed 与工具边界） |
