# src/routers/webhooks.py
import os
import logging
import aiofiles
import httpx
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, status, Response
from sqlalchemy.orm import Session

# Import project modules
from src.database.session import get_db
from src.database.models import User, Lead, MediaInteraction, ProcessingStatus, LeadSource
from src.security.encryption import protector

# Setup Logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Webhooks"])

# Configuration
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "my_secret_token")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
SHARED_STORAGE_PATH = "/app/storage"  # Matches the Docker volume path

@router.get("/whatsapp")
async def verify_webhook(request: Request):
    """
    Meta Verification Challenge.
    Used by Facebook to verify that this server owns the callback URL.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully.")
        return int(challenge)
    
    logger.warning("❌ Webhook verification failed: Invalid token.")
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/whatsapp")
async def receive_whatsapp_message(request: Request, db: Session = Depends(get_db)):
    """
    Ingests incoming messages from Meta/WhatsApp Cloud API.
    Downloads audio files and queues them for the Worker.
    """
    try:
        data = await request.json()
        
        # 1. Parse Meta's nested JSON structure
        # Check if the payload actually contains messages
        entry = data.get('entry', [])[0]
        changes = entry.get('changes', [])[0]
        value = changes.get('value', {})
        
        if 'messages' not in value:
            # This might be a status update (sent/delivered/read), we ignore it for now
            return {"status": "ignored_status_update"}

        message = value['messages'][0]
        sender_phone = message['from']  # The Lead's raw phone number
        message_type = message['type']
        
        # 2. Identify the User (Business Owner)
        # In a multi-tenant system, we would map value['metadata']['phone_number_id'] to a User.
        # For this MVP, we fetch the first user (assuming Single Tenant per container).
        user = db.query(User).first() 
        if not user:
            logger.error("❌ No user found in DB to attach this lead to.")
            return {"status": "error_no_user"}

        # 3. Find or Create the Lead
        # NOTE: Since phone numbers are encrypted in DB, we cannot simply query .filter(phone==sender_phone).
        # We iterate and decrypt. (Optimization for later: Add a hashed_phone_index column).
        lead = None
        all_leads = db.query(Lead).filter(Lead.user_id == user.id).all()
        
        for l in all_leads:
            try:
                if protector.decrypt(l.phone_number) == sender_phone:
                    lead = l
                    break
            except Exception:
                continue # Skip corrupted/legacy data
        
        if not lead:
            # Create new lead
            lead_name = value.get('contacts', [{}])[0].get('profile', {}).get('name', 'Unknown')
            lead = Lead(
                user_id=user.id,
                phone_number=protector.encrypt(sender_phone), # Encrypt before saving
                name=lead_name,
                source=LeadSource.WHATSAPP,
                status="NEW"
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)
            logger.info(f"🆕 New Lead created: {lead.name}")

        # 4. Handle Audio Messages
        if message_type == 'audio':
            audio_id = message['audio']['id']
            
            # Step A: Get the Media URL from Meta
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
                
                # Meta API to get the download URL
                url_resp = await client.get(
                    f"https://graph.facebook.com/v17.0/{audio_id}",
                    headers=headers
                )
                
                if url_resp.status_code != 200:
                    logger.error(f"Failed to get media URL: {url_resp.text}")
                    return {"status": "error_meta_api"}
                
                media_url = url_resp.json().get("url")
                
                # Step B: Download the actual file binary
                file_resp = await client.get(media_url, headers=headers)
                
                if file_resp.status_code != 200:
                    logger.error("Failed to download media binary.")
                    return {"status": "error_download"}

                # Step C: Save to Shared Volume
                # Naming format: leadID_timestamp.ogg
                filename = f"lead_{lead.id}_{int(datetime.now().timestamp())}.ogg"
                file_path = os.path.join(SHARED_STORAGE_PATH, filename)
                
                # Ensure directory exists
                os.makedirs(SHARED_STORAGE_PATH, exist_ok=True)

                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(file_resp.content)
                
                logger.info(f"💾 Audio saved at: {file_path}")

            # 5. Create Job for the Worker
            # This entry triggers the background Worker to run Whisper + Gemini
            media_interaction = MediaInteraction(
                user_id=user.id,
                lead_id=lead.id,    # Link to the specific lead
                sender_phone=sender_phone,
                media_type="AUDIO", # Matches MediaType.AUDIO enum
                file_path=file_path,
                status=ProcessingStatus.PENDING # Worker looks for PENDING
            )
            db.add(media_interaction)
            db.commit()
            
            logger.info(f"✅ Job Queued: {media_interaction.id}")

        # 6. Handle Text Messages (Optional, for direct AI replies to text)
        elif message_type == 'text':
             text_body = message['text']['body']
             media_interaction = MediaInteraction(
                user_id=user.id,
                lead_id=lead.id,
                sender_phone=sender_phone,
                media_type="TEXT",
                message_text=text_body,
                status=ProcessingStatus.PENDING
            )
             db.add(media_interaction)
             db.commit()
             logger.info(f"✅ Text Job Queued: {media_interaction.id}")

        return {"status": "success"}

    except Exception as e:
        logger.exception(f"⚠️ Critical Webhook Error: {e}")
        # Always return 200 to Meta, otherwise they will retry indefinitely
        return {"status": "error", "detail": str(e)}