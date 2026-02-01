# LeadFlowAI 🛡️

**Secure-by-Design SaaS Platform with Multimodal AI Agents.**

LeadFlowAI is a next-generation CRM & AI Agent platform engineered with a **Security-First mindset**. It demonstrates a robust DevSecOps pipeline, utilizing a **Zero Trust** network architecture to eliminate external attack surfaces while providing seamless, automated deployments.

The system features an autonomous **WhatsApp AI Agent** capable of understanding both **Text and Voice Notes** (Hebrew/English) to manage bookings, cancellations, and customer inquiries in real-time.

## 🏗️ Security Architecture Overview

The infrastructure creates a "Dark Server" environment. The production server exposes **zero** inbound ports (0.0.0.0/0) to the public internet. All ingress traffic is tunneled and inspected via Cloudflare's Edge Network.

```mermaid
graph TD
    Attacker[⛔ Internet Scanners] -.->|Blocked (No Open Ports)| FW[AWS Security Group]
    
    User((Authorized User)) -->|HTTPS / mTLS| CF[Cloudflare Edge (WAF + Access)]
    GitHub((GitHub Actions)) -->|Service Token Auth| CF
    Twilio((Twilio Webhook)) -->|Signed Request| CF
    
    CF -->|Encrypted Tunnel (Argo)| Cloudflared[cloudflared Container]
    
    subgraph "Production (Fedora Linux / Hardened)"
        direction TB
        Cloudflared -->|Host Network| AppStack
        
        subgraph "App Stack (Rootless Podman)"
            API[FastAPI Service]
            AI[AI Engine (Gemini)]
        end
        
        API -.->|Runtime Injection| SSM[AWS SSM Parameter Store]
    end

```

## 🔐 Key Security Implementations

### 1. Zero Trust Network Access (ZTNA)

* **Attack Surface Reduction:** SSH and HTTP ports (22, 80, 443) are blocked at the AWS Security Group level.
* **Identity-Aware Proxy (IAP):** SSH access is proxied via `cloudflared`. Authentication requires passing Cloudflare Access policies.
* **WAF & Bot Management:** Custom WAF rules configured to allow specific CI/CD pipeline traffic while mitigating automated threats.

### 2. Hardened Container Runtime

* **Daemonless & Rootless:** The platform runs on **Podman** instead of Docker to mitigate container breakout vulnerabilities.
* **Systemd Integration:** Services are managed via `systemd` user units, ensuring persistence and auto-recovery.
* **Immutable Infrastructure:** Containers are ephemeral; no state is stored inside the application container.

### 3. Secrets Management Strategy

* **No .env Files:** Production secrets are never stored on disk or committed to Git.
* **Runtime Injection:** Sensitive data (DB credentials, API Keys) is fetched dynamically from **AWS Systems Manager (SSM) Parameter Store**.

## 🧠 AI & Business Logic (New)

The platform powers a **Yoga Studio Management Agent** ("Lea") that handles:

* **Multimodal Input:** Native processing of **Voice Notes (Audio)** and Text via **Google Gemini 1.5 Flash**.
* **Complex Reasoning:** Handles conditional logic (e.g., "Cancel class if > 24h, otherwise waitlist").
* **WhatsApp Integration:** Full bi-directional integration via Twilio API.
* **Crash-Resilient Parsing:** Robust JSON handling to ensure 24/7 availability even with unpredictable LLM outputs.

## 🔄 Secure CI/CD Pipeline (DevSecOps)

The deployment pipeline demonstrates how to automate "Click-to-Deploy" without compromising security boundaries:

1. **Build & Scan:** Code is linted, built into OCI-compliant images, and pushed to **GHCR**.
2. **Tunnel Authentication:** The GitHub Runner authenticates against the Cloudflare Edge using high-entropy **Service Tokens**.
3. **Encrypted Transport:** Deployment commands are sent over a secure WebSocket tunnel (SSH over HTTPS).
4. **Surgical Update:** Zero-downtime container replacement on the target server.

## 🛠️ Tech Stack

| Domain | Technologies |
| --- | --- |
| **Backend** | Python 3.11, FastAPI, Pydantic, SQLAlchemy (Async) |
| **AI Core** | **Google Gemini 1.5 Flash** (Audio & Text Analysis) |
| **Integrations** | **Twilio** (WhatsApp API), Cloudflare Zero Trust |
| **Cloud & DevOps** | AWS (SSM, EC2), GitHub Actions, Podman (Rootless), Systemd |
| **Database** | PostgreSQL 15, Alembic |
| **Security** | Argon2, JWT, Cloudflare Access (mTLS/Service Tokens) |

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