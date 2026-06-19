# MyLeads AI — Frontend

> **Production SaaS** · Next.js 14 · TypeScript · RTL (Hebrew) · AI-powered CRM

The frontend of [MyLeads AI](https://my-leads.app) — a full-stack AI lead management platform built for Israeli fitness & wellness businesses. This layer handles everything the end user sees: authentication, the live AI chat simulator, the leads dashboard, KYC flows, and the agency partner portal.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS + Heebo font (Hebrew RTL) |
| Testing | Vitest (unit) + Playwright (e2e) |
| Analytics | PostHog (pageviews, funnels, dogfooding) |
| Auth | httpOnly JWT cookies + Remember Me |
| Build | Docker + GitHub Actions CI/CD |

---

## Key Features

**AI Chat Simulator**
Live interface that mirrors the AI agent's conversation flow. Supports feature toggles, direct lightning-mode responses, and real-time sync with backend state.

**Lead Management Dashboard**
Full CRM view with skeleton loaders, toast notifications (react-hot-toast), and human handoff indicators. Supports RTL layout natively.

**KYC Flow**
Persistent identity verification via localStorage with multi-step form logic and validation.

**Agency Partner Portal**
Dedicated `/dashboard/agency` view with leaderboard, conversion tracking, and AI-graded lead quality metrics per partner.

**Authentication**
Secure login with httpOnly cookie-based JWT, Remember Me persistence, and client-side cooldown locks on sensitive triggers (anti-DDoS UX).

---

## Project Structure

```
frontend/
├── app/              # Next.js App Router pages & layouts
├── components/       # Reusable UI components
├── actions/          # Server actions (auth, forms)
├── lib/              # Utilities, API clients
├── types/            # Shared TypeScript types
├── __tests__/        # Vitest unit tests
└── e2e/              # Playwright end-to-end tests
```

---

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

**Environment variables required:**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_POSTHOG_KEY=...
```

---

## Testing

```bash
# Unit tests (Vitest)
npm run test

# End-to-end tests (Playwright)
npm run test:e2e
```

---

## Development Approach

This project was built entirely using AI-assisted development — Claude, Cursor, and ChatGPT were used daily for code generation, prompt refinement, architecture decisions, and debugging. The goal was to move fast without sacrificing structure: every major feature is tested, typed, and documented.

---

## Related

- [Backend (Python/FastAPI)](../src/) — AI agent engine, webhook handling, telephony integrations
- [Infrastructure](../nginx/) — Nginx + Cloudflare Zero Trust + Docker Compose
- [Security Layer](../data-gate/) — WASM DLP Firewall (Rust/Envoy)
