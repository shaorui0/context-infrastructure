---
metadata:
  kind: pattern
  status: final
  summary: "FP latency alert notes: when ingress `waiting_latency` rises while upstream latency is normal, suspect ingress/connection/scheduling layers first. Provides a fixed debug order (decompose request_time/upstream_response_time/waiting_latency, check Ingress/APISIX logs, align change events) and prerequisites for the monitor decision."
  tags: ["fp", "latency", "ingress", "waiting-latency"]
  first_action: "Decompose waiting_latency vs upstream latency"
---

## Case B: Ingress waiting_latency up, upstream latency normal

### Alert / Trigger

- latency alert
- waiting_latency rises
- upstream_response_time is normal

---

### Core Call

- The issue is **not in upstream**
- More likely in ingress / connection / scheduling layers

---

### Debug Order (fixed)

### 1) Latency decomposition

Confirm:

- request_time
- upstream_response_time
- waiting_latency

-> Focus on waiting_latency

---

### 2) Ingress / APISIX logs

Check:

- upstream connection
- endpoint jitter
- retry/queue behavior

Example (read-only) Loki query snippet:

```text
{namespace="ingress-nginx",container="controller"} |~ "waiting_latency" 
```

---

### 3) Change events

- traffic switch
- restart
- config change

Confirm whether it is:

- a mitigation action
- or a newly introduced variable

---

### Decision

- **Default**: `monitor`
- Prerequisites:
    - blast radius does not expand
    - latency does not keep worsening

---

### Exit Criteria

- waiting_latency drops or stabilizes
- no SLA regression
    
    -> Done

## Verify

- the delta between request_time and upstream_response_time (waiting_latency) drops
- ingress logs no longer show abnormal retries/queueing/upstream connection issues
    

---

## ⚠️ Multi-Layer Chain Trap (apisix → nginx ingress)

When the serving path is: **External Apisix → Internal Nginx Ingress → Backend Pod**

External apisix's `upstream_response_time` = total time for internal nginx ingress + backend pod.
It does **NOT** tell you whether the backend pod is healthy or whether waiting_latency is at ingress.

**Wrong read**: apisix log shows `upstream_response_time=5s` → do NOT conclude "upstream slow".
**Correct action**: drill to nginx ingress access log, decompose at ingress layer.

Nginx ingress log fields:
```
request_time  upstream_response_time  [proxy_upstream_name]  upstream_pod_ip:port  upstream_bytes  upstream_latency
```
`waiting_duration = request_time - upstream_response_time` at nginx ingress layer is the true signal.

Related case: `knowledge/cases/case-apisix-ingress-chain-waiting-latency-transient.md`
