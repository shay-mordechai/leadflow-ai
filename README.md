# LeadFlowAI 🛡️

**Secure-by-Design SaaS Platform with AI-Driven Workflows.**

LeadFlowAI is a next-generation CRM platform engineered with a **Security-First mindset**. It demonstrates a robust DevSecOps pipeline, utilizing a **Zero Trust** network architecture to eliminate external attack surfaces while providing seamless, automated deployments.

## 🏗️ Security Architecture Overview

The infrastructure creates a "Dark Server" environment. The production server exposes **zero** inbound ports (0.0.0.0/0) to the public internet. All ingress traffic is tunneled and inspected via Cloudflare's Edge Network.

```mermaid
graph TD
    Attacker[⛔ Internet Scanners] -.->|Blocked (No Open Ports)| FW[AWS Security Group]
    
    User((Authorized User)) -->|HTTPS / mTLS| CF[Cloudflare Edge (WAF + Access)]
    GitHub((GitHub Actions)) -->|Service Token Auth| CF
    
    CF -->|Encrypted Tunnel (Argo)| Cloudflared[cloudflared Container]
    
    subgraph "Production (Fedora Linux / Hardened)"
        direction TB
        Cloudflared -->|Host Network| AppStack
        
        subgraph "App Stack (Rootless Podman)"
            API[FastAPI Service]
            Worker[Background Worker]
        end
        
        API -.->|Runtime Injection| SSM[AWS SSM Parameter Store]
    end

```

## 🔐 Key Security Implementations

### 1. Zero Trust Network Access (ZTNA)

* **Attack Surface Reduction:** SSH and HTTP ports (22, 80, 443) are blocked at the AWS Security Group level.
* **Identity-Aware Proxy (IAP):** SSH access is proxied via `cloudflared`. Authentication requires passing Cloudflare Access policies (Email OTP for humans, Service Tokens for CI/CD bots).
* **WAF & Bot Management:** Custom WAF rules configured to allow specific CI/CD pipeline traffic while mitigating automated threats and scanners (Bot Fight Mode integration).

### 2. Hardened Container Runtime

* **Daemonless & Rootless:** The platform runs on **Podman** instead of Docker. Containers run as non-root users to mitigate container breakout vulnerabilities.
* **Systemd Integration:** Services are managed via `systemd` user units, ensuring persistence and auto-recovery without requiring root privileges.
* **Immutable Infrastructure:** Containers are ephemeral; no state is stored inside the application container.

### 3. Secrets Management Strategy

* **No .env Files:** Production secrets are never stored on the disk or committed to Git.
* **Runtime Injection:** Sensitive data (DB credentials, API Keys) is fetched dynamically from **AWS Systems Manager (SSM) Parameter Store** during the container startup phase using AWS SDK.
* **Least Privilege:** IAM roles and Cloudflare Tokens are scoped strictly to the minimum required permissions.

## 🔄 Secure CI/CD Pipeline (DevSecOps)

The deployment pipeline demonstrates how to automate "Click-to-Deploy" without compromising security boundaries:

1. **Build & Scan:** Code is linted, built into OCI-compliant images, and pushed to **GHCR**.
2. **Tunnel Authentication:** The GitHub Runner authenticates against the Cloudflare Edge using high-entropy **Service Tokens** (Client ID/Secret) to bypass Zero Trust policies.
3. **Encrypted Transport:** Deployment commands are sent over a secure WebSocket tunnel (SSH over HTTPS), eliminating the need for a VPN.
4. **Surgical Update:** The pipeline performs a zero-downtime container replacement on the target server without disrupting the tunnel infrastructure.

## 🛠️ Tech Stack

| Domain | Technologies |
| --- | --- |
| **Backend** | Python 3.11, FastAPI, Pydantic, SQLAlchemy (Async) |
| **Security** | Cloudflare Zero Trust (Tunnels, Access, WAF), Argon2 Hashing, JWT |
| **Cloud & DevOps** | AWS (SSM, EC2), GitHub Actions, Podman (Rootless), Systemd |
| **Database** | PostgreSQL 15, Alembic |
| **AI Processing** | Faster-Whisper (Quantized), LLM Integration |

## 🚀 Local Development

To spin up the environment locally (bypassing the Zero Trust layer):

```bash
# Clone the repo
git clone https://github.com/shay-mordechai/leadflow-ai.git

# Start services using Podman Compose
podman-compose up -d --build

# Access Documentation
open http://localhost:8000/docs

```

## 👤 Author

**Shay Mordechai**

* **Cloud Security Enthusiast & Full-Stack Developer.**
* Passionate about bridging the gap between modern software development and enterprise-grade security architecture.
* *Connect with me to discuss Cloud Security, ZTNA, or Python.*

---

*Verified Secure Deployment via GitHub Actions.* 🟢