# src/database/models.py
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, ForeignKey, Enum, Integer, func
)
# We use GUID as a helper to handle UUIDs across both SQLite and Postgres
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

# Ensure encryption is imported
from src.security.encryption import protector 

Base = declarative_base()

# --- HELPER FOR CROSS-DB UUID SUPPORT ---
class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as string without hyphens.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value

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
    TEXT = "TEXT" 

class ProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# --- MODELS ---

class User(Base):
    __tablename__ = "users"
    
    # Using GUID for cross-DB compatibility
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # Billing & Plan Info
    plan_tier = Column(Enum(PlanTier), default=PlanTier.STARTER, nullable=False)
    subscription_status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL, nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_ip = Column(String, nullable=True)

    # Security & Location Tracking
    last_known_city = Column(String, nullable=True)
    last_known_country = Column(String, nullable=True)

    # Business Info
    business_type = Column(String, nullable=True) 
    assigned_phone_number = Column(String, unique=True, index=True, nullable=True)
    personal_whatsapp = Column(String, nullable=True) 
    
    # AI Settings
    openai_api_key = Column(String, nullable=True)

    # Relationships
    leads = relationship("Lead", back_populates="user", cascade="all, delete-orphan")
    media_files = relationship("MediaInteraction", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    business_profile = relationship("BusinessProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")

class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    business_name = Column(String, nullable=False, default="My Business")
    business_type = Column(String, default="General")
    ai_tone = Column(String, default="Professional")
    products_services = Column(Text, nullable=True)
    custom_instructions = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="business_profile")

class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Internal Encrypted Fields
    _name_encrypted = Column("name", String, nullable=True)
    _phone_encrypted = Column("phone_number", String, nullable=True)
    
    email = Column(String, nullable=True)
    city = Column(String, nullable=True)
    source = Column(Enum(LeadSource), default=LeadSource.MANUAL, nullable=False)
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW, nullable=False, index=True)
    
    # AI Analysis Data
    transcription_summary = Column(Text, nullable=True)
    original_transcript = Column(Text, nullable=True)
    coach_feedback = Column(Text, nullable=True)
    suggested_reply = Column(Text, nullable=True)
    
    needs_followup = Column(Boolean, default=False)
    followup_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    user = relationship("User", back_populates="leads")
    media_files = relationship("MediaInteraction", back_populates="lead")

    # Property getters/setters handle seamless encryption
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
    __tablename__ = "media_interactions"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(GUID(), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    
    file_path = Column(String, nullable=False)
    message_text = Column(Text, nullable=True) 
    media_type = Column(Enum(MediaType), default=MediaType.AUDIO, nullable=False)
    
    processed = Column(Boolean, default=False) 
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING, index=True)
    transcription_text = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    suggested_reply = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    user = relationship("User", back_populates="media_files")
    lead = relationship("Lead", back_populates="media_files")

class Integration(Base):
    __tablename__ = "integrations"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    platform_name = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    webhook_url = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="integrations")