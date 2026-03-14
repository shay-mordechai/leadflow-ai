# src/scripts/manage_cli.py
import sys
import argparse
from prettytable import PrettyTable
from sqlalchemy.orm import Session
from src.database.session import SessionLocal
from src.database.models import User, PlanTier, SubscriptionStatus, BusinessProfile, AIAgent, UserRole, Lead

# ==============================================================================
# GENERAL MANAGEMENT
# ==============================================================================

def list_users():
    """Lists all users in the database with key details."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        table = PrettyTable()
        table.field_names = ["ID", "Name", "Email", "Role", "Plan", "Status", "Active"]
        
        for u in users:
            table.add_row([
                str(u.id)[:8],
                u.name,
                u.email,
                u.role.value if hasattr(u, 'role') and u.role else "CLIENT",
                u.plan_tier.value if hasattr(u, 'plan_tier') and u.plan_tier else "N/A",
                u.subscription_status.value if hasattr(u, 'subscription_status') and u.subscription_status else "N/A",
                "✅ YES" if u.is_active else "❌ NO"
            ])
        print(table)
    finally:
        db.close()

def toggle_user(email: str):
    """Activates or deactivates a user account (Freeze/Unfreeze)."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ User {email} not found.")
            return

        user.is_active = not user.is_active
        db.commit()
        state = "ACTIVATED" if user.is_active else "DEACTIVATED (Frozen)"
        print(f"✅ Success! User {email} is now {state}.")
    except Exception as e:
        print(f"❌ Database error: {e}")
        db.rollback()
    finally:
        db.close()

def upgrade_user(email: str):
    """
    Directly upgrades a user to PRO status.
    Replaces the old manage_coupons.py functionality.
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

def show_stats():
    """Displays high-level system statistics."""
    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        total_leads = db.query(Lead).count()
        total_partners = db.query(User).filter(User.role == UserRole.PARTNER).count()
        
        print("\n📊 --- SYSTEM STATISTICS --- 📊")
        print(f"Total Registered Users: {total_users}")
        print(f"Total Active Partners:  {total_partners}")
        print(f"Total Leads Processed:  {total_leads}")
        print("-------------------------------\n")
    finally:
        db.close()

def onboard_client(email, biz_name, biz_type, tone, prompt):
    """
    Agency Command: Fully configures a client's AI brain in one shot.
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

# ==============================================================================
# PARTNER / AGENCY MANAGEMENT (NEW)
# ==============================================================================

def approve_partner(email: str):
    """
    Approves a partner/campaigner who registered via the Partner Portal.
    Sets them to ACTIVE and ensures they have the PARTNER role.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ Error: User with email {email} not found.")
            return

        user.is_active = True
        user.role = UserRole.PARTNER
        user.plan_tier = PlanTier.PRO  # Partners get PRO dashboard access
        db.commit()
        print(f"✅ Success! Partner '{user.agency_name or user.name}' ({email}) is now APPROVED and ACTIVE.")
    except Exception as e:
        print(f"❌ Database error: {e}")
        db.rollback()
    finally:
        db.close()

def assign_client(client_email: str, partner_email: str):
    """
    Links a client to a specific partner/campaigner.
    This allows the partner to see the client's performance in their dashboard.
    """
    db = SessionLocal()
    try:
        client = db.query(User).filter(User.email == client_email).first()
        partner = db.query(User).filter(User.email == partner_email).first()

        if not client:
            print(f"❌ Error: Client {client_email} not found.")
            return
        if not partner:
            print(f"❌ Error: Partner {partner_email} not found.")
            return
        
        if partner.role != UserRole.PARTNER:
            print(f"⚠️ Warning: {partner_email} is not marked as a PARTNER. Proceeding anyway, but you may want to run 'approve-partner' on them.")

        client.partner_id = partner.id
        db.commit()
        print(f"🤝 Success! Client '{client.business_name or client.name}' is now managed by Agency '{partner.agency_name or partner.name}'.")
    except Exception as e:
        print(f"❌ Database error: {e}")
        db.rollback()
    finally:
        db.close()


# ==============================================================================
# CLI ROUTER
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadFlow AI Master CLI", formatter_class=argparse.RawTextHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # --- General Commands ---
    subparsers.add_parser("list", help="List all users in the system")
    subparsers.add_parser("stats", help="Show system statistics (users, leads, etc.)")
    
    toggle_parser = subparsers.add_parser("toggle", help="Activate/Deactivate a user account (Freeze)")
    toggle_parser.add_argument("--email", required=True, help="User's email")
    
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade a user to PRO plan")
    upgrade_parser.add_argument("--email", required=True, help="User's email")

    onboard_parser = subparsers.add_parser("onboard", help="Quickly configure a new client's AI Brain")
    onboard_parser.add_argument("--email", required=True, help="Client's registered email")
    onboard_parser.add_argument("--name", required=True, help="Business Name")
    onboard_parser.add_argument("--type", default="NLP Coaching", help="Business Category")
    onboard_parser.add_argument("--tone", default="Professional & Empathetic", help="AI Tone")
    onboard_parser.add_argument("--prompt", required=True, help="Full System Prompt for the AI")
    
    # --- Agency / Partner Commands ---
    approve_parser = subparsers.add_parser("approve-partner", help="Approve a new campaigner/agency")
    approve_parser.add_argument("--email", required=True, help="Partner's registered email")
    
    assign_parser = subparsers.add_parser("assign-client", help="Assign a client to a campaigner's agency")
    assign_parser.add_argument("--client", required=True, help="Client's email")
    assign_parser.add_argument("--partner", required=True, help="Partner's email")

    args = parser.parse_args()
    
    # Route execution based on command
    if args.command == "list": 
        list_users()
    elif args.command == "stats":
        show_stats()
    elif args.command == "toggle":
        toggle_user(args.email)
    elif args.command == "upgrade":
        upgrade_user(args.email)
    elif args.command == "onboard":
        onboard_client(args.email, args.name, args.type, args.tone, args.prompt)
    elif args.command == "approve-partner":
        approve_partner(args.email)
    elif args.command == "assign-client":
        assign_client(args.client, args.partner)

# ==============================================================================
# Usage Examples:
# 
# 1. View Users:
#    python manage_cli.py list
# 
# 2. Approve a Campaigner:
#    python manage_cli.py approve-partner --email "dekel@agency.com"
# 
# 3. Assign a Client to a Campaigner:
#    python manage_cli.py assign-client --client "moshe@clinic.com" --partner "dekel@agency.com"
# ==============================================================================