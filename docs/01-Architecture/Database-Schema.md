
# Database Schema & Migrations (`PostgreSQL 15 + pgvector`)

Schema changes are managed exclusively through **Alembic** (`alembic/`) with dual SQLite (unit tests) and PostgreSQL (integration/production) compatibility enforced by `alembic check` in CI.

## Core Tables

| Table | Primary Key | Tenant Foreign Key | Key Columns & Purpose |
| --- | --- | --- | --- |
| `users` | `UUID` | Self (`id`) | `email`, `plan_tier` (`STARTER`/`PRO`), `monthly_ai_messages`, `assigned_phone_number`, `personal_whatsapp`, `is_active`, `is_admin` |
| `phone_numbers` | `UUID` | `owner_id -> users.id` | `number` (E.164, e.g., `+972523064991`), `country_code` (`IL`), `provider` (`meta`), `provider_id` (Meta Phone Number ID), `is_active` |
| `ai_agents` | `UUID` | `user_id -> users.id` | `system_prompt`, `voice_id`, `language` (`he-IL`), `phone_number_id`, `is_active` |
| `business_profiles` | `UUID` | `user_id -> users.id` | `business_name`, `business_type`, `products_services`, `custom_instructions` |
| `leads` | `UUID` | `user_id -> users.id` | `name`, `phone_number`, `source` (`WHATSAPP`, `FACEBOOK`, `MARKETING`, `MANUAL`), `status`, `bot_active`, `requires_human`, `qualification_score` |
| `messages` | `UUID` | Via `lead_id -> leads.id` | `sender_type` (`user`/`assistant`/`system`), `content`, `external_id` (Meta `wamid` unique dedup), `created_at` |
| `pending_approvals` | `UUID` | `user_id -> users.id` | HITL Draft Mode & tool execution queue (`status`: `PENDING`, `APPROVED`, `EDITED`, `REJECTED`) |
| `knowledge_documents` | `UUID` | `user_id -> users.id` | Uploaded pricing sheets/FAQs, `status` (`INDEXED`), `kb_version`, `pgvector` embedding chunks |

## Concurrency & Quota Patterns

* **Atomic Message Credit Reservation:** `_reserve_ai_message_credit()` executes `UPDATE users SET monthly_ai_messages = monthly_ai_messages + 1 WHERE id = :uid AND monthly_ai_messages < :limit RETURNING monthly_ai_messages` to prevent TOCTOU race conditions.
* **Session Transaction Discipline:** Read-only queries (such as `ConversationMemoryService.get_lead_memory()`) must commit/close any implicit SQLAlchemy transaction before opening explicit `async with db.begin():` write blocks.
