# Layer 2 — AWS Instance Reference Guide
## Record Health ADI — BioMistral 7B Private Inference Server

**Document version:** 1.0
**Created:** 2026-04-08
**Instance:** i-0b18bb25724c52734
**Region:** us-west-2 (Oregon)
**Account:** 386315604625 (Tenavet LLC)
**IAM user:** tenavet-dev

---

## 1. Instance Specs

```
Instance type:    g4dn.xlarge
GPU:              Tesla T4 (15GB VRAM)
vCPUs:            4
RAM:              16GB
Storage:          100GB gp3
OS:               Ubuntu 22.04
AMI:              ami-09a372bc8e4d71425
                  Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.7 (Ubuntu 22.04)
CUDA:             12.8
NVIDIA driver:    580.126.09
Model:            cniongolo/biomistral (BioMistral 7B, 4.4GB GGUF quantized)
Serving:          Ollama (systemd service, auto-starts on boot)
Cost:             ~$0.53/hour on-demand — STOP WHEN NOT IN USE
```

---

## 2. AWS CLI Profile

All commands use the `tenavet` profile. Never operate as root.

```bash
# Verify you're using the right identity
aws sts get-caller-identity --profile tenavet
```

Expected output:
```json
{
    "UserId": "AIDAVT4RUKKIXSXVDJKRO",
    "Account": "386315604625",
    "Arn": "arn:aws:iam::386315604625:user/tenavet-dev"
}
```

---

## 3. Start the Instance

```bash
aws ec2 start-instances \
  --instance-ids i-0b18bb25724c52734 \
  --region us-west-2 \
  --profile tenavet
```

Wait ~30 seconds then get the new public IP (it changes every start):

```bash
aws ec2 describe-instances \
  --instance-ids i-0b18bb25724c52734 \
  --query 'Reservations[0].Instances[0].{State:State.Name,PublicIP:PublicIpAddress}' \
  --region us-west-2 \
  --profile tenavet
```

Wait until `State` shows `running` before SSH-ing in.

---

## 4. SSH In

```bash
ssh -i ~/.ssh/tenavet-layer2.pem ubuntu@{PUBLIC_IP}
```

Replace `{PUBLIC_IP}` with the IP from the describe-instances command above.

Type `yes` on first connect to accept the host fingerprint.

**Key file location:** `~/.ssh/tenavet-layer2.pem`
**Key name in AWS:** `tenavet-layer2`
**Permissions:** 400 (set automatically on creation — if SSH rejects the key run `chmod 400 ~/.ssh/tenavet-layer2.pem`)

---

## 5. Verify GPU and Model on Login

```bash
# Check GPU is visible
nvidia-smi

# Check Ollama service is running
systemctl status ollama

# Test model responds
ollama run cniongolo/biomistral "What is a normal range for hemoglobin in an adult male?"
```

Expected: Tesla T4 visible in nvidia-smi, Ollama active, model returns clinical answer.

---

## 6. Stop the Instance

Always stop when not actively working. The instance costs ~$0.53/hour running.

From your local terminal (not SSH):

```bash
aws ec2 stop-instances \
  --instance-ids i-0b18bb25724c52734 \
  --region us-west-2 \
  --profile tenavet
```

Stopped instances incur no compute cost. EBS storage (~$8/month for 100GB gp3) continues regardless.

---

## 7. Dynamic IP — What To Know

The public IP changes every time the instance starts. There is no Elastic IP assigned yet.

**Workflow each session:**
1. Start instance
2. Run describe-instances to get current IP
3. SSH using current IP

**Future:** Assign an Elastic IP to get a static address. Not yet configured — add in a future infrastructure sprint.

---

## 8. Security Group

```
Group ID:   sg-0891a04872a03b0b7
Name:       tenavet-layer2-sg
Rule:       TCP port 22 (SSH) from your current IP only
```

**If SSH times out after your IP changes:**

Get your current IP and update the rule:

```bash
# First remove the old rule (update the CIDR to whatever was previously set)
aws ec2 revoke-security-group-ingress \
  --group-id sg-0891a04872a03b0b7 \
  --protocol tcp \
  --port 22 \
  --cidr {OLD_IP}/32 \
  --region us-west-2 \
  --profile tenavet

# Add new rule with current IP
MY_IP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress \
  --group-id sg-0891a04872a03b0b7 \
  --protocol tcp \
  --port 22 \
  --cidr ${MY_IP}/32 \
  --region us-west-2 \
  --profile tenavet
```

---

## 9. Ollama Commands (run inside SSH session)

```bash
# List installed models
ollama list

# Run a prompt
ollama run cniongolo/biomistral "your prompt here"

# Check Ollama service status
systemctl status ollama

# Restart Ollama if needed
sudo systemctl restart ollama

# Ollama API endpoint (local only, not exposed externally yet)
curl http://localhost:11434/api/generate \
  -d '{"model": "cniongolo/biomistral", "prompt": "What is HbA1c?", "stream": false}'
```

---

## 10. Billing and Cost Controls

```
Budget alert:   $50/month
Alert threshold: 80% ($40)
Alert email:    jason_nolte@hotmail.com
Budget name:    tenavet-monthly
```

Check current month spend:

```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --profile tenavet
```

---

## 11. AWS Quota

```
Quota:      Running On-Demand G and VT instances
Limit:      4 vCPUs
Region:     us-west-2
Status:     Approved 2026-04-08
Request ID: 45ac42026f82489cb46c4f4848748ea2ahCamsTX
```

The g4dn.xlarge uses all 4 vCPUs. You cannot run a second GPU instance simultaneously under this quota without requesting an increase.

---

## 12. Next Infrastructure Steps (Not Yet Built)

These are planned but not yet implemented:

- **Elastic IP** — static IP so the address doesn't change on every start
- **HTTP inference endpoint** — expose Ollama API to Cloudflare Worker (Layer 3 integration)
- **VPC hardening** — remove public IP dependency, route through private endpoint
- **Systems Manager Session Manager** — replace SSH with AWS-native access (no open ports)
- **IAM role for EC2** — instance-level permissions instead of user credentials

---

## 13. Architecture Context

This instance is **Layer 2** in the three-layer model stack:

```
Layer 1 — On-device CoreML        PHI never leaves device
Layer 2 — This instance           Clinical reasoning, structured extraction
                                   Fires on cases Layer 1 can't resolve
                                   MIMIC-IV training runs execute here
Layer 3 — AWS Bedrock             Stateless escalation only
                                   Fires on cases Layer 2 can't resolve
                                   Never receives raw PHI or MIMIC content
```

See `INTEGRATION_LAYER.md` and `SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md` section 1.3 for full architecture.

---

*End of document. Update PublicIP field after each session start.*
