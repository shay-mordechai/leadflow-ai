# src/manage_cli.py
import sys
import argparse
from prettytable import PrettyTable
from src.database.session import SessionLocal
from src.database.models import User, Lead, BusinessProfile

def list_users():
    """
    Lists all users in the database with key details.
    """
    db = SessionLocal()
    users = db.query(User).all()
    
    table = PrettyTable()
    table.field_names = ["ID", "Name", "Email", "Phone", "Plan", "Active", "Created"]
    
    for u in users:
        # Critical Fix: Handle potential NoneType for created_at
        created_date = u.created_at.strftime("%Y-%m-%d") if u.created_at else "N/A"
        
        table.add_row([
            str(u.id)[:8],
            u.name,
            u.email,
            u.assigned_phone_number or "N/A",
            u.plan_tier,
            "YES" if u.is_active else "NO",
            created_date
        ])
    
    print(table)
    db.close()

def toggle_user(email):
    """
    Toggles user status between Active/Frozen.
    """
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f"❌ User {email} not found.")
        return
    
    user.is_active = not user.is_active
    db.commit()
    
    status = "ACTIVE" if user.is_active else "FROZEN"
    print(f"✅ User {user.name} is now {status}")
    db.close()

def show_stats():
    """
    Shows simple high-level statistics.
    """
    db = SessionLocal()
    total_users = db.query(User).count()
    paying_users = db.query(User).filter(User.is_active == True).count()
    print(f"\n📊 STATS: Users: {total_users} | Paying: {paying_users}\n")
    db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadFlow AI Management CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("list", help="List all users")
    subparsers.add_parser("stats", help="Show system statistics")
    
    toggle = subparsers.add_parser("toggle", help="Toggle user active status")
    toggle.add_argument("email", help="User email address")
    
    args = parser.parse_args()
    
    if args.command == "list": list_users()
    elif args.command == "stats": show_stats()
    elif args.command == "toggle": toggle_user(args.email)
    else: parser.print_help()