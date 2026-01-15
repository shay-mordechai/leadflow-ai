# LeadFlowAI 🚀

**Next-Gen SaaS CRM for Service Providers.**
LeadFlowAI is a secure, containerized SaaS platform designed to automate lead intake via WhatsApp, process audio using AI, and manage customer relationships with strict data isolation.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)
![Podman](https://img.shields.io/badge/Podman-Ready-892CA0.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ Key Features

* **🏢 True SaaS Architecture:** Built from the ground up with **User-Based Multi-Tenancy**. Each user sees only their own data.
* **🔐 Secure Authentication:** Complete Registration & Login flows using JWT tokens and password hashing (Argon2/BCrypt).
* **🎙️ AI Audio Pipeline:** (In Progress) Ingests WhatsApp voice notes, transcribes via **Whisper**, and summarizes via LLMs.
* **🛡️ Hardened Security:**
    * Dependency Injection based Security Gates (`dependencies.py`).
    * Strict Context Variable isolation for user requests.
    * Encryption-at-Rest for sensitive PII data.
* **🐳 Cloud Native:** Fully containerized with Podman/Docker, ready for CI/CD deployment via GitHub Actions.

## 🛠️ Tech Stack

* **Backend:** FastAPI (Python), SQLAlchemy (Sync/Async), Pydantic.
* **Database:** PostgreSQL 15.
* **Environment Management:** Miniforge / Mamba.
* **Containerization:** Podman & Docker Compose.
* **Frontend:** Server-Side Rendering (Jinja2) + TailwindCSS.
* **DevOps:** GitHub Actions (Build & Push to GHCR).

## 🚀 Getting Started

### Prerequisites
* **Podman** (Recommended) or Docker.
* **Python 3.11+** (if running locally without containers).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/shay-mordechai/leadflow-ai.git](https://github.com/shay-mordechai/leadflow-ai.git)
    cd leadflow-ai
    ```

2.  **Environment Setup:**
    Create a `.env` file in the root directory:
    ```ini
    # App Config
    SECRET_KEY=your_super_secret_key_change_this
    DEBUG=True

    # Database
    POSTGRES_USER=myuser
    POSTGRES_PASSWORD=mypassword
    POSTGRES_DB=leadflow
    POSTGRES_HOST=127.0.0.1
    # Internal Docker URL: postgresql://myuser:mypassword@db:5432/leadflow
    ```

3.  **Run with Podman/Docker:**
    ```bash
    # Build and start the App and DB
    podman-compose up -d --build
    ```

4.  **Initialize Database (Nuclear Reset):**
    ⚠️ *Note: This script wipes the public schema and creates the new SaaS tables (Users, Leads).*
    ```bash
    podman exec leadflow_app python src/scripts/reset_db_schema.py
    ```

5.  **Access the App:**
    * **Landing Page:** `http://localhost:8000`
    * **Login/Dashboard:** `http://localhost:8000/login`
    * **Docs:** `http://localhost:8000/docs`

## 📂 Project Structure

```text
├── src/
│   ├── database/      
│   │   ├── models.py      # User & Lead Models
│   │   └── session.py     # DB Connection logic
│   ├── routers/       
│   │   ├── auth.py        # Login/Register endpoints
│   │   ├── leads.py       # Protected Lead management
│   │   └── ui.py          # Frontend views
│   ├── security/      
│   │   └── dependencies.py # Auth Gatekeeper (Context Vars)
│   ├── scripts/
│   │   └── reset_db_schema.py # Migration utility
│   ├── templates/         # HTML (Jinja2) UI
│   └── main.py            # App entry point
├── docker-compose.yml
└── requirements.txt

```

## 🔄 CI/CD Workflow

This project uses **GitHub Actions** for automated deployment:

1. **Push to Main:** Code is linted and built.
2. **Build:** A container image is created and pushed to `ghcr.io`.
3. **Deploy:** The EC2 server pulls the new image and restarts the service via SSH.

## 👤 Author

**Shay Mordechai**

* Full-Stack Developer & Security Researcher.
* Specializing in Secure SaaS Architecture & AI Automation.

---

*Built with ❤️ and Python.*
