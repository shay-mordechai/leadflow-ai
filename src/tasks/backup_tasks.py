# src/tasks/backup_tasks.py
import logging
import os
import sqlite3
from datetime import datetime
from src.config import settings
from src.services.storage.s3_service import s3_service

logger = logging.getLogger("DatabaseBackup")

def backup_database_to_s3():
    """
    Creates a safe, non-blocking snapshot of the live SQLite database
    and uploads it securely to Amazon S3.
    """
    logger.info("🗄️ Starting scheduled database backup to S3...")
    
    # 1. Extract file path (e.g., from 'sqlite:////app/data/leads.db' -> '/app/data/leads.db')
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    if not os.path.exists(db_path):
        logger.error(f"❌ Backup failed: Database file not found at {db_path}")
        return
        
    # 2. Create a temporary safe snapshot
    # We use sqlite3.backup() because simply copying the file while it's in WAL mode 
    # and being written to can lead to a corrupted backup.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"leads_backup_{timestamp}.db"
    temp_backup_path = f"/tmp/{backup_filename}"
    
    try:
        # Generate safe snapshot
        with sqlite3.connect(db_path) as source:
            with sqlite3.connect(temp_backup_path) as dest:
                source.backup(dest)
        
        logger.info(f"✅ Local snapshot created successfully: {backup_filename}")
        
        # 3. Upload to S3
        s3_key = f"backups/database/{backup_filename}"
        
        with open(temp_backup_path, "rb") as f:
            success = s3_service.upload_fileobj(
                file_obj=f,
                object_name=s3_key,
                content_type="application/vnd.sqlite3"
            )
            
        if success:
            logger.info(f"☁️ SUCCESS: Database backed up to S3 -> {s3_key}")
        else:
            logger.error("❌ ERROR: Failed to upload database backup to S3.")
            
    except Exception as e:
        logger.error(f"🔥 Database backup process crashed: {e}")
        
    finally:
        # 4. Cleanup temporary local snapshot to save disk space
        if os.path.exists(temp_backup_path):
            os.remove(temp_backup_path)
            logger.info("🧹 Cleaned up temporary backup file.")