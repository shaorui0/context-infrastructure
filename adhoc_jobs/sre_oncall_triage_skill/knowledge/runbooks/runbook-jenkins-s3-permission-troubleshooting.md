---
metadata:
  kind: runbook
  status: draft
  summary: "Runbook for Jenkins S3 upload 403/AccessDenied: confirm caller identity, then locate explicit deny across IAM/bucket policy/VPC-IP conditions; treat policy changes as `#MANUAL`."
  tags: ["jenkins", "s3", "iam", "access-denied"]
  first_action: "Run `aws sts get-caller-identity`"
---

# Issue Type: Jenkins — AWS S3 Permission Issues

## Problem Pattern
- Jenkins build fails with S3 upload errors
- `com.amazonaws.services.s3.model.AmazonS3Exception` / HTTP 403
- Error message references "explicit deny in a resource-based policy"

## Investigation

### 1. Confirm caller identity and bucket access
```bash
aws sts get-caller-identity
aws s3 ls s3://<bucket-name>/
aws s3api get-bucket-policy --bucket <bucket-name>
```

### 2. Check Jenkins agent network location
```bash
aws ec2 describe-instances \
  --filters "Name=private-ip-address,Values=<agent-ip>" \
  --query "Reservations[].Instances[].{InstanceId:InstanceId,VpcId:VpcId,PrivateIpAddress:PrivateIpAddress}"
```

### 3. Common deny sources in DV

| Source | What to look for |
|--------|-----------------|
| Bucket policy VPC/IP condition | `DenyNotVPCNotVPN` / `AllowVPC` / `AllowVPN` statements — agent VPC not in the allowed list |
| IAM user policy | Missing `s3:PutObject` / `s3:GetObject` / `s3:ListBucket` |
| Credential mismatch | Jenkins using wrong credential ID |

```bash
aws iam list-attached-user-policies --user-name <username>
aws iam list-user-policies --user-name <username>
```

## Remediation (`#MANUAL`)

### Network-based restriction — add Jenkins VPC to bucket policy
```bash
aws s3api get-bucket-policy --bucket <bucket-name> > original_policy.json
# Edit: add Jenkins agent VpcId to aws:sourceVpc condition array
aws s3api put-bucket-policy --bucket <bucket-name> --policy file://updated_policy.json
```

### Verify
```bash
aws s3 cp test.txt s3://<bucket-name>/test.txt
aws s3 rm s3://<bucket-name>/test.txt
```

## Reference Case: JENKINS_14635

- **Bucket**: `datavisor-staging-uswest2`
- **IAM user**: `CronProd`
- **Agent IP**: `192.168.116.26`

```bash
#MANUAL
aws iam list-attached-user-policies --user-name CronProd
aws iam list-user-policies --user-name CronProd

aws s3api get-bucket-policy --bucket datavisor-staging-uswest2

aws ec2 describe-instances \
  --filters "Name=private-ip-address,Values=192.168.116.26" \
  --query "Reservations[].Instances[].{InstanceId:InstanceId,VpcId:VpcId}"

aws s3api get-bucket-policy --bucket datavisor-staging-uswest2 > original_policy.json
# Edit: add Jenkins VPC to aws:sourceVpc condition arrays
aws s3api put-bucket-policy --bucket datavisor-staging-uswest2 --policy file://updated_policy.json
```

**Root cause**: bucket policy had `DenyNotVPCNotVPN` + `AllowVPC`/`AllowVPN` statements; Jenkins agent VPC was not in the allowed list. Fix: added agent VPC to `AllowVPC` condition.

**Note**: VPC/IP-based explicit denies override IAM user Allow grants — IAM policy changes alone will not fix this.
