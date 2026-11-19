-- 2024-01-28: Added Subscription and Profile fields
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_tier VARCHAR(20) DEFAULT 'STARTER';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'TRIAL';
ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_whatsapp VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS business_type VARCHAR(100);

-- 2024-01-25: Added Worker fields
ALTER TABLE media_interactions ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'PENDING';
ALTER TABLE media_interactions ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE media_interactions ADD COLUMN IF NOT EXISTS suggested_reply TEXT;