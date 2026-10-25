# src/scripts/setup_bridal_e2e.py
# Professional English Comment:
# E2E Provisioning Script for LeadFlow AI. Idempotently sets up Business Owner, Marketer, and AI Persona.

import argparse, os, sys, uuid
sys.path.append(os.getcwd())

from src.database.models import User, UserRole, PlanTier, SubscriptionStatus, BusinessProfile, AIAgent, PhoneNumber
from src.database.session import SessionLocal
from src.security.hashing import get_hash

def setup_bridal_e2e(
    email="admin@bridalstudio.test",
    name="Bridal Makeup Studio",
    phone="+972500000000",
    marketer_email="marketer@agency.test",
    api_key="mk_live_bridal_test_key_abc123",
):
    db = SessionLocal()
    try:
        print("🚀 Starting Bridal E2E Provisioning...")
        p = db.query(User).filter(User.email == marketer_email).first()
        if not p:
            p = User(
                id=uuid.uuid4(), name="Marketer Partner", email=marketer_email,
                hashed_password=get_hash("MarketerTemp123!"), role=UserRole.PARTNER,
                plan_tier=PlanTier.PRO, subscription_status=SubscriptionStatus.ACTIVE,
                is_active=True, agency_name="Bridal Agency", business_type="Agency: Marketing"
            )
            db.add(p); db.flush()
            print(f"✅ Created Marketer Partner: {p.email}")
        else:
            p.is_active = True; db.flush()
            print(f"ℹ️ Marketer Partner {p.email} already exists.")

        o = db.query(User).filter(User.email == email).first()
        pwd = "TempPassword123!"
        if not o:
            o = User(
                id=uuid.uuid4(), name="Bridal Makeup Studio Owner", email=email,
                hashed_password=get_hash(pwd), role=UserRole.CLIENT,
                plan_tier=PlanTier.PRO, subscription_status=SubscriptionStatus.ACTIVE,
                is_active=True, business_name=name, business_type="Bridal Makeup & Hair Styling",
                assigned_phone_number=phone, marketing_api_key=api_key, partner_id=p.id
            )
            db.add(o); db.flush()
            print(f"✅ Created Business Owner Tenant: {o.email}")
        else:
            o.business_name = name; o.plan_tier = PlanTier.PRO
            o.subscription_status = SubscriptionStatus.ACTIVE; o.is_active = True
            o.assigned_phone_number = phone; o.marketing_api_key = api_key; o.partner_id = p.id
            db.flush()
            print(f"ℹ️ Business Owner Tenant {o.email} updated.")

        prof = db.query(BusinessProfile).filter(BusinessProfile.user_id == o.id).first()
        svc = "חבילת כלות: איפור ניסיון, איפור ועיצוב שיער ביום החתונה, וערכת טאצ'-אפ. החל מ-2,500 ₪."
        inst = "הקפידי להיות אדיבה, צנועה ומקצועית. שאלי מיד את תאריך החתונה ומיקום ההתארגנות, והציעי שיחת ייעוץ."
        if not prof:
            prof = BusinessProfile(
                id=uuid.uuid4(), user_id=o.id, business_name=name,
                business_type="Bridal Makeup & Hair Styling", ai_tone="Professional & Empathetic",
                products_services=svc, custom_instructions=inst,
                summary_template="סיכום פנייה: שם הכלה, תאריך חתונה, מיקום ההתארגנות, והאם תואמה שיחת ייעוץ."
            )
            db.add(prof)
            print("✅ Created Business Profile.")
        else:
            prof.business_name = name; prof.products_services = svc; prof.custom_instructions = inst
            print("ℹ️ Business Profile updated.")

        prompt = f"נציג וירטואלי מקצועי ואדיב של {name} (איפור כלות). שירותים: {svc}. הנחיות: {inst}."
        agent = db.query(AIAgent).filter(AIAgent.user_id == o.id).first()
        if not agent:
            agent = AIAgent(
                id=uuid.uuid4(), user_id=o.id, system_prompt=prompt,
                voice_id="bridal_voice_he", language="he-IL", is_active=True
            )
            db.add(agent)
            print("✅ Created AI Agent Persona.")
        else:
            agent.system_prompt = prompt; agent.is_active = True
            print("ℹ️ AI Agent Persona updated.")

        ph = db.query(PhoneNumber).filter(PhoneNumber.number == phone).first()
        if not ph:
            ph = PhoneNumber(
                id=uuid.uuid4(), number=phone, country_code="IL",
                provider="twilio", is_active=True, owner_id=o.id
            )
            db.add(ph)
            print(f"✅ Created Phone Number mapping: {phone}")
        else:
            ph.owner_id = o.id
            print(f"ℹ️ Phone Number mapping {phone} updated.")

        db.commit()
        print("\n" + "="*70)
        print("✨ BRIDAL MAKEUP E2E PROVISIONING SUCCESSFUL ✨")
        print("="*70)
        print(f"👤 Business Owner Email   : {o.email}")
        print(f"🔑 Temporary Password     : {pwd}")
        print(f"🏢 Business Studio Name   : {name}")
        print(f"📞 Mock Phone Number      : {phone}")
        print(f"🤝 Marketer / Partner     : {p.email}")
        print(f"🔑 Marketer API Key       : {api_key}")
        print("="*70 + "\n")
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-email", default="admin@bridalstudio.test")
    parser.add_argument("--business-name", default="Bridal Makeup Studio")
    parser.add_argument("--business-phone", default="+972500000000")
    parser.add_argument("--marketer-email", default="marketer@agency.test")
    parser.add_argument("--marketing-api-key", default="mk_live_bridal_test_key_abc123")
    args = parser.parse_args()
    setup_bridal_e2e(args.business_email, args.business_name, args.business_phone, args.marketer_email, args.marketing_api_key)
