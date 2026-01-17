# manage.py
import sys
import argparse
from sqlalchemy import text
from prettytable import PrettyTable # pip install prettytable

# טוען את המערכת שלנו
from src.database.session import SessionLocal
from src.database.models import User, Lead, BusinessProfile

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def list_users():
    """מציג טבלה של כל המשתמשים"""
    db = SessionLocal()
    users = db.query(User).all()
    
    table = PrettyTable()
    table.field_names = ["ID", "Name", "Email", "Phone", "Plan", "Active?", "Created"]
    
    for u in users:
        table.add_row([
            str(u.id)[:8], # מציג רק תחילת ה-UUID לנוחות
            u.name,
            u.email,
            u.assigned_phone_number or "N/A",
            u.plan_tier,
            "✅" if u.is_active else "❌",
            u.created_at.strftime("%Y-%m-%d")
        ])
    
    print(table)
    db.close()

def toggle_user(email):
    """מפעיל או מקפיא משתמש לפי אימייל"""
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        print(f"❌ User with email {email} not found.")
        return

    user.is_active = not user.is_active
    db.commit()
    status = "ACTIVE" if user.is_active else "FROZEN"
    print(f"✅ User {user.name} is now {status}")
    db.close()

def show_stats():
    """מציג נתונים גלובליים"""
    db = SessionLocal()
    total_users = db.query(User).count()
    total_leads = db.query(Lead).count()
    paying_users = db.query(User).filter(User.is_active == True).count()
    
    print(f"""
    📊 SYSTEM STATS
    ================
    Total Users:   {total_users}
    Paying Users:  {paying_users}
    Total Leads:   {total_leads}
    """)
    db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadFlow Management Tool")
    subparsers = parser.add_subparsers(dest="command")

    # Command: list
    subparsers.add_parser("list", help="List all users")
    
    # Command: stats
    subparsers.add_parser("stats", help="Show system stats")

    # Command: toggle
    toggle_parser = subparsers.add_parser("toggle", help="Toggle user active status")
    toggle_parser.add_argument("email", help="User email address")

    args = parser.parse_args()

    if args.command == "list":
        list_users()
    elif args.command == "stats":
        show_stats()
    elif args.command == "toggle":
        toggle_user(args.email)
    else:
        parser.print_help()



# איך עובדים עם זה?
# במקום להיכנס לדפדפן, אתה פותח את הטרמינל (במחשב שלך או ב-SSH לשרת) ומריץ פקודות כמו האקר אמיתי:

# לראות את כל המאמנים:

# python manage.py list
# להפעיל למאמן את החשבון (אחרי ששילם בביט):

# python manage.py toggle yossi@gym.com
# לראות כמה לידים נכנסו היום:

# python manage.py stats