# OCI Homelab — AI Stock Pipeline on Oracle Cloud Free Tier

A fully automated deployment of an ARM-based Ubuntu 24.04 server on Oracle Cloud Infrastructure (OCI), provisioned with Terraform and GitHub Actions. The server runs Apache Airflow, PostgreSQL, and a daily stock-market AI pipeline powered by Groq LLM.

---

## What This Repo Does

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Infrastructure | Terraform + OCI | Creates VCN, subnet, security list, compute instance |
| OS Bootstrap | cloud-init | Installs all packages, configures Airflow + PostgreSQL |
| CI/CD | GitHub Actions | Auto-deploys on push to `main`; destroy is manual-only |
| Data | yfinance | Fetches daily OHLCV for 10 US + Indian stocks |
| AI signals | Groq (llama-3.3-70b) | BUY / HOLD / SELL with confidence score |
| Storage | PostgreSQL | Persists signals in `stock_signals` table |
| Alerts | Telegram Bot | Morning report when BUY signals are found |

The VM uses the **VM.Standard.A1.Flex** shape (2 OCPUs, 12 GB RAM, 100 GB boot), which is covered by OCI's Always-Free tier limits.

---

## Prerequisites

- An **OCI account** (free tier is sufficient — [cloud.oracle.com](https://cloud.oracle.com))
- A **GitHub account** with this repo forked or cloned
- An SSH key pair on your local machine (`ssh-keygen -t ed25519 -f ~/.ssh/oci_homelab`)
- A **Groq API key** (free at [console.groq.com](https://console.groq.com))
- (Optional) A Telegram bot token for alerts

---

## Step 1 — Get Your OCI Credentials

You need five values from the OCI Console. Open [cloud.oracle.com](https://cloud.oracle.com) and follow these steps:

### 1.1 Tenancy OCID

1. Click the **profile icon** (top-right) → **Tenancy: \<your-name\>**
2. Copy the **OCID** field at the top of the page
3. It looks like: `ocid1.tenancy.oc1..aaaaaa...`

### 1.2 User OCID

1. Click the **profile icon** → **My Profile**
2. Copy the **OCID** at the top
3. It looks like: `ocid1.user.oc1..aaaaaa...`

### 1.3 API Key (Fingerprint + Private Key)

1. On the **My Profile** page, scroll to **API Keys** in the left menu
2. Click **Add API Key** → **Generate API Key Pair**
3. Download the **Private Key** (`.pem` file) — save it somewhere safe
4. Click **Add** — OCI shows the **fingerprint** (format: `xx:xx:xx:...:xx`)
5. Copy the fingerprint

### 1.4 Region Identifier

1. Look at the top-right of the OCI Console — it shows your region name (e.g. "US East (Ashburn)")
2. The identifier is shown in the URL or in **Profile → My Profile → Home Region**
3. Common identifiers:

| Region Name | Identifier |
|-------------|-----------|
| US East (Ashburn) | `us-ashburn-1` |
| US West (Phoenix) | `us-phoenix-1` |
| Germany Central (Frankfurt) | `eu-frankfurt-1` |
| India South (Hyderabad) | `ap-hyderabad-1` |
| India West (Mumbai) | `ap-mumbai-1` |
| UK South (London) | `uk-london-1` |
| Japan East (Tokyo) | `ap-tokyo-1` |

---

## Step 2 — Add GitHub Secrets

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

Add all six secrets:

| Secret Name | Where to find it |
|-------------|-----------------|
| `OCI_TENANCY_OCID` | OCI Console → Profile → Tenancy → OCID field |
| `OCI_USER_OCID` | OCI Console → Profile → My Profile → OCID field |
| `OCI_FINGERPRINT` | OCI Console → My Profile → API Keys → fingerprint column |
| `OCI_PRIVATE_KEY` | Contents of the `.pem` file you downloaded (paste the whole file including `-----BEGIN...-----`) |
| `OCI_REGION` | Region identifier, e.g. `ap-mumbai-1` |
| `SSH_PUBLIC_KEY` | Contents of your SSH public key, e.g. `cat ~/.ssh/oci_homelab.pub` |

> **Important:** For `OCI_PRIVATE_KEY`, paste the entire PEM file content including the header and footer lines.

---

## Step 3 — Deploy

### Option A: Push to main branch (automatic)

```bash
git clone https://github.com/YOUR_USERNAME/oci-homelab.git
cd oci-homelab
git add .
git commit -m "Initial deployment"
git push origin main
```

The **Deploy OCI Homelab** workflow starts automatically. Watch progress in **Actions** tab.

### Option B: Manual trigger

1. GitHub repo → **Actions** tab
2. Select **Deploy OCI Homelab**
3. Click **Run workflow** → **Run workflow**

### What happens during deploy

- Terraform creates VCN, subnet, security list, and the ARM VM (~3 minutes)
- cloud-init installs all packages and configures services (~10 minutes after VM boots)
- The workflow prints the public IP when Terraform finishes

---

## Step 4 — Connect via SSH

```bash
# Replace PUBLIC_IP with the IP shown in the workflow output
ssh -i ~/.ssh/oci_homelab ubuntu@PUBLIC_IP
```

If connection is refused, wait 2–3 minutes for cloud-init to finish, then try again.

---

## Step 5 — Configure API Keys on the VM

After SSH-ing in, run the setup script:

```bash
bash /home/ubuntu/ai-pipeline/scripts/setup_env.sh
```

This prompts you for:
- **GROQ_API_KEY** — from [console.groq.com](https://console.groq.com) → API Keys
- **TELEGRAM_BOT_TOKEN** — from [@BotFather](https://t.me/botfather) on Telegram
- **TELEGRAM_CHAT_ID** — message [@userinfobot](https://t.me/userinfobot) to get your chat ID

The script saves credentials, copies the DAG to Airflow, restarts services, and runs a smoke test.

---

## Step 6 — Access Airflow UI

Open in your browser:

```
http://PUBLIC_IP:8080
```

Login: **admin** / **admin123**

The **stock_market_pipeline** DAG appears in the list. It runs automatically Mon–Fri at 06:00 UTC, or you can trigger it manually via the UI or CLI:

```bash
airflow dags trigger stock_market_pipeline
```

---

## Step 7 — Run the Test Script

```bash
python3 /home/ubuntu/ai-pipeline/scripts/test_setup.py
```

Expected output:
```
[OK] yfinance — AAPL last price: $XXX.XX
[OK] chromadb — in-memory collection created successfully
[OK] groq — module version: X.X.X
[OK] pandas — DataFrame shape: (3, 1)

All tests passed!
```

---

## Step 8 — Destroy Infrastructure

To avoid any unexpected OCI costs, destroy resources when not needed.

1. GitHub repo → **Actions** → **Destroy OCI Homelab**
2. Click **Run workflow**
3. In the **confirm** field, type `DESTROY` exactly (case-sensitive)
4. Click **Run workflow**

All OCI resources (VM, VCN, subnets, security list) will be deleted.

---

## Troubleshooting

### "Out of Capacity" error during deploy

OCI A1 ARM instances are popular and sometimes unavailable. The deploy workflow automatically retries up to **10 times** with a **60-second pause** between attempts. If it still fails after 10 retries:

1. Try a different availability domain — edit `main.tf` line with `availability_domains[0]` to `[1]` or `[2]`
2. Try a different region — update `OCI_REGION` secret and retry
3. Try at a different time of day — capacity fluctuates

### SSH connection refused

- Wait 5–10 minutes — cloud-init is still running packages
- Verify the security list has port 22 open (check OCI Console → Networking → VCN → Security Lists)
- Ensure you're using the correct key: `ssh -i ~/.ssh/oci_homelab ubuntu@PUBLIC_IP`
- Check cloud-init logs: once connected, run `sudo tail -f /var/log/cloud-init-output.log`

### Airflow not starting / UI not accessible

```bash
# Check if Airflow processes are running
ps aux | grep airflow

# View logs
tail -100 ~/airflow/logs/webserver.log
tail -100 ~/airflow/logs/scheduler.log

# Restart manually
export AIRFLOW_HOME=/home/ubuntu/airflow
pkill -f "airflow webserver" || true
pkill -f "airflow scheduler" || true
nohup airflow webserver --port 8080 > ~/airflow/logs/webserver.log 2>&1 &
nohup airflow scheduler > ~/airflow/logs/scheduler.log 2>&1 &
```

Also verify the OCI firewall (port 8080 in security list) AND the OS-level iptables:

```bash
sudo iptables -L INPUT -n | grep 8080
# If missing:
sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
```

### DAG shows import error in Airflow UI

```bash
# Test the DAG directly
airflow dags list-import-errors

# Check Python imports
python3 /home/ubuntu/airflow/dags/stock_pipeline.py
```

---

## What Gets Installed and Why

| Package | Why |
|---------|-----|
| `yfinance` | Download OHLCV stock data from Yahoo Finance |
| `ta-lib-binary` | Technical analysis (wheel avoids C build complexity) |
| `chromadb` | Local vector database for future RAG features |
| `groq` | Official Groq Python SDK — fast LLM inference |
| `langchain` + `langchain-community` | LLM orchestration framework |
| `psycopg2-binary` | PostgreSQL adapter for Python |
| `pandas` | Data manipulation and RSI/MACD calculation |
| `apache-airflow` | Workflow orchestration and scheduling |
| `vastai` | VastAI GPU rental API (for future GPU jobs) |
| `python-telegram-bot` | Send formatted alerts to Telegram |
| `docker.io` + `docker-compose` | Container runtime for future services |
| `postgresql` | Local database for signal persistence |

---

## Next Steps — Adding More DAGs

The Airflow dags folder is at `~/airflow/dags/`. Drop any `.py` file there and Airflow picks it up within 30 seconds.

Ideas to extend the pipeline:

```
dags/
├── stock_pipeline.py          # Already included — daily signals
├── options_flow.py            # Unusual options activity scanner
├── earnings_calendar.py       # Pre-earnings volatility alerts
├── portfolio_tracker.py       # Track a virtual portfolio P&L
└── news_sentiment.py          # Scrape headlines and run sentiment LLM
```

To add a new DAG:

```bash
# On the VM
cp my_new_dag.py ~/airflow/dags/
airflow dags list  # Verify it appears
```

---

## Architecture Diagram

```
GitHub Actions
     │  push to main
     ▼
Terraform (OCI Provider)
     │  creates
     ▼
OCI VCN (10.0.0.0/16)
  └── Public Subnet (10.0.1.0/24)
       └── VM.Standard.A1.Flex (Ubuntu 24.04 ARM)
            ├── PostgreSQL  :5432  → ai_pipeline DB
            ├── Airflow UI  :8080  → stock_market_pipeline DAG
            │    ├── fetch_stock_data   (yfinance)
            │    ├── analyze_with_llm   (Groq LLM)
            │    └── send_alerts        (Telegram Bot)
            └── Docker             → future services
```

---

## Security Notes

- The security list opens ports to `0.0.0.0/0` for simplicity. In production, restrict PostgreSQL (5432) to your IP only.
- Airflow runs without TLS. Do not expose the admin credentials publicly.
- Rotate your OCI API key and Groq API key periodically.
- The `terraform.tfvars` and `*.pem` files are in `.gitignore` — never commit them.
