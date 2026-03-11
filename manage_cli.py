# manage_cli.py
import sys
import argparse
import asyncio
import uuid
from prettytable import PrettyTable
from sqlalchemy.orm import Session
from src.database.session import SessionLocal
from src.database.models import User, PlanTier, SubscriptionStatus, BusinessProfile, AIAgent

def list_users():
    """Lists all users in the database with key details."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        table = PrettyTable()
        table.field_names = ["ID", "Name", "Email", "Plan", "Status", "Active"]
        
        for u in users:
            table.add_row([
                str(u.id)[:8],
                u.name,
                u.email,
                u.plan_tier,
                u.subscription_status,
                "✅ YES" if u.is_active else "❌ NO"
            ])
        print(table)
    finally:
        db.close()

def onboard_client(email, biz_name, biz_type, tone, prompt):
    """
    Agency Command: Fully configures a client's AI brain in one shot.
    This allows you to set up a client without ever logging into their dashboard.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ User {email} not found. Create the user via /register first.")
            return

        # 1. Upgrade to PRO
        user.plan_tier = PlanTier.PRO
        user.subscription_status = SubscriptionStatus.ACTIVE

        # 2. Setup/Update Business Profile
        profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == user.id).first()
        if not profile:
            profile = BusinessProfile(user_id=user.id)
            db.add(profile)
        
        profile.business_name = biz_name
        profile.business_type = biz_type
        profile.ai_tone = tone

        # 3. Setup AI Agent Prompt
        agent = db.query(AIAgent).filter(AIAgent.user_id == user.id).first()
        if not agent:
            agent = AIAgent(user_id=user.id)
            db.add(agent)
        
        agent.system_prompt = prompt
        agent.is_active = True

        db.commit()
        print(f"🚀 Client '{biz_name}' ({email}) is now fully ONBOARDED and LIVE!")
        print(f"🔗 Webhook URL: https://my-leads.app/api/v1/leads/webhook/{user.id}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadFlow AI Agency CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # List command
    subparsers.add_parser("list", help="List all users")
    
    # Onboard command
    onboard = subparsers.add_parser("onboard", help="Quickly configure a new client")
    onboard.add_argument("--email", required=True, help="Client's registered email")
    onboard.add_argument("--name", required=True, help="Business Name")
    onboard.add_argument("--type", default="NLP Coaching", help="Business Category")
    onboard.add_argument("--tone", default="Professional & Empathetic", help="AI Tone")
    onboard.add_argument("--prompt", required=True, help="Full System Prompt for the AI")
    
    args = parser.parse_args()
    
    if args.command == "list": 
        list_users()
    elif args.command == "onboard":
        onboard_client(args.email, args.name, args.type, args.tone, args.prompt)
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