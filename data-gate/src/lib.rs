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

#[no_mangle]
pub fn _start() {
    proxy_wasm::set_log_level(LogLevel::Info);
    proxy_wasm::set_root_context(|_| -> Box<dyn RootContext> {
        Box::new(DataHopRootContext)
    });
}

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
    fn on_http_response_headers(&mut self, _num_headers: usize, _end_of_stream: bool) -> Action {
        // Check for the "X-Data-TTL" header.
        // If the TTL is 1 or less, it implies the data should not leave the current boundary unredacted.
        if let Some(ttl_str) = self.get_http_response_header("X-Data-TTL") {
            if let Ok(ttl) = ttl_str.parse::<i32>() {
                if ttl <= 1 {
                    info!("Data Hop Firewall: TTL restriction detected (TTL={}). Enabling redaction.", ttl);
                    self.should_redact = true;
                }
            }
        }

        // Check for the "X-Data-Context" header.
        // If the context is explicitly marked as "External", enforce redaction.
        if let Some(context_str) = self.get_http_response_header("X-Data-Context") {
            if context_str.eq_ignore_ascii_case("External") {
                info!("Data Hop Firewall: External context detected. Enabling redaction.");
                self.should_redact = true;
            }
        }

        // If redaction is required, we must intercept the body.
        // We remove the Content-Length header because the body size will change after redaction.
        if self.should_redact {
            self.set_http_response_header("Content-Length", None);
            // We need to buffer the entire body to parse it as JSON.
            // Returning Action::Continue here allows headers to pass, but we will pause in on_http_response_body.
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
                            warn!("Data Hop Firewall: Failed to serialize redacted JSON: {}", e);
                            // In a fail-closed scenario, we might clear the body or return an error.
                            // Here, we choose to clear the body to prevent data leakage.
                            self.set_http_response_body(0, body_size, b"{\"error\": \"Internal Server Error: Serialization Failure\"}");
                            self.set_http_response_header("Content-Type", Some("application/json"));
                        }
                    }
                }
                Err(e) => {
                    warn!("Data Hop Firewall: Failed to parse response body as JSON: {}", e);
                    // If parsing fails but redaction was required, we must not let the raw body pass.
                    // Fail closed.
                    self.set_http_response_body(0, body_size, b"{\"error\": \"Internal Server Error: Data Validation Failure\"}");
                    self.set_http_response_header("Content-Type", Some("application/json"));
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
