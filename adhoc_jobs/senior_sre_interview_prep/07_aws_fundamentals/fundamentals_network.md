# AWS Fundamentals：Network (VPC / 负载均衡 / DNS)

这一节的考点在哪：网络是我在 50 集群、6 region 实战里踩坑最多的一层，但也是最容易被问出"教科书背了但没用过"破绽的一层。面试官如果懂行，会顺着"跨集群故障转移怎么做"往下问到 DNS TTL 的物理下限、ENI 和 Pod 密度的关系、SG 和 NACL 评估顺序这几个具体点。这节尽量把每个理论点都挂回我们真实的 K8s-on-AWS 网络排障方法论，挂不回去的就明确标成理论。

## 1. VPC / 子网 / 路由表 / IGW / NAT

**面试官会怎么问**：VPC 的基本组件怎么串起来？NAT Gateway 有什么成本陷阱？

**标准答案（理论骨架）**
- VPC 是隔离的虚拟网络，子网是 VPC 内按 AZ 划分的地址段，路由表决定子网内流量去哪（本地路由 vs 出 IGW vs 出 NAT vs 出 VPC Peering/Transit Gateway）。Internet Gateway（IGW）给有公网 IP 的资源提供双向互联网访问；NAT Gateway 给私有子网内无公网 IP 的资源提供**出网**访问（私有资源发起连接，外部不能主动连进来）。
- **NAT Gateway 的成本与带宽陷阱**：按小时计费 + 按处理的数据量（每 GB）计费，且有带宽上限（单个 NAT Gateway 约 45Gbps，超过需要多个或用 NAT Instance 自建）；很多团队第一次收到 AWS 账单大头是 NAT Gateway 的数据处理费，尤其是当私有子网里的服务频繁访问 S3/其他 AWS 服务时：这些流量本可以完全绕开 NAT（走 VPC Endpoint），却被默认路由表送去 NAT 转了一圈。

**我的场景锚点**
- 标准生产布局（`interview-8-k8s-cluster-build.md`）：VPC 跨 3 AZ，Public 子网放 NLB/NAT Gateway/堡垒机，Private 子网放 master/worker（无公网 IP，出网走 NAT）；这是我实际参与设计和维护的分层原则，不是背书本。
- 真实 repo 现状有一处已知差距：某测试集群配置是单 AZ + public/private 子网复用（同一个 subnet ID），这是明确标注的"测试集群妥协，生产必须改跨 AZ"的例子，我们在真实运维文档里显式记录了这个差距而不是假装它不存在。
- CIDR 分层：VPC CIDR（节点网络）、Pod CIDR（`192.168.0.0/16`，CNI 管）、Service CIDR（`10.96.0.0/16`，kube-proxy/CoreDNS 管）三个独立平面绝不能重叠，这条是我们 K8s 网络设计的硬约束。

**如果被追问到边界**：生产环境具体 VPC CIDR、精确子网划分（哪些是 3 AZ、哪些还是遗留单 AZ）没有素材完整覆盖全部 50 个集群，`⚠️ 待确认：50 集群里有多少仍是单 AZ 遗留配置`。

---

## 2. SG vs NACL

**面试官会怎么问**：Security Group 和 NACL 有什么区别？评估顺序是怎样的？

**标准答案（理论骨架）**
- **SG（有状态）**：作用在 ENI 层面，只需要放行一个方向（比如放行入站 443，回程流量自动放行，不需要显式配出站规则对应回程），只支持 Allow 规则（没有 Deny），一个实例可以关联多个 SG，多个 SG 的规则取并集。
- **NACL（无状态）**：作用在子网层面，入站和出站必须**分别显式放行**（回程流量不会自动放行），支持 Allow 和 Deny（按规则号从小到大顺序评估，第一条匹配的生效），默认 NACL 全放行，自定义 NACL 默认全拒绝。
- 评估顺序：一个请求要同时通过子网级 NACL（入+出）和实例级 SG（有状态方向）才能通；NACL 更适合"整个子网级别的粗粒度阻断"（比如封禁一个已知恶意 IP 段），SG 更适合"这个服务该被谁访问"的精细授权。

**我的场景锚点**
- 我们生产 SG 设计是**刻意的粗粒度信任边界**策略：内部 SG 对整个 VPC CIDR、VPN CIDR、管理网 CIDR 全协议放行，出站全放行；东西向的端口级隔离**下放给 CNI 的 NetworkPolicy**，而不是在 SG 层做逐端口最小化（`interview-8-k8s-cluster-build.md` §2(b)）。这是一个有意识的权衡：好处是加组件不用改 SG，坏处是集群内部零隔离，一旦有 Pod 被攻陷可以横向打全 VPC，这条在我们的"安全债"清单里是显式记录的已知代价，不是没意识到。
- **真实踩过的坑（值得讲）**：我们用 Calico IPIP 模式，跨节点 Pod 流量走的是 **IP protocol 4（IPIP 封装）**，不是常规的 TCP/UDP 端口。如果 SG 收紧成逐端口最小化，最容易漏放行的就是这个 protocol 4，一旦漏放，跨节点 Pod 完全不通，而这个故障现象和"端口没配对"很像，容易走错排障方向。
- NACL：素材中没有证据表明我们对 NACL 做过定制（大概率用默认全放行 NACL，隔离全部下放到 SG+CNI 层），`⚠️ 待确认：是否有任何环境自定义了 NACL`。

---

## 3. ENI 与 IP 分配

**面试官会怎么问**：K8s 的 Pod 密度是怎么受 ENI 限制的？你们 600+ 节点怎么应对？

**标准答案（理论骨架）**
- 每个 EC2 实例可挂载的 ENI 数量、每个 ENI 可分配的私有 IP 数量都由实例类型决定（越大的实例支持越多 ENI 和每 ENI IP 数）；这个上限直接决定了"VPC 原生 IP 分配模式"下单节点能起多少 Pod（比如 AWS VPC CNI 默认给每个 Pod 分配一个真实 VPC IP，节点的 Pod 上限 = ENI 数 × 每 ENI IP 数，通常还要减去实例自身占用的 IP）。
- 这个约束只在"Pod 直接用 VPC IP"（VPC 原生 CNI）模式下成立；如果 CNI 走 overlay 封装（Pod 网段独立于 VPC），Pod 密度就不再受 ENI/VPC IP 配额约束，改为受 CNI 自身的 IP 池设计约束。

**我的场景锚点**
- 我们的 CNI 选型是 Calico IPIP（Pod 走独立于 VPC 的 `192.168.0.0/16` 网段，跨节点靠 IPIP 隧道封装），这个模式下 **Pod 密度不受 ENI/VPC IP 配额约束**：这是我们选 overlay 而不是 VPC 原生模式的一个直接后果（即便 repo 里同时支持 Cilium ENI 模式）。这个区分本身是回答"600+ 节点、Pod 密度会不会被 ENI 卡住"这个问题的正确框架：先说清楚"这取决于 CNI 模式"，再说明我们用的模式不受这个约束，而不是不假思索地背"K8s 有 ENI 限制"。
- 如果集群启用 Cilium ENI 模式（`eni.enabled=true`，`awsEnablePrefixDelegation=true`），才会真正吃 ENI/VPC IP 配额，这时候子网 IP 容量必须提前算清楚，否则会遇到"子网 IP 耗尽，Pod 起不来"这一 Cilium ENI 模式下最常见的事故：这条我们的运维文档里明确写了权衡取舍表。

**如果被追问到边界**：见下一节 CNI 的诚实边界标注。

---

## 4. CNI 与 VPC 网络的接缝

**面试官会怎么问**：你们用什么 CNI？为什么选它？

**我的场景锚点（先说清楚证据边界）**
- 我们的 IaC repo（Packer+Ansible+kubeadm）里，CNI 是**可配置的两选一**：默认 **Calico IPIP**（`cilium_install=false`，跨节点 Pod 流量走 IPIP 隧道封装，Pod IP 独立于 VPC、不占 VPC 地址，代价是封装 MTU 开销约 20B、Pod IP 在 VPC 层不可见即 SG/流日志看不到）；可选 **Cilium ENI**（`cilium_install=true`，不封装、Pod 直接拿真实 VPC IP、eBPF 替代 kube-proxy、性能更接近裸金属，代价是消耗 VPC IP 且强耦合 AWS）。
- **⚠️ 待确认：我们 50 个生产集群实际启用的是 Calico 还是 Cilium，或者两者都有（不同集群不同选择）**。repo 层面的默认值是 Calico，但默认值不等于生产实际配置，素材没有给出跨 50 集群的确切分布，这条我不编造，留给瑞哥自己核实。
- 不管哪种 CNI，我确认过的排障方法论是一致的：Client → DNS → AWS LB → Ingress/Service → Pod 的分层排障（见第 9 节），这条与具体 CNI 无关，是更底层的通用方法。

**如果被追问到边界**：能讲清两种 CNI 的权衡取舍（这是我读过 repo 源码得出的结论，不是纯背概念），但不能确定回答"我们生产用的是哪个"，如果被逼问，诚实答法是"这是我材料整理时发现的一个待确认项，repo 支持两种、默认 Calico，具体哪个集群用哪个我需要回去核实，不敢在面试现场编"。

---

## 5. 跨 AZ 流量费与延迟

**面试官会怎么问**：跨 AZ 流量为什么要小心？

**标准答案（理论骨架）**`[理论，成本量化见 06 目录]`
- 跨 AZ 数据传输按方向双向计费（发送方和接收方都可能被计费一次，取决于具体服务），同 AZ 内流量通常免费；跨 AZ 延迟通常在个位数毫秒，远低于跨 region，但在高频调用链路（比如数据库多副本同步、微服务链路里每一跳都跨 AZ）上会累积成有意义的尾延迟。
- 典型陷阱：为了高可用把服务多 AZ 部署是对的，但如果没有做"同 AZ 优先路由"（K8s 的 Topology Aware Routing/`internalTrafficPolicy=Local` 之类的机制），流量可能大量无谓跨 AZ 传输，同时拉高延迟和账单。

**我的场景锚点**：我们的 3 master 跨 3 AZ 是为了 etcd quorum 容错（HA 需求压倒同 AZ 优化），这是一个"故意接受跨 AZ 通信延迟换取容错"的例子。至于业务流量层面是否做了同 AZ 优先路由优化，`⚠️ 待确认`，没有素材佐证；跨 AZ 流量的成本量化和治理策略归 06 目录（AWS cost/FinOps）覆盖，这里只讲机制不重复数字。

---

## 6. ELB 谱系

**面试官会怎么问**：ALB/NLB/CLB 怎么选？target group 健康检查怎么配？

**标准答案（理论骨架）**
- **ALB（L7）**：理解 HTTP/HTTPS，支持基于 host/path 的路由、WebSocket、gRPC（需要额外配置）；适合需要应用层路由决策的场景，会做 TLS 终止。
- **NLB（L4）**：只做 TCP/UDP/TLS 透传，不理解应用层协议，延迟更低、吞吐更高、支持静态 IP/弹性 IP，适合需要 L4 透传（不终止 TLS）或极高性能的场景。
- **CLB（Classic，遗留）**：旧一代，功能介于两者之间，新项目基本不再用。
- Target group 健康检查：可配置协议/端口/路径/间隔/阈值，不健康目标自动摘除，"connection draining"（现在叫 deregistration delay）让正在处理的连接优雅结束再摘除目标，避免生硬掐断。
- 跨区域负载均衡（cross-zone load balancing）：决定流量是否均匀打到所有 AZ 的所有目标，还是优先本 AZ 目标；ALB 默认开启且不计费，NLB 需要显式开启且开启后跨 AZ 部分要计数据传输费。

**我的场景锚点**
- 我们的 apiserver 入口用的是 **internal NLB**（L4），原因很明确：apiserver 是 TLS+gRPC，需要 L4 透传不做 TLS 终止；`scheme=internal` 让控制面只在 VPC 内可达。Target Group 是 TCP 6443，健康检查 10 秒间隔/阈值 3；任一 master 挂掉，NLB 自动摘除该后端，控制面不中断（`interview-8-k8s-cluster-build.md` 步骤 4）。
- 业务流量入口走 `type=LoadBalancer` + `aws-load-balancer-type: nlb` annotation，由 CCM 建业务 NLB，后面接 ingress-nginx 按 Host/Path 路由（本质是 NLB 做 L4 转发，L7 路由交给 ingress-nginx 自己做，而不是在 ALB 层做）。

---

## 7. Route53（DNS 层，含故障切换的物理下限）

**面试官会怎么问**：Route53 的路由策略有哪些？DNS 层做故障切换，下限能压到多快？

**标准答案（理论骨架）**`[理论]`
- 路由策略：Simple、Weighted（按权重分流量）、Latency-based（按延迟选最近 region）、Failover（主备，配合健康检查自动切换）、Geolocation/Geoproximity、Multivalue answer。
- 健康检查：Route53 定期探测目标端点，失败达到阈值后把对应记录从 DNS 响应里摘除（Failover/Multivalue 路由策略下生效）。
- **TTL 与故障切换的时间下限**：DNS 记录有 TTL，理论上 TTL 到期后客户端会重新解析拿到新记录；但实际下限远比"改一下 TTL"复杂：很多客户端/操作系统/中间代理会**忽略或延长**实际的 DNS 缓存时间（不遵守 TTL），加上应用层连接池可能持有已建立的连接不会因为 DNS 变了就主动断开重连；所以"DNS 层故障切换"在真实世界里的下限通常是分钟级，不是秒级，即便把 TTL 设到几秒。

**为什么生产系统通常不把切换点放在 DNS 层** `[理论]`
- DNS 层故障切换的时间下限由三件事共同决定：记录 TTL、客户端与中间解析器是否真的遵守 TTL、以及已建立连接的生命周期。前两条决定新连接多久才会解析到新地址，第三条决定旧连接什么时候才消失。JVM 一类的客户端库默认可能永久缓存解析结果，连接池只要连接没断就一直复用，所以把 TTL 调到几秒并不能把切换时间压到几秒。
- 因此需要秒级生效的切换点通常放在 DNS 之后的转发层：ALB target-group 权重、API Gateway 路由指向、Global Accelerator 端点权重、K8s Ingress canary 权重。这些都是在**连接建立之后仍然生效**的转发层决策，客户端不需要重新解析域名，也不需要重建连接。DNS 只负责把客户端带到入口，入口之后怎么分流由转发层说了算。
- Global Accelerator 在这个模型里的位置值得单独说：它用 Anycast 静态 IP 做入口，客户端解析到的 IP 长期不变，故障转移发生在 AWS 全球网络内部的端点权重上，等于把"客户端要重新解析"这个变量整个拿掉。
- 反过来说，DNS 层依然有它合适的位置：region 级别的容灾切换、按地理位置分配入口、以及可以接受分钟级收敛的场景。判据是这次切换的目标 RTO 是否宽于 DNS 缓存的现实收敛时间。

**如果被追问到边界**：Route53 的加权/地理路由策略我没有配置过，`[纯理论，无一手经验]`；DNS 排障（CoreDNS vs Route53 的分层判断）有实战经验，见第 9 节。

---

## 8. VPC Endpoint / PrivateLink

**面试官会怎么问**：VPC Endpoint 是什么？怎么帮你省 NAT 费用？

**标准答案（理论骨架）**`[理论]`
- **Gateway Endpoint**（仅支持 S3 和 DynamoDB）：在路由表里加一条指向 S3/DynamoDB 的路由，流量不经过 NAT/IGW，完全在 AWS 网络内部走，免费（不额外计费）。
- **Interface Endpoint**（PrivateLink，支持绝大多数其他 AWS 服务）：在子网内创建一个 ENI，通过私有 DNS 把服务域名解析到这个 ENI，流量走 PrivateLink 而不出公网，按小时+按处理流量计费（比 NAT 便宜但不是免费）。
- 典型收益：私有子网里的服务大量访问 S3 时，配置 Gateway Endpoint 可以完全消除这部分 NAT Gateway 的数据处理费。

**我的场景锚点**：这条是明确的补课项。Doris/VictoriaMetrics 都大量读写 S3（Doris tablet 存储、VM 冷存储归档），如果这些流量目前是经过 NAT Gateway 出去再回来，S3 Gateway Endpoint 会是一个立等可用的省钱点；但素材里没有证据表明我们已经配置了 S3 Gateway Endpoint。`⚠️ 待确认：是否已配置 S3 Gateway Endpoint，还是 S3 流量目前经 NAT`。如果面试现场被问到这条，诚实且加分的答法是主动提出"这是我复盘时发现的一个可能的成本优化点，值得回去核实"，而不是假装已经做了。

---

## 9. 常见网络排障方法（真实一手方法论）

**面试官会怎么问**：K8s on AWS 网络故障怎么排查？给我一个思路。

**标准答案 + 我的场景锚点（这条几乎全是一手经验，直接融合讲）**

统一请求路径心智模型：`Client → DNS → AWS LB(ALB/NLB) → Node/Ingress → Service → Pod → App`（`pattern-aws-k8s-networking-troubleshooting-pattern.md`）。

**第一刀：先按症状分类，不要先猜原因**
- **Timeout**：更可能是路由没通、health check 失败、target group 不健康、SG/NACL/路由表拦截、ingress 到 backend 之前链路阻断。
- **Connection refused**：更可能是这一跳根本没有 listener（ingress 没真正加载 tcp-services 端口、Service `targetPort` 配错、后端进程只绑定在 `127.0.0.1`）。
- **High latency with normal upstream**：更可能是 ingress 排队/连接复用/重试行为、endpoint 抖动、edge 层（如 APISIX）本身的处理延迟，不是 upstream 真的慢。

**分层排障顺序（由外到内，只在第一个失败点停下）**
- L0 确认症状：`dig +short <domain>`、`curl -vk --connect-timeout 3 --max-time 10 <url>`。
- L1 AWS 边缘：确认 LB 类型和 listener/target group/health check、确认来源是否被 SG/NACL/WAF 允许。
- L2 集群入口（Ingress/Gateway）：ingress controller pod 是否健康、日志里配置同步是否成功。
- L3 Service 路由：`kubectl get svc/endpointslice`，确认 Service 有非空的 Endpoints。
- L4 Pod/应用：`kubectl describe pod`、`kubectl logs`、`kubectl exec -- ss -lntp` 确认进程真的监听在预期地址端口。

**核心原则（这条比任何单个命令都值钱）**
- **Control-plane truth ≠ data-plane truth**：ConfigMap 存在不等于 ingress 已经 reload 并监听这个端口；Service 存在不等于 Endpoints 非空；Endpoint 存在不等于进程监听地址正确；DNS 解析正确不等于 target group 健康。任何一步都要同时看"对象存在"和"流量真的会经过它"两件事。
- **只在第一处失败点停下，不要同时查 5 层**：前一跳没通，后一跳的状态没有解释价值，这是控制排查范围、避免"5 层同时开表格瞎猜"的关键纪律。

**我的场景锚点**：这套方法论是我们团队在 50 集群、6 region 环境下反复验证过的排障语法，能跨 DNS/AWS LB/Ingress/Service/Endpoint/Pod 反复复用，而不是针对某一次具体故障临时拼出来的。它也是"DNS 只是入口映射层，不是世界本身"这条认知的实践版本：DNS 解析对了只能说明域名指向正确的入口，完全不能推出后面 ingress/target/backend 都健康。

**如果被追问到边界**：这套方法论本身很扎实，但具体到"BGP session 断开的秒数"这类和 CNI 具体实现（BGP vs VXLAN）强绑定的细节，`⚠️ 待确认`，没有素材支撑到这个精确度，不编造具体数字。
