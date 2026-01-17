# src/routers/webhooks.py
from fastapi import APIRouter, Request, HTTPException, Depends, status
from sqlalchemy.orm import Session
import os
import aiofiles
import httpx
from datetime import datetime

from src.database.session import get_db
from src.database.models import User, Lead, MediaInteraction, MediaType, ProcessingStatus, LeadSource
from src.security.encryption import protector

router = APIRouter(tags=["Webhooks"])

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "my_secret_token")
META_API_URL = "https://graph.facebook.com/v17.0"
SHARED_STORAGE_PATH = "/app/storage"  # Must match the Volume path

@router.get("/whatsapp")
async def verify_webhook(request: Request):
    """Meta Verification Challenge"""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/whatsapp")
async def receive_whatsapp_message(request: Request, db: Session = Depends(get_db)):
    """Handles incoming messages from Meta"""
    data = await request.json()
    
    try:
        # Navigate Meta's complex JSON structure
        entry = data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        
        if 'messages' not in value:
            return {"status": "no_messages"}

        message = value['messages'][0]
        sender_phone = message['from']  # The Lead's phone number
        business_phone_id = value['metadata']['phone_number_id'] # Your ID

        # 1. Find the User (Coach) via the Business Phone ID
        # (For MVP we might assume one user, but better to query integration table)
        # TODO: In real production, query Integration table by phone_number_id
        user = db.query(User).first() 
        if not user:
            print("❌ No user found for this incoming message")
            return {"status": "ignored"}

        # 2. Find or Create Lead
        # We need to decrypt phones to search (Inefficient, but ok for MVP)
        # Better: Store a hashed_phone_index for searching
        lead = None
        all_leads = db.query(Lead).filter(Lead.user_id == user.id).all()
        for l in all_leads:
            if l.phone_number == sender_phone:
                lead = l
                break
        
        if not lead:
            lead = Lead(
                user_id=user.id,
                phone_number=sender_phone,
                name=value['contacts'][0]['profile']['name'], # WhatsApp Name
                source=LeadSource.WHATSAPP,
                status="NEW"
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)

        # 3. Handle Audio
        if message['type'] == 'audio':
            media_id = message['audio']['id']
            
            # Get Media URL from Meta
            # We need the User's Access Token (Assumed stored in env for MVP or DB)
            access_token = os.getenv("META_ACCESS_TOKEN") 
            
            async with httpx.AsyncClient() as client:
                # Step A: Get URL
                url_resp = await client.get(
                    f"{META_API_URL}/{media_id}",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                media_url = url_resp.json().get("url")
                
                # Step B: Download File
                file_resp = await client.get(
                    media_url,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                # Save to Shared Volume
                filename = f"{lead.id}_{int(datetime.now().timestamp())}.ogg"
                file_path = os.path.join(SHARED_STORAGE_PATH, filename)
                
                # Ensure directory exists
                os.makedirs(SHARED_STORAGE_PATH, exist_ok=True)

                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(file_resp.content)

            # 4. Create DB Entry for Worker
            media = MediaInteraction(
                user_id=user.id,
                lead_id=lead.id,
                file_path=file_path,
                media_type=MediaType.AUDIO,
                status=ProcessingStatus.PENDING
            )
            db.add(media)
            db.commit()
            print(f"✅ Saved audio for Lead {lead.name}: {filename}")

        return {"status": "success"}

    except Exception as e:
        print(f"⚠️ Error parsing webhook: {e}")
        return {"status": "error"}