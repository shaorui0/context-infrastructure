# SRE 第一性原理模型: Availability / Overload / SLI-SLO

## 元数据

- 类型: BestPractice
- 适用场景: 事故复盘, 系统设计, 指标体系设计, 容量与过载治理
- 创建日期: 2026-03-26
- 来源: 多次对话 + 框架蒸馏

---

## 1) Availability: 概率分解

- 定义: 在给定时间窗口内, 系统能正常响应请求的比例。
- 拆解:
  - Availability = P(不出故障)
  - + P(出了故障但快速检测) * P(检测后快速恢复或有损降级)
- 关键点: Detection(监控+告警)是容易被遗漏但不可或缺的环节, 没有检测, recovery/degrade 无从触发。

### 手段按目标归类

- 防故障发生: 冗余, 消除单点
- 控制故障半径: isolation, 限流/丢弃保护核心路径
- 缩短故障持续时间: fast fail, recovery(重启/failover/回滚)
- 故障期间维持部分价值: degrade(有损服务优于无服务)

## 2) Overload: lambda vs mu 坐标系

- 先判定: 这是 latency 问题还是 capacity 问题。
- 用 `lambda`(到达率) vs `mu`(处理率) 作为统一坐标。
- 当 `lambda > mu` 时, queue 必然出现, 关键在于:
  - queue 在哪里
  - 有没有 retry amplification/retry storm
  - 有没有 backpressure/rate limit
  - failure 如何传播(队列, 级联超时, 依赖放大)

### 分层模型(用于收敛讨论)

- physical limits: latency/capacity/failure
- system behavior: load/queue/propagation
- control mechanisms: cache/queue/rate limit/retry/redundancy
- abstraction leakage: 跨层排障成本

## 3) Latency SLI/SLO: 四层概念分离

- SLI: 衡量什么
- Histogram: 怎么记录分布
- Quantile: 怎么查看分布中的统计值
- SLO: 对该指标在时间窗口内施加什么目标

### 推荐口径

- `SLI = requests_under_threshold / valid_requests`
- `SLO = SLI >= target over time window`
- `P99 <= Xms` 更适合作为观测视角或补充视角, 不要默认把 quantile 当成 SLI 本体。
