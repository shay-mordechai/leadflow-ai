# manage_coupons.py
import sys
import uuid
import argparse
from src.database.session import SessionLocal
from src.models import User, PlanTier, SubscriptionStatus

def create_admin_coupon(email: str):
    """
    Directly upgrades a user to PRO status in the database.
    Useful for manual onboarding or testing without billing logic.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ Error: User with email {email} not found.")
            return

        user.plan_tier = PlanTier.PRO
        user.subscription_status = SubscriptionStatus.ACTIVE
        db.commit()
        print(f"✅ Success! {email} is now a PRO user.")
    except Exception as e:
        print(f"❌ Database error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadFlow AI Admin Tools")
    parser.add_argument("--upgrade", type=str, help="Email of the user to upgrade to PRO")
    
    args = parser.parse_args()
    
    if args.upgrade:
        create_admin_coupon(args.upgrade)
    else:
        parser.print_help()

# Usage:
# ssh production "podman exec leadflow-backend python manage_coupons.py --upgrade shay.mordechai@proton.me"