# 开场故事（选哪条主线，怎么讲前 30 秒）

「讲一个你最有代表性的项目」这道题决定整场面试走向。素材硬度不是问题，排序和封装才是（`research/interview_story.md` 的核心诊断）。

---

## 1. 选主线（先判断岗位类型）

| 岗位侧重的信号 | 选哪条主线 | 为什么 |
|---|---|---|
| JD 提数据平台、OLAP、数仓、lakehouse、大数据 | **Doris 主线** | 他最深的一条，且有引擎级工作，天花板最高 |
| JD 提 K8s 平台、集群运维、交付、发布 | **K8s 升级主线** | 跨 50 集群、零事故，规模感最直观 |
| JD 提可观测性、SLO、监控 | **可观测性主线** | 架构决策 + 数字漂亮，从资源指标到 SLO 的认知转变是加分项 |
| JD 提 AI / agent / 平台前瞻 | **AIOps 主线** | 市场稀缺度最高，但要防「玩具」质疑，见 03 目录 |
| JD 泛 SRE 无明显偏向 | **Doris 主线**，但把开场的引擎细节压缩，多留时间给可靠性与成本论证 | 一条主线能覆盖 6 个域 |

不确定就先反问一句：这个岗位头半年最想解决的问题是什么。对方的答案直接告诉你选哪条。

---

## 2. Doris 主线开场（30 秒，已定稿，逐字背）

来源 `research/interview_story.md`，已经过面试官视角诊断，不要自己改。

> 我们的反欺诈事件层要同时服务两种冲突的负载：毫秒级点查的 serving 流量，和越来越多 AI agent 驱动的、不可预测的 ad-hoc 分析。老的 ClickHouse shared-nothing 层对后者既不能隔离也不能弹性扩容：一条重查询能饿死整个共享池，我实测过一条 `SELECT * LIMIT 10` 墙钟排了 61 秒、CPU 只用 60ms。我做的不是一次迁移，而是把这层重构成存算分离架构，并把查询路由做进了 Doris 引擎本身：执行前判 heavy/light，按需把 spot 计算池从 0 拉起、用完缩回 0。

英文版：

> Our anti-fraud event layer had to serve two conflicting workloads at once: millisecond point lookups for serving traffic, and a growing volume of unpredictable ad-hoc analytics driven by AI agents. The old ClickHouse shared-nothing layer could neither isolate nor elastically scale for the second one. A single heavy query could starve the shared pool: I measured a `SELECT * LIMIT 10` waiting 61 seconds of wall clock while using 60 milliseconds of CPU. So what I did was not a migration. I restructured the layer into a disaggregated storage-compute architecture and pushed query routing into the Doris engine itself, classifying heavy versus light before execution and scaling a spot compute pool from zero on demand.

**为什么这样开场**：不能说「I led the migration of...」。那个动词会让面试官在前 5 秒锁定「搬数据加对账」的执行者框架，后面所有硬货都被这个框过滤掉。业务钩子（AI 驱动的不可预测负载）必须立刻钉在实测的饥饿案例上（61 秒 / 60 毫秒），否则会被追问「具体哪个 agent、上线了吗」而悬空。

**3 分钟展开顺序**（每段的详细弹药在 `01_doris_db_operations/story_bank.md`）：

1. (20s) 上面那段钩子
2. (30s) 结构性问题框定。明说论证不建立在 ClickHouse 慢上；点查占比推翻团队假设，作为「用数据改变设计」的一拍
3. (40s) 两件最硬的事，headline 先行：证明静态路由结构性不可能（同模板换参数 EXPLAIN 逐字节相同、真实内存差 23×），所以是信号问题不是规则问题，于是零删除纯加法进引擎；以及允许分类器不完美的两层防御（错误成本不对称，所以 recall 是安全不变量；漏网的 3 秒内被硬内存限制杀掉并自动升级）。金句：HPA 是分钟级的，OOM 是秒级的
4. (30s) 引擎级 war story 选 compaction 死亡螺旋：三因连乘、加 BE 无效、修复后 40s→<100ms
5. (20s) 判断力 headline：决定什么不该开源，机制上游、策略留内部，改变了 leadership 的决定
6. (20s) 边界与结果收尾：preprod 生产规模验证 + 10T 生产化推进中

### 这条主线的负面清单（违反就掉档）

- 不以 99.945% 对账开场或展开。那是尽职信号不是架构信号，收进追问弹药
- 不背 K8s 救火清单。operator 信号
- 前 60 秒不交代 preprod-only。放结尾，配 10T 生产化顶回去
- 不过度渲染 AI agent。必须绑定实测饥饿案例
- 不主动打开 benchmark 诚实性话题。被问「数字可信吗」时它才是满分答案
- 删掉一切「I also」「顺手」这类 scope-diminishing 措辞

---

## 3. K8s 升级主线开场（30 秒）

```
我们有 50 个生产 Kubernetes 集群跨 6 个 region，控制面是 kubeadm 自建的。
要把它们从 1.24 升到 1.29，跨越了 dockershim 移除和 PSP 下线这两个破坏性变更。
原来单集群要 18 到 21 小时，我把它做成了自动化流程，压到 3 到 4 小时，零事故。
但我想讲的重点不是省了时间：是我怎么让一个高风险变更变成可以重复执行、
每一步都可验证、任何一步都能停下来的流程。
```

最后那句是把话题从「自动化省时间」抬到「变更的确定性设计」的关键，一定要说。展开与追问防线见 `04_iac_cicd_k8s/story_bank.md`。

---

## 4. 可观测性主线开场（30 秒）

```
我们原来用 Prometheus Federation 覆盖 50 个集群，每周 OOM 两到三次，
数据滞后 45 秒，这意味着告警到的时候现场已经过去了。
我主导迁到了 VictoriaMetrics，现在 120 万活跃 series、每秒 8 万采样点，
OOM 归零、滞后进到 5 秒内。
不过这个项目真正改变我的地方是告警设计：
我们过去在资源指标上设阈值，后来改成按租户的 SLI 做记录规则，
因为客户感受不到 CPU 用了多少，只感受到自己的请求成不成功。
```

最后一段是他从资源指标到 SLO 的认知转变（`g_slo_topdown.md`），这是可观测性岗位最想听的。展开见 `02_monitoring_slo/story_bank.md`。

---

## 5. AIOps 主线开场（30 秒）

```
我给自己的 oncall 建了一套 agent harness。
但我想先说它不做什么：它不自动执行任何会改变集群状态的命令。
所有 kubectl 或 helm 的变更操作都必须我点头，而且每条命令都要带一行意图注释进审计日志。
我做的是把调查、判断、操作三个阶段用文件级的 gate 隔开，
让 agent 在调查阶段读不到 runbook，避免它先看答案再找证据。
每条结论都必须引用一行原始证据，引不出来置信度就压到 3 分以下。
本质上这是把变更控制那套 SRE 方法论用在了 LLM 上。
```

开场就先说「它不做什么」是刻意的：面试官对 AI 碰生产的第一反应是不信任，先把 approval gate 亮出来，后面的设计才听得进去。展开与三类质疑的防线见 `03_aiops/story_bank.md`。

---

## 6. 通用的开场纪律

数字先行还是结论先行都可以，但**动词决定框架**。「我迁移了」「我运维了」「我协助了」把自己放进执行者框；「我重构了」「我把 X 做进了 Y」「我证明了 X 结构性不可能」把自己放进设计者框。同一件事换个动词就是两个档位。

每条主线的开场都留一个明确的钩子给面试官追问，不要一口气讲完所有硬货。他们追问什么，就说明他们在意什么。
