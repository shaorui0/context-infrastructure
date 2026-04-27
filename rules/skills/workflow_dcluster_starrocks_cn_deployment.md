# dcluster StarRocks CN 部署与验证

## 元数据

- **类型**: Workflow
- **适用场景**: dcluster StarRocks CN 代码变更后的构建、部署、E2E 验证
- **环境**: kwestdeva (k8s-aws-us-dev-a) / qa-security namespace
- **创建日期**: 2026-04-15
- **来源**: CRE-6630 StarRocks CN tier + warehouse 开发过程

---

## When to Use

- dcluster Java 代码或 Helm chart 变更后，需要部署到 deva 验证
- StarRocks CN API 功能测试
- Spot CN 池的创建、扩缩、销毁验证

## Prerequisites

- `kwestdeva` alias 已配置（`kubectl --kubeconfig=.../dev_a.config`）
- Docker Desktop 运行中（需要 `docker buildx` 支持 amd64 交叉编译）
- `docker-registry.dv-api.com` 登录凭证
- Java 17 + Maven

---

## 步骤 1: 构建

```bash
# 构建 JAR
cd /Users/rshao/work/work-harness/code_repos/dcluster/dcluster/clusterManager
mvn clean package -Dmaven.test.skip=true -q

# 构建 amd64 镜像并推送（Mac 是 arm64，K8s 节点是 amd64）
cd /Users/rshao/work/work-harness/code_repos/dcluster
docker buildx build --platform linux/amd64 \
  -t docker-registry.dv-api.com/cloud/dcluster-deployment:<tag> \
  -f Dockerfile --push .
```

**重要**：每次部署用**不同的 tag**（如 `starrocks-cn-api-v2b`）。K8s 默认 `imagePullPolicy: IfNotPresent`，相同 tag 不会拉新镜像。

## 步骤 2: 部署

```bash
# 更新镜像
kwestdeva set image deployment/dcluster-deployment \
  dcluster-deployment=docker-registry.dv-api.com/cloud/dcluster-deployment:<tag> \
  -nqa-security

# 等待 rollout
kwestdeva rollout status deployment/dcluster-deployment -nqa-security --timeout=120s

# 确认新 pod 运行中
kwestdeva get pods -nqa-security -l app=dcluster-deployment
```

## 步骤 3: Port-forward

```bash
kwestdeva port-forward deployment/dcluster-deployment 18080:8080 -nqa-security &
```

所有 API 请求通过 `http://localhost:18080/cluster/` 访问。

## 步骤 4: E2E 验证

### StarRocks CN API v2 测试清单

```bash
# T1: Launch
curl -s -X POST http://localhost:18080/cluster/starrocks-cn/launch \
  -H "Content-Type: application/json" \
  -d '{"tier":"small","warehouse":"e2e_test"}'
# 预期: 返回 cluster ID (int > 0)

# T2: 输入校验 - 无 tier
curl -s -X POST http://localhost:18080/cluster/starrocks-cn/launch \
  -H "Content-Type: application/json" -d '{"warehouse":"x"}'
# 预期: -1

# T3: 输入校验 - 未知 tier
curl -s -X POST http://localhost:18080/cluster/starrocks-cn/launch \
  -H "Content-Type: application/json" -d '{"tier":"xlarge"}'
# 预期: -1

# T4: Status
curl -s http://localhost:18080/cluster/starrocks-cn/{id}/status
# 预期: status=LAUNCHING, workers=1

# T5: 验证 pod 资源 (tier=small → 2cpu/8Gi)
NS="starrocks-qa-security-e2e-test-{id}"
kwestdeva get pod -n $NS -o jsonpath='{.items[0].spec.containers[0].resources}'

# T6: 验证 ConfigMap (feAddress 自动构造, warehouse 传递)
kwestdeva get configmap -n $NS -o yaml | grep -A 5 'fe_address\|warehouse'
# 预期: fe_address: starrocks-fe.qa-security.svc.cluster.local:9020
# 预期: warehouse: e2e_test

# T7: Scale up
curl -s -X POST http://localhost:18080/cluster/starrocks-cn/{id}/scale-up
# 预期: "0", status 中 workers=2

# T8: Scale down
curl -s -X POST http://localhost:18080/cluster/starrocks-cn/{id}/scale-down
# 预期: "0", workers=1

# T9: Scale down 到底
curl -s -X POST http://localhost:18080/cluster/starrocks-cn/{id}/scale-down
# 预期: "Cannot scale below 1 CN"

# T10: Terminate
curl -s -X DELETE http://localhost:18080/cluster/starrocks-cn/{id}
# 预期: "0"

# T11: Terminate 幂等
curl -s -X DELETE http://localhost:18080/cluster/starrocks-cn/{id}
# 预期: "This cluster is already terminated."
```

### Init container warehouse 行为

Init container 自动注册 CN 到 FE：
- 若 FE 支持 warehouse → `CREATE WAREHOUSE IF NOT EXISTS` + `ALTER SYSTEM ADD COMPUTE NODE ... TO WAREHOUSE`
- 若 FE 不支持（非 shared-data 模式）→ 自动 fallback 到 default_warehouse

检查 init container 日志：
```bash
kwestdeva logs <pod> -n <ns> -c register-cn
```

### 等待 pod 就绪（Spot 节点冷启动 ~9 分钟）

```bash
# Pod 会经历: Pending → Init:0/1 → PodInitializing → Running (0/1) → Running (1/1)
# Pending 阶段 CA 扩 Spot ASG（~70s），kubeadm join（~80s），init container（~50s），镜像拉取（~200s）

# 查看进度
kwestdeva describe pod <pod> -n <ns> | grep -A 10 'Events:'

# 查看 CA 是否触发
kwestdeva describe pod <pod> -n <ns> | grep TriggeredScaleUp
```

## 步骤 5: 清理

```bash
# 终止测试集群
curl -s -X DELETE http://localhost:18080/cluster/starrocks-cn/{id}

# 停止 port-forward
kill %1

# 回滚 dcluster 镜像到 production
kwestdeva set image deployment/dcluster-deployment \
  dcluster-deployment=docker-registry.dv-api.com/cloud/dcluster-deployment:DV.202602A.External_DAPP73-5662686 \
  -nqa-security
```

---

## Tier 档位

| 档位 | CPU | Memory | Cache |
|------|-----|--------|-------|
| small | 2 | 8Gi | 10Gi |
| medium | 4 | 16Gi | 30Gi |
| large | 8 | 32Gi | 60Gi |

Launch 永远从 1 个 CN 开始。用 scale-up/scale-down 调整数量。

## 关键路径

| 文件 | 说明 |
|------|------|
| `dcluster/clusterManager/.../controller/ClusterController.java` | REST 端点 |
| `dcluster/clusterManager/.../service/ClusterServiceImpl.java` | 业务逻辑 |
| `dcluster/clusterManager/.../configuration/AppConfig.java` | Tier + FE 配置 |
| `dcluster/clusterManager/.../model/StarRocksCNLaunchRequest.java` | Launch DTO |
| `helm/starrocks-cn/` | Helm chart（values, configmap, deployment） |
| `dcluster/clusterManager/src/test/.../StarRocksCNClusterServiceTest.java` | 单元测试 |

## 踩过的坑

| 问题 | 根因 | 解决 |
|------|------|------|
| `ImagePullBackOff` 在 K8s | Mac 构建了 arm64 镜像，K8s 需要 amd64 | `docker buildx build --platform linux/amd64` |
| 相同 tag 新镜像不生效 | `imagePullPolicy: IfNotPresent` 缓存 | 每次用不同 tag |
| feAddress 用了 `external-job-namespace` | `appConfig.getExternalNamespace()` 不是 FE 的 namespace | 改用 `getPodNamespace()` 读 K8s service account |
| Warehouse 命令失败后 CN 未注册 FE | `CREATE WAREHOUSE` 失败被 `\|\| true` 吞掉，整个分支静默失败 | 改为检查返回码，失败 fallback 到 default 注册 |
| ConfigMap 查询返回空 | `kubectl get configmap -o jsonpath` 在 items 列表上需要精确 name | 用 `-o yaml \| grep` 或指定 ConfigMap 名 |
