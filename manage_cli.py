# manage_cli.py
import sys
import argparse
import asyncio
from prettytable import PrettyTable
from src.database.session import SessionLocal
from src.database.models import User, PlanTier, SubscriptionStatus

def list_users():
    """
    Lists all users in the database with key details.
    """
    db = SessionLocal()
    try:
        users = db.query(User).all()
        table = PrettyTable()
        table.field_names = ["ID", "Name", "Email", "Plan", "Status", "Active", "Created"]
        
        for u in users:
            created_date = u.created_at.strftime("%Y-%m-%d") if u.created_at else "N/A"
            table.add_row([
                str(u.id)[:8],
                u.name,
                u.email,
                u.plan_tier,
                u.subscription_status,
                "✅ YES" if u.is_active else "❌ NO",
                created_date
            ])
        print(table)
    finally:
        db.close()

def upgrade_user(email):
    """
    Manually upgrades a user to PRO status.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ User {email} not found.")
            return
        
        user.plan_tier = PlanTier.PRO
        user.subscription_status = SubscriptionStatus.ACTIVE
        db.commit()
        print(f"🚀 User {email} successfully upgraded to PRO!")
    finally:
        db.close()

def toggle_user(email):
    """
    Toggles user status between Active/Frozen.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ User {email} not found.")
            return
        
        user.is_active = not user.is_active
        db.commit()
        status = "ACTIVE" if user.is_active else "FROZEN"
        print(f"✅ User {user.name} is now {status}")
    finally:
        db.close()

def show_stats():
    """
    Shows simple high-level statistics.
    """
    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        pro_users = db.query(User).filter(User.plan_tier == PlanTier.PRO).count()
        print(f"\n📊 SYSTEM STATS")
        print(f"Total Users: {total_users}")
        print(f"Active Users: {active_users}")
        print(f"PRO Users: {pro_users}\n")
    finally:
        db.close()

async def run_manual_followup():
    """
    Triggers the Smart Follow-up logic manually for testing.
    """
    from src.tasks.followup_tasks import process_smart_followups
    print("⏳ Running manual follow-up check for stale leads...")
    await process_smart_followups()
    print("✅ Follow-up process complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadFlow AI Management CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("list", help="List all users")
    subparsers.add_parser("stats", help="Show system statistics")
    subparsers.add_parser("followup", help="Manually trigger smart follow-ups")
    
    toggle = subparsers.add_parser("toggle", help="Toggle user active status")
    toggle.add_argument("email", help="User email address")
    
    upgrade = subparsers.add_parser("upgrade", help="Upgrade user to PRO")
    upgrade.add_argument("email", help="User email address")
    
    args = parser.parse_args()
    
    if args.command == "list": 
        list_users()
    elif args.command == "stats": 
        show_stats()
    elif args.command == "toggle": 
        toggle_user(args.email)
    elif args.command == "upgrade": 
        upgrade_user(args.email)
    elif args.command == "followup": 
        asyncio.run(run_manual_followup())
    else: 
        parser.print_help()

# Usage Examples:
# View Users Table
# ssh production "podman exec leadflow-backend python manage_cli.py list"

# Upgrade user to pro
# ssh production "podman exec leadflow-backend python manage_cli.py upgrade shay.mordechai@proton.me"

# Active/Deactive a user
# ssh production "podman exec leadflow-backend python manage_cli.py toggle shay.mordechai@proton.me"

# View Statistics info
# ssh production "podman exec leadflow-backend python manage_cli.py stats"

# Trigger follow-ups manually
# ssh production "podman exec leadflow-backend python manage_cli.py followup"