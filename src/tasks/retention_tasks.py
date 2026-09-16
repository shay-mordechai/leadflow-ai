# src/tasks/retention_tasks.py
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from celery import shared_task
from sqlalchemy.orm import Session

from src.config import settings
from src.database.models import CoachingSession, Lead, MediaInteraction, Message
from src.database.session import SessionLocal

logger = logging.getLogger("RetentionTasks")

BATCH_SIZE = 200

# Never unlink JSON tenant profiles or the live SQLite file.
_PROTECTED_SUFFIXES = (".db", ".db-wal", ".db-shm", ".json")
_PROTECTED_PATH_MARKERS = (os.sep + "profiles" + os.sep, "/profiles/")


def _retention_cutoff() -> datetime:
    ttl_hours = max(1, int(getattr(settings, "RETENTION_TTL_HOURS", 24) or 24))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
    if settings.DATABASE_URL.startswith("sqlite"):
        return cutoff.replace(tzinfo=None)
    return cutoff


def _allowed_roots() -> list[str]:
    candidates = (
        "/app/storage",
        "/app/data",
        os.path.abspath("storage"),
        os.path.abspath("data"),
        os.path.abspath("./storage"),
        os.path.abspath("./data"),
    )
    roots: list[str] = []
    for path in candidates:
        try:
            roots.append(os.path.realpath(path))
        except OSError:
            continue
    return roots


def _is_protected_path(real_path: str) -> bool:
    lowered = real_path.lower()
    if lowered.endswith(_PROTECTED_SUFFIXES):
        return True
    return any(marker in real_path for marker in _PROTECTED_PATH_MARKERS)


def _safe_unlink(file_path: Optional[str]) -> bool:
    """
    Delete a local media file if it lives under storage/data mounts.
    Missing files, S3 keys, and paths outside the allowed roots are skipped.
    """
    if not file_path or not str(file_path).strip():
        return False

    candidate = str(file_path).strip()
    if candidate.startswith("s3://") or candidate.startswith("http://") or candidate.startswith("https://"):
        logger.info("Skipping remote media path during retention: %s", candidate)
        return False

    try:
        real_path = os.path.realpath(candidate)
    except OSError as exc:
        logger.warning("Could not resolve media path %s: %s", candidate, exc)
        return False

    if _is_protected_path(real_path):
        logger.warning("Refusing to delete protected path during retention: %s", real_path)
        return False

    if not any(real_path == root or real_path.startswith(root + os.sep) for root in _allowed_roots()):
        logger.warning("Refusing to delete path outside storage/data roots: %s", real_path)
        return False

    try:
        if os.path.isdir(real_path):
            logger.warning("Refusing to delete directory during retention: %s", real_path)
            return False
        if not os.path.exists(real_path):
            logger.info("Retention file already absent: %s", real_path)
            return False
        os.remove(real_path)
        logger.info("Expunged media file: %s", real_path)
        return True
    except FileNotFoundError:
        logger.info("Retention file already absent: %s", real_path)
        return False
    except OSError as exc:
        logger.error("Failed to unlink %s: %s", real_path, exc)
        return False


def _purge_messages(db: Session, cutoff: datetime) -> int:
    deleted = 0
    try:
        deleted = (
            db.query(Message)
            .filter(Message.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to delete expired Message rows")
        return 0
    return int(deleted or 0)


def _purge_media_interactions(db: Session, cutoff: datetime) -> int:
    purged = 0
    while True:
        try:
            batch = (
                db.query(MediaInteraction)
                .filter(MediaInteraction.created_at < cutoff)
                .limit(BATCH_SIZE)
                .all()
            )
            if not batch:
                break
            for media in batch:
                _safe_unlink(media.file_path)
                db.delete(media)
                purged += 1
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to purge an expired MediaInteraction batch")
            break
    return purged


def _purge_coaching_sessions(db: Session, cutoff: datetime) -> int:
    purged = 0
    while True:
        try:
            batch = (
                db.query(CoachingSession)
                .filter(
                    CoachingSession.created_at < cutoff,
                    CoachingSession.audio_file_path != "",
                )
                .limit(BATCH_SIZE)
                .all()
            )
            # Also catch already-unlinked rows that still hold transcript text.
            if not batch:
                batch = (
                    db.query(CoachingSession)
                    .filter(
                        CoachingSession.created_at < cutoff,
                        (CoachingSession.transcript.isnot(None))
                        | (CoachingSession.summary.isnot(None)),
                    )
                    .limit(BATCH_SIZE)
                    .all()
                )
            if not batch:
                break
            for session in batch:
                _safe_unlink(session.audio_file_path)
                # audio_file_path is NOT NULL — keep the row, wipe payload.
                session.audio_file_path = ""
                session.transcript = None
                session.summary = None
                purged += 1
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to wipe an expired CoachingSession batch")
            break
    return purged


def _wipe_lead_transcriptions(db: Session, cutoff: datetime) -> int:
    """CRM lead rows stay; transcribed / AI text columns are cleared."""
    wiped = 0
    while True:
        try:
            batch = (
                db.query(Lead)
                .filter(
                    Lead.created_at < cutoff,
                    (Lead.transcription_summary.isnot(None))
                    | (Lead.original_transcript.isnot(None))
                    | (Lead.coach_feedback.isnot(None))
                    | (Lead.suggested_reply.isnot(None))
                    | (Lead.ai_feedback_note.isnot(None)),
                )
                .limit(BATCH_SIZE)
                .all()
            )
            if not batch:
                break
            for lead in batch:
                lead.transcription_summary = None
                lead.original_transcript = None
                lead.coach_feedback = None
                lead.suggested_reply = None
                lead.ai_feedback_note = None
                wiped += 1
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to wipe an expired Lead transcription batch")
            break
    return wiped


@shared_task(name="purge_expired_tenant_data", bind=True, max_retries=2)
def purge_expired_tenant_data(self):
    """
    Enforce the 24-hour privacy window: unlink local media, delete chat
    transcripts, and wipe processed text that has aged past RETENTION_TTL_HOURS.
    """
    cutoff = _retention_cutoff()
    logger.info("Starting retention purge for records older than %s", cutoff.isoformat())

    db: Session = SessionLocal()
    stats = {
        "messages": 0,
        "media_interactions": 0,
        "coaching_sessions": 0,
        "leads_wiped": 0,
    }
    try:
        stats["messages"] = _purge_messages(db, cutoff)
        stats["media_interactions"] = _purge_media_interactions(db, cutoff)
        stats["coaching_sessions"] = _purge_coaching_sessions(db, cutoff)
        stats["leads_wiped"] = _wipe_lead_transcriptions(db, cutoff)
        logger.info("Retention purge complete: %s", stats)
        return stats
    except Exception as exc:
        db.rollback()
        logger.exception("Retention purge aborted")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
