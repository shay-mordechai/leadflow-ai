# LeadFlowAI 🛡️

**Secure-by-Design Full-Stack SaaS Platform with Multimodal AI Agents.**

LeadFlowAI is a next-generation CRM & AI Agent platform engineered with a **Security-First mindset**. It demonstrates a robust DevSecOps pipeline, utilizing a **Zero Trust** network architecture and **React Server Components (RSC)** to eliminate external attack surfaces while providing a modern, high-performance user experience.

The system features a **Hybrid AI Engine** combining **Local Privacy-First Processing** (Whisper) with Cloud Intelligence (Gemini) to manage bookings, transcribe meetings, and automate customer inquiries via WhatsApp.

## 🏗️ Security Architecture Overview

The infrastructure creates a "Dark Server" environment. The production server exposes **zero** inbound ports (0.0.0.0/0) to the public internet. All ingress traffic is tunneled and inspected via Cloudflare's Edge Network to the Next.js Frontend.

The architecture leverages **Next.js 14 App Router**, where the Frontend Server talks directly to the Backend API within the internal Docker network, reducing client-side latency and exposure.

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
            Frontend[Next.js 14 Server (RSC)]
            Backend[FastAPI Service]
            
            Frontend <-->|Internal Docker Network| Backend
        end
        
        Backend -.->|Local Processing| Whisper[Whisper AI (CPU)]
        Backend -.->|Storage| DB[(PostgreSQL)]
    end

```

## 🔐 Key Security Implementations

### 1. Zero Trust Network Access (ZTNA)

* **Attack Surface Reduction:** SSH and HTTP ports (22, 80, 443) are blocked at the AWS Security Group level.
* **Identity-Aware Proxy (IAP):** SSH access is proxied via `cloudflared`. Authentication requires passing Cloudflare Access policies.

### 2. Strict Data Sanitization (The "Air Gap")

* **Pydantic Response Models:** We implement a strict "First Line of Defense" in the backend. API endpoints use specific Pydantic Output Schemas (`UserResponse`) that automatically strip sensitive fields (password hashes, internal IDs, OTP codes) before serialization.
* **React Server Components (RSC):** Data fetching occurs server-side. Sensitive business logic remains in the Next.js server environment and is never exposed to the client browser via `useEffect` waterfalls.

### 3. Secrets Management Strategy

* **AWS Systems Manager (SSM):** Production secrets (DB credentials, API Keys, SMTP configs) are stored securely in AWS SSM Parameter Store.
* **Runtime Injection:** Secrets are loaded directly into the application environment at runtime using `boto3`, ensuring no sensitive data exists in the file system or `.env` files.

### 4. Hardened Container Runtime

* **Daemonless & Rootless:** The platform runs on **Podman** instead of Docker to mitigate container breakout vulnerabilities.
* **Systemd Integration:** Services are managed via `systemd` user units for persistence and auto-recovery.

## 🧠 AI & Business Logic

The platform powers a **Smart Business Assistant** capable of:

* **Local Audio Transcription:** Uses **OpenAI Whisper** running locally on the EC2 instance to transcribe voice notes without third-party data leaks.
* **Intelligent Reasoning:** Uses **Google Gemini 1.5 Flash** for complex intent analysis and conversation flow.
* **Automated Documentation:** Generates professional **PDF Meeting Summaries** and receipts automatically using `FPDF`.
* **Secure Communications:** Asynchronous email notifications (OTP, Receipts) via `fastapi-mail` and WhatsApp integration via Twilio.

## 🔄 SaaS Workflow & Business Logic

The platform implements a complete End-to-End SaaS lifecycle, managing the user journey from registration to AI deployment:

### 1. Onboarding & Identity
* **Secure Registration:** Users sign up with strict password policies (Bcrypt hashing).
* **MFA Verification:** A 2-step verification process via Email OTP ensures account integrity before access is granted.
* **Business Profiling:** Users define their business persona (Tone, Services, Pricing), which dynamically injects context into the AI model.

### 2. Subscription & Billing Engine
* **Webhook-Driven Payments:** Integration with external payment providers (Mock/Morning/Stripe).
* **Real-time Upgrades:** Listens for secure payment webhooks to instantly upgrade users from `STARTER` to `PRO` tiers.
* **Coupon System:** Built-in logic for promotional campaigns and admin overrides.

### 3. Telephony Aggregator Module
* **Multi-Provider Search:** A smart aggregation layer that queries multiple providers (**Twilio, Vonage, Plivo**) simultaneously.
* **Cost Optimization:** The system automatically compares rates and presents the user with the most cost-effective phone numbers available in their region (IL/US).
* **Automated Provisioning:** Once purchased, the number is instantly configured with the correct Webhook URLs to route traffic to the AI Agent.

### 4. The AI Runtime (The "Brain")
* **Context-Aware Responses:** Incoming WhatsApp messages are analyzed against the user's specific `BusinessProfile`.
* **RAG-Lite Architecture:** The AI retrieves relevant business context (Hours, Prices) before generating a response using **Gemini 1.5**.

## 💻 Modern Tech Stack

| Domain | Technologies |
| --- | --- |
| **Frontend** | **Next.js 14 (App Router / RSC)**, TypeScript, Tailwind CSS, Lucide Icons |
| **Backend** | Python 3.11, **FastAPI**, Pydantic V2, SQLAlchemy |
| **AI & NLP** | **Whisper (Local)**, Google Gemini 1.5, FPDF2 |
| **Infrastructure** | **Podman (Rootless)**, Cloudflare Zero Trust, **AWS EC2 & SSM** |
| **Auth & Security** | JWT (Stateless), **MFA (Email OTP)**, BCrypt, RBAC |

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
