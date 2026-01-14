# src/database/models.py

import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, ForeignKey, Enum, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from src.security.encryption import protector

Base = declarative_base()

# --- ENUMS ---
# Defining Enums here ensures consistency across the application and database.

class PlanTier(str, enum.Enum):
    STARTER = "STARTER"
    PRO = "PRO"

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    TRIAL = "TRIAL"

class LeadSource(str, enum.Enum):
    FACEBOOK = "FACEBOOK"
    INSTAGRAM = "INSTAGRAM"
    WHATSAPP = "WHATSAPP"
    MANUAL = "MANUAL"
    LANDING_PAGE = "LANDING_PAGE"

class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    QUALIFIED = "QUALIFIED"
    LOST = "LOST"

class MediaType(str, enum.Enum):
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"

# --- MODELS ---

class User(Base):
    """
    Represents a SaaS customer (Coach/Business Owner).
    Replaces the previous 'Tenant' model to support SaaS subscriptions.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Auth & Profile
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # SaaS & Subscription Logic
    plan_tier = Column(Enum(PlanTier), default=PlanTier.STARTER, nullable=False)
    subscription_status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Virtual Number (Twilio) - Nullable for STARTER tier
    assigned_phone_number = Column(String, unique=True, index=True, nullable=True)
    
    # BYOK (Bring Your Own Key) - Encrypted storage recommended in production, keeping simple for now
    openai_api_key = Column(String, nullable=True)

    # Relationships
    leads = relationship("Lead", back_populates="user", cascade="all, delete-orphan")
    media_files = relationship("MediaInteraction", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")


class Lead(Base):
    """
    The core entity. Represents a potential client.
    PII (Name/Phone) is encrypted at rest using the 'protector' utility.
    """
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Encrypted PII Columns
    _name_encrypted = Column("name", String, nullable=True)
    _phone_encrypted = Column("phone_number", String, nullable=True)
    
    # Metadata
    city = Column(String, nullable=True)
    source = Column(Enum(LeadSource), default=LeadSource.MANUAL, nullable=False)
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW, nullable=False, index=True)
    
    # AI Analysis & Transcription Results
    transcription_summary = Column(Text, nullable=True) # AI Summary
    original_transcript = Column(Text, nullable=True)   # Raw Text
    coach_feedback = Column(Text, nullable=True)        # Notes from the user
    
    # Conversion Tracking
    is_converted = Column(Boolean, default=False)
    
    # Retention & Automation
    suggested_reply = Column(Text, nullable=True)       # AI drafted reply
    needs_followup = Column(Boolean, default=False)
    followup_date = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="leads")
    media_files = relationship("MediaInteraction", back_populates="lead")

    # Encryption Helpers
    @property
    def name(self):
        return protector.decrypt(self._name_encrypted) if self._name_encrypted else None

    @name.setter
    def name(self, value):
        self._name_encrypted = protector.encrypt(value) if value else None

    @property
    def phone_number(self):
        return protector.decrypt(self._phone_encrypted) if self._phone_encrypted else None

    @phone_number.setter
    def phone_number(self, value):
        self._phone_encrypted = protector.encrypt(value) if value else None


class MediaInteraction(Base):
    """
    Tracks raw media files (WhatsApp Voice Notes, Images).
    Used for:
    1. Transcribing audio to text.
    2. Enforcing the 24-hour retention policy (Privacy).
    """
    __tablename__ = "media_interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True) # Nullable if lead not yet identified

    file_path = Column(String, nullable=False) # Path to local storage / S3
    media_type = Column(Enum(MediaType), default=MediaType.AUDIO, nullable=False)
    
    processed = Column(Boolean, default=False) # Has AI processed this?
    
    # Crucial for Cron Job (Delete files where created_at < 24h ago)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="media_files")
    lead = relationship("Lead", back_populates="media_files")


class Integration(Base):
    """
    Stores authentication tokens for external platforms.
    """
    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    platform_name = Column(String, nullable=False) # e.g., "FACEBOOK", "HUBSPOT"
    access_token = Column(String, nullable=False)  # Encrypt this in production!
    webhook_url = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="integrations")


# Keeps previous models if needed for legacy support, 
# otherwise they should be migrated or removed.
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(45), nullable=True)
    action = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    severity = Column(String(20), default="INFO")