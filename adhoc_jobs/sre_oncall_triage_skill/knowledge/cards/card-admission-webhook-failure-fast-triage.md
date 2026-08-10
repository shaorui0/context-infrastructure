---
metadata:
  kind: card
  status: draft
  summary: "Admission webhook failure 快速定位：多 tenant / 多 helm install 同时失败 + x509 错误 → 查 caBundle"
  tags: ["card", "admission-webhook", "ingress-nginx", "x509", "webhook", "helm", "oncall", "change-management"]
  first_action: "diff ValidatingWebhookConfiguration caBundle vs admission Secret CA"
  related:
    - "cases/case-ingress-nginx-admission-webhook-cabundle-stale.md"
    - "cards/card-nginx-fast-triage.md"
---

# Card: Admission Webhook Failure — Fast Triage

## TL;DR（最多 3 分钟）

符合以下组合 → 直接走本 card：
- 多个不相关 tenant / namespace / helm install 在同一分钟开始失败
- 错误含 `x509: certificate signed by unknown authority`
- 错误含 `failed calling webhook "<webhook-name>"`（如 `validate.nginx.ingress.kubernetes.io`）
- 近期（< 24h）相关 component 有 helm upgrade / 重部署

**根因大概率**：ValidatingWebhookConfiguration 的 `caBundle` 字段 stale / missing / 与对应 admission Secret 的 CA 不一致。

## Step 1 — 从 webhook 名定位 owner

Error 里的 `webhook "<name>"`：
| Webhook 名 | Owner | Secret name | Namespace |
|---|---|---|---|
| `validate.nginx.ingress.kubernetes.io` | ingress-nginx | `ingress-nginx-admission` | `ingress-nginx` |
| `cert-manager-webhook` | cert-manager | `cert-manager-webhook-ca` | `cert-manager` |
| `kyverno` | kyverno | — | `kyverno` |
| `validate.node.kubernetes.io` | kubelet | — | kube-system |

不在表里 → `kubectl -n <ns> describe validatingwebhookconfiguration <name>` 看 owner reference。

## Step 2 — 一把梭命令（read-only）

`<ALIAS>` = alert cluster 对应 alias（见 `reference-clusters.md`），例如 `kwestproda`。

```bash
# INTENT: caBundle 是否为空 / 与 Secret CA 是否一致
<ALIAS> get validatingwebhookconfiguration ingress-nginx-admission -o yaml | grep -A2 caBundle

diff <(<ALIAS> get validatingwebhookconfiguration ingress-nginx-admission \
        -o jsonpath='{.webhooks[0].clientConfig.caBundle}') \
     <(<ALIAS> get secret ingress-nginx-admission -n ingress-nginx \
        -o jsonpath='{.data.ca}')
```

**解读**：
- caBundle 为空 → 明确根因
- caBundle 非空但与 Secret 不一致 → 也是根因（cert rotation 后未同步）
- 两者一致 → 排除本 hypothesis，走其他分支（pod down、API server CA rotation、SNI 问题）

## Step 3 — 确认时间对齐

```bash
# INTENT: 升级时间是否和故障时间对齐（< ~30min 窗口）
helm history ingress-nginx -n ingress-nginx
<ALIAS> get validatingwebhookconfiguration ingress-nginx-admission \
  -o jsonpath='{.metadata.creationTimestamp}'
```

对齐 → 强证据支持 helm upgrade 是根因。

## Step 4 — 排除 webhook pod down

```bash
<ALIAS> get pods -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
```

Pod 都 Running/Ready → 不是 pod 层面；确认 caBundle 路径。
Pod CrashLoop → 另一条路径（pod 故障），不在本 card 范围。

## Step 5 — 修复（`#MANUAL`）

参考 `knowledge/cases/case-ingress-nginx-admission-webhook-cabundle-stale.md` §建议操作。不要在 fast-triage 阶段执行 patch —— 先上报，人工 approve。

## 反模式（不要这么做）

- ❌ 第一反应怀疑 Flink / 特定 tenant：多 tenant 同步失败排除了应用层
- ❌ 重启 ingress-nginx-controller 先：Pod 重启不会修复 webhook config（config 是 cluster-level 资源）
- ❌ 绕过 webhook（`--disable-admission-plugins`）：高风险，不是 fix
- ❌ 没 alias 就用 `kubectl ...`：违反 Alias-first Hard Constraint

## Cross-reference

- 详细 case：`cases/case-ingress-nginx-admission-webhook-cabundle-stale.md`
- ingress-nginx 通用 triage：`cards/card-nginx-fast-triage.md`
- Routing：见 `agent-routing-table.md` Cluster 6（change management regression）
