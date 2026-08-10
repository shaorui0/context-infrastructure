# Dynamic Resume Site — 内容总纲（2026-07-20 定稿）

单一事实源：`work-harness/code_repos/infra/cre6630-infra/cre-6630/interview/INTERVIEW-PROJECT.md`（2026-07-20 刷新版，82 sessions / 409 highlights）。

## 架构

四层钻取：L0 resume（30 秒可读）→ L1 九轴诚实雷达（depth 实线 + target 虚线）→ L2 域卡片 → L3 thinking + 项目 evidence。设计不变量：每个能力声明链接到 artifact；thinking 层排在 skills 之上。原型：`prototype/dynamic-resume.jsx`（React + recharts，昭和仪表盘配色）。技术选型：Astro + YAML/MDX 数据驱动，静态部署，独立 public repo，英文为主。

原型待修事实错误：`years: 10` → ~4；`location: Kobe` → 以实际为准。

## 九域雷达分数（evidence 密度定标，v1）

| 域 | depth | target | 旗舰 evidence |
|---|---|---|---|
| 数据与状态 | 82 | 90 | CH→Doris 迁移（99.945% 对账）、四 OOM 点、livelock、EBS snapshot 恢复 5.2B 行 |
| 可观测性 | 80 | 85 | VM+Grafana+Loki 平台（50 集群/1.2M series）、query_log 取证、latency 分解 |
| 分布式系统 | 78 | 88 | 存算分离权衡、L1+L2 准入控制、traffic-switch、file-open-bound |
| 平台/自动化 | 76 | 85 | agent harness、ACP、dcluster controller、升级自动化 |
| 事件响应 | 72 | 82 | 20+ P1/P2 MTTR ~30min、两次 compaction 事故、nginx P100 RCA |
| 基础设施与容量 | 70 | 80 | IaC 四层（Packer+Ansible+kubeadm）、Doris OOM 治理、容量实验 |
| 发布与变更 | 68 | 78 | K8s 1.24→1.29 跨 50 集群（18-21h→3-4h 零事故）、staged dry-run |
| 影响力 | 52 | 75 | 内部培训 deck、告警治理倡议、双语写作 |
| 安全与合规 | 40 | 65 | agent 安全（sealed tools/attestation/hooks）；传统合规 pending 用户确认 |

## L3 产出清单（按优先级）

1. ✅ **Featured case study: CH→Doris**（`content/case_study_ch_to_doris.md`）— 覆盖 6 域的锚点页面
2. 博客「宽表迁移是内存工程问题」— 四 OOM 点 + livelock + 独家写吞吐 A/B（列宽摆动 5×、优化栈 <4-12%、bulk vs stream 50×）
3. 博客「我们离开 ClickHouse，但它还更快」— 四支柱引擎级论证、AI 查询形状不可预测打 CH 排序键死穴、内存硬隔离
4. 博客「查询路由是准入控制」— L1/L2、离散分层 vs 连续伸缩、1,240× 单查询成本比（doc 71）
5. 事故三连：nginx P100 memcached（公开前补 after 数据）、大租户 QPS 联合止血、CH connection refused 逐跳定位
6. DR：5.2B 行 EBS snapshot 恢复 + 量化验证（标注 RPO≈24h 隐含、一次性演练非制度）
7. thinking 短文：SELECT 1 探针骗人 / CA 差 0.1 核静默不扩 / 空闲 CG clusterHealth 红是设计 / 稳态够≠峰值够（livelock 与 YB WAL 重放同构）/ 三条独立证据链才是实锤（4504 孤儿 tablet）

## 脱敏规则（写进发布 pipeline）

1. 客户名/租户名/内部代号（sofi、nasa、galileo、CRE-6630、kwestdeva 等）永不出现
2. PII 列名不出现：`HASH(ssn)` → "high-cardinality user identifier"
3. 规模数字用取整形式：~5.2B rows / ~4 TiB / ~3,700 cols；精确到个位的行数是指纹（99.945% 对账的两个大数可用，非客户指纹）
4. query_log 负载画像只讲方法论与量级（"well over 90%"），不讲精确占比
5. 开源措辞："engine-level work on an Apache Doris fork; mechanism prepared for upstream, policy kept internal by design"——PR merge 前不写 "contributed to Apache Doris"
6. preprod 边界不上公开页，被追问时讲（不主动声称 prod 部署）
7. 内网 IP / 卷 ID / 集群名 / dashboard uid / *.dv-api.com 全删

## 数字口径备忘

- 行数/容量：evidence 锁定 5.17B / 4.07 TiB source（Doris 侧 ≈5.6TB）。用户口述 6B/6T 无出处，公开材料用 evidence 值。
- 集群数全站统一 50（2026-07-20 用户裁决）；40 tenants 已移除（监控素材无出处）。
- compaction 事故有两次：score ~2,500（disable_auto_compaction 死亡螺旋）与 score ~4,504（DROP 表孤儿 tablet 卡死）。用户记忆的 5k = 后者。两个故事分开讲。

## 待办

- [ ] 安全合规域：用户确认 SOC2/PCI/IAM 真实经历（pending）
- [ ] nginx P100 RCA 补修复后 after 数据
- [ ] 可选补强实验：Doris 原生 `WARM UP COMPUTE GROUP FORCE` 实测（heavy 池 0→1 首查 2.9s → 20ms）
- [ ] Astro 站点骨架 + 数据 schema（domains/evidence YAML）
- [ ] 独立 public repo 创建（用 /personal-git-push 流程推 ryan42xyz）
