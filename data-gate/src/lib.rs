// src/lib.rs
use log::{info, warn};
use proxy_wasm::traits::*;
use proxy_wasm::types::*;
use serde_json::{json, Value};

// Define the sensitive fields that must be redacted.
// Expanded to include common SSM secrets and tokens to prevent data leakage.
const SENSITIVE_FIELDS: &[&str] = &[
    "password",
    "credit_card",
    "internal_token",
    "ssn",
    "api_key",
    "access_token",     // Added for OAuth/API token protection
    "refresh_token",    // Added for session token protection
    "db_password",      // Added for database credential protection
    "client_secret",    // Added for application secret protection
    "auth_token"        // General catch-all for auth tokens
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
                
                // Optionally remove the header so the client doesn't see it
                self.set_http_response_header("X-Data-TTL", None);
                
                // 🛑 THE MAGIC FIX: Remove Content-Length so curl doesn't hang! 🛑
                self.set_http_response_header("Content-Length", None);
            }
        }
        Action::Continue
    }

    fn on_http_response_body(&mut self, body_size: usize, end_of_stream: bool) -> Action {
        if !self.should_redact {
            return Action::Continue;
        }

        if !end_of_stream {
            // Buffer the body until the stream is complete.
            // This is necessary for JSON parsing, as partial JSON is invalid.
            return Action::Pause;
        }

        // Retrieve the full response body.
        if let Some(body_bytes) = self.get_http_response_body(0, body_size) {
            match serde_json::from_slice::<Value>(&body_bytes) {
                Ok(mut json_body) => {
                    // Recursively redact sensitive fields.
                    redact_sensitive_fields(&mut json_body);

                    // Serialize the modified JSON back to a string.
                    match serde_json::to_string(&json_body) {
                        Ok(new_body) => {
                            // Replace the response body with the redacted version.
                            self.set_http_response_body(0, body_size, new_body.as_bytes());
                            info!("Data Hop Firewall: Response body redacted successfully.");
                        }
                        Err(e) => {
                            warn!("Data Hop Firewall: Failed to serialize redacted JSON: {}. Passing raw body.", e);
                            // Fail-safe: pass original body if serialization fails
                            self.set_http_response_body(0, body_size, &body_bytes);
                        }
                    }
                }
                Err(e) => {
                    warn!("Data Hop Firewall: Failed to parse response body as JSON: {}. Passing raw body.", e);
                    // Fail-safe: If it's an HTML error page or empty, just pass it through without panicking
                    self.set_http_response_body(0, body_size, &body_bytes);
                }
            }
        }

        Action::Continue
    }
}

/// Recursively traverses a JSON Value and redacts sensitive fields.
fn redact_sensitive_fields(value: &mut Value) {
    match value {
        Value::Object(map) => {
            // Use clone to iterate safely while modifying the original map
            let keys: Vec<String> = map.keys().cloned().collect();
            for key in keys {
                // Check if the key is in our list of sensitive fields (case-insensitive check is safer).
                let key_lower = key.to_lowercase();
                if SENSITIVE_FIELDS.iter().any(|&s| s == key_lower.as_str()) {
                    map.insert(key, json!("[REDACTED]"));
                } else if let Some(val) = map.get_mut(&key) {
                    // Recursively process nested objects and arrays.
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