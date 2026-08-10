---
metadata:
  kind: case
  status: draft
  summary: "StarRocks FE CrashLoopBackOff — BDB 元数据记录旧 IP，Pod 重启后 IP 变化导致角色停留 UNKNOWN"
  tags: ["starrocks", "k8s", "crashloop", "statefulset", "helm", "bdb", "fqdn"]
  first_action: "kubectl exec 进容器读 /opt/starrocks/fe/log/fe.log（FE 日志不写 stdout）"
  related: ["runbooks/runbook-starrocks-iceberg-deployment.md"]
  derived_from: "code_repos/feature-platform/reqs/cre-6630/fp-starrocks-deployment/docs/history.md"
---

## TL;DR（5 步）

1. **告警信号**: StarRocks FE StatefulSet pod 285 次重启，CrashLoopBackOff，kubectl logs 为空
2. **关键发现**: 容器内 `/opt/starrocks/fe/log/fe.log` 记录 BDB 角色停留 `UNKNOWN`，旧 IP 与新 Pod IP 不匹配
3. **根因**: BerkeleyDB 元数据（PVC）记录了旧 Pod IP；Pod 重启后 IP 变化，BDB 无法识别 → 角色 UNKNOWN → port 9030 不开 → liveness probe 60s 后 kill（exit code 143）
4. **修复**: (a) 临时：Scale down → 删 PVC → Scale up；(b) 永久：Service 改 headless + `--host_type FQDN` 参数让 BDB 记录 DNS 名而非 IP
5. **后续**: CN 需 rollout restart 重连新 FE

## 信号

- `kubectl get pods` 显示 FE pod RestartCount > 50，状态 `CrashLoopBackOff`
- `kubectl logs <fe-pod>` 输出为空（FE 日志写文件不写 stdout）
- `kubectl describe pod <fe-pod>` Exit Code: 143（SIGTERM，被 liveness probe kill）
- FE pod liveness probe：`tcp-socket port 9030`，9030 只有角色确定后才开

## Evidence Chain

**读取真实日志**（FE 不写 stdout，必须进容器）：
```bash
kubectl exec -it starrocks-fe-0 -- cat /opt/starrocks/fe/log/fe.log | grep -E "UNKNOWN|BDB|IP|role"
```

典型输出：
```
[FE] this node is in UNKNOWN state, waiting for quorum...
[FE] my IP is 192.168.157.167, but BDB stored 192.168.228.18
```

**原因链**:
- BerkeleyDB 在 PVC 里记录了旧 IP `192.168.228.18`
- Pod 重启分配了新 IP `192.168.157.167`
- 单节点 BDB 无法与旧记录匹配 → 角色 `UNKNOWN`
- port 9030 不开 → liveness probe 60s 失败 → Pod 被 kill（exit 143）
- 循环

## 结论

**根因 likely 是**：K8s Pod IP 非稳定，但 StarRocks FE 的 BerkeleyDB 元数据默认用 IP 注册自身。单节点 BDB 没有法定人数可选举，一旦 IP 不匹配就永久 UNKNOWN。

## 建议操作

### 临时修复（恢复服务）

```bash
# 1. Scale down
kubectl scale statefulset starrocks-fe --replicas=0

# 2. 删 PVC（清除 BDB 旧记录）
kubectl delete pvc <fe-pvc-name>

# 3. Scale up（BDB 重新初始化）
kubectl scale statefulset starrocks-fe --replicas=1

# 4. 等 FE ready 后重跑 init SQL（重注册 CN + 创建 catalog）
kubectl exec -it starrocks-fe-0 -- mysql -h 127.0.0.1 -P 9030 -u root
```

### 永久修复（防复发）

**Helm chart 改动：**

1. **Service 改 headless**（`starrocks-fe.yaml`）：
```yaml
spec:
  clusterIP: None  # headless，Pod 获得稳定 DNS 记录
```

2. **FE command 加 FQDN 参数**：
```yaml
command:
  - /opt/starrocks/fe/bin/start_fe.sh
  - --host_type
  - FQDN
```

**注意**：K8s 不允许原地修改 Service clusterIP，必须先删 Service 再 helm upgrade：
```bash
kubectl delete svc starrocks-fe
helm upgrade fp-starrocks ./charts-starrocks -f values.yaml
```

**验证（修复后）**：
```sql
SHOW FRONTENDS\G
-- Name 字段应为 FQDN 格式:
-- starrocks-fe-0.starrocks-fe.<namespace>.svc.cluster.local_9010_...
-- Alive: true, Role: LEADER
```

**CN 重连**：
```bash
kubectl rollout restart deployment starrocks-cn
```

## 关键教训

- **FE 日志不写 stdout**，`kubectl logs` 看到空不等于没有日志，必须 exec 进容器读 log 文件
- **BDB 默认用 IP 注册**，K8s Pod IP 非稳定，StatefulSet + headless Service 是标准解法
- **liveness probe exit 143** = SIGTERM（被 probe kill），不是程序自己崩溃
- **PVC 删除是破坏性操作**，生产前确认数据在 S3（shared_data 模式下 FE meta 在 PVC，业务数据在 S3，删 PVC 只丢 FE 元数据，CN 可以重新注册）
