---
metadata:
  kind: case
  status: draft
  summary: "ingress-nginx helm upgrade 重建 ValidatingWebhookConfiguration 时 caBundle 丢失，导致所有 helm install 经 admission webhook 失败（x509 unknown authority），多 tenant Flink batch job 批量失败"
  tags: ["ingress-nginx", "admission-webhook", "helm-upgrade", "x509", "caBundle", "cluster6", "change-management", "multi-tenant"]
  first_action: "diff ValidatingWebhookConfiguration.webhooks[].clientConfig.caBundle 与 ingress-nginx-admission Secret.data.ca"
  related:
    - "runbooks/runbook-ingress-nginx-tcp-services-nlb-port-config.md"
    - "cards/card-nginx-fast-triage.md"
  derived_from: "/Users/rshao/work/work-harness/cases/2026-04-16_1500_flink-batch-cabundle-failure.md"
---

# Case: ingress-nginx Admission Webhook caBundle Stale post-upgrade

## TL;DR（5 步）

1. **告警信号**：多 tenant 同时 Flink batch job 失败 + helm install 报错含 `x509: certificate signed by unknown authority` + `validate.nginx.ingress.kubernetes.io`
2. **关键发现**：`ValidatingWebhookConfiguration ingress-nginx-admission` 的 `caBundle` 字段缺失 / 与 Secret `ingress-nginx-admission` 的 CA 不一致
3. **根因**：近期 ingress-nginx helm upgrade 重建了 webhook config，但 caBundle 未注入 / 未从 Secret patch 回来 → apiserver 无法验证 webhook TLS 证书 → 所有含 Ingress 资源的 helm install 全失败
4. **修复**：从 Secret 读 CA 并 patch 回 webhook config 的 caBundle 字段（`#MANUAL`）
5. **后续**：改用 cert-manager 管理 webhook 证书；加 canary 监控定期 dry-run ingress 创建

## 信号

```yaml
alertname: Flink batch jobs failing cluster-wide (helm INSTALLATION FAILED)
cluster: aws-uswest2-prod-a   # → alias kwestproda
cluster_alias: kwestproda
namespace_application: dcluster
namespace_root_cause: ingress-nginx
multi_tenant: true             # nasa task 47805 + sofi task 27903 within same minute
error_signature:
  - "x509: certificate signed by unknown authority"
  - "validate.nginx.ingress.kubernetes.io"
  - "ingress-nginx-controller-admission.ingress-nginx.svc:443"
recent_change: ingress-nginx helm upgrade（本次 2026-04-16T03:09:28Z 重建 webhook config）
jira: PI-145452
```

## Evidence Chain

**Step 1 — 确认 webhook config caBundle 状态**（read-only）:
```bash
# INTENT: 读当前 caBundle 字段，应该非空
kwestproda get validatingwebhookconfiguration ingress-nginx-admission -o yaml | grep -A2 caBundle
```

**Step 2 — 对比 caBundle vs Secret**（read-only）:
```bash
# INTENT: 若两者不一致或 webhook caBundle 为空，即为根因
diff <(kwestproda get validatingwebhookconfiguration ingress-nginx-admission \
         -o jsonpath='{.webhooks[0].clientConfig.caBundle}') \
     <(kwestproda get secret ingress-nginx-admission -n ingress-nginx \
         -o jsonpath='{.data.ca}')
```

**Step 3 — 确认升级时机**（read-only）:
```bash
# INTENT: 确认 webhook config 重建时间是否和告警时间接近
kwestproda get validatingwebhookconfiguration ingress-nginx-admission \
  -o jsonpath='{.metadata.creationTimestamp}'
helm history ingress-nginx -n ingress-nginx
```

**Step 4 — 排除 webhook pod 本身故障**（read-only）:
```bash
# INTENT: controller pod running/ready 说明不是 pod 层面问题
kwestproda get pods -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
```

## 因果链

nginx ingress helm upgrade → ValidatingWebhookConfiguration 重建 → caBundle 丢失 → apiserver 无法验证 admission webhook TLS → 所有 `helm install`（含 Ingress 资源）经过 webhook 时被拒 → 下游 batch job（如 flink-session-cluster）启动失败 → 多 tenant 同时受影响（因为 webhook 是 cluster-wide 基础设施）

## 结论

**根因 likely 是**：ingress-nginx helm chart 的 admission webhook 证书管理由 helm hook 一次性生成；升级时 hook 重跑生成新 CA 到 Secret，但 webhook config 的 caBundle 字段未被同步 patch。在 webhook config 被重建但 caBundle patch 步骤未完成的窗口内，所有 admission 请求失败。

**为什么多 tenant 同时失败**：admission webhook 是 cluster-wide，所有经过它的 `helm install` 都被 block；Flink batch job 通过 dcluster helm install 启动 session cluster，所以批量失败。这是排除应用层根因的强信号。

## 建议操作

### 诊断（只读，可直接执行）

| # | 命令 | 目的 |
|---|------|------|
| 1 | `kwestproda get validatingwebhookconfiguration ingress-nginx-admission -o yaml \| grep -A2 caBundle` | 看 caBundle 是否为空 |
| 2 | `diff <(kwestproda get validatingwebhookconfiguration ingress-nginx-admission -o jsonpath='{.webhooks[0].clientConfig.caBundle}') <(kwestproda get secret ingress-nginx-admission -n ingress-nginx -o jsonpath='{.data.ca}')` | 确认 caBundle 与 Secret 一致性 |
| 3 | `kwestproda get events -n ingress-nginx --sort-by='.lastTimestamp' \| tail -30` | 看最近是否有 webhook 或 controller 事件 |
| 4 | `helm history ingress-nginx -n ingress-nginx` | 确认升级时间 |

### 修复（`#MANUAL`，需人工确认后执行）

```bash
#MANUAL
# INTENT: 从 Secret 读取 CA，patch 回 webhook config 的 caBundle 字段
# 影响面：恢复全集群 ingress admission webhook → 解锁所有 helm install
# 风险：低。Patch 是 add 操作，不覆盖已有数据；如 caBundle 已存在则 apply 失败（再切成 replace）
kwestproda patch validatingwebhookconfiguration ingress-nginx-admission \
  --type='json' \
  -p="[{\"op\":\"add\",\"path\":\"/webhooks/0/clientConfig/caBundle\",\"value\":\"$(kwestproda get secret ingress-nginx-admission -n ingress-nginx -o jsonpath='{.data.ca}')\"}]"
```

### 验证（修复后）

```bash
# 1. dry-run ingress 创建，看 webhook 是否通过
kwestproda create ingress test-webhook-verify \
  --rule="test.example.com/=test-svc:80" \
  --class=nginx --dry-run=server -o yaml

# 2. 重试一个失败的 Flink task
# （通过 dcluster API 重跑 task 47805 或 27903）
```

### 回滚

若 patch 后 webhook 仍失败：
```bash
#MANUAL
# INTENT: 删除 caBundle 字段让 ingress-nginx 重新注入（某些 helm chart 版本会 auto-inject）
kwestproda patch validatingwebhookconfiguration ingress-nginx-admission \
  --type='json' \
  -p='[{"op":"remove","path":"/webhooks/0/clientConfig/caBundle"}]'
# 触发 controller 重启让 hook 重新跑
kwestproda rollout restart deployment ingress-nginx-controller -n ingress-nginx
```

## 关键教训

- **多 tenant 同时同机制失败 → 强 cluster-wide 基础设施信号**：第一反应不应该是应用层（Flink、job logic），而是 ingress / DNS / API server / admission webhook 这类共享组件
- **`x509: certificate signed by unknown authority` + webhook 名** = admission webhook TLS 问题；webhook 名反指向拥有者（这里是 ingress-nginx）
- **近期 helm upgrade + webhook failure** 是典型 change-management 回归；routing 到 triage Cluster 6，不要误路由到 Cluster 1（ingress/routing 本身）或 Cluster 3（stateful pressure）
- **Helm hook 生成的证书不是 cert-manager 管理的证书**：前者一次性、无 rotation；后者可 auto-rotate。长期防复发应迁移到 cert-manager
- **admission webhook 失败的 blast radius 广**：阻断所有经过 webhook 的 K8s API 写入；缓解优先于根因调查
