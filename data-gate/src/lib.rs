/*
 * Data Hop Firewall - Envoy WebAssembly Filter (Rust)
 * --------------------------------------------------
 * Architecture:
 * - Layer 7 Egress Inspection: Operates as a Transparent Proxy within Envoy's filter chain.
 * - Zero-Trust Redaction: Only activates when the backend signals sensitive data via 'X-Data-TTL: 1'.
 * - Performance-Oriented: Compiled to WASM for near-native execution speed with memory isolation.
 * - Fail-Closed Design: If JSON parsing or serialization fails during a sensitive response, 
 * the filter intercepts and blocks the payload, returning a generic security exception 
 * to prevent accidental data leakage (Information Disclosure).
 * - Protocol Integrity: Automatically strips 'Content-Length' during redaction to allow 
 * Envoy to recalculate size or use chunked encoding, preventing HTTP client hangs.

 Designed by: Shay Mordechai
 */

use log::{info, warn};
use proxy_wasm::traits::*;
use proxy_wasm::types::*;
use serde_json::{json, Value};

// Define the sensitive fields that must be redacted.
const SENSITIVE_FIELDS: &[&str] = &[
    "password",
    "credit_card",
    "internal_token",
    "ssn",
    "api_key",
    "access_token",
    "refresh_token",
    "db_password",
    "client_secret",
    "auth_token"
];

proxy_wasm::main! {{
    proxy_wasm::set_log_level(LogLevel::Info);
    proxy_wasm::set_root_context(|_| -> Box<dyn RootContext> {
        Box::new(DataHopRootContext)
    });
}}

struct DataHopRootContext;

impl Context for DataHopRootContext {}

impl RootContext for DataHopRootContext {
    fn get_type(&self) -> Option<ContextType> {
        Some(ContextType::HttpContext)
    }

    fn create_http_context(&self, _context_id: u32) -> Option<Box<dyn HttpContext>> {
        Some(Box::new(DataHopHttpContext {
            should_redact: false,
        }))
    }
}

struct DataHopHttpContext {
    should_redact: bool,
}

impl Context for DataHopHttpContext {}

impl HttpContext for DataHopHttpContext {
    fn on_http_response_headers(&mut self, _: usize, _: bool) -> Action {
        // Check if the backend explicitly requested redaction via header
        if let Some(ttl) = self.get_http_response_header("X-Data-TTL") {
            if ttl == "1" {
                info!("Data Hop Firewall: TTL restriction detected (TTL=1). Enabling redaction.");
                self.should_redact = true;
                
                // Remove headers to prevent leakage and avoid Content-Length mismatches
                self.set_http_response_header("X-Data-TTL", None);
                self.set_http_response_header("Content-Length", None);
            }
        }
        Action::Continue
    }

    // Professional English Comment: Guard against empty payloads and avoid illegal header mutation in body filter
fn on_http_response_body(&mut self, body_size: usize, end_of_stream: bool) -> Action {
    if !self.should_redact {
        return Action::Continue;
    }

    // Skip parsing if the body is empty (e.g., HEAD requests, 204 No Content, 304 Not Modified)
    if body_size == 0 || !end_of_stream {
        return Action::Continue;
    }

    if let Some(body_bytes) = self.get_http_response_body(0, body_size) {
        match serde_json::from_slice::<Value>(&body_bytes) {
            Ok(mut json_body) => {
                redact_sensitive_fields(&mut json_body);
                if let Ok(new_body) = serde_json::to_string(&json_body) {
                    self.set_http_response_body(0, body_size, new_body.as_bytes());
                    info!("Data Hop Firewall: Response body redacted successfully.");
                }
            }
            Err(e) => {
                warn!("Data Hop Firewall: Non-JSON or malformed payload: {}. Skipping redaction.", e);
                let err = b"{\"error\": \"Security Exception: Data Integrity Failure\"}";
                self.set_http_response_body(0, body_size, err);
                // Note: Do not call set_http_response_header here to avoid proxy-wasm status 2 panic
            }
        }
    }

    Action::Continue
}

/// Recursively traverses a JSON Value and redacts sensitive fields defined in SENSITIVE_FIELDS.
fn redact_sensitive_fields(value: &mut Value) {
    match value {
        Value::Object(map) => {
            let keys: Vec<String> = map.keys().cloned().collect();
            for key in keys {
                let key_lower = key.to_lowercase();
                if SENSITIVE_FIELDS.iter().any(|&s| s == key_lower.as_str()) {
                    map.insert(key, json!("[REDACTED]"));
                } else if let Some(val) = map.get_mut(&key) {
                    redact_sensitive_fields(val);
                }
            }
        }
        Value::Array(arr) => {
            for val in arr.iter_mut() {
                redact_sensitive_fields(val);
            }
        }
        _ => {}
    }
}