# Professional English Comment:
# Database seeding script for development and demonstration purposes.
# Synchronized with the hashing utilities in src.security.hashing.

from src.database.session import SessionLocal
from src.database.models import Tenant, Lead
from src.security.hashing import get_hash
import uuid

def seed_data():
    db = SessionLocal()
    try:
        # 1. Create or Get Mock Coach (Tenant)
        # We check by whatsapp_number to prevent duplicate entries
        coach = db.query(Tenant).filter(Tenant.whatsapp_number == "0501234567").first()

        if not coach:
            coach = Tenant(
                id=uuid.uuid4(),
                name="יוסי המאמן",
                whatsapp_number="0501234567",
                city_coverage="תל אביב, הרצליה, רמת גן",
                api_key_hash=get_hash("demo-key-123"),
                is_active=True
            )
            db.add(coach)
            db.flush()
            print(f"✅ Created Coach: {coach.name}")
        else:
            print(f"ℹ️ Coach {coach.name} already exists.")

        # 2. Check if we already have leads to avoid clutter
        existing_leads_count = db.query(Lead).filter(Lead.tenant_id == coach.id).count()
        if existing_leads_count > 0:
            print(f"ℹ️ {existing_leads_count} leads already exist for this coach. Skipping lead seeding.")
        else:
            # Create a Qualified Lead
            lead1 = Lead(
                id=uuid.uuid4(),
                tenant_id=coach.id,
                name="ישראל ישראלי",
                phone_number="0541112233",
                city="תל אביב",
                status="QUALIFIED",
                summary_text="הלקוח מעוניין בתוכנית ליווי אישית לריצת מרתון. גר בתל אביב ופנוי בבקרים.",
                last_message_text="אני גר בתל אביב, מתי אפשר לקבוע פגישת ייעוץ?"
            )

            # Create a Lead that needs re-routing
            lead2 = Lead(
                id=uuid.uuid4(),
                tenant_id=coach.id,
                name="מיכל כהן",
                phone_number="0529998877",
                city="חיפה",
                status="REROUTED",
                coach_feedback="MISMATCH: הלקוחה גרה בחיפה, יוסי המאמן אינו מכסה אזור זה.",
                summary_text="הלקוחה מחפשת מאמן פילאטיס בחיפה. יש להפנות למאמן אזור צפון.",
                last_message_text="שלום, אני מחיפה. אתם מגיעים לפה לאימונים אישיים?"
            )

            db.add_all([lead1, lead2])
            print("✅ Demo leads seeded successfully!")

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
