# LeadFlow AI — Product & Architecture Roadmap (`TODO.md`)

> **Strategic Directive (Scope Guardrail):**
> Do **not** implement Phase 2/3 features during the active MVP pilot. The immediate engineering and business priority is **Phase 1 (Speed-to-Lead MVP)**: achieving $<60\text{s}$ initial WhatsApp response times and reducing lead drop-off from $50\%$ to $<15\%$. All Conversation Intelligence and "Virtual CMO" capabilities below are gated behind initial pilot validation and recurring customer revenue (Upsell Tier).

---

## Phase 1: MVP Pilot Hardening (Immediate Action Items)

### 1.1 WhatsApp Voice Note Transcription Guardrails
- [x] **Retain Core Voice Note Pipeline:** Keep existing local/fast transcription for short WhatsApp voice notes ($10\text{--}60\text{s}$), as it directly supports the Speed-to-Lead KPI.
- [x] **Outbound Wasm DLP Protection:** Ensure `transcription_text` and `ai_summary` JSON keys remain registered in the Rust/Wasm Envoy outbound filter (`SENSITIVE_FIELDS`).
- [ ] **Enforce Audio Duration Cap (DoS & Cost Prevention):**
  - Add a pre-processing check on incoming WhatsApp media webhooks to inspect audio duration/file size before queuing transcription.
  - Reject voice notes exceeding **$180\text{ seconds}$ ($3\text{ minutes}$)** or **$5\text{ MB}$**.
  - Trigger an automated polite fallback reply: *"I received your voice note, but it is a bit too long to process automatically. Could you send a brief voice message (under 2 minutes) or type your main question?"*

---

## Phase 2: Asynchronous Audio Pipeline & OS-Level Resource Isolation

### 2.1 FastAPI Ingestion & Celery Task Queue
- [ ] **Asynchronous Upload Endpoint (`POST /api/v1/media/upload`):**
  - Accept `.mp4`, `.mp3`, `.ogg`, and `.wav` files from the business owner dashboard or virtual PBX webhooks.
  - Stream uploads to an isolated, encrypted temporary volume (`/var/leadflow/tmp_audio/{tenant_id}/`).
  - Create a task record in PostgreSQL (`status: queued`, `tenant_id`, `created_at`) and dispatch a Celery job: `transcribe_and_summarize.delay(task_id, file_path, tenant_id)`.
  - Return HTTP `202 Accepted` immediately with `{"task_id": "...", "sla_tier": "weekly_or_monthly"}`.

### 2.2 CPU-Only Optimization & Trickle Worker (`leadflow-cx23`)
To run heavy transcription workloads on a 2-vCPU VPS without GPU hardware or degrading FastAPI/Envoy real-time latency:
- [ ] **Dedicated Low-Priority Celery Queue:**
  - Provision a dedicated worker queue with strict single-task concurrency:
    ```bash
    celery -A app.worker worker -c 1 -Q transcription_batch
    ```
- [ ] **OS & Container Resource Throttling (Prevent Self-Inflicted DoS):**
  - Apply Linux process scheduling priority: `nice -n 19` and `ionice -c 3` (idle disk I/O class).
  - Enforce Podman/cgroups CPU ceiling so transcription never consumes more than $50\%$ of a single core:
    ```bash
    --cpu-quota=50000 --cpu-period=100000 --memory=1024m
    ```
- [ ] **Nightly Trickle Window Execution (`00:00–06:00`):**
  - Configure `leadflow-beat` to hold non-urgent meeting/call recordings in Redis and process them sequentially during off-peak night hours when live WhatsApp lead traffic is near zero.
- [ ] **Local Transcription Engine Tuning (`faster-whisper`):**
  - Pre-convert uploaded media to $16\text{ kHz}$ mono WAV using `ffmpeg`:
    ```bash
    ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav
    ```
  - Run `faster-whisper` (CTranslate2 backend) on CPU using `int8` quantization (`compute_type="int8"`, `device="cpu"`, model `base` or `small`) to keep RAM usage around $\sim 500\text{ MB}$ and achieve a $3\text{--}4\times$ speedup over standard PyTorch.
  - Enable Voice Activity Detection (`vad_filter=True`) to strip $30\%\text{--}50\%$ of dead air/silence prior to inference.

### 2.3 Capacity Planning & Cloud Scaling Trigger
- **Baseline CPU Math:** With `int8` quantization and VAD enabled, the Real-Time Factor ($\text{RTF}$) on a modern vCPU is $\approx 0.5\text{--}0.65$ (a $30\text{-minute}$ call takes $\sim 15\text{--}20\text{ minutes}$ of CPU time).
- **Nightly Throughput Ceiling:** A single throttled core running across a $6\text{-hour}$ nightly window can safely process **$10\text{--}15\text{ full calls per 24 hours}$**.
- [ ] **Backlog Drift Alerting (Scale Trigger):**
  - Emit a metric/alert if queued audio duration exceeds $6\text{ hours}$ of unprocessed backlog.
  - **Migration Path when Triggered:** Do not integrate enterprise SaaS tools like Gong (mismatched for SMB budgets and WhatsApp/mobile workflows). Instead, switch long-call processing to pay-as-you-go Enterprise APIs (**Deepgram** or **AWS Transcribe / Azure OpenAI Whisper**) under a signed **Data Processing Agreement (DPA)** with strict **Zero Data Retention (ZDR)** enabled.

---

## Phase 3: Privacy-By-Design & Ephemeral Audio Lifecycle

Full phone calls and coaching sessions contain high-risk PII (health details, family names, financial data, credit cards) subject to Israeli Privacy Protection regulations and Wiretapping Laws (חוק האזנת סתר).

- [ ] **Mandatory Recording Consent Verification:**
  - Require tenant onboarding attestation that call recording disclosures are active on their PBX/device.
- [ ] **Ephemeral Audio Pipeline (Zero Raw Audio Retention):**
  1. Ingest encrypted audio file to temporary disk.
  2. Execute local transcription in isolated worker memory.
  3. **Immediate PII Scrubbing:** Pass raw transcript through local regex/NER scrubbing (stripping credit card numbers, Israeli IDs, phone numbers, and names) *before* database persistence or LLM summarization.
  4. **Permanent File Destruction:** Execute `os.unlink(file_path)` inside a `finally` block immediately after transcription completes. Raw audio must **never** be stored long-term.
  5. Ensure all outbound API responses serving transcripts or summaries carry the `x-data-ttl: 1` header so the **Envoy Rust/Wasm DLP filter** enforces a second layer of structural redaction.

---

## Phase 4: Multi-Channel Smart Notification Engine

To notify business owners when asynchronous batch jobs finish without relying on client-side polling:

- [ ] **Tier 1 — Real-Time In-App Push (WebSockets / SSE):**
  - Push task completion events (`status: completed`) directly to the active browser session if the dashboard tab is open.
- [ ] **Tier 2 — Browser Web Push (Service Worker):**
  - Implement Web Push API notifications for backgrounded browser tabs.
- [ ] **Tier 3 — Automated WhatsApp Fallback (`leadflow-beat`):**
  - Create a `notifications` table in PostgreSQL:
    ```sql
    CREATE TABLE notifications (
        id SERIAL PRIMARY KEY,
        tenant_id UUID NOT NULL,
        user_id UUID NOT NULL,
        task_id UUID NOT NULL,
        message TEXT NOT NULL,
        is_read BOOLEAN DEFAULT FALSE,
        whatsapp_sent BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    ```
  - Schedule a `leadflow-beat` periodic task every $5\text{ minutes}$ to query unacknowledged notifications older than $10\text{ minutes}$:
    ```sql
    SELECT * FROM notifications
    WHERE is_read = FALSE
      AND whatsapp_sent = FALSE
      AND created_at < NOW() - INTERVAL '10 minutes';
    ```
  - Dispatch a WhatsApp Business API template message to the business owner's personal phone (*"Your meeting/call summary is ready in the dashboard"*), and update `whatsapp_sent = TRUE`.

---

## Phase 5: "Virtual CMO" — Map-Reduce Marketing Intelligence Engine

Instead of selling "raw transcription" (a low-margin commodity), position the feature as an automated **Virtual Marketing Director** with relaxed, high-value SLAs: **Weekly Meeting Digests** (before the next client session) and **Monthly Strategic Reviews**.

### 5.1 Nightly "Map" Phase (Per-Call Structured Extraction)
- [ ] After each call is transcribed and sanitized at night, run a lightweight, deterministic LLM extraction prompt to store compact structured metadata in PostgreSQL (and embeddings in `pgvector`), avoiding storing or re-reading massive raw text blobs:
  ```json
  {
    "call_id": 1042,
    "tenant_id": "uuid",
    "interaction_type": "sales_call | coaching_session | whatsapp_voice",
    "lead_intent": "Mental training program for athletes",
    "main_objection": "Price comparison vs. Competitor X",
    "source_channel": "Facebook Evening Campaign",
    "sentiment_score": 0.78,
    "outcome": "closed_won | closed_lost | follow_up_scheduled"
  }
  ```

### 5.2 Weekly & Monthly "Reduce" Phase (Aggregated Agentic Reports)
- [ ] **Weekly Coaching / Meeting Prep Digest:**
  - Run a weekly scheduled job per tenant that compiles action items, client commitments, and key topics from the previous session so the business owner is prepared before the next weekly appointment.
- [ ] **Monthly "Virtual CMO" Strategic Report (1st of Every Month):**
  - Query the structured JSON metadata table across all calls from the past $30\text{ days}$ (bypassing LLM context-window limits and minimizing token costs).
  - Generate an executive marketing insights report delivered via Dashboard + WhatsApp:
    - **Objection Trends:** e.g., *"38% of lost leads this month cited Competitor X's pricing. Recommendation: Add a comparison FAQ block to your landing page highlighting your 1-on-1 follow-up advantage."*
    - **Channel ROI & Ad Spend:** e.g., *"Leads mentioning 'exam anxiety' closed at 65% vs. 12% general average. Recommendation: Shift next month's ad budget toward this specific keyword/audience."*
- [ ] **Future SMB Ecosystem Connectors (Post-Traction):**
  - Webhook ingestion from local Israeli virtual PBXs (e.g., Callbox, Yemot HaMashiach).
  - Outbound sync via Make/Zapier or native webhooks to SMB CRMs (Fireberry, Powerlink, monday.com, Google Sheets).