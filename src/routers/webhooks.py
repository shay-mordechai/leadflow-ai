from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from src.database.session import get_db
from src.database.models import User
from src.services.audio_processor import AudioProcessor

router = APIRouter(tags=["Webhooks"])
logger = logging.getLogger("Webhooks")

@router.post("/whatsapp/{user_id}", status_code=status.HTTP_200_OK)
async def whatsapp_webhook(
    user_id: str,
    payload: Dict[Any, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Receives WhatsApp events from GreenAPI.
    Uses BackgroundTasks to process audio without blocking the response.
    """
    # 1. Security Check: Validate User ID exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"Webhook received for unknown user: {user_id}")
        # Return 404 to avoid leaking user existence
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Filter Payload - We are interested in Audio only
    webhook_type = payload.get("typeWebhook")
    message_type = payload.get("messageData", {}).get("typeMessage")

    # GreenAPI sends 'audioMessage' or 'voiceMessage'
    if webhook_type == "incomingMessageReceived" and message_type in ["audioMessage", "voiceMessage"]:
        
        # 3. Dispatch Background Task (Fire and Forget)
        processor = AudioProcessor(user_id, payload)
        background_tasks.add_task(processor.process_pipeline)
        
        return {"status": "processing_started"}

    return {"status": "ignored_type"}