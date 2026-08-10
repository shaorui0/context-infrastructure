# META
id: w-inc-qps
kicker_en: INCIDENT
kicker_cn: 事故
title_en: Order of operations under fire
title_cn: 火线上的操作顺序
sub_en: Split, shed, then scale — and why the intuitive order takes the database down.
sub_cn: 先分流、再卸载、后扩容，以及为什么直觉顺序会把数据库放倒。
domains: [incident, dist]

# EN

## Symptom

One tenant's query rate spiked far above baseline. Serving latency rose, error rates climbed on the dependency chain, and asynchronous recomputation began competing with the message queue and the database for the same headroom.

## The sequence, and why it cannot be reordered

1. **Stop the bleeding first.** Split traffic 50/50 to a second cluster. Reversible in seconds, buys headroom everywhere downstream, changes no behavior.

2. **Shed non-critical load second.** Dynamically degrade the non-critical async recomputation — rate-limit it to zero through runtime configuration, no restarts. The system keeps serving its primary contract while background work yields.

3. **Scale third, with caps.** Serving and async pools scale out under explicit ceilings; the message queue's partitions double; the database scales vertically 2×.

Scaling first is the intuitive move and the wrong one: adding consumers under uncontrolled inflow feeds the surge directly into the slowest stateful component. The database gets pushed over the cliff by the very capacity that was meant to save it, and capacity added under pressure arrives minutes late to a seconds-scale problem. Shedding before scaling is what makes the scaling safe.

## Validation discipline

Each step had to prove itself before the next: error rate, P95/P99, consumer-lag slope reversal (lag must be *falling*, flat is not recovery), and database headroom — each with a stability window of at least 10–15 minutes. Rollback criteria were staged in advance, so de-escalation was a checklist, not a judgment call at 2 a.m.

> Under overload, the order of operations is the decision. Everything on the list was correct; done in the wrong order, the same list takes the system down.

# CN

## 症状

一个租户的查询量冲到基线之上很远。serving 延迟上升，依赖链错误率攀升，异步重算开始和消息队列、数据库争夺同一份余量。

## 顺序，以及为什么不能重排

1. **先止血。**把流量 50/50 切到第二个集群。秒级可逆，为下游所有环节买到余量，不改变任何行为。

2. **再卸载非关键负载。**动态降级非关键的异步重算：运行时配置把它限流到零，不用重启。系统继续履行主契约，后台工作让路。

3. **最后带上限扩容。**serving 与异步池在显式上限下扩容；消息队列分区翻倍；数据库垂直扩 2 倍。

先扩容是直觉动作，也是错误动作：在失控的流入下增加消费者，等于把激增直接喂给最慢的有状态组件。数据库会被本该拯救它的容量推下悬崖，而压力之下追加的容量对秒级问题来说总是晚几分钟。先卸载，扩容才安全。

## 验证纪律

每一步都要自证之后才有下一步：错误率、P95/P99、消费积压斜率反转（积压必须在下降，持平不算恢复）、数据库余量，每项至少 10–15 分钟稳定窗口。回滚判据提前分级，降级操作是一张清单，不是凌晨两点的临场判断。

> 过载之下，操作顺序就是决策本身。清单上每一项都是对的；顺序错了，同一张清单会把系统放倒。
