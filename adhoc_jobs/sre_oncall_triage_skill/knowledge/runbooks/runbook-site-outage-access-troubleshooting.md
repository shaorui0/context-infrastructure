---
metadata:
  kind: runbook
  status: final
  summary: "End-to-end checklist for site access outages: start from the user side and DNS/connectivity, then narrow down to Kubernetes Pod/Service/Ingress, and extend to AWS ELB/security groups/route tables/Route 53/CloudFront and tracing to quickly isolate scope and find the root cause."
  tags: ["outage", "dns", "ingress", "aws", "networking"]
  first_action: "Run `dig` and `curl -v` to isolate DNS vs backend"
---

# Site Outage / Access Troubleshooting

## TL;DR (Do This First)
1. Scope: single user vs all users; single page vs whole site?
2. DNS: `dig +short <domain>`
3. Connectivity: `curl -v https://<domain>` — confirm status code / TLS
4. Backend chain: Service → Ingress → Pods (read-only)
5. If AWS edge is involved: ELB target health / SG / Route53

## Safety Boundaries
- Read-only: DNS/connectivity checks, `kubectl get/describe/logs`
- `#MANUAL`: changing DNS/Ingress/LB/security groups, restarting controllers

## DV Cluster Aliases

| Alias | Environment |
|-------|-------------|
| `kdev` | Development |
| `kwest` / `kwestproda` | West prod |
| `keast` / `keastproda` | East prod |

## DV Domain Pattern
- External-facing: `*.dv-api.com` (e.g. `admin-demo2.dv-api.com`)
- Ingress terminates TLS; routes to Services in relevant namespace

## Step 1: Client-side triage
- Ask: single page or whole site? Specific device/network/ISP?
- Try incognito / clear cache
- Get screenshot or exact error code

## Step 2: DNS and connectivity
```bash
dig +short <domain>
curl -v https://<domain>
```

## Step 3: K8s backend chain

### Identify cluster from domain / alert context, then:
```bash
<cluster-alias> get pods,svc,ing -n <namespace>
<cluster-alias> describe ing <ingress-name> -n <namespace>
<cluster-alias> describe svc <service-name> -n <namespace>
# Confirm endpoints have healthy Pod IPs
```

### Common DV ingress paths to check
- FP (Fraud Prevention) services: namespace varies by client tenant
- UI / admin portal: typically in a shared namespace

### Check pod health
```bash
<cluster-alias> get pods -n <namespace>
<cluster-alias> logs <pod-name> -n <namespace> --tail=100
<cluster-alias> logs <pod-name> -n <namespace> --previous   # if restarted
```

## Step 4: AWS edge checks (`#MANUAL` if changes needed)

### ELB target health
```bash
aws elbv2 describe-target-groups --load-balancer-arn <ALB-ARN>
aws elbv2 describe-target-health --target-group-arn <Target-Group-ARN>
```

### Route53 DNS record
```bash
aws route53 list-resource-record-sets --hosted-zone-id <Zone-ID> | grep <domain-name>
```

## Common Failure Modes

| Symptom | Likely cause | Where to look |
|---------|-------------|---------------|
| DNS resolution fails | Route53 record missing/wrong | `dig` + Route53 console |
| TLS error | Certificate expired | `curl -v` for cert dates |
| 502/503 from LB | Pods unhealthy | ELB target health + pod logs |
| 404 from Ingress | Ingress rule mismatch | `describe ing` |
| Partial failure (some users) | ELB target deregistration mid-deploy | Target health check |
