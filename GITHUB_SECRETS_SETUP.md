# GitHub Secrets Setup for OCI Homelab Deployment

This document explains how to add the required secrets to your GitHub repository so the deploy workflow can provision your OCI infrastructure.

## Step 1: Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions** and add the following secrets:

### Required Secrets

| Secret Name | Description | Where to Find |
|-------------|-------------|---------------|
| `OCI_TENANCY_OCID` | OCI tenancy OCID | OCI Console → Profile → Tenancy |
| `OCI_USER_OCID` | OCI IAM user OCID | OCI Console → Profile → My Profile |
| `OCI_FINGERPRINT` | MD5 fingerprint of your API key | OCI Console → My Profile → API Keys |
| `OCI_PRIVATE_KEY` | PEM-formatted private key (full content) | OCI Console → My Profile → API Keys |
| `OCI_REGION` | OCI region, e.g., `us-ashburn-1` | OCI Console → top-right region selector |
| `SSH_PUBLIC_KEY` | Your SSH public key (ed25519 or RSA) | `cat ~/.ssh/id_ed25519.pub` |
| `OCI_AVAILABILITY_DOMAIN` | Full AD name, e.g., `nhrz:US-ASHBURN-AD-1` | OCI Console → Instance details |
| `OCI_UBUNTU_IMAGE_ID` | Ubuntu 20.04 ARM (aarch64) image OCID | OCI Console → Compute → Images |
| `OCI_INSTANCE_DISPLAY_NAME` | Instance display name, e.g., `instance-20260621-1000` | Your choice (appears in OCI Console) |

### Optional Secrets

| Secret Name | Default Value |
|-------------|---|
| `OCI_FAULT_DOMAIN` | `FAULT-DOMAIN-3` |
| `OCI_OCPUS` | `2` |
| `OCI_MEMORY_IN_GBS` | `12` |

## Step 2: Get Your OCI Details

### 1. Tenancy OCID
- Go to **OCI Console → Profile (top-right) → Tenancy**
- Copy the OCID value
- Format: `ocid1.tenancy.oc1..aaaa...`

### 2. User OCID
- Go to **OCI Console → Profile → My Profile**
- Copy the OCID value
- Format: `ocid1.user.oc1..aaaa...`

### 3. API Key & Fingerprint
- Go to **OCI Console → Profile → My Profile → API Keys**
- Click **Add API Key** (or use an existing one)
- Copy the **Fingerprint** (format: `xx:xx:xx:xx:...`)
- Download the private key (PEM file)
- Open the PEM file with a text editor and copy its full contents

### 4. Region
- OCI Console → top-right corner
- For this project, use `us-ashburn-1` (Ashburn, US-East)
- Or copy from the URL: `https://cloud.oracle.com/?region=us-ashburn-1`

### 5. SSH Public Key
On your local machine:
```bash
# If you have an ed25519 key
cat ~/.ssh/id_ed25519.pub

# Or if using RSA
cat ~/.ssh/id_rsa.pub
```
Copy the entire output (starts with `ssh-ed25519` or `ssh-rsa`).

### 6. Availability Domain
- Go to **OCI Console → Compute → Instances**
- View any existing instance
- Copy the **Availability Domain** (format: `nhrz:US-ASHBURN-AD-1`)
- For Ashburn region, options are: `nhrz:US-ASHBURN-AD-1`, `nhrz:US-ASHBURN-AD-2`, `nhrz:US-ASHBURN-AD-3`

### 7. Ubuntu 20.04 ARM Image OCID
- Go to **OCI Console → Compute → Images**
- Search for "Ubuntu 20.04"
- Filter by **Shape**: `VM.Standard.A2.Flex`
- Look for an image with **aarch64** in the name
- Copy its OCID (format: `ocid1.image.oc1.iad.aaaa...`)

Alternatively, use the OCI CLI:
```bash
oci compute image list \
  --compartment-id <your-tenancy-ocid> \
  --operating-system "Canonical Ubuntu" \
  --operating-system-version "20.04" \
  --query 'data[?contains("display_name", "aarch64")].[id,display_name]' \
  --output table
```

## Step 3: Add Secrets to GitHub

1. Open your repository on GitHub
2. Go to **Settings → Secrets and variables → Actions**
3. Click **New repository secret**
4. For each secret:
   - **Name**: Exact secret name from the table above
   - **Secret**: Paste the value
   - Click **Add secret**

⚠️ **Important**: GitHub secrets are masked in logs. Never paste secrets directly into code or commit them.

## Step 4: Verify Secrets

Run the workflow to verify setup:

1. Go to **Actions** tab in your repository
2. Click **Deploy OCI Homelab** workflow
3. Click **Run workflow → Run workflow**
4. Monitor the job logs for any `terraform apply` errors

If secrets are missing or invalid, Terraform will fail at the **Create terraform.tfvars** step with clear error messages.

## Troubleshooting

### Secret not found error
```
Error: Context access might be invalid: OCI_PRIVATE_KEY
```
→ Go to **Settings → Secrets** and verify the secret exists and is spelled correctly.

### API key authentication failed
```
Error: 401-NotAuthenticated
```
→ Verify your `OCI_PRIVATE_KEY` matches your uploaded API key fingerprint (they must be a pair).

### Image OCID not found
```
Error: 404-NotFound, Instance source image not found
```
→ Verify the `OCI_UBUNTU_IMAGE_ID` is correct and exists in your region/compartment.

### Out of capacity error
(Only on free tier; you have $300 credits so this shouldn't occur)
```
Error: 500-InternalError, Out of host capacity
```
→ The workflow will retry up to 10 times with 60-second delays.

## Cost Estimation

Your $300 free credits should cover:
- **VM.Standard.A2.Flex** (2 OCPUs, 12 GB RAM): ~$0.05/hour
- **100 GB block storage**: included for 30 days
- **Networking**: free for outbound, minimal inbound costs
- **PostgreSQL, Docker, Airflow**: free software, only compute + storage costs

At $0.05/hour, your credits provide ~6,000 hours of runtime (~8 months 24/7).

---

Once you've added all secrets, the workflow will automatically provision your infrastructure on the next push to `main` or manual trigger.
