
# Edge Security & Rust/Wasm Data Hop Firewall (`data-gate/`)

## Architecture (`Envoy Proxy + WebAssembly`)

`leadflow-data-gate` runs Envoy Proxy on `127.0.0.1:10000` inside `leadflow-prod.pod`, terminating all traffic from Cloudflare Tunnel and routing:

* `/api/*`, `/webhooks/*`, `/health/*`, `/openapi.json` → `leadflow_backend` (`127.0.0.1:8000`)
* `/*` → `leadflow_frontend` (`127.0.0.1:3000`)

## `data_hop_firewall.wasm` (Fail-Closed Edge DLP)

* **Trigger Contract:** Inspects HTTP responses tagged with `X-Data-TTL: 1` (external hop boundary).
* **Recursive JSON Redaction:** Traverses nested JSON objects and arrays to redact **41 sensitive PII and credential keys** (passwords, tokens, API keys, government IDs, financial fields) before responses leave the pod.
* **Fail-Closed Guarantee:** If JSON serialization fails during redaction on a `TTL=1` payload, Envoy drops/blocks the response rather than leaking raw data.
* **Performance Benchmark:** `< 2%` throughput overhead, `-0.30 ms` median P50 delta, `0%` non-2xx error increase.
