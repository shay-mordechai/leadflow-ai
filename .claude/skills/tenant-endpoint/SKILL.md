---
name: tenant-endpoint
description: Checklist and architectural rules for creating or modifying FastAPI tenant-scoped endpoints in leadflow-ai. Use when adding new API routes.
---

# Tenant Endpoint Guidelines (`leadflow-ai`)

1. **Authentication & Identity:** Always use `current_user: User = Depends(get_current_user)`. Never trust client-supplied `tenant_id` or `user_id`.
2. **Multi-Tenant Isolation:** Every database query or update MUST explicitly filter by `user_id == current_user.id` (or `tenant_id`).
3. **IDOR Prevention:** If an entity ID (e.g. `lead_id`, `approval_id`, `doc_id`) is requested, query with `filter(Entity.id == entity_id, Entity.user_id == current_user.id)` and raise `404` if not found.
4. **Input Validation:** Use Pydantic v2 models with `model_config = ConfigDict(extra="forbid")` and tight string length / numeric bounds.
5. **DLP & Edge Headers:** Endpoints returning sensitive tenant PII should set `response.headers["X-Data-TTL"] = "1"`.
6. **Rate Limiting:** Apply `@limiter.limit("X/minute")` to all routes.
