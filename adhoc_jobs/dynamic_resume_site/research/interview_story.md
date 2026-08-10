# Doris 项目 Interview Story（双 agent 合成，2026-07-20）

来源：面试官视角诊断 agent + 复杂度地图 agent。两份完整报告在对话记录，本文是可执行版。

## 核心诊断

素材硬度足够（P8 信号充足），问题 100% 在排序和封装：

1. **「migration」这个动词给项目定了性**。开场 "I led the migration of..." 让面试官前 5 秒锁定「搬数据+对账」的执行者框架，后面所有硬货都被这个框过滤。
2. **三张 P8 王牌全在从句位置**：(a) 改引擎本身（fork Doris FE 加 SQL 语句）；(b) 设计「允许分类器不完美」的两层安全架构；(c) 逐行列 7 个业务耦合点、改变 leadership 的开源决策。"I also contributed…" 是 scope-diminishing 措辞。
3. **AI 动机在 dossier 里一个字都没有**。用户本人最强的 why-now 钩子（AI agent 时代前端打不可预测查询 → 需要 dynamic scaling 的 BE）没落纸。
4. **P7 信号占了黄金位置**：99.945% 对账是尽职不是架构；K8s 救火清单是 operator 信号。全部降级为追问弹药。

## 定稿开场（30 秒）

> 我们的反欺诈事件层要同时服务两种冲突的负载：毫秒级点查的 serving 流量，和越来越多 AI agent 驱动的、不可预测的 ad-hoc 分析。老的 ClickHouse shared-nothing 层对后者既不能隔离也不能弹性扩容：一条重查询能饿死整个共享池，我实测过一条 `SELECT * LIMIT 10` 墙钟排了 61 秒、CPU 只用 60ms。我做的不是一次迁移，而是把这层重构成存算分离架构，并把查询路由做进了 Doris 引擎本身：执行前判 heavy/light，按需把 spot 计算池从 0 拉起、用完缩回 0。

要点：业务钩子（AI/不可预测负载）必须立刻钉在实测饥饿案例上，防止「具体哪个 agent、上线了吗」的追问悬空。

## 3 分钟版排序

1. (20s) why-now 钩子（上面那段）
2. (30s) 结构性问题框定：明说「论证不建立在 CH 慢上」；94.2% 点查推翻团队假设作为「用数据改变设计」的 beat
3. (40s) 两件最硬的事，headline 先行：
   - 证明静态路由结构性不可能（同模板换参数 EXPLAIN 逐字节相同、内存差 23×；stock 45% 准确率/27% heavy-miss）→ signal problem not rule problem → 0 删除纯加法进引擎，recall 7%→100%，189/189 parity
   - 允许不完美的两层防御：错误成本不对称 ⇒ recall 是安全不变量；漏网 3 秒被 404MB 硬限杀掉自动升级。金句「HPA 是分钟级的，OOM 是秒级的」
4. (30s) 引擎级 war story 选 compaction 死亡螺旋：2,500 段/tablet、43GB task abort、三因连乘（关 auto-compaction × S3 冷读 7s/段 × 46× 压缩衰减）、加 BE 无效（632 no-op vs 9 真 merge）、修复 40s→<100ms
5. (20s) 判断力 headline：决定什么不该开源，mechanism 上游 / policy 留内部，改变 leadership 决定
6. (20s) 边界+结果收尾：preprod 生产规模验证 + 10T 生产化推进中。**绝不在开头自曝 preprod**

## 复杂度锚点（一句话立住深度，挑 2-3 个用）

1. Bloom filter 砍 73% 扫描行、墙钟不动：它减的是扫多少行，减不了开多少文件
2. 同模板换参数 EXPLAIN 逐字节相同、真实内存差 23×：静态 hint 结构性无解
3. 稀疏宽表 46× memtable→segment 压缩衰减：靠 buffer 顶到 1GB 段需要 46GB 内存表，不可行
4. compaction 债欠时按段数计息、还时按 S3 round-trip 计费；加 BE 无效因为单 tablet 不可拆
5. SELECT 1 被 FE 常量折叠、不派发 BE，空池也返回健康

## 重要性论证（公司级三条）

- 成本：4TB 迁移零额外 BE 盘；heavy 池 floor-0，burst 场景省 92%（OD）~97%（spot）
- SLA：单查询成本比 1,240×（一条窗口查询 = 1,240 条点查；18 条重查询 = 21,755 条点查总算力），无隔离时一条查询能拖垮全部租户的实时欺诈决策
- AI 产品线 enabler：旧架构 1M 采样 = 漏欺诈；路由+弹性是 AI ad-hoc 负载能上线的前置条件

## 不要讲（负面清单）

- 不以 99.945% 对账开场或展开（尽职信号）
- 不背 K8s 救火清单（operator 信号，收进弹药库）
- 不在前 60 秒交代 preprod-only（放结尾，配 10T 生产化顶回去）
- 不过度渲染 AI agent（绑定实测饥饿案例，可随时落地）
- 不主动打开 benchmark 诚实性长征（被问「数字可信吗」时才是满分答案）
- 删掉一切 "I also / 顺手" 措辞

## 追问弹药路由

| 追问 | 弹药 |
|---|---|
| 为什么非要动引擎 | 23× + 逐字节相同 + plugin 框架只有 audit hook |
| 误判打进共享池会怎样 | L2 fixed-slot 404MB、3s kill、自动升级，端到端验证过 |
| prod 会炸出什么 preprod 没见过的 | chart drift 4→1 副本、file_cache 对 10T 杯水车薪、月体积 8.3× 不均、storageSize 只在 PVC 首建生效 |
| 为什么不是 Trino/Snowflake/继续调 CH | 五约束交集；CH 真弹性闭源 SaaS-only 是架构缺口；Trino 无自有存储布局 |
| 讲一个你算错的 | benchmark 撤回 / sizing 5GB→610MB / NoSuchKey 自埋雷公开撤回 |

## 待用户确认

- AI 动机的落地程度：有没有可引用的真实 agent 负载（哪怕 preprod 压测），决定这个钩子能讲多实
- 是否按此重写 dossier 的 §1 电梯陈述和 site case study 开头
