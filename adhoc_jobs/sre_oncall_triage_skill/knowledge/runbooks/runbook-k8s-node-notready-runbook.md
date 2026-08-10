---
metadata:
  kind: runbook
  status: final
  summary: "Kubernetes Node NotReady oncall runbook: symptoms, core commands, common causes (kubelet, resources, networking, AWS), remediation steps, and a prevention checklist."
  tags: ["k8s", "node", "notready", "kubelet"]
  first_action: "Run `kubectl get nodes` and `kubectl describe node`"
---

# Issue Type: Node NotReady

## TL;DR (Do This First)
1. Identify affected nodes: `${CLUSTER_ALIAS} get nodes | grep -i NotReady`
2. Snapshot node state: `${CLUSTER_ALIAS} describe node <node-name>` (focus on Conditions + Events)
3. Check impact: `${CLUSTER_ALIAS} get pods -A -o wide | grep <node-name>`
4. If remediation requires cordon/drain/reboot/ASG replace, stop and hand off as `#MANUAL`

## Safety Boundaries
- Read-only: `get/describe/logs/top` and log inspection
- `#MANUAL`: cordon/drain, kubelet restarts, instance replacement, ASG changes

## Verification
- Node returns to `Ready`
- Pods recover (no mass `Terminating`/`ContainerCreating` stuck)
- Alerts clear (`KubeNodeNotReady`/`KubeletDown`)

## Standard Investigation

### 1. Node and pod status
```bash
${CLUSTER_ALIAS} get nodes | grep NotReady
${CLUSTER_ALIAS} describe node <node-name>
${CLUSTER_ALIAS} get pods --all-namespaces -o wide | grep <node-name>
```

### 2. Common causes and signals

| Cause | How to detect |
|-------|--------------|
| Kubelet down | Conditions show `KubeletReady=False`; `systemctl status kubelet` on node |
| Disk pressure | Node condition `DiskPressure=True`; `df -h` on node |
| Memory pressure | Node condition `MemoryPressure=True`; OOM entries in `dmesg` |
| Calico/CNI failure | `${CLUSTER_ALIAS} get pods -n kube-system \| grep calico` shows crash |
| AWS EC2 hardware issue | `aws ec2 describe-instance-status --instance-id <id>` shows impaired status |

### 3. Calico + AWS EC2 combined check

When both CNI and EC2 status checks are abnormal, treat as AWS hardware/network issue:
```bash
${CLUSTER_ALIAS} get pods -n kube-system | grep calico
aws ec2 describe-instance-status --instance-id <instance-id>
```

If EC2 status check shows `failed` → instance replacement is likely required (`#MANUAL`).

### 4. Stuck pods after node goes NotReady (`#MANUAL`)
```bash
${CLUSTER_ALIAS} delete pod <pod-name> -n <namespace> --force --grace-period=0
```

## Reference Case: CLUSTER_EASTPRODA_20250505

- **Node**: `ip-172-30-66-69.ec2.internal` on `eastproda`
- **Cause**: High resource utilization (98% CPU, 93% memory) contributed to kubelet unresponsiveness
- **Actions**: Checked AWS health status → force-deleted stuck pods → rebooted instance (`#MANUAL`)
- **Follow-up**: Resource allocation review for workloads on the node
