# TODO：简历条目纵深化（Why / How / 难点）

目标：工作经历里每条 bullet 都可下钻到一个项目深页，固定骨架 = 为什么做（业务动机）→ 怎么做（架构与路径）→ 难点（3-5 个，带数字）→ 生产化（适用时）。深页同时充当 blog 内容。

页面骨架模板：
- **Why**：业务痛点 + why now，一个量化锚点
- **How**:架构决策 + 执行路径，配 1 张文字架构图或阶段表
- **难点**：每个难点 = 现象 + 机制 + 解法 + 数字
- **Production**：灰度/回滚/验证纪律（有真实内容才写）
- 结尾链接相关 field notes / 其他文章

---

## P0 已有页面改造

### T0. Case study（CH→Doris）按 Why/How/难点 重构开头 ⚠️ 待用户确认 interview story 骨架
- 现状：七幕叙事，开头 "I led the migration" 已被面试官视角诊断为定性错误
- 改法：开场换成 research/interview_story.md 的定稿版（AI 负载钩子 + 61s/60ms 饥饿案例 +「不是迁移是重构」）；小节名对齐 Why(为什么离开 CH)/How(架构+内存工程+路由)/难点(两次 compaction 事故等)
- 素材：research/interview_story.md、INTERVIEW-PROJECT.md
- 依赖：用户确认 AI 动机可讲多实（有无 preprod 压测数字）

---

## P1 新项目深页（对应 resume bullet，按优先级）

### T1. 替换 Prometheus Federation → VictoriaMetrics 平台（用户点名）
- 对应 bullet：Observability #1
- **Why**：Federation 每周 OOM、数据延迟 45s、单点无多租户隔离；30 集群 40 租户的规模逼出重建
- **How**：vmagent → VictoriaMetrics → vmalert → Alertmanager → Grafana + Loki 全链路；迁移路径（双写/切换顺序）；~1.2M active series / ~80K samples/s 容量设计
- **难点**：(1) 迁移期间不丢告警的切换编排 (2) 多租户 series 基数治理 (3) recording rules 兼容性 (4) lag 45s→<5s 的实现机制
- **Production**：如何灰度到 30 个集群、回滚预案
- 素材：work-contexts/career/interview/interview-3-monitoring.md(+architecture/reference)、contexts/thought_review/victoriametrics_sre_playbook_20260402.md、victoriametrics_ops_review_20260402.md
- 脱敏：内部集群名、tenant 名；规模数字可用（resume 已公开）
- 状态：☐ 未开始

### T2. 生产 K8s 升级 1.24→1.29（用户点名）
- 对应 bullet：Deployment & Reliability #1
- **Why**：版本 EOL/安全合规压力 + 30+ 集群手工升级 18-21h/个不可持续
- **How**：Upgrade Safety System 三段式 check → plan(dry-run) → apply+evidence；control-plane 排序、etcd 备份闸门、worker 滚动策略；自动化工具把单集群压到 3-4h
- **难点**：(1) API deprecation 扫描与存量 manifest 治理 (2) 有状态工作负载（DB pod）的驱逐顺序 (3) 多 region 之间的升级波次设计 (4) 零事故的验证标准是什么
- **Production**：双 prod（East/West）零 downtime 的执行记录、回滚触发条件
- 素材：interview-1-k8s_upgrade.md(+reference)、fy2026_self_assessment.md Q1/Q3、knowledge/runbooks/runbook-k8s-upgrade-plan-runbook.md
- 脱敏：runbook 里内网 IP/cert 路径/AMI ID 较多，摘方法论不搬原文
- 状态：☐ 未开始

### T3. 自动流量切换系统（traffic-switch）
- 对应 bullet：Traffic & Multi-Region #1
- **Why**：故障切流靠人工 runbook 5-15 分钟，对实时反欺诈 SLA 不可接受
- **How**：Master-Detector 两层架构；覆盖 ALB / API Gateway / Global Accelerator / K8s 四层后端；从 0 设计到接入 30 集群
- **难点**：(1) 检测的假阳性治理（切错比不切更糟）(2) 四种后端的切换原语不一致 (3) 切换本身的幂等与回切 (4) 分钟→秒级的路径压缩在哪
- 素材：interview-2_traffic_switch.md(+reference)
- 脱敏：架构可讲，内部服务名泛化
- 状态：☐ 未开始

### T4. 引擎级查询路由（EXPLAIN ROUTE PLAN 独立成页）
- 对应 bullet：Data Infra OLAP #2（现在只在 case study 里占两段，值得独立深页作为「改引擎」王牌）
- **Why**：静态路由结构性不可能（同模板换参数 EXPLAIN 逐字节相同、内存差 23×）；stock 45% 准确率/27% heavy-miss
- **How**：signal problem not rule problem → PlanEstimateCollector 纯加法暴露 CBO 估算 → 15 规则分类器 Java port → ANTLR grammar/planner 接入点；189/189 parity 工程
- **难点**：(1) 跨语言 parity 的 tri-state accessor 语义 (2) QEMU 43min build → 分层验证策略 (3) 什么不该 upstream 的边界判断（7 个耦合点）(4) LIMIT blindspot 这类 spec 级 bug 的发现方式
- 素材：dimensions/opensource.md、perf-routing.md、plan/51、26-28
- 状态：☐ 未开始

### T5. 弹性计算层（dcluster 0→N→0）
- 对应 bullet：Data Infra OLAP #3
- **Why**：heavy 长尾查询需要物理隔离+按需算力；单查询成本比 1,240×，静态常驻池 burst 场景多花 92-97%
- **How**：HPA 角色收缩（300 行部署逻辑→一个 CR patch）；spot 冷池链路 66s 节点+2min 注册；分层探活设计
- **难点**：(1) CA scale-from-zero 的两类静默不扩根因 (2) SELECT 1 探针骗局 (3) 空闲 CG clusterHealth 红是设计 (4) per-query 弹性是表演、离散分层才是稳态
- 素材：dimensions/doris-arch.md、plan/72-dcluster-scaling-dynamics-spec.md
- 状态：☐ 未开始

### T6. 三层告警体系与分租户 SLI
- 对应 bullet：Observability #2
- **Why**：40 租户共享告警面 → 噪音互相淹没；需要租户级故障隔离与 SLA 追踪
- **How**：三层分级 + inhibition 降噪 + per-tenant SLI recording rules + latency 分解
- **难点**：(1) severity 语义治理（每级意味着什么动作）(2) inhibition 规则的级联误抑制 (3) 分租户基数与查询代价
- 素材：interview-3-monitoring.md、fy2026 告警治理段
- 状态：☐ 未开始（可与 T1 合并成一篇「监控平台」大页，二选一）

---

## P1.5 视角页（thesis 下钻，第三条腿：认知层）

入口：首页 thesis 一句话变成可点，跳到 Perspectives 区（4 页）。新 writing kicker = PERSPECTIVE。

### V1. 我所理解的 SRE 需要的能力
- 骨架现成：`work-harness/code_repos/infra/cre6630-infra/SRE-core-skill-map.md`
- 内容：视角转换（工具清单 → 问题能力，「精通 = 抽象泄漏时能往下钻」）→ 九域框架及推导逻辑（为什么是这九个：四个稳态交付带 + 分布式智识内核 + 事件响应时间维度 + 安全 + 数据状态 + 组织影响力）→ 事故响应为什么是不可外包的护城河 → DBA/SRE 划界五件套（拓扑/失败恢复/容量/备份演练/可观测）→ 监控拆成「运营=核心 / 建设=专家项」
- 联动：这页同时回答雷达「为什么是九个轴」，radar note 链过来
- 补充素材：bestpractice_sre_reliability_models（Availability/Overload/SLI-SLO 第一性）、traditional 7 层工具箱
- 状态：☐ 素材最全，可先写

### V2. 我当前做了什么，匹配什么能力
- 内容：打分方法（evidence 密度定标，不是自评）→ 九域逐域：核心 evidence + 数字 → oncall 行为统计交叉验证（21 documented investigations，touching 分布：incident ~14 / data 8 / obs 6 / infra 6 / dist 5 / release 5）→ 分数与统计互证
- 素材：content_plan 分数表 + knowledge 盘点统计（本次两 agent 产出）
- 状态：☐ 素材已齐，纯组装

### V3. 接下来应该做什么
- 内容：gap = target − depth 逐域说明 → 三个优先投资：传统安全合规面（40→65 需要什么 evidence）、SLO/error budget 的真实运营记录（72→82）、跨团队立项级 influence case（52→75）→ 每项写清「什么算补上了」
- 定位：「简历告诉你我会什么，这页告诉你我知道自己还不会什么」——诚实雷达的文字版
- 状态：☐ 短页，风险是写成空话，必须每条挂可检验的 evidence 定义

### V4. AI agent 的扩展（SRE → AI Infrastructure 主线宣言页，差异化最高）
- 两问结构（用户定义）：
  - **发展到今天带来什么变化**：oncall 执行层被 agent 接管（调查/取证/初判），人从执行者变 harness 设计者与裁决者；知识资产从「人读的 runbook」变「agent 可执行的判别器」；实例支撑：4504 三链并行取证、oncall triage harness（phase lock/mutation gate）、dossier 本身由 mining pipeline 产出
  - **还有什么需要工程师做**：意图与约束定义（agent 的 admission control）、mutation 主权与 blast radius 边界、eval 与 agent SLO/error budget、平台原语（agent 也需要 reconcile loop）、最终判断责任（agent emits evidence, human decides policy——与「engine emits data, caller decides policy」同构）
- 素材：contexts/thought_review/k8s_sre_agent_controllability_model_20260330.md（SRE 与 agentic AI 同构）、bestpractice_agent_reliability_engineering、bestpractice_agentic_control_primitives（Spec/Loop/Hook/Fork）、agent_slo_error_budget_survey、agent_ops_competency_model_v1、T12 公理、ACP
- 状态：☐ 素材最厚，需要最强的收敛裁剪

---

## P1.75 新事故长文候选（knowledge 盘点产出，写在 T1-T6 之后）

- ☐ **僵尸系统表 OOM**（升格为第 6 篇长文 `w-inc-oom`，挂 data+incident+obs 三域）：升级残留 >1TiB 死数据、后台 merge 1 秒内 2→21.6GiB、30s 采集完全错过、1s 粒度内部指标定案、修复+全舰队横向审计
- ☐ CH CPU 92% 反直觉归因（query 67% vs merge 10%，多信号判定矩阵）→ 一句话 evidence 或短文
- ☐ caBundle 变更事故（多租户同分钟同机制失败 = cluster 级信号，发布域旗舰）
- ☐ Debezium schema 变更三跳因果链（431s ≠ 8h 网络层判断）
- ☐ MirrorMaker 每分区吞吐天花板（重启修不好的 lag；脱敏项多：tabapay/人名/链接）
- ☐ 其余 3 条（BDB IP 绑定、liveness 误杀、假 P99）作一句话 evidence 进域页

---

## P2 结构与集成

### T7. 站点结构：resume bullet → 深页链接
- RESUME.items 已支持 #W# 链接占位；新增 writings 类型 kicker=PROJECT；Selected Writing 列表分组（Projects / Incidents / Case Study）
- 状态：☐ 未开始（随第一篇新深页一起做）

### T8. Oncall 九域统计集成（方案已定：A 骨架 + B 限定 + C 克制）
- **A 骨架**：6 个有 case 的域加 Track Record 统计行 + 8 条精选 case 作一句话 evidence 进 DOMAINS[].evidence（零新组件）
- **B 限定**：只在事件响应域放一张 7 失败域索引表（脱敏自 reference-case-taxonomy，全站唯一新组件）
- **C 克制**：只把僵尸表 OOM 升格为第 6 篇长文，其余保持一句话
- **统计口径五规则**：case 与 runbook 永不合并成大数；trace 不计（基数=21）；_archived 不计；表述为「21 documented investigations（其中 20+ 为生产 P1/P2）」区分调查数与事故数；各域计数标 "touching"（跨域挂载，总和 >21 属正常）；security/influence 如实 0 或不显示
- **解释句**（统计行 tooltip）：每条记录都是 on-call 处理过的真实生产事故，蒸馏成症状→定位→修复→教训四段，保留因果证据链，去除全部客户/集群/内部标识
- 状态：☐ 方案定稿，待实施

### T9. Interview story 落地（等用户确认）
- dossier §1 电梯陈述重写 + case study 开头重写（=T0）
- 状态：☐ 待确认

## P3 待补素材（之前遗留）

- ☐ nginx P100 修复后 after 数据
- ☐ 安全合规域：SOC2/PCI/IAM 真实经历确认
- ☐ WARM UP COMPUTE GROUP 实验（弹性叙事补强）
- ☐ 正式部署：public repo + 域名 + /en /cn 真路径

---

## 写作纪律（每页过一遍）

- 脱敏七规则见 content_plan.md；每个数字可回溯到 evidence 文件
- 客观语域（JD register），技术术语保留英文
- Why 必须落在量化痛点上，不悬浮；难点每个都要有机制层解释
