# LeadFlowAI 🛡️

**Secure-by-Design Full-Stack SaaS Platform with Multimodal AI Agents.**

LeadFlowAI is a next-generation CRM & AI Agent platform engineered with a **Security-First mindset**. It demonstrates a robust DevSecOps pipeline, utilizing a **Zero Trust** network architecture to eliminate external attack surfaces while providing a modern, reactive user experience.

The system features a **Hybrid AI Engine** combining **Local Privacy-First Processing** (Whisper) with Cloud Intelligence (Gemini) to manage bookings, transcribe meetings, and automate customer inquiries via WhatsApp.

## 🏗️ Security Architecture Overview

The infrastructure creates a "Dark Server" environment. The production server exposes **zero** inbound ports (0.0.0.0/0) to the public internet. All ingress traffic is tunneled and inspected via Cloudflare's Edge Network to the Next.js Frontend, which proxies API requests internally.

```mermaid
graph TD
    Attacker[⛔ Internet Scanners] -.->|Blocked (No Open Ports)| FW[AWS Security Group]
    
    User((Authorized User)) -->|HTTPS / mTLS| CF[Cloudflare Edge (WAF + Access)]
    GitHub((GitHub Actions)) -->|Service Token Auth| CF
    
    CF -->|Encrypted Tunnel (Argo)| Cloudflared[cloudflared Container]
    
    subgraph "Production (Fedora Linux / Hardened)"
        direction TB
        Cloudflared -->|localhost:3000| Frontend
        
        subgraph "App Stack (Rootless Podman)"
            Frontend[Next.js 14 Client]
            Backend[FastAPI Service]
            
            Frontend <-->|Internal Docker Network| Backend
        end
        
        Backend -.->|Local Processing| Whisper[Whisper AI (CPU)]
        Backend -.->|Storage| DB[(SQLite/Postgres)]
    end

```

## 🔐 Key Security Implementations

### 1. Zero Trust Network Access (ZTNA)

* **Attack Surface Reduction:** SSH and HTTP ports (22, 80, 443) are blocked at the AWS Security Group level.
* **Identity-Aware Proxy (IAP):** SSH access is proxied via `cloudflared`. Authentication requires passing Cloudflare Access policies.
* **Frontend Proxying:** The Next.js frontend handles all API rewrites, hiding the backend topology from the client browser.

### 2. Hardened Container Runtime

* **Daemonless & Rootless:** The platform runs on **Podman** instead of Docker to mitigate container breakout vulnerabilities.
* **Systemd Integration:** Services (`container-leadflow-frontend`, `container-leadflow-backend`) are managed via `systemd` user units, ensuring persistence and auto-recovery.
* **Immutable Infrastructure:** Containers are ephemeral; state is persisted only in mounted volumes.

### 3. Secrets Management Strategy

* **No .env Files in Repo:** Production secrets are injected at runtime via CI/CD variables or **AWS Systems Manager (SSM)**.
* **MFA & OTP:** Custom implementation of Email-based Multi-Factor Authentication.

## 🧠 AI & Business Logic

The platform powers a **Smart Business Assistant** capable of:

* **Local Audio Transcription:** Uses **OpenAI Whisper** running locally on the EC2 instance to transcribe voice notes without third-party data leaks.
* **Intelligent Reasoning:** Uses **Google Gemini 1.5 Flash** for complex intent analysis and conversation flow.
* **Automated Documentation:** Generates professional **PDF Meeting Summaries** and receipts automatically using `FPDF`.
* **WhatsApp Integration:** Full bi-directional integration via Twilio API.

## 💻 Modern Tech Stack

| Domain | Technologies |
| --- | --- |
| **Frontend** | **Next.js 14**, React, TypeScript, Tailwind CSS, Lucide Icons |
| **Backend** | Python 3.11, **FastAPI**, Pydantic, SQLAlchemy |
| **AI & NLP** | **Whisper (Local)**, Google Gemini 1.5, FPDF2 |
| **Infrastructure** | **Podman (Rootless)**, Cloudflare Zero Trust, AWS EC2, GitHub Actions |
| **Communications** | **FastAPI-Mail**, Twilio API |

## 🔄 Secure CI/CD Pipeline (DevSecOps)

The deployment pipeline automates "Click-to-Deploy" for a multi-container architecture:

1. **Parallel Builds:** GitHub Actions builds Frontend and Backend images in parallel.
2. **Tunnel Authentication:** The Runner authenticates against the Cloudflare Edge using high-entropy **Service Tokens**.
3. **Encrypted Transport:** Deployment commands are sent over a secure WebSocket tunnel.
4. **Orchestrated Update:** Stops old containers, pulls new images, and restarts services with `systemd` persistence in under 30 seconds.

## 🚀 Local Development

To spin up the full environment locally:

```bash
# Clone the repo
git clone [https://github.com/shay-mordechai/leadflow-ai.git](https://github.com/shay-mordechai/leadflow-ai.git)

# Run via Docker Compose (Builds both Front & Back)
docker-compose up -d --build

# Access Application
# Frontend: http://localhost:3000
# Backend API Docs: http://localhost:8000/docs

```

## 👤 Author

**Shay Mordechai**

* **Cloud Security Enthusiast & Full-Stack Developer.**
* Passionate about bridging the gap between modern software development and enterprise-grade security architecture.
* *Connect with me to discuss Cloud Security, ZTNA, or Python.*

---

*Verified Secure Deployment via GitHub Actions.* 🟢