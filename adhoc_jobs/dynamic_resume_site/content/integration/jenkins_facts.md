# Jenkins 工作事实层（resume 素材清单）

> 挖掘时间：2026-07-20
> 素材来源：
> - 工作 repo：`/Users/rshao/work/work-harness/code_repos/jenkins-config/`（团队共享 Jenkins pipeline 库，Rui 306 commits，全 repo 第一贡献者，时间跨度 2025-03 至 2025-08）
> - 个人项目：`/Users/rshao/work/context-infrastructure/work-contexts/toy-proj/jenkins-mgt/`
> - 叙事框架对齐：`/Users/rshao/work/context-infrastructure/work-contexts/career/interview/interview-5-cicd_reliability.md`
>
> 核心背景事实（贯穿全部素材）：公司把 Jenkins 从旧 K8s 集群（us_mgt，jenkins-k8s-mgt.datavisor.io）迁移到新 K8s 集群（east_mgt，jenkins-mgt.dv-api.com），两套 Jenkins 都跑在 Kubernetes 上、用 kubernetes plugin 动态起 agent pod。用户的大部分工作是这次迁移的落地和迁移后 CI/CD 的稳定化，不是「日常维护脚本」。

---

## 1. 事实清单

### A. 生产镜像 nightly 构建流水线（自建，最有简历价值）

**做了什么**：从零写了 `production-build` pipeline，一个 cron 触发的 nightly 生产 Docker 镜像构建编排器，跨 4 个生产分支 x 3 类服务（FP Services / API Server / NGSC），编排下游 pre-process → build-image job 链。

设计点（都有代码可证）：
- **cron 参数持久化**：Jenkins declarative pipeline 的参数在 cron 触发时会回落到 default，他把上次人工触发的参数写到持久卷上的 properties 文件（`PARAM_PERSISTENCE_FILE = /root/.m2/repository/production-build-params.properties`），cron 触发时读回，人工触发时保存并动态更新 job 参数定义。解决了「cron 构建用错分支」这类真实问题。
- **下游状态收集**：逐个下游 job 收集 `service/branch/job/number/result/console url` 到 `BUILD_RESULTS` JSON，失败前先落盘保存已有结果（partial results 不丢）。
- **失败归因 + oncall 路由**：`FAILED_SERVICE`/`FAILED_BRANCH` 归因，失败时按服务名映射到对应 oncall（`FP_ONCALL`/`APISERVER_ONCALL`/`NGSC_ONCALL`）在 Slack @ 对应的人，Email 列表可配置。成功/失败双通道通知（Slack #general-build + email），通知失败本身有 try/catch 不阻塞 pipeline。
- **FORCE_BUILD 幂等开关贯穿全链**：从 production-build → pre-process → base build 逐层透传 `FORCE_BUILD` 参数，底层 build job 先查镜像 tag 是否已存在（`cicdUtils.dockerImageExistsDapp`），存在且非 force 则跳过构建。重跑安全。

**证据**：
- `pipelines/global/k8s/build/production-build/Jenkinsfile`（859 行，git log 显示该文件由他创建，INDEV-2649 系列 commit）
- commits：`939e81fc7 [PATCH] Persistency cron parameters`、`dd02bf606 [PATCH] Collect downstream status`、`398e478f9 [PATCH] Alert enhancement`、`a69ab7eb4 [PATCH] Add force_build param in pre-process-build`、`d2dc8b2e1 [INDEV-2649] Cron build production images`、`8d52da9a0 [INDEV-2649] Build multiple branch once`
- `pipelines/global/k8s/build/pre-process/Jenkinsfile`、`pipelines/global/k8s/build/base/Jenkinsfile`（L27/L57/L111/L142：`dockerImageExists` + `FORCE_BUILD` 门）

**简历价值判断**：值得写。这是「把 pipeline 当系统设计」的实物：状态持久化、失败归因、通知路由、幂等重跑，四个属性齐全，且和他已有的 CI/CD 可靠性面试框架（幂等/错误处理）直接对得上。

### B. Jenkins 跨集群迁移的依赖修复（故障修复，值得写但要打包成一个故事）

**做了什么**：Jenkins 从旧集群迁到新集群后构建大面积失败，他做了系统性的根因定位和修复，涉及三类故障：

1. **Maven 依赖链断裂**：根因是外部仓库失效（maven.twttr.com 超时、repo.spring.io 认证失败）+ 迁移时 .m2 缓存没带过去 + Maven `.lastUpdated` 失败记录阻止重试。受影响包：hadoop-lzo、内部 ruleengine SNAPSHOT、joda-time、ua-parser、hibernate-validator。修复方案：mirror 重定向到 Maven Central（排除内部仓库）、跨集群 `kubectl cp` 迁移包（带 SHA1 校验、权限修复、`_remote.repositories` 重写）、清理 `.lastUpdated`。修完后还**删掉了 Jenkinsfile 里前人留下的 ua-parser workaround 代码**（`59f46e6f1` 等 3 个 "Remove workaround codes of mvn pakage install" commits）。
   - 证据：`docs/maven-dependency-fix.md`、`docs/hibernate-validator-fix-guide.md`、`fix-hibernate-validator-deps.sh`（287 行）、`deploy-maven-packages.sh`、`copy-hibernate-validator-from-us.sh`
2. **Debian Buster EOL 源失效**：构建镜像基于 Debian Buster，官方源下线导致 apt 失败。修复：切 archive.debian.org + `Check-Valid-Until false`；后续把 agent 镜像升级到 Bookworm（见 C）。
   - 证据：`fix-debian-buster-repos.sh`、`diagnose-debian-issues.sh`（含 `apt-get update --dry-run` 诊断）、commit `0b73cd057 [INDEV-18151] Added security software source fixes`
3. **Arcanist/PHP 兼容性**：land-code pipeline 里 2019 年版 Arcanist/libphutil 与 PHP 8 不兼容（`Phobject::rewind()` 返回类型错误），强制所有 arc 命令走 PHP 7.1；另修 pipeline 内 git credential 问题（`@Library('jenkinsconfig@east-mgt')` 语法错误 + credential helper 配置）。
   - 证据：commit `2efd5f73b [Cursor] Fix Arc PHP compatibility`、`62170b846 bugfix: resolve git credential issue in pipeline`、`ccc38fe7f [PATCH] Recovery land code`（净删 166 行恢复被改坏的 land 逻辑）

**简历价值判断**：值得写，但不要写成三个 bullet，打包成「迁移 + 稳定化」一个故事。亮点在根因链条（仓库失效 → 缓存缺失 → `.lastUpdated` 卡死重试）和「修完顺手删 workaround」的治理动作。

### C. Jenkins agent（slave）镜像现代化（值得作为辅助事实）

**做了什么**：维护 Jenkins agent Dockerfile（他 touch 50 次，是该文件主要维护者）：基础镜像升级（`000ffe1b1 upgrade slave docker base image`）、Debian 源切到 Bookworm、Java 8/17 多版本构建环境（INDEV-2649 Java17 build image 系列）、Maven 3.3 + Java 8 组合配置、Dockerfile 优化（`[PATCH] slave dockerfile optimization`）。agent 是 K8s 动态 pod（kubernetes plugin），.m2 缓存挂 PVC（`maven-pvc.yaml`，`jenkins-m2` claim）。

**证据**：`pipelines/global/k8s/jenkinsci/slave/Dockerfile`、`maven-pvc.yaml`、`jenkins.yaml`（agent pod spec 快照，印证 K8s 动态 agent + docker.sock + m2 PVC 架构）

**简历价值判断**：单独不够一条 bullet，作为迁移故事或「K8s 上的 Jenkins」语境的支撑事实。

### D. jenkins-mgt 自研管理面板（个人项目，值得单独写）

**做了什么**：因为 Jenkins 原生 UI 是单 job 视角，链式 pipeline（entrypoint → pre-process → build-image → deploy）没有统一视图，自己写了一个 Flask 聚合面板：
- 按真实 pipeline 执行顺序组织 Folder → Job → 最近 5 次 build 三层视图
- 新旧两套 Jenkins 环境一键切换（迁移期的真实需求：跨环境对比构建结果）
- 一键用上次成功构建的参数 replay、参数追溯/复制
- `ThreadPoolExecutor` 并发抓取（max_workers 8/10），README 记录了实测数字：总耗时 8.31s → 5.79s（30.3%），吞吐 1.20 → 1.73 jobs/s
- 凭据不落 repo（配置注释明确 credentials 走 .env），有单元测试（454 行 test），Docker + K8s 部署清单齐全

**证据**：`README.md`（双语，动机写得很清楚）、`jenkins_manager.py`（1088 行）、`app.py`（10 个 REST 端点）、`test_jenkins_manager.py`、`k8s/`、`jobs_config.yaml.example`

**简历价值判断**：值得写，但标注为个人工具项目（personal tooling），不冒充团队交付。价值点是「发现工作流摩擦 → 自己造工具消除」+ 有量化数字。

### E. 普通脚本维护（如实标注：不值得进简历）

- 大量 `[PATCH] Debug`/`test`/`cicd debug` commit（37+27+21+21 个）：迭代调试痕迹，说明当时缺 pipeline 本地测试手段，只能 push-and-run。不写进简历，但可作为深页「诚实边界」素材。
- `fix-debian-buster-repos.sh` 本身只是 sources.list 替换脚本，单看是脚本级维护。
- `build.gradle`/`settings.gradle`：给 shared library（`src/com/datavisor/utils/*.groovy`）提供 IDE 依赖解析用的 Gradle 骨架（jenkins-core 2.45、groovy-all），不是他写的核心资产，不写。
- `system_diagrams.md`：内容是日语学习 app 的架构图，误放进这个 repo 的无关文件，不是 Jenkins 素材。
- `vars/*.groovy`（signoff 系列）、`pipelines/release/`：团队既有资产，他不是主要作者，不能声称。`docs/release-process-analysis.md` 是他做的**流程分析文档**（读懂了整个 release 状态机），可作深页背景知识，不可写成「我建了 release 系统」。

---

## 2. 简历 bullet 草案（DataVisor 经历下）

**Bullet 1（工作 repo 事实，迁移 + nightly pipeline 合并叙事）**

- EN: Stabilized CI/CD through a cross-cluster Jenkins migration (both instances on Kubernetes with dynamic agents): root-caused and fixed build failures from dead upstream Maven repositories, EOL Debian Buster apt sources, and Arcanist/PHP 8 incompatibility; then built a cron-driven nightly production image pipeline covering 4 production branches x 3 service groups, with parameter persistence across cron runs, per-service on-call routed Slack/email alerts, and an image-exists check that makes re-runs skip completed builds.
- 中文: 主导 Jenkins 跨 K8s 集群迁移后的 CI/CD 稳定化：定位并修复外部 Maven 仓库失效、Debian Buster 源下线、Arcanist 与 PHP 8 不兼容三类构建故障；随后搭建 cron 驱动的 nightly 生产镜像流水线（4 条生产分支 x 3 类服务），实现 cron 参数持久化、按服务路由到对应 oncall 的 Slack/邮件告警、以及基于镜像存在性检查的可安全重跑机制。

**Bullet 2（个人项目，放 projects 区，不与工作事实混写）**

- EN: Built a Jenkins aggregation dashboard (Flask, 1k+ LOC, unit-tested, K8s-deployable) that renders chained pipelines as a single ordered view across two Jenkins environments, with one-click parameter replay; concurrent fetching via ThreadPoolExecutor cut page load from 8.3s to 5.8s (~30%).
- 中文: 自研 Jenkins 聚合面板（Flask，含单测与 K8s 部署清单）：把链式 pipeline 按执行顺序聚合成单页视图，支持新旧两套 Jenkins 环境切换与上次成功参数一键 replay；ThreadPoolExecutor 并发抓取将页面加载从 8.3 秒降至 5.8 秒（约 30%）。

---

## 3. 域 evidence 草案（release / platform 域）

**Evidence 1（release 域）**

- EN: Owned the production image build path in a shared Jenkins pipeline library (top contributor, 306 commits): authored the 859-line nightly production-build orchestrator with downstream result collection, failure attribution (failed service + branch), and force-build idempotency gates propagated through the pre-process and base build layers.
- 中文: 在团队共享 Jenkins pipeline 库中负责生产镜像构建链路（第一贡献者，306 commits）：编写 859 行的 nightly production-build 编排器，实现下游构建结果收集、失败归因（服务 + 分支）、以及贯穿 pre-process 和底层构建的 force-build 幂等门。

**Evidence 2（platform 域）**

- EN: Maintained the Jenkins-on-Kubernetes build platform through an environment migration: dynamic agent image modernization (Debian Buster to Bookworm, Java 8/17 dual toolchains), Maven cache repair on the shared PVC (checksum-verified package migration, cleanup of stale .lastUpdated records), and removal of legacy per-package workarounds from Jenkinsfiles once the root cause was fixed.
- 中文: 在环境迁移期间维护 Jenkins-on-Kubernetes 构建平台：动态 agent 镜像现代化（Debian Buster 升 Bookworm，Java 8/17 双工具链）、共享 PVC 上的 Maven 缓存修复（带校验和的包迁移、清理过期 .lastUpdated 记录），并在根因修复后移除 Jenkinsfile 中遗留的逐包 workaround 代码。

---

## 4. 深页可声称的事实池（供文章引用）

### 幂等性的真实体现

| 事实 | 出处 |
|---|---|
| 底层 build job 先查镜像 tag 是否存在（`cicdUtils.dockerImageExistsDapp`），存在且非 FORCE_BUILD 则跳过构建 stage，pipeline 重跑不重复产出 | `pipelines/global/k8s/build/base/Jenkinsfile` L27/L111/L142 |
| FORCE_BUILD 参数从顶层编排器逐层透传到叶子 job（production-build → pre-process → build），显式区分「重跑补齐」与「强制重建」两种语义 | `pipelines/global/k8s/build/pre-process/Jenkinsfile`；commit `a69ab7eb4` |
| cron 参数持久化到 PVC 上的 properties 文件，cron 触发读回、人工触发覆写，消除「cron 重跑用了 default 参数」的不一致 | `pipelines/global/k8s/build/production-build/Jenkinsfile` L36, L76-107, L760-810；commit `939e81fc7` |
| 修复脚本的重入安全措施：`deploy-maven-packages.sh` 部署前先做带时间戳的 backup、部署后 SHA1 校验（`verify_deployment`）；`fix-debian-buster-repos.sh` 修改 sources.list 前先备份 | `deploy-maven-packages.sh` L121-146, L272-330；`fix-debian-buster-repos.sh` L13 |
| 诊断脚本用只读操作探测：`diagnose-debian-issues.sh` 用 `apt-get update --dry-run` 先诊断再动手 | `diagnose-debian-issues.sh` L47-48 |

诚实边界：这些是**操作级幂等**（skip-if-exists、checkpoint 文件、备份 + 校验），不是声明式 reconcile。Jenkins 命令式 pipeline 本身不幂等，他做的是在命令式框架里补幂等属性，这正好是 interview-5 框架里「Jenkins 天生不幂等」论点的第一手案例。另外修复脚本大多 `set -e` 快速失败但没有事务回滚，dry-run 只在诊断脚本里有、修复脚本没有 dry-run 模式。

### 可监控性的真实体现

| 事实 | 出处 |
|---|---|
| 下游 job 状态采集：每个下游构建的 service/branch/result/console URL 收进 BUILD_RESULTS JSON，失败前先落盘保存 partial results | `pipelines/global/k8s/build/production-build/Jenkinsfile` L228-250；commits `dd02bf606`/`3c9ee4e39` |
| 失败归因：FAILED_SERVICE/FAILED_BRANCH 全局变量，异常路径也回填（catch 里从 buildGroups 提取服务名） | 同上 L115-117, L254-259 |
| 告警路由：失败按服务名映射 oncall（fp → oncall-fp，apiserver → oncall-decision，ngsc → oncall-ui）在 Slack 里 @ 对应人；成功/失败均发 Slack + email 双通道；通知发送本身 try/catch 不阻塞 | 同上 L38-47, L584-620；commit `398e478f9` |
| 通知内容包含每分支每服务的构建结果明细和「因前序失败未执行」的剩余项 | 同上 L560-580 |

诚实边界：监控停留在**事件通知层**（构建级 Slack/email），没有 metrics 化（无 Prometheus 指标、无构建时长趋势、无 DORA 指标采集）。jenkins-mgt 面板补了「状态可见性」但也是拉取式展示，不是告警系统。

### 只是脚本级维护的部分（写文章时不要拔高）

- `fix-*.sh` 系列本质是 kubectl exec 包装的 runbook 自动化，作用对象是单个 agent pod 的 .m2 缓存，不是平台级修复；长期方案（内部 Maven mirror）写在文档建议里但没有落地证据。出处：`docs/maven-dependency-fix.md` L87-90「建议」节。
- 91 个 Debug/test commit 的迭代方式说明当时没有 pipeline 的本地验证 / staging 环境，靠生产 Jenkins 反复试。这个可以作为「命令式 CI 可测试性差」的自嘲式论据，但不是成就。
- `@Library('jenkinsconfig@east-mgt-rui')` 长期指向个人分支（production-build Jenkinsfile L23），说明 shared library 的分支治理是弱项，不要声称「configuration-as-code 治理」。repo 里没有 JCasC（jenkins.yaml 只是 agent pod spec 快照，不是 Jenkins Configuration as Code）。

---

## 5. 脱敏提示

进站点/文章前必须处理的内部信息（均真实存在于 repo）：

**高危（不可出现在任何公开内容）**
- `jenkins-config/jenkins.yaml` L28-31：**明文 AWS AccessKey + SecretKey**（AKIAJQXAV6RLY5CGQ2DA 及对应 secret），L23 还有 JENKINS_SECRET。这份文件本身不该进 git，建议提醒用户处理（轮换密钥 + 从历史清除）。
- `pipelines/global/k8s/jenkinsci/slave/Dockerfile`：`COPY .git-credentials` 进镜像的做法本身是内部实现，不要展示。
- credentials ID 名单：`jenkins-backend`、`ph_api_token`、`nexus-repo-cred`、`sonarqube_login`（land-code Jenkinsfile）。

**内部 URL / 域名（公开时用占位符替换）**
- jenkins-mgt.dv-api.com、jenkins-k8s-mgt.datavisor.io（jenkins-mgt/jobs_config.yaml）
- docker-registry.dv-api.com、maven.datavisor.com、ph.datavisor.com（Phabricator）
- kubeconfig 本地路径：`infra_oncall_mgt/dv_kubeconfig/east_mgt.config` / `us_mgt.config`（fix 脚本硬编码）

**内部名词（视 resume 语境决定，站点深页建议泛化）**
- 生产分支命名：`DV.202501AM2.External.weeklyhotfix` 等（production-build Jenkinsfile L30/L61）
- 服务名：fp / fp-async / fp-cron / dv-liquibase / apiserver / ngsc / dcluster / dcube
- 同事邮箱：xiaochao.huang@ / jianglin.guo@（EMAIL_LIST）、oncall Slack 组名（oncall-fp / oncall-decision / oncall-ui）
- JIRA 编号：INDEV-2649、INDEV-18151、INDEV-2642 可保留编号形态但不要带内部链接
- resources/ 下的 40+ 环境 groovy 文件名暴露客户/环境拓扑（env_aws_us_sony.groovy、gov、paypal 分支名等），**客户名（sony、paypal）绝对不可出现**

