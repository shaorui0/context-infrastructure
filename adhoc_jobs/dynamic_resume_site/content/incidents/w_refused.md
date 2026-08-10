# META
id: w-inc-refused
kicker_en: INCIDENT
kicker_cn: 事故
title_en: Refused is not timeout
title_cn: refused 不是 timeout
sub_en: Two words that halve the search space, and two root causes found by walking eight hops.
sub_cn: 两个词把搜索空间砍半；走完八跳找到两个根因。
domains: [incident, obs]

# EN

## Symptom

External connections to a database service failed instantly with `connection refused`. Instantly is the clue: *refused* means the packet arrived and nothing was listening — fast and deterministic. *Timeout* means a listener exists but is not answering. The two words point at different halves of the stack, and conflating them wastes the first hour.

## Walk the hops, stop at the first failure

The path had eight hops: client → DNS → load balancer → NodePort → ingress → Service → Endpoints → pod. The method is unglamorous: verify each hop actually listens or resolves, in order, and stop at the first one that fails. On this class of incident it has produced two different root causes:

- **The listener that looked configured.** The ingress controller's TCP-services ConfigMap existed with the right entries — but the controller had never loaded it. Configuration present, listener absent. Everything upstream of the ingress was innocent by inspection.

- **The label that went stale.** Subtler: after an abnormal pod restart, the database operator failed to refresh the pod's readiness label. The Service selector required that label, so the Endpoints list was empty — the Service existed, the pod was actually serving, and no traffic could ever arrive. Control-plane truth had diverged from data-plane truth, and only the Endpoints hop showed it.

## Fix and verify

Reload the controller in the first case; restart the workload so the operator re-evaluates its labels in the second. Verification mirrors the diagnosis: confirm the port is actually in a listening state and the Endpoints list is non-empty — the two exact things that were broken, not a generic health check.

> Symptom classification before tooling: refused vs. timeout, then hop by hop. The method is boring, which is why it works at 3 a.m.

# CN

## 症状

外部连接数据库服务瞬间失败，报 `connection refused`。「瞬间」就是线索：*refused* 意味着包到了、没人在听，快速且确定。*timeout* 意味着有监听者但不应答。两个词指向栈的不同半边，混为一谈会浪费掉第一个小时。

## 逐跳走，停在第一个失败处

链路有八跳：client → DNS → 负载均衡 → NodePort → ingress → Service → Endpoints → pod。方法毫无花哨：按序核实每一跳确实在监听或解析，停在第一个失败的跳。在这类事故上，它找到过两个不同的根因：

- **看起来配置了的监听者。**ingress controller 的 TCP services ConfigMap 存在且条目正确，但 controller 从未加载它。配置在，监听者不在。ingress 上游的一切当场无罪。

- **变陈旧的标签。**更隐蔽：一次异常重启后，数据库 operator 没有刷新 pod 的就绪标签。Service 选择器要求那个标签，于是 Endpoints 是空的：Service 存在、pod 实际在服务，而流量永远到不了。控制面真相偏离了数据面真相，只有 Endpoints 这一跳暴露它。

## 修复与验证

第一种情况 reload controller；第二种重启工作负载，让 operator 重新评估标签。验证与诊断互为镜像：确认端口真的处于监听状态、Endpoints 非空。就是坏掉的那两件事，不是一个泛泛的健康检查。

> 先分类症状再上工具：refused 还是 timeout，然后逐跳。方法很无聊，所以它在凌晨三点也管用。
