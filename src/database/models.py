# src/database/models.py
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, ForeignKey, Enum, Integer, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from src.security.encryption import protector

Base = declarative_base()

# --- ENUMS ---
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
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Auth & Profile
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    #SaaS & Subscription Logic
    plan_tier = Column(Enum(PlanTier), default=PlanTier.STARTER, nullable=False)
    subscription_status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_ip = Column(String, nullable=True)

    # Virtual Number (Twilio)
    assigned_phone_number = Column(String, unique=True, index=True, nullable=True)
    
    # BYOK (Bring Your Own Key)
    openai_api_key = Column(String, nullable=True)

    # Relationships
    # cascade="all, delete-orphan" ensures Python-side cleanup
    leads = relationship("Lead", back_populates="user", cascade="all, delete-orphan")
    media_files = relationship("MediaInteraction", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    
    # One-to-One relationship with BusinessProfile
    business_profile = relationship("BusinessProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")


class BusinessProfile(Base):
    """
    Stores the 'Brain' configuration for the AI Agent.
    Defines how the AI should behave, speak, and sell for this specific user.
    """
    __tablename__ = "business_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    business_name = Column(String, nullable=False, default="My Business")
    business_type = Column(String, default="General") # e.g., "Real Estate", "Fitness"
    
    # AI Personality Configuration
    ai_tone = Column(String, default="Professional") # Professional, Friendly, Urgent
    products_services = Column(Text, nullable=True) # "We sell X for $Y..."
    custom_instructions = Column(Text, nullable=True) # "Never mention price..."
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="business_profile")


class Lead(Base):
    """
    The core entity. Represents a potential client.
    PII (Name/Phone) is encrypted at rest using the 'protector' utility.
    """
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Encrypted PII Columns
    _name_encrypted = Column("name", String, nullable=True)
    _phone_encrypted = Column("phone_number", String, nullable=True)
    email = Column(String, nullable=True) # Not encrypted for easier searching/mailing, can be encrypted if strict GDPR required.
    
    # Metadata
    city = Column(String, nullable=True)
    source = Column(Enum(LeadSource), default=LeadSource.MANUAL, nullable=False)
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW, nullable=False, index=True)
    
    # AI Analysis & Transcription Results
    transcription_summary = Column(Text, nullable=True) # AI Summary
    original_transcript = Column(Text, nullable=True)   # Raw Text
    coach_feedback = Column(Text, nullable=True)        # Notes from the user
    
    # Retention & Automation
    suggested_reply = Column(Text, nullable=True)       # AI drafted reply
    needs_followup = Column(Boolean, default=False)
    followup_date = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

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
    """
    __tablename__ = "media_interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)

    file_path = Column(String, nullable=False)
    media_type = Column(Enum(MediaType), default=MediaType.AUDIO, nullable=False)
    
    processed = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", back_populates="media_files")
    lead = relationship("Lead", back_populates="media_files")


class Integration(Base):
    """
    Stores authentication tokens for external platforms.
    """
    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    platform_name = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    webhook_url = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="integrations")
