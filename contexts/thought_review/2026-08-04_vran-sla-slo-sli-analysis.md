# 5G vRAN / vDU 的 SLA 到底是什么——SLA / SLO / SLI 分析

日期：2026-08-04
类型：调研整合 + 分析，用于回答开放问题
关联：`contexts/thought_review/2026-08-04_intel-bkc-monitoring-retrospective-raw-material.md` 第 1.4 节留下的核心开放问题
调研方式：3 路并行 subagent（标准规范层 / 商业契约层 / 工程落地层）+ 1 路子任务（NOC 实践），检索 3GPP、O-RAN、ITU-T、GSMA、TRAI、FCC、Red Hat、VMware、Intel 原始文档与学术论文，交叉核对

---

## 0. 结论先行

**「5G vRAN 的 SLA 应该是什么」这个问题，问法本身需要先拆开。** 因为在这个领域里，「SLA」这个词被三种完全不同的东西共用了：

| 层 | 是什么 | 谁定的 | 数字的性质 |
|---|---|---|---|
| **技术规格目标（target）** | URLLC 0.5ms、可靠性 1-10⁻⁵ 这类数字 | 3GPP，给芯片和设备厂商设计用 | 明文写着「不是强制要求」 |
| **运营 SLO** | 运营商内部对小区/网络的门限 | 运营商自定，无公开标准 | 真正驱动告警和排班 |
| **客户 SLA** | 写进合同、违约要赔钱的承诺 | 运营商 ↔ 企业客户 | 基本不公开 |

3GPP TS 22.261 Table 7.2.2-1 的 NOTE 9 原文写得极其直白：**"All the values in this table are targeted values and not strict requirements"**（该表在 Release 16 起已迁移至 TS 22.104）。也就是说标准给的那些漂亮数字，**连 SLO 都不是**，是给设计芯片的人看的规格书目标。

**从 target 到 SLO 再到 SLA，中间这两层转化没有任何标准可抄，必须自己做。这就是「vRAN 的 SLA 是什么」的真实答案：它不是一个可以查表得到的东西，它是一个必须自己设计的东西。**

这一条直接回答了原始素材 1.4 节的自问。当年缺的不是指标——指标 3GPP 定义了几百个——缺的是**把技术指标转化成「出了事该不该叫人起床」的那个判断结构**。

---

## 1. 「Latency / Success rate / Throughput」三件套：对，但有三处会失真

原始素材里提的三点方向正确，它们确实覆盖了 vRAN 的主要 SLI 维度。但直接套用互联网 SRE 的形态会在三个地方出问题，而这三处恰好是内行会追问的地方。

### 1.1 失真一：Latency 在 L1 层不是分位数问题，是 deadline 问题

互联网服务讲 p99 = 800ms，隐含的失败模型是**渐进降级**：超了只是用户等得久，系统还在工作。

vDU 的 L1 处理不是这样。它的失败模型是**二元的**：在 deadline 内完成 = 正常，超过 = 这个 slot 的数据直接作废，触发 HARQ NACK 重传，吞吐塌陷；严重时 DU 崩溃、小区离线。中间没有「稍微差一点但还凑合」这个状态。

deadline 从哪来：

- **Slot 长度由 numerology 钉死**（TS 38.211 Table 4.3.2-1，已核实 ETSI PDF 原文）：
  µ=0 (15kHz) → 1ms；µ=1 (30kHz) → 0.5ms；µ=2 (60kHz) → 0.25ms；µ=3 (120kHz) → 125µs
- **HARQ 处理时限 N1/N2** 由 TS 38.214 §5.3 / §6.4 按 symbol 数查表给出，不是单一常数，实际 RTT 还叠加网络配置的 K0/K1/K2 偏移
- **触发重传的判据**是 BLER 目标（业界常用 < 5%）

所以正确的 SLI 形态是 **deadline miss rate**（错过截止时间的 slot 占比）——注意它形式上是个**成功率**指标，不是延迟指标。这会反过来决定监控怎么建：**直方图的分桶要围绕 deadline 那个点设计**，而不是均匀分桶或者默认的指数分桶。这一点对做监控的人是很具体的工程指导。

> ⚠️ **表述精度警告（面试会被追问）**
> - 「deadline miss rate 应该取代 p99」这句话，**3GPP 和 O-RAN 的规范里都没有明文写过**。它是从学术界一致实践反推出来的：Concordia (SIGCOMM'21)、RENC (NSDI'25)、Hades (arXiv 2502.00603) 在评估 L1/HARQ 层时清一色用 deadline miss rate，到应用层才切回 percentile。准确说法是**「业界揭示性实践」，不是「标准规定」**。
> - 广为流传的「vDU L1 有 ~3 slot 硬 deadline」，那是 **Intel FlexRAN 具体实现的 PHY 处理线程调度周期**（来源：RENC, USENIX NSDI 2025），**不是 3GPP 条款**。你是在 Intel 做的，把厂商实现值说成标准，内行会当场抓住。通用说法应该是「deadline 约等于一个 TTI 长度」。

### 1.2 失真二：Success rate 不是一个数，是一条链

互联网的成功率通常就是 HTTP 2xx 占比，一个数。RAN 侧一个用户从开机到能上网要连过四道关，每道关有独立的成功率，任何一道塌了用户都完蛋，但根因完全不同：

| 关卡 | 指标 | 标准出处 | 塌了指向什么 |
|---|---|---|---|
| ① 接入 | RRC 连接建立成功率 | TS 28.554 §6.2.4 的乘法因子；计数器 `RRC.ConnEstabSucc/Att`（规定排除 cause=mo-Signalling） | 信令面过载、许可控制拒绝、覆盖边缘 |
| ② 承载建立 | PDU Session Setup Success Rate（4G: E-RAB） | TS 28.554 §6.2.5（只给语义，公式 deferred 到 28.552） | 核心网侧、传输面、QoS 资源不足 |
| ③ 保持 | Retainability（异常释放） | TS 28.554 §6.5.1/6.5.2 | 无线链路失败、干扰、切换配置错误 |
| ④ 移动 | Handover Success Rate | TS 28.554 §6.6.1 | 邻区关系配置、切换门限、跨频/跨 RAT 配置 |

组合形态：**Total / Partial DRB Accessibility = RRC 建立成功率 × NG 信令建立成功率 × DRB 建立成功率**（TS 28.554 §6.2.4，已核实原文）。4G 的对应物是 **CSSR = RRC SSR × E-RAB SSR**——注意 CSSR 是派生复合指标，不是独立 counter。

> ⚠️ **量纲陷阱：Retainability 根本不是百分比。**
> TS 28.554 §6.5 定义的是「异常释放次数 / 会话活跃时长」，**单位是次/秒**，是泊松强度参数，不是无量纲比例。这意味着**不能直接塞进 SRE 的 error budget 框架**（error budget 是无量纲比例），必须先做时间维度归一化。这是「电信 KPI ≠ 互联网 SLI」最锋利的一个例子——名字听着一样，量纲都对不上。

### 1.3 失真三：Throughput 的定义里藏着一条工程规则

3GPP 的吞吐量定义（TS 28.552 / LTE 对照 TS 36.314 §4.1.6.1，后者已核实原文）是「成功传输的 RLC SDU 数据量 / 传输时长」，但原文明确要求 **"shall exclude the volume of the last piece of data emptying the buffer"**——排除清空缓冲区的最后一片数据。

这不是排除信令开销，是排除**末端 burst-tail 效应**：最后一小块数据传完时链路已经空了，把它算进去会系统性低估吞吐。逻辑上等价于 SRE 语境里「排除长连接收尾的非代表性采样」。这个细节值得记住——它说明电信 KPI 的定义精细度往往高于互联网 SLI 的随手定义。

---

## 2. SLI 五层地图：这是「分层结论」的骨架

原始素材 1.4 节说「结论应该是分层的：第一眼结论和深入结论，但第一眼结论具体长什么样没想清楚」。

**电信业有现成的标准答案：TM Forum 的 KPI → KQI → CEI 三层模型**（GB962 CEM 框架）。把它和平台层拼起来，就是 vRAN 完整的五层 SLI 地图：

| 层 | 指标形态 | 谁看 | 回答什么问题 | 代表实现 |
|---|---|---|---|---|
| **L5 客户体验** | CEI / QoE MOS (1–5) | 业务侧、市场 | 用户满意吗？值不值得投资？ | Huawei CEI（GB962）；Ericsson ELI |
| **L4 服务质量** | KQI：按业务分的 accessibility / retainability / integrity | 服务运营中心 (SOC) | 哪个业务坏了？影响多少人？ | Ericsson SLI (Service Level Index) / CLI (Cell Level Index) |
| **L3 网元 KPI** | RRC 成功率、切换成功率、PRB 利用率、吞吐 | NOC / 网优 | 哪个小区坏了？ | 三大厂商 KPI 字典（五大族分类） |
| **L2 平台 SLI** | CPU 抢占、PTP offset、hugepage、DPDK imissed、FEC fallback | 云平台 / SRE | 底座还健康吗？ | node_exporter、Intel RDT、ptp4l、DPDK telemetry |
| **L1 硬实时** | deadline miss rate、cyclictest max latency | 平台验收 / 内核 | 这台机器还能跑 vRAN 吗？ | cyclictest / oslat / hwlatdetect |

**这个分层不是学术分类，是组织架构的分界线。** MYCOM OSI 的产品描述直说了：原始 KPI 留给 NOC / 工程团队，聚合后的 KQI/SLI/CEI 送给业务侧做变现。**指标分层对应的是「谁在看、要做什么决策」的分层。**

### 2.1 「第一眼结论」的具体形态

回答 1.4 节的留白——第一眼看的不是 CPU 曲线，是**四个成功率排成一行 + 一个可用性**：

```
接入成功率  |  承载建立成功率  |  Retainability  |  切换成功率  |  小区可用性
```

哪个红了，直接指向一整类问题域（见 1.2 的表）。然后才往下钻到 L3 网元 KPI → L2 平台 SLI → L1 硬实时。

**这就是 top-down 和 bottom-up 的实际分野。** 不是抽象的方法论差异，是**指标之间有没有因果链**的差异：

- Bottom-up 的「CPU 变化率 panel」孤立存在时只是噪音——CPU 冲高到底要不要半夜爬起来？没有上层 SLI 就永远答不了
- 一旦有了上层 SLI，同一个 CPU 指标的意义立刻变了：它不再是被观测对象，而是**「接入成功率掉了，往下查」这条路径上的第二跳**

指标本身没变，变的是它在因果链上的位置。

---

## 3. 排查：A + B = C 的分段定位，在 RAN 里是协议自带的

原始素材里的方法论——「A + B = C，C 有问题时判断是 A 还是 B」——在 fronthaul 上不需要我们发明，**O-RAN 直接把它写进了协议**。

### 3.1 T1a / T2a / Ta3 / Ta4：分段边界固化成协议约束

O-RAN WG4 CUS 规范定义了一组时间窗口：

- **T1a / Ta4**：O-DU 侧的发送 / 接收窗口（处理段）
- **T2a / Ta3**：O-RU 侧的接收 / 发送窗口（处理段）
- **T12 / T34**：网络传输段
- 关系式如下行的 `T1a = T12 + T2a`

包到得太早或太晚，O-RU **直接丢弃不处理**。也就是说「网络问题 vs 计算问题」的切分点是写进规范里的常量，不是靠事后猜。

**这是分段定位方法论的极致形态：把分段边界固化成协议约束。** 观测到耗时增加落在 T12/T34 → 怀疑 fronthaul 交换机排队 / 拥塞；落在 T1a/Ta4 → 怀疑 O-DU 处理超时。若是 PDV（包延迟变化）突增而非绝对延迟增加 → 怀疑没启 IEEE 802.1Qbv / Qbu 或 QoS 队列配置错。

> 未核实：T1a/T2a 等的**精确数值表**未能拿到 O-RAN 官方 PDF（>10MB 抓取失败）。网传的 "T2amin=100µs" 之类是二级来源的教学示例，**不可当规范数值引用**。概念和关系式是可靠的。

### 3.2 端到端分段预算表

| 段 | 典型量级 | 异常时怀疑什么 |
|---|---|---|
| 空口 scheduling | slot 级（0.125–1ms 随 numerology） | 时延升高但重传率不变 → 调度器排队（PRB 不足/并发 UE 暴增）；伴随重传率上升 → 信道质量（SINR/干扰） |
| Fronthaul 传输 | U-plane 典型 100µs（低至 25µs）；C-plane 1ms；S-plane 25–500µs；M-plane 100ms | 见 3.1 的窗口判据 |
| └ 光纤传播 | ~5µs/km 单向 | 与站间距成线性 → 正常；不成比例 → 设备段 |
| O-DU L1 (PHY) | 符号周期 ~35.7µs (30kHz/20MHz) | 单 slot 耗时逼近符号周期 → 核绑定失效 / 被抢占（裸机基带卡不会有这问题） |
| O-DU L2 (MAC 调度) | 每 slot 唤醒一次，只有几百µs 做决策 | VM 调度、上下文切换、cache miss、I/O 虚拟化开销 |
| Midhaul → O-CU (F1) | 1–2ms（20–40km） | 此段是统计型 IP 流量，波动指向 IP 传输拥塞，与无线侧无关 |
| Backhaul → UPF (N3) | NG-U 规范范围 1–50ms | P99 上升但 P50 稳定 → UPF 数据面排队/CPU 饱和，不是传输本身 |

关键的架构性区分：**RU–DU 段是「恒定速率、时间关键」（100µs 预算），DU–CU 以上是「统计型 IP 流量」（ms 级预算）**。两段的 QoS 类别完全不同，不能用同一套阈值思路。

**3GPP 侧也是分段统计的**：TS 28.554 §6.3.1.1 把下行时延拆成 `DLLat_gNB-DU = DRB.RlcSduLatencyDl` 和 `DLDelay_gNBCUUP = DRB.PdcpSduDelayDl + DRB.PdcpF1Delay`，单位 0.1ms，**各自独立 measurement，没有一个「UE 到核心网入口」的单一测量点**。

### 3.3 「最好的方式是 trace」——分层成立，不是普遍成立

| 层 | per-request trace 可行？ | 实际做法 |
|---|---|---|
| L1 / 空口 slot 级（µs、每 TTI） | **不成立**。开销和实时性都不允许运行时插桩 + context 传播 | 聚合 counter + 离线事件回放。OAI 的 **T-tracer** 是范本：实时线程只写 timestamp + 事件类型到共享内存，独立进程异步收集分析；配合短窗口 ftrace/perf 复现抓取 |
| L2/L3 信令、call 级（ms–s） | **部分成立**。能按 UE/call 串联，但是触发式、抽样激活、批量落盘的事后机制 | 3GPP Trace (TS 32.421/32.422)、MDT (TS 37.320)、CTR/CHR + 事后批处理关联。参考量级：STRCA 论文用华为真实 5GC 数据，172,060 条 trace 批处理耗时 107 秒，根因准确率 76.3%——**本质是批处理不是流式** |
| RIC / E2 KPM / O1（10ms–分钟级聚合） | **不成立**（作为分段定位工具）。上报的是 granularity period 内的聚合值，已丢失单次事务时序 | Cell/UE 级聚合 KPI 流 + xApp/rApp 闭环 |

> ⚠️ **术语碰撞（跨领域交流必踩）**：电信规范里的 "Trace"（TS 32.421/422 的 Signalling Based Trace、Cell Traffic Trace）和 OpenTelemetry 的 trace 是**同名不同物**。前者按订户激活、事后批量落盘；后者每请求实时生成、跨服务传播 context。MDT 同理，它做的是把 UE 侧无线测量关联回位置，替代人工 drive test，不是分段延迟归因工具。

**准确表述**：RAN 里跨物理段的分段定位确实在做，但载体不是 trace，而是**每段各自的聚合 counter + 协议内建时间窗口 + 时间戳半自动关联**。「一次请求一条 trace 贯穿全链路」在 RAN 里不存在，L1 层从未出现过。

---

## 4. vRAN 特有的失败模式：虚拟化多出来的那一层

这是 vRAN 区别于传统专用基带硬件的核心，也是 L2 平台 SLI 存在的理由。

| 类别 | 机制 | 观测手段 | 阈值/判据 |
|---|---|---|---|
| CPU | 核绑定失效、pod 抢占实时核 | `isolcpus` + PerformanceProfile；`ps -o psr` 核实；cyclictest 抓 spike | telco RAN 普遍不接受 **≥20µs** 的 latency spike |
| CPU | C-state 唤醒延迟 | `turbostat` 看 C-state 驻留 + cyclictest 对时点；`tuned-adm` 关深 C-state | **C6 及更深退出延迟可达 133µs+**——对 sub-10µs 的 PHY 处理是致命的 |
| CPU | SMI（系统管理中断） | `cyclictest --smi`；`hwlatdetect`（专测硬件/固件层） | **有则必查**，没有「低于多少算合格」这种数字 |
| CPU | kernel preemption | `ftrace` 的 `preemptirqsoff` tracer | PREEMPT_RT 下压测最大延迟可降至约 279µs（基线因平台而异） |
| 内存 | NUMA 跨节点 | `numastat`；K8s Topology Manager（对齐失败 → pod admission 失败，是可观测的失败模式） | 具体延迟倍数未查到权威量化 |
| 内存 | hugepage 不足 | node_exporter 的 `/sys/devices/system/node/*/meminfo` | **已知陷阱**：hugepage 预留但未被应用占用时会被 OS 计为 "used"，造成负载假象 |
| Cache | LLC 争抢（noisy neighbor） | Intel RDT via `resctrl` / `pqos`：CMT 监控 LLC occupancy，MBM 监控带宽，按 CLOS 分类 | Intel 官方 NFV 实验确认 LLC 是多租户 CNF 性能劣化主因之一 |
| 网络 | SR-IOV/DPDK 丢包 | DPDK telemetry `/ethdev/stats` | **`imissed`** → PMD 轮询跟不上；**`rx_nombuf`** → mbuf 池配置不足。这两种失败模式必须区分 |
| 时钟 | PTP 失锁 / offset 超限 | `pmc -u -b 0 'GET CURRENT_DATA_SET'`；OpenShift `linuxptp-daemon` 出 Prometheus 指标 | 见下方同步预算 |
| 加速卡 | ACC100/ACC200 队列积压、fallback 到软件 FEC | SR-IOV FEC Operator | **公开资料几乎是黑盒**，未查到队列 telemetry 具体名称与 fallback 检测方法 |

**可观测性成熟度排序**：PTP（有国际标准数字 + 专门 daemon）> CPU/cache（Intel 工具链成熟）> DPDK 网络（有接口但阈值靠经验）> 加速卡队列（几乎黑盒）。

### 4.1 时间同步：数字最硬的一层

- **O-DU 侧 max|TE|**：**LLS-C1 ≤ 1.420µs，LLS-C2 ≤ 1.325µs**（O-RAN.WG4.CUS.0-v14.00.01 Table 11.3.2.x，经 Renesas 在 ATIS 官方演讲 PDF 直引条款号+数值）。常被简化引用的「±1.5µs」是这两个精确值的四舍五入——**写文章用精确值**
- **O-RU 侧 |TE|**：常规 ≤80ns，增强型 ≤35ns
- **relative TAE**：Category A 130ns / B 260ns / C 1100–3000ns —— ⚠️ **这来自 ITU-T G.8271.2，不是 O-RAN 自己的条款**，不要说成「O-RAN 规定」
- **T-TSC 预算**：Class B 60ns / 增强型 15ns；每跳边界时钟常量误差 10–20ns
- **LLS-C1~C4 拓扑**：C1 = O-DU 直连作 master；C2 = 中间有交换机 (T-BC)；C3 = 独立 PRTC/T-GM；C4 = O-RU 本地 GNSS

### 4.2 平台验收：可以直接引用的数字

| 工具 | 合格线 | 出处 |
|---|---|---|
| **cyclictest** | max latency **< 20µs**，持续跑满 12 小时 | Red Hat OpenShift "Performing latency tests for platform verification"（4.9–4.18 各版本一致） |
| **oslat**（busy-loop 模拟 DPDK PMD） | 同样 < 20µs，建议与 cyclictest 交叉验证 | 同上 |
| **hwlatdetect** | 内核默认 gap > 10µs 即报告；**telco 行业验收线未查到** | kernel.org。用途：cyclictest 抓到 spike 且 hwlatdetect 同时抓到 → 问题在硬件/BIOS 层，内核调优解决不了 |
| 实测参考 | VMware 实测 < 10µs（裸机与 vSphere 7.0U3 均是） | 「良好调优的表现」，不是合格线 |

平台硬前提（已核实厂商文档）：
- **Red Hat Telco RAN DU 参考设计**：每 NUMA 节点保留 Core 0，1GB hugepages，**必须 RT kernel**，全部硬件支持 IRQ affinity
- **VMware Telco Cloud Platform RAN 2.2**：fronthaul 0–20km；基站侧至少两块同速率物理 NIC，其中一个 **SR-IOV VF 专供 PTP**；ESXi 需实时优化；基站侧用本地盘不用共享存储
- **Intel 4th Gen Xeon + vRAN Boost**：20 核（功耗优化 / 农村小站）/ 32 核（性能优化 / 密集城区 massive MIMO）；~2 倍容量（Intel 自估）；~20% 功耗节省

> **一个值得注意的空白**：Intel 公开文档里**没有任何一处给出 DU 处理时延预算的硬数字**（「L1 必须在 X µs 内完成」这类阈值完全没公开）。多次尝试抓 builders.intel.com 的 FlexRAN 白皮书全部 404。

**从平台前提违反 → 上层 SLA 后果的量化因果链，全网找不到。** 只有定性描述（「GNSS/PTP 丢失导致同步漂移，最终 UE 掉线」）和学术论文估算（CPU 争抢可致高达 40% 性能下降）。**没有任何厂商或运营商公开过「PTP 漂移 X ns → Y 次掉话」这种数据。** 这是整个领域最大的证据空白，也意味着**这条链是要自己在生产环境里测出来的**。

---

## 5. 商业契约层：RAN 的 SLA 为什么不能照抄 IT SLA

### 5.1 可用性三层，数字完全不同

| 层 | 典型数字 | 出处 |
|---|---|---|
| 网元/小区级 | TRAI：BTS 累计停机 ≤2%（2009）→ 收紧到 1.5% → 1%（2024 新规，改按小区计） | TRAI 2009/2024 规定 PDF |
| 端到端服务级 | ITU-T G.1028：**4G-4G/4G-固网通话可用性 99%；4G-3G 98%** | ITU-T G.1028 (2019) |
| 厂商示例 SLO | Ericsson 文章示例：「99.9% 的连接服务可用性，在约定速率和延迟下」 | Ericsson Technology Review |

监管口径差异极大：**FCC 完全没有法定可用性 % 目标**，它的抓手是 NORS 上报触发线（中断 ≥30 分钟**且**影响 ≥90 万「用户分钟」）——那是事故报告阈值，不是持续可用性 KPI。**BEREC 明说** 90%–100% 这个阈值由各国 NRA 自选，不是统一欧盟数字。**日本総務省、中国工信部、Ofcom 均未找到数字化可用性标准。**

### 5.2 为什么不能照抄——两个机制性原因

**（1）RAN 的宕机是地理性、渐进降级的，不是二元的。**
USPTO 9173106 给出了最清晰的解释：单个小区停机 ≠ 覆盖区失联，因为「受影响 UE 处于相邻小区覆盖重叠区的部分会被邻区补偿，实际信号丢失区域可能小于该小区的 Voronoi 覆盖区」。IT 系统是挂/不挂，RAN 是**一块地理区域的服务质量下降了多少**。

**（2）公开的「五个九」本身就是被口径修饰过的。**
Pipeline Publishing 那篇 *"Carrier-Grade: Five Nines, the Myth and Reality"* 点破得很直接：「不知道从何时起，单个网元的可靠性指标变成了整网可用性的衡量标准……客户不关心某个网元挂了，客户只关心他们付费的服务是否照常工作。」文章指出运营商公开的五个九，其实是**排除了计划性维护、主动修复事件、未被客户投诉的故障之后的 SLA 合规率**，不是原始 uptime。

工程上的应对是**分层叠加冗余**：在 99.9% SLA 的云平台上叠冗余机制，让上层 VNF 达到 99.999% 服务级 SLA——**元素级目标要比服务级目标严格约一个数量级**。

### 5.3 切片：SLA 契约化的当前状态

**GSMA NG.116 (GST) v8.0** 是这个方向最完整的公开文本，但关键发现是：**几乎所有属性都标记为 Optional**——它是一张「契约要素清单」，不是强制最低标准。

- Availability 分级：低 <90% / 中 90–95% / 高 >95–99.999% / 极高 >99.999%
- **Isolation level 原文写着 "Editor's note: FFS (For Further Study)"——隔离等级在 v8.0 里根本没定义任何数值**

GST 的 NEST 样例值得单独看：eMBB+IMS 99.999%、URLLC 99.999%、V2X 99.999%、HMTC 99.999%、**MIoT 只有 99.9%**。**即：GSMA 自己的样例里可用性几乎全挤在 99.9%–99.999%，真正的差异化变量是 5QI 和设备密度/速度，不是可用性本身。**

**5QI 表（TS 23.501 Table 5.7.4-1，经 ETSI TS 123 501 V18.5.0 原文核实）** 是 SLA 落到技术参数的关键桥梁：

| 5QI | 类型 | PDB | PER | 业务 |
|---|---|---|---|---|
| 1 | GBR | 100 ms | 10⁻² | 会话语音 |
| 2 | GBR | 150 ms | 10⁻³ | 会话视频 |
| 5 | Non-GBR | 100 ms | 10⁻⁶ | IMS 信令 |
| 9 | Non-GBR | 300 ms | 10⁻⁶ | 默认承载 |
| **82** | 时延关键 GBR | **10 ms** | **10⁻⁴** | 离散自动化 |
| 83 | 时延关键 GBR | 10 ms | 10⁻⁴ | 离散自动化 / V2X 车队 |
| 84 | 时延关键 GBR | 30 ms | 10⁻⁵ | 智能交通 |

**赔付条款的现实很骨感**：没有找到任何一份公开的、专门针对 5G 切片的赔付条款。Verizon NaaS SLA（2026-01）有真实赔付表（可用性 100%/99.95%/99.90%/99.50%/99.00%，按小时计赔 5%–10%/h，上限 25%–50% 月费），但**全文没提「网络切片」或 5QI，是传统托管专线产品**。Verizon 的「5G Network Slice – Enhanced Internet」宣传「SLA-backed」，但只给吞吐量数字（下行 200Mbps/上行 45Mbps），**没有公开的可用性承诺或赔付条款**。德国电信商用切片确认「带定制 SLA」，细节不披露。

**结论：切片 SLA 目前停留在「企业定制保密条款」或「SLA-backed 营销话术」阶段，还没有出现像 MPLS 专线那样公开、标准化的赔付表。**

### 5.4 多厂商解耦后责任归属：行业公开承认的空白

**O-RAN Alliance 没有任何规范定义跨厂商（O-DU / O-RU / O-Cloud / SI）的 SLA 责任归属规则。** 这不是没查到，是行业公开承认的空白。

SDxCentral 的经典描述：「当 Open RAN 出现故障，责任会散落到系统集成商、不同硬件软件供应商身上……没有一个『掐脖子』的对象，出了问题大家互相指责，最终把责任推给运营商。」

行业给出的是**两种相反的商业解法**，都不是标准：

1. **Rakuten Symphony 模式**——把多厂商组件打包成统一平台，商业上自己扛下「一个掐脖子对象」的角色，Tech Mahindra 作首选 SI，明确对外宣传目的就是避免甩锅
2. **Dish 模式**——直接否定「外包集成」这个前提。Dish 高管原话：「运营商的工作就是做集成，你不能把集成外包出去。」Dish 自己当 SI，并拿 NTIA 5000 万美元建 **ORCID**（Open RAN Center for Integration & Deployment）做中立测试验证

架构上最接近答案的是 **O-RAN 的 SMO / Non-RT RIC / rApp（R1 接口）**框架——它标准化了多厂商保障应用的接口，但解决的是**互操作性**，不是**法律责任划分**。其余手段（OTIC 中立实验室、TIP+VIAVI VALOR、Tier-1 运营商联盟的认证打标框架）全都是**部署前互操作验证，不是事后责任划分工具**。

---

## 6. 术语碰撞清单（跨领域讲这个话题必备）

这些是「同名不同物」，混用会直接产生误解，也是判断对方是不是真懂的分水岭：

| 词 | 电信语境 | 互联网/SRE 语境 |
|---|---|---|
| **SLI** | Ericsson 的 **Service Level Index**——一个 0–100 的用户体验复合分，带心理学加权，做 NPS 代理 | **Service Level Indicator**——一条原始测量曲线 |
| **Trace** | TS 32.421/422 的触发式、按订户激活、批量落盘的事后记录 | OpenTelemetry 式每请求实时 span 链 |
| **Retainability** | 次/秒（泊松强度） | 若类比「错误率」则量纲错误 |
| **Availability** | 地理性、渐进降级、按覆盖区加权，且公开数字通常已排除计划维护 | 二元 uptime |
| **Target** | 3GPP 明文「不是强制要求」的设计规格 | SLO 常被当作团队内部承诺 |

---

## 7. 回接原始素材 1.4 节：当年的真正缺口是什么

综合上面所有内容，可以给 1.4 节那个自问一个明确的答案：

**当年缺的不是指标，是指标之间的因果链，以及从技术 target 到运营判断的转化动作。**

三条具体的：

1. **「在 Grafana 建 CPU 变化率 panel」这个动作本身没错，错在它悬空。** 它属于 L2 平台 SLI，本来应该是「接入成功率掉了 → 往下查」这条路径上的第二跳。脱离上层 SLI，平台指标就只是噪音——因为它回答不了「要不要半夜爬起来」。

2. **「第一眼结论」是有标准答案的，而且当年触手可及。** KPI → KQI → CEI 是 TM Forum 的成熟框架，四个成功率排一行就是第一眼看板。没想到这一层，不是能力问题，是**没有意识到「指标该分层给不同角色看」这件事本身需要设计**。

3. **但这里有一个必须诚实承认的客观因素：这个领域的「该看什么」是封闭的隐性知识。** Ericsson / Nokia / Huawei 三家的 KPI 字典**全都没有官方公开版本**，能查到的全是 NDA 材料的第三方转载。O-RAN 规范要注册付费下载。这和互联网 SRE 有 Google SRE Book 这种公开正典完全不同。所以「当年没建立起 SLA 视角」里，有一部分是行业信息结构造成的，不全是个人认知盲区——但这**不能当成免责**，因为 top-down 思考问题的习惯本身是可迁移的，不依赖领域知识。

这也回答了原始素材 1.5 节那个张力（「当时做得浅」vs「做得不浅只是没意识到」）：**做的东西不浅（联邦架构、多源采集、存储分层都是真问题），但组织这些东西的框架是缺失的。** 有零件，没有装配图。这个判断比两个原始说法都更准确，也更适合做成长性叙事——它承认了当年的工作量和技术含量，同时准确指出了缺口的性质。

---

## 8. 证据强度与未证实清单

**高置信（已直读一手 PDF 原文）**：TS 38.211 numerology 表、TS 38.214 N1/N2 条款、TS 28.554 各 KPI 公式与量纲、TS 36.314 吞吐量定义、TR 38.913 URLLC/eMBB 目标值、TS 22.261 NOTE 9、TS 23.501 5QI 表、GSMA NG.116 v8.0、TRAI 2009/2024 规定、47 CFR §4.9、VMware TCP RAN 2.2、Intel vRAN Boost Fact Sheet、Red Hat OpenShift 延迟测试文档。

**中置信（多源交叉一致但未直读原文）**：TS 28.552 的 UL PDCP SDU Loss Rate 公式、5G 吞吐量定义、O-RAN S-plane TAE 数值（经 Renesas/ATIS 官方 slide 直引条款号）。

**明确未证实，不可当结论引用**：

1. O-RAN.WG4.CUS.0 中 T1a/T2a/Ta3/Ta4 的**精确数值表**（网传数字均为教学示例）
2. Fronthaul 常被引用的「单向 100µs 预算 / PDV <100ns / intrinsic latency <8µs」——未定位到 WG9.XTRP-REQ 原文
3. O-RAN WG6 O-Cloud 硬件加速的**量化性能门限**——多方确认公开层面只有接口/架构定义，无强制数值
4. PDU Session Setup Success Rate 在 TS 28.552 的精确计数器公式；TS 28.554 §6.8 Packet transmission reliability 完整定义
5. Intel FlexRAN 官方白皮书原文（builders.intel.com 相关 PDF 全部 404），及其中的 DU 时延预算硬数字
6. 「deadline miss rate 应取代 p99」这一论断的**规范性出处**——只有学术界的揭示性实践
7. 三大设备商官方域名托管的现行 KPI 字典
8. 任何运营商公开披露的 RAN/切片可用性数字 SLA（NTT Docomo、KDDI、Rakuten、中国移动、中国电信、Vodafone 全部未找到）
9. 专门针对 5G 切片的公开违约赔付条款
10. 从平台前提违反到 SLA 后果的**量化因果链**（PTP 漂移 X ns → Y 次掉话）
11. ACC100/ACC200 队列 telemetry 具体名称与软件 FEC fallback 检测方法
12. hwlatdetect 的 telco 行业验收阈值
13. 日本総務省 / 中国工信部 / Ofcom 的数字化网络可用性监管标准
14. TS 22.104（Rel-16 起接替 TS 22.261 行业场景表）原文
