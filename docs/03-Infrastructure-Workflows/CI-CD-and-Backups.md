
# CI/CD Pipeline & Disaster Recovery Backups

## Continuous Integration & Deployment (`.github/workflows/production.yml`)

1. **Quality & Security Gate:** Runs `ruff format --check`, `ruff check`, `Semgrep` SAST, `alembic check`, offline AI Golden Dataset evals (`scripts/run_evals.py --mode offline`), and `pytest` (`scripts/verify_harness.sh`).
2. **Container Build & Scan:** Builds `leadflow-backend`, `leadflow-frontend` (with `NEXT_PUBLIC_API_URL=https://my-leads.app` and `HOSTNAME=0.0.0.0`), and `leadflow-data-gate`, scans images with `Trivy`, and pushes to GHCR.
3. **Zero-DB-Downtime Production Rollout (`deploy.sh`):**
* Triggered via HMAC-SHA256 signed webhook (`300s` replay window).
* Pulls updated images and restarts only app-tier Systemd Quadlet units (`leadflow-backend`, `leadflow-worker`, `leadflow-beat`, `leadflow-frontend`, `leadflow-data-gate`) inside `leadflow-prod.pod`.
* Leaves `leadflow-db` and `leadflow-redis` running continuously, then executes `alembic upgrade head` and verifies `https://my-leads.app/health/db-sync-status`.


4. **Autonomous CI Triage (`.github/workflows/ci-triage.yml`):** Automatically inspects failed CI/deploy runs and posts root-cause diagnostics.

## Backups & GDPR Data Retention

* **Cloudflare R2 Backups:** Scheduled `pg_dump -Fc` snapshots are compressed and uploaded to Cloudflare R2 object storage. Monthly restore drills verify backup integrity in an isolated staging container.
* **90-Day GDPR Purge:** Daily Celery Beat job purges expired raw conversation logs and temporary media older than 90 days in compliance with privacy commitments.
