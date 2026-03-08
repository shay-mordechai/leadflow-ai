# 🛡️ Data Hop Firewall (Envoy Wasm Filter)

> **Zero-Trust Data Flow Control for Microservices.** > Enforcing L7 Data Bleed Prevention via Logical Data TTL and WebAssembly.

## 📖 Overview

In modern microservice architectures (e.g., Next.js React Server Components, decoupled backends), **Data Bleed** and **Over-fetching** have become critical security vulnerabilities. Often, backend services pull massive objects from a database and transmit them entirely across service boundaries, relying on the frontend to filter what the user sees. This architectural flaw exposes sensitive PII and internal tokens to the network layer, leading to severe IDOR and BOLA vulnerabilities.

The **Data Hop Firewall** introduces a novel concept: **Logical Data TTL (Time-To-Live)**. 
Built as a highly optimized WebAssembly (Wasm) plugin for **Envoy Proxy**, it actively enforces Data Contracts at the infrastructure layer. It intercepts JSON payloads and deterministically drops or redacts sensitive fields based on the contextual "Hop" limit, ensuring that internal backend "whispers" never leak to public frontends.

## ✨ Core Features

* **Logical TTL Enforcement:** Inspects custom headers (e.g., `X-Data-TTL`, `X-Data-Context`) to determine the allowed exposure level of the payload.
* **Recursive Redaction:** Deeply traverses JSON responses to identify and redact sensitive keys (e.g., `password`, `credit_card`, `ssn`), regardless of how deeply nested they are.
* **Fail-Closed Security:** Operates on a strict zero-trust model. If JSON parsing fails or serialization encounters an error during redaction, the payload is dropped to prevent accidental data exposure.
* **High Performance:** Written in memory-safe **Rust** and compiled to WebAssembly, ensuring near-zero latency overhead when deployed in an Envoy Sidecar or API Gateway.

## 🏗️ Architecture: "The Whisper Pipe"

Unlike traditional Network Firewalls (L3/L4) that block IPs, or API Security tools that passively monitor traffic, this Wasm filter acts as an active **L7 Data Gatekeeper**. 

1. **Hop 0 (DB -> Backend):** Backend retrieves a full user object.
2. **Hop 1 (Backend -> Frontend):** The Backend attempts to send the object across the network.
3. **Interception:** The Envoy Proxy (running this Wasm filter) intercepts the response. Recognizing the data boundary (TTL=1), it surgically removes sensitive fields from the JSON payload in-memory.
4. **Delivery:** The Frontend receives a sanitized payload, completely blind to the original sensitive data.

## 🛠️ Build Instructions

### Prerequisites
* [Rust Toolchain](https://rustup.rs/) (latest stable)
* Envoy Proxy (v1.20+)

### Compilation
Add the WebAssembly compilation target to your Rust environment:
```bash
rustup target add wasm32-unknown-unknown

```

Compile the filter in release mode (optimizes for binary size and performance):

```bash
cargo build --target wasm32-unknown-unknown --release

```

The compiled binary will be generated at:
`target/wasm32-unknown-unknown/release/data_hop_firewall.wasm`

## 🚀 Deployment (Envoy Integration)

To deploy this filter, mount the compiled `.wasm` file into your Envoy container and configure your `envoy.yaml` to load it via the `envoy.filters.http.wasm` extension.

*(Note: Envoy configuration requires defining the VM configuration and routing the specific clusters through this HTTP filter).*

## 🔬 Security & Compliance

This project strictly avoids dynamic memory allocation pitfalls during payload traversal and aborts on panic to prevent Wasm VM escapes. It is designed to aid organizations in maintaining strict compliance (GDPR, HIPAA) by physically restricting data flow.

---

*Developed by [Shay Mordechai](https://github.com/shay-mordechai) | Security Researcher & Systems Architect*
