# src/routers/system.py
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from src.tasks.backup_tasks import backup_database_to_s3
import logging

router = APIRouter(prefix="/api/v1/system", tags=["System"])
logger = logging.getLogger("SystemRouter")

# Security Secret (Make sure this matches what you put in the AWS EventBridge headers!)
CRON_SECRET = "my_super_secret_cron_key_2026" 

@router.post("/backup")
async def trigger_s3_backup(
    background_tasks: BackgroundTasks,
    x_cron_secret: str = Header(None)
):
    """
    Secure Webhook triggered by AWS EventBridge every night.
    """
    if x_cron_secret != CRON_SECRET:
        logger.warning("Unauthorized backup attempt detected.")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Send the backup task to the background so AWS gets an immediate 200 OK response
    background_tasks.add_task(backup_database_to_s3)
    
    return {"status": "success", "message": "Backup task triggered in background."}