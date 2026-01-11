# LeadFlowAI 🚀

**AI-Powered CRM & Lead Management for Small Businesses.**
LeadFlowAI is a secure, cloud-ready SaaS platform designed to help coaches and service providers manage leads via WhatsApp voice notes, automate follow-ups, and schedule appointments intelligently.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ Key Features

* **🎙️ Voice-to-Data:** Analyzes WhatsApp voice notes using **Google Gemini AI** to extract lead intent, sentiment, and details.
* **🧠 Smart Replies:** Generates context-aware Hebrew reply drafts for WhatsApp with a single click.
* **📅 Smart Calendar:** Integrated scheduling system with 14-day availability management.
* **🔔 Retention Tools:** Automated follow-up reminders and visual indicators for "hot" leads.
* **📊 Data Ownership:** Full CSV export capabilities for tenant data sovereignty.
* **🔒 Enterprise Security:**
    * Argon2 & BCrypt hashing (Pre-hashed SHA-256 for compatibility).
    * Fernet Encryption for PII (Personal Identifiable Information) in the DB.
    * Rate Limiting & Secure Headers.

## 🛠️ Tech Stack

* **Backend:** FastAPI (Python), SQLAlchemy (Async), Pydantic.
* **Database:** PostgreSQL.
* **Caching & Broker:** Redis.
* **Async Tasks:** Celery (for AI processing and background jobs).
* **AI Engine:** Google Gemini Pro API.
* **Frontend:** Server-Side Rendering with Jinja2 + TailwindCSS.
* **Infrastructure:** Docker & Podman Compose.

## 🚀 Getting Started

### Prerequisites
* Docker & Docker Compose (or Podman).
* Google Gemini API Key.

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
    ALLOWED_HOSTS=["*"]

    # Database
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=postgres
    POSTGRES_DB=coaching_db
    DATABASE_URL=postgresql://postgres:postgres@db:5432/coaching_db

    # Redis
    REDIS_URL=redis://redis:6379/0

    # AI Service
    GOOGLE_API_KEY=your_gemini_api_key_here
    ```

3.  **Run with Docker/Podman:**
    ```bash
    # Build and start services
    docker-compose up -d --build
    ```

4.  **Initialize Database:**
    ```bash
    # Run the initialization script to create tables and seed demo data
    docker-compose exec web python src/scripts/init_db.py
    ```

5.  **Access the App:**
    Open your browser at `http://localhost:8000`.

## 📂 Project Structure

```text
├── src/
│   ├── database/      # SQLAlchemy models & session
│   ├── routers/       # API endpoints (leads, sessions)
│   ├── security/      # Encryption & Hashing logic
│   ├── services/      # AI integration & Celery tasks
│   ├── static/        # CSS & Assets
│   ├── templates/     # HTML (Jinja2) UI
│   └── main.py        # App entry point
├── docker-compose.yml
└── requirements.txt

```

## 🛡️ Security Note

This project uses **Encryption-at-Rest**. Sensitive fields (Phone, Name) are encrypted in the database using a symmetric key. Ensure you keep your `SECRET_KEY` safe in production.

## 👤 Author

**Shay Mordechai**

* Full-Stack Developer & Security Researcher.
* Passion for Cloud Architecture and AI Solutions.

---

*Built for the Modern Solopreneur.*
