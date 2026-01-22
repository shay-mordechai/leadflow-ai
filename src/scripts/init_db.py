# src/scripts/init_db.py

import sys
import os
import uuid
import logging

# Professional English Comment:
# Ensure the project root is in the python path for module resolution when running as a script.
sys.path.append(os.getcwd())

from src.database.models import Base, User  # Note: Assuming User is the primary model now, replace Tenant if needed
from src.database.session import engine, SessionLocal
from src.security.hashing import get_hash

# Setup logging for better visibility during deployment
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DatabaseInit")

def init_db():
    """
    Initializes the database schema and seeds initial required data.
    Ensures idempotency by checking for existing records before seeding.
    """
    logger.info(">> Starting database schema initialization...")

    try:
        # Professional English Comment:
        # metadata.create_all() is idempotent; it creates tables only if they don't exist.
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created or verified successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to create tables: {e}")
        return

    session = SessionLocal()
    try:
        # Professional English Comment:
        # Check for existing data to prevent duplicate seeding in production.
        # Replacing 'Tenant' with 'User' or your specific primary model.
        # If you still have a Tenant model, ensure it's imported correctly.
        existing_user = session.query(User).first()

        if not existing_user:
            logger.info(">> No existing users found. Seeding Demo Account...")

            # Generate a raw API key for initial access
            raw_api_key = str(uuid.uuid4())

            # Professional English Comment:
            # Hash the key using the system's hashing utility (SHA-256 + Bcrypt)
            # to ensure security standards are met even for demo data.
            hashed_key = get_hash(raw_api_key)

            # Creating a Demo User / Tenant
            demo_account = User(
                id=uuid.uuid4(),
                name="Demo Admin",
                email="admin@leadflow.local",
                hashed_password=get_hash("Admin123!"), # Example password
                
                # --- MANDATORY FIELDS ---
                business_type="General Business",
                is_active=True,
                plan_tier="PRO",
                subscription_status="ACTIVE",
                # ------------------------
                
                last_known_city="Tel Aviv",
                last_known_country="Israel"
            )

            session.add(demo_account)
            session.commit()

            print("\n" + "="*50)
            print("🚀 DEMO ACCOUNT CREATED SUCCESSFULLY")
            print(f"👤 Name: {demo_account.name}")
            print(f"📧 Email: {demo_account.email}")
            print(f"🔑 Initial API Key: {raw_api_key}")
            print("="*50 + "\n")
        else:
            logger.info(">> Existing data detected. Skipping seed generation.")

    except Exception as e:
        logger.error(f"❌ Error during data seeding: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    init_db()