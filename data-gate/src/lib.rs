/*
 * Data Hop Firewall - Envoy WebAssembly Filter (Rust)
 * --------------------------------------------------
 * Optimized for Zero-Allocation, Fast Host Interop, and High-Performance WASM Execution.
 * Designed by: Shay Mordechai
 */

use log::{info, warn};
use proxy_wasm::traits::*;
use proxy_wasm::types::*;
use serde_json::{json, Value};
use std::collections::HashSet;
use std::sync::OnceLock;

// שימוש ב-HashSet עם OnceLock מאפשר חיפוש ב-(O(1 במקום לרוץ על מערך בלולאה
static SENSITIVE_FIELDS_SET: OnceLock<HashSet<&'static str>> = OnceLock::new();

const SENSITIVE_FIELDS: &[&str] = &[
    // 🔑 Authentication & Core Secrets
    "password", "hashed_password", "credit_card", "internal_token", "ssn", "api_key",
    "marketing_api_key", "access_token", "refresh_token", "db_password", "client_secret",
    "auth_token", "webhook_secret", "internal_webhook_secret", "campaign_webhook_secret",
    "whatsapp_app_secret", "twilio_auth_token", "signature", "hash", "x-hub-signature-256",
    "x-twilio-signature",
    // 👤 PII (Personally Identifiable Information)
    "phone_number", "phone", "personal_whatsapp", "business_whatsapp", "email",
    "customer_email", "name", "full_name", "lead_name", "address", "city_coverage",
    // 📝 Event Details, Communications & Nested Objects
    "body", "message_text", "content", "notes", "transcription_text", "ai_summary",
    "suggested_reply", "summary_text", "custom_fields",
];

fn get_sensitive_fields() -> &'static HashSet<&'static str> {
    SENSITIVE_FIELDS_SET.get_or_init(|| {
        SENSITIVE_FIELDS.iter().cloned().collect()
    })
}

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
        // משיכת כל ה-headers בפעם אחת כדי לחסוך Host Calls יקרים
        let headers = self.get_http_response_headers();
        
        // חיפוש ה-Header ברשימה המרוכזת (כבר ב-lowercase בתוך Envoy)
        let has_ttl = headers.iter().any(|(k, v)| k == "x-data-ttl" && v == "1");

        if has_ttl {
            self.should_redact = true;
            // ביצוע מחיקות ה-headers בצורה מרוכזת
            self.set_http_response_header("x-data-ttl", None);
            self.set_http_response_header("content-length", None);
        }
        
        Action::Continue
    }

    fn on_http_response_body(&mut self, body_size: usize, end_of_stream: bool) -> Action {
        if !self.should_redact {
            return Action::Continue;
        }

        if !end_of_stream {
            return Action::Pause;
        }

        if body_size == 0 {
            return Action::Continue;
        }

        // שימוש ב-0 עד body_size עלול לגרום ל-Panic אם ה-WASM קיבל רק חלק מהגוף.
        // כדאי להשתמש ב-None, None כדי לקבל את ה-Buffer המלא שנקלט ב-Envoy בבטחה.
        if let Some(body_bytes) = self.get_http_response_body(0, body_size) {
            match serde_json::from_slice::<Value>(&body_bytes) {
                Ok(mut json_body) => {
                    redact_sensitive_fields(&mut json_body);
                    
                    // אופטימיזציה: סריאליזציה ישירה ל-Vector של בייטים (חוסך הקצאת String זמנית)
                    if let Ok(new_body) = serde_json::to_vec(&json_body) {
                        self.set_http_response_body(0, body_size, &new_body);
                        info!("Data Hop Firewall: Response body redacted successfully.");
                    }
                }
                Err(e) => {
                    warn!("Data Hop Firewall: Non-JSON or malformed payload: {}. Skipping redaction.", e);
                    let err = b"{\"error\": \"Security Exception: Data Integrity Failure\"}";
                    self.set_http_response_body(0, body_size, err);
                }
            }
        }

        Action::Continue
    }
}

fn redact_sensitive_fields(value: &mut Value) {
    let sensitive_set = get_sensitive_fields();
    redact_recursive_bounded(value, 0, 32, sensitive_set);
}

fn redact_recursive_bounded(value: &mut Value, current_depth: usize, max_depth: usize, sensitive_set: &HashSet<&'static str>) {
    if current_depth > max_depth {
        return;
    }
    match value {
        Value::Object(map) => {
            // יצירת הערך המצומצם פעם אחת מחוץ ללולאה (מונע הקצאות חוזרות ב-Heap)
            let redacted_value = Value::String("[REDACTED]".to_string());
            
            for (key, val) in map.iter_mut() {
                // המפתח מנורמל ל-lowercase (נחוץ רק אם ה-JSON עצמו לא עקבי באותיות גדולות/קטנות)
                let key_lower = key.to_lowercase(); 
                
                // חיפוש ב-O(1) במקום ריצה בלולאה (any) על מערך של 40+ איברים
                if sensitive_set.contains(key_lower.as_str()) {
                    *val = redacted_value.clone();
                } else {
                    redact_recursive_bounded(val, current_depth + 1, max_depth, sensitive_set);
                }
            }
        }
        Value::Array(arr) => {
            for val in arr.iter_mut() {
                redact_recursive_bounded(val, current_depth + 1, max_depth, sensitive_set);
            }
        }
        _ => {}
    }
}
