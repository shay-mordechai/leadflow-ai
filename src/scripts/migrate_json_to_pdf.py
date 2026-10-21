import json

from src.database.models import Lead, Tenant
from src.database.session import SessionLocal


def migrate():
    db = SessionLocal()
    try:
        # 1. Create a Default Tenant for existing data
        default_tenant = Tenant(name="Legacy Migration", api_key_hash="...")
        db.add(default_tenant)
        db.commit()

        # 2. Load JSON
        with open("data/inquiries.json") as f:
            old_data = json.load(f)

        # 3. Transform and Insert
        for phone, data in old_data.items():
            new_lead = Lead(
                tenant_id=default_tenant.id,
                phone_number=phone,  # SQLAlchemy TypeDecorator will encrypt this automatically
                name=data.get("name"),
                # Map other fields...
            )
            db.add(new_lead)

        db.commit()
        print("Migration Complete. Check 'leads' table.")
    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
