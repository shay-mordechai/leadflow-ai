# System Topology & Runtime Architecture

## Production Topology (`leadflow-cx23` — Hetzner Cloud)
LeadFlow runs as a **Rootless Podman Pod (`leadflow-prod.pod`)** managed by **Systemd Quadlets** (`~/.config/containers/systemd/leadflow/`) with `loginctl enable-linger` enabled for user `deployer`.

- **Zero Public Inbound Ports:** Hetzner firewall blocks all inbound TCP/UDP ports. External HTTPS traffic enters strictly through **Cloudflare Tunnel** (`cloudflared`) to `127.0.0.1:10000`.
- **Shared Loopback Network Namespace:** All containers inside `leadflow-prod.pod` communicate over `127.0.0.1` without Docker bridge NAT overhead or host port exposure.

| Container | Unit File | Internal Port | Host Port | Role |
| :--- | :--- | :--- | :--- | :--- |
| `leadflow-data-gate` | `leadflow-data-gate.container` | `10000` | `127.0.0.1:10000` | Envoy L7 ingress router + Rust/Wasm `data_hop_firewall` DLP |
| `leadflow-backend` | `leadflow-backend.container` | `8000` | None | FastAPI async API, webhooks, `AgentHarness` |
| `leadflow-frontend` | `leadflow-frontend.container` | `3000` | None | Next.js 16 standalone UI (`/`, `/dashboard`, `/privacy`, `/terms`) |
| `leadflow-worker` | `leadflow-worker.container` | — | None | Celery background worker (async tasks, audio/Whisper, retries) |
| `leadflow-beat` | `leadflow-beat.container` | — | None | Single-instance Celery Beat scheduler (Watchdog, GDPR purge) |
| `leadflow-db` | `leadflow-db.container` | `5432` | None | PostgreSQL 15 (`pgvector/pgvector:pg15` target) with `FORCE RLS` |
| `leadflow-redis` | `leadflow-redis.container` | `6379` | None | Debounce locks, webhook dedup (`SET NX`), JWT revocation, token budgets |

## Podman Pod Loopback Binding Rule (Next.js)
Podman injects `HOSTNAME=leadflow-prod` into pod containers at runtime, overriding Dockerfile `ENV HOSTNAME="0.0.0.0"`. Both `frontend/Dockerfile` and `leadflow-frontend.container` start Next.js via:
```sh
sh -c "HOSTNAME=0.0.0.0 exec node server.js"

```

This guarantees Envoy (`leadflow_frontend` cluster -> `127.0.0.1:3000`) always connects over loopback without `503 Service Unavailable`.

## Local Test Topology (`leadflow-test.pod`)

Local testing on Fedora (`devops-box`) mirrors production using `leadflow-test.pod` and `.env.test`, exposing `127.0.0.1:{10000,3000,8000,5432}` for automated Playwright/Pytest verification.
