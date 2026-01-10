# src/scripts/init_db.py

import sys
import os
import uuid

# Professional English Comment:
# Ensure the project root is in the python path for module resolution.
sys.path.append(os.getcwd())

from src.database.models import Base, Tenant
from src.database.session import engine, SessionLocal
from src.security.hashing import get_hash

def init_db():
    print(">> Creating database tables...")

    # Create all tables defined in models.py
    Base.metadata.create_all(bind=engine)
    print(">> Tables created successfully.")

    session = SessionLocal()
    try:
        # Check if the demo tenant already exists to avoid duplicates
        existing_tenant = session.query(Tenant).first()

        if not existing_tenant:
            print(">> Seeding Demo Tenant...")

            # Generate a raw API key
            raw_api_key = str(uuid.uuid4())

            # Professional English Comment:
            # We use the robust get_hash function from security/hashing.py
            # which handles SHA-256 pre-hashing to support bcrypt limitations.
            hashed_key = get_hash(raw_api_key)

            demo_tenant = Tenant(
                id=uuid.uuid4(),
                name="Demo Coach (Local)",
                whatsapp_number="972500000000",

                # --- NEW MANDATORY FIELDS (Fixes NotNullViolation) ---
                personal_whatsapp="0500000000", # Dummy number for notifications
                requires_new_number=False,      # Default logic
                business_type="General Business", # Default category
                # -----------------------------------------------------

                city_coverage="תל אביב, הרצליה, רמת גן",
                api_key_hash=hashed_key,
                is_active=True
            )

            session.add(demo_tenant)
            session.commit()

            print("\n" + "="*50)
            print("✅ DEMO TENANT CREATED SUCCESSFULLY")
            print(f"👤 Name: {demo_tenant.name}")
            print(f"📱 Personal WhatsApp: {demo_tenant.personal_whatsapp}")
            print(f"🔑 API Key: {raw_api_key}") # Use this key for testing headers
            print("="*50 + "\n")
        else:
            print(">> Tenant already exists. Skipping seed generation.")

    except Exception as e:
        print(f"❌ Error initializing DB: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    init_db()
