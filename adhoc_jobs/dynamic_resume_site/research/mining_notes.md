# 三线挖掘摘要（2026-07-19 三 subagent + 2026-07-20 dossier 刷新）

完整事实以刷新后的 dossier 为准（INTERVIEW-PROJECT.md + dimensions/）。本文只留 site 写作需要的判断性结论。

## 弹性伸缩线

- 叙事定盘星：**离散分层 + 引擎内准入判定，不是 HPA**。OOM 秒级、扩容分钟级，准入控制是第一防线，弹性只是漏判长尾的落脚点。
- dcluster 从上一代 300 行 StarRocks 部署器收缩成一行 JSON-patch：「平台原语成熟了，bespoke 工具就该收缩」是最强 senior 信号。
- warmup 评估：warm up SQL suite 只对 IO-bound + 热集可预测场景合理；应改用 Doris 原生 `WARM UP COMPUTE GROUP ... FORCE`（job 化、可从热 CG 拷 cache）。宽投影是 CPU 列解码 bound（cold 76s/warm 50s，cache hit 100%），warmup 无效；弹性 heavy 池（0 副本用完即拆）写 warmup suite 是反模式，接受 3-5min 冷启税正确。
- 诚实边界：ASG/launch template 层实际深度是「消费与修补」（加 tag、开 LT 版本、调 requests），非从零设计 mixed instances policy；on-demand vs spot 决策成立但未量化。site/面试别写过头。
- 深挖点：SELECT 1 探针被 FE 常量折叠不派发 BE；CA 差 0.1 核 allocatable 静默不扩（两类根因：requests > allocatable、scale-from-zero 缺 node-template tag）；空闲 CG 让 clusterHealth 红是设计不是故障。
- doc 72（dcluster spec）已把探活修进正确的层（C3 readiness/aliveBackends）+ C4 排队感知扩容；tier-2 CG 明确砍掉。

## 迁移运维线

- 真实主线是内存工程（四 OOM 点 + 1.7B livelock），有 file:line 证据；独家数据资产 = 列宽维度写吞吐 A/B（官方 benchmark 全是窄表）。
- compaction/tablet 在 dossier 刷新后已是硬实测（两次事故 + 修复配方 + 46× 压缩衰减 + 加 BE 无效实证 632 no-op vs 9 merge）。
- 交叉验证：tablet 1-10GB、-235 因果链、vertical compaction 内存 1/10 均与官方一致；抓到官方 FAQ `max_tablet_version_num` 默认值漂移（旧文档 500 / 近版 2000），发表时标注反而加分。
- 金句池：迁移是内存工程问题 / footer = row_groups × columns / 小片≠小内存 / 导入内存 ∝ 表大小 / bloom cuts rows not files / compaction 债是复利的。

## 事故与 DR 线

- 定选三事故：nginx P100 memcached（4.5/5，整数尾延迟=人为 timeout 常量；缺 after 数据）、大租户 QPS 联合止血（闭环最完整，先止血→动态降级→带 cap 扩容的顺序模型）、CH connection refused 逐跳（refused vs timeout 二分，8 跳链路）。备选：galileo「证无罪」（逐段分解定责）、CH CPU 92%（对抗确认偏误：query+merge 都要查）。
- DR 唯一强选：5.2B 行 prod EBS snapshot → 独立卷恢复 + 量化验证（count 50s / GROUP BY 83s）。先纠错误前提（CH TTL DELETE 物理 unlink，无 S3 tiering 可捞），再选可证零风险架构。标注：RPO≈24h 隐含、一次性演练非制度。
- 负面发现：「CH 年度 dump 到 S3」是迁移导出不是备份策略，不当 DR evidence。
- etcd 备份/回滚（K8s 升级 Phase 0）作副证据一句话带过：备份纪律真、被迫 restore 未发生。
- 脱敏提示：kubectl describe 截图可能含明文密码 env；客户名清单见 content_plan.md。

## 事实源索引

- 刷新版 dossier：`cre6630-infra/cre-6630/interview/`（INTERVIEW-PROJECT.md、dimensions/×5、_raw/highlights.jsonl 409 条）
- compaction 一手：`plan/70-compaction-fix-and-full-load-sync.md`、`plan/68-sofi-10t-production-todo.md`
- CG/负载画像：`plan/71-cg-design.md`（1,240× 成本比、18 window ≈ 21,755 点查）
- dcluster spec：`plan/72-dcluster-scaling-dynamics-spec.md`（file:line 级）
- 事故原文：`contexts/thought_review/nginx_waiting_latency_memcached_root_cause_20260408.md`、`contexts/galileo_latency_investigation_20260626/REPORT.md`、`agents/sre_oncall_triage_skill/knowledge/cases/`
- K8s 升级/监控平台：`work-contexts/career/interview/interview-1/-3/-4`、resume.tex
