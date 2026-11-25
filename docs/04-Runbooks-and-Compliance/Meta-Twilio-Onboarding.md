
# Meta WhatsApp & Twilio Production Onboarding Runbook

## 1. Live Meta App Configuration (`MyLeads AI App`)

* **Meta App ID:** `1822751712478439` (Status: **Published / Live**)
* **WhatsApp Business Account (WABA) ID:** `1114562600986258`
* **Business Phone Number:** `+972 52-306-4991` (`Phone Number ID: 1360601097133343`)
* **Webhook Callback URL:** `https://my-leads.app/webhooks/whatsapp` (Graph API `v27.0`, subscribed to `messages`, `message_template_status_update`, `account_alerts`)
* **Compliance URLs (Verified `200 OK` with `facebookexternalhit/1.1`):**
* Privacy Policy & User Data Deletion URL: `https://my-leads.app/privacy`
* Terms of Service URL: `https://my-leads.app/terms`
* App Icon: `frontend/public/logo-1024.jpg` (`1024x1024`)



## 2. Database Tenant Mapping (`phone_numbers`)

Every onboarded WhatsApp number must be mapped in PostgreSQL `phone_numbers` so `_resolve_tenant()` routes inbound webhooks:

```sql
INSERT INTO phone_numbers (id, number, country_code, provider, provider_id, is_active, created_at, owner_id)
VALUES (gen_random_uuid(), '+972523064991', 'IL', 'meta', '1360601097133343', true, NOW(), '<tenant_uuid>');

```

## 3. Approved Utility Template for Cold Leads (`lead_welcome_he`)

Meta blocks free-form messages outside the 24-hour customer service window. Cold leads from landing pages and Facebook/Instagram Lead Ads must receive an approved Utility Template first:

* **Name:** `lead_welcome_he` | **Category:** `UTILITY` | **Language:** `he`
* **Body:** `היי {{1}}, תודה שהשארת פרטים אצל {{2}}! קיבלנו את הפנייה שלך ונשמח לעזור לך כאן בוואטסאפ.`

## 4. Scaling Beyond 250 Conversations/Day & Twilio `+972`

* Complete **Meta Business Verification** and **App Review** (`whatsapp_business_management`, `whatsapp_business_messaging`) to lift the initial 250 conversations/24h tier.
* For programmatic Israeli numbers via Twilio, submit a `+972` Regulatory Bundle (business registration certificate, Israeli ID, proof of address) 48–72 hours prior to tenant activation.
