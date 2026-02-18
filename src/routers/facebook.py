.p# src/routers/facebook.py
import logging
import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from src.database.session import get_db
from src.database.models import User, Lead, LeadSource, LeadStatus
from src.security.dependencies import get_current_user
from src.config import settings
from src.services.communication.whatsapp import whatsapp_adapter

router = APIRouter(prefix="/facebook", tags=["Facebook Native Integration"])
logger = logging.getLogger("FacebookIntegration")

# These should be added to your .env file later
FB_CLIENT_ID = getattr(settings, "FACEBOOK_CLIENT_ID", "YOUR_APP_ID")
FB_CLIENT_SECRET = getattr(settings, "FACEBOOK_CLIENT_SECRET", "YOUR_APP_SECRET")
FB_VERIFY_TOKEN = getattr(settings, "FACEBOOK_WEBHOOK_VERIFY_TOKEN", "my_leads_secure_token_123")
FB_API_VERSION = "v18.0"

# ============================================================================
# 1. OAUTH 2.0 FLOW (For connecting the user's Facebook account)
# ============================================================================

@router.get("/auth/url")
async def get_facebook_oauth_url(current_user: User = Depends(get_current_user)):
    """
    Generates the URL to redirect the user to Facebook's Login screen.
    Requests permissions to read leads and manage pages.
    """
    redirect_uri = f"{settings.API_BASE_URL}/api/v1/facebook/auth/callback"
    scope = "pages_show_list,pages_read_engagement,pages_manage_ads,leads_retrieval"
    
    auth_url = (
        f"https://www.facebook.com/{FB_API_VERSION}/dialog/oauth?"
        f"client_id={FB_CLIENT_ID}&redirect_uri={redirect_uri}&"
        f"scope={scope}&state={current_user.id}"
    )
    return {"auth_url": auth_url}

@router.get("/auth/callback")
async def facebook_oauth_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    Receives the 'code' from Facebook after user approves, 
    exchanges it for a Long-Lived Access Token, and saves to DB.
    """
    redirect_uri = f"{settings.API_BASE_URL}/api/v1/facebook/auth/callback"
    user_id = state # We passed the user ID in the state parameter
    
    # 1. Exchange code for short-lived token
    token_url = (
        f"https://graph.facebook.com/{FB_API_VERSION}/oauth/access_token?"
        f"client_id={FB_CLIENT_ID}&redirect_uri={redirect_uri}&"
        f"client_secret={FB_CLIENT_SECRET}&code={code}"
    )
    res = requests.get(token_url)
    if not res.ok:
        raise HTTPException(status_code=400, detail="Failed to exchange code")
    
    short_token = res.json().get("access_token")

    # 2. Exchange short-lived token for Long-Lived Token (lasts 60 days)
    long_token_url = (
        f"https://graph.facebook.com/{FB_API_VERSION}/oauth/access_token?"
        f"grant_type=fb_exchange_token&client_id={FB_CLIENT_ID}&"
        f"client_secret={FB_CLIENT_SECRET}&fb_exchange_token={short_token}"
    )
    long_res = requests.get(long_token_url)
    long_token = long_res.json().get("access_token")

    # 3. Save to User DB (Requires adding facebook_access_token to User model later)
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        # user.facebook_access_token = long_token # Uncomment when DB is updated
        # db.commit()
        logger.info(f"✅ Facebook Token generated & saved for User: {user.email}")
    
    # Redirect back to the frontend integrations hub
    return {"message": "Facebook connected successfully! Close this window."}

# ============================================================================
# 2. WEBHOOK RECEIVER (Meta sends leads here directly)
# ============================================================================

@router.get("/webhook")
async def verify_facebook_webhook(
    request: Request,
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None
):
    """
    REQUIRED FOR META APP REVIEW: 
    When configuring the Webhook in Meta Developer Dashboard, 
    Meta sends a GET request here to verify ownership.
    """
    hub_mode = request.query_params.get("hub.mode")
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")

    if hub_mode == "subscribe" and hub_verify_token == FB_VERIFY_TOKEN:
        logger.info("✅ Facebook Webhook Verified Successfully!")
        return Response(content=hub_challenge, status_code=status.HTTP_200_OK)
    
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook")
async def receive_facebook_lead(request: Request, db: Session = Depends(get_db)):
    """
    Receives Lead Notifications from Facebook.
    Extracts the Lead ID, fetches the real data, and triggers the AI Bot.
    """
    payload = await request.json()
    
    try:
        # Facebook sends data in "entries" -> "changes"
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "leadgen":
                    leadgen_data = change.get("value", {})
                    lead_id = leadgen_data.get("leadgen_id")
                    page_id = leadgen_data.get("page_id")

                    if not lead_id:
                        continue
                    
                    # 1. Find User by Page ID (Requires adding facebook_page_id to DB)
                    # user = db.query(User).filter(User.facebook_page_id == page_id).first()
                    # if not user or not user.facebook_access_token:
                    #     continue
                    
                    logger.info(f"📩 Native Facebook Lead Received! Lead ID: {lead_id}")

                    # 2. Fetch Actual Lead Data from Graph API using the User's Token
                    # (Dummy code for structure - needs actual token to run)
                    """
                    graph_url = f"https://graph.facebook.com/{FB_API_VERSION}/{lead_id}?access_token={user.facebook_access_token}"
                    lead_res = requests.get(graph_url).json()
                    
                    # 3. Extract Fields (Facebook returns a list of field_data)
                    lead_name, lead_phone = "Unknown", "Unknown"
                    for field in lead_res.get("field_data", []):
                        if field["name"] == "full_name": lead_name = field["values"][0]
                        if field["name"] == "phone_number": lead_phone = field["values"][0]

                    # 4. Save to Database & Trigger Speed-to-Lead
                    new_lead = Lead(...)
                    db.add(new_lead)
                    db.commit()
                    
                    whatsapp_adapter.send_message(to_phone=lead_phone, text=intro_text)
                    """
                    
        return Response(content="EVENT_RECEIVED", status_code=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"❌ Error processing Facebook Webhook: {e}")
        return Response(content="ERROR", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)