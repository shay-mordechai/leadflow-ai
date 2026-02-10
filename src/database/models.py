# src/database/models.py
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, ForeignKey, Enum, Integer, func
)
from sqlalchemy.orm import relationship

# --- IMPORT BASE & GUID FROM SESSION ---
from src.database.session import Base, GUID

# Security: Encryption wrapper for PII and OTPs
from src.security.encryption import protector 

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

class SessionStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# --- MODELS ---

class User(Base):
    __tablename__ = "users"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    
    # Security: Never query this column directly in responses. Use Pydantic to exclude it.
    hashed_password = Column(String, nullable=False)
    
    plan_tier = Column(Enum(PlanTier), default=PlanTier.STARTER, nullable=False)
    subscription_status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL, nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_ip = Column(String, nullable=True)

    last_known_city = Column(String, nullable=True)
    last_known_country = Column(String, nullable=True)

    # Security: OTP is encrypted at rest
    _otp_encrypted = Column("otp_code", String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)

    business_name = Column(String, nullable=True)
    business_type = Column(String, nullable=True) 
    assigned_phone_number = Column(String, unique=True, index=True, nullable=True)
    personal_whatsapp = Column(String, nullable=True) 
    
    openai_api_key = Column(String, nullable=True)

    # Relationships with Cascade Delete (GDPR: Delete user = Delete all their data)
    leads = relationship("Lead", back_populates="user", cascade="all, delete-orphan")
    media_files = relationship("MediaInteraction", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    business_profile = relationship("BusinessProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    phone_numbers = relationship("PhoneNumber", back_populates="owner", cascade="all, delete-orphan")
    coaching_sessions = relationship("CoachingSession", back_populates="user", cascade="all, delete-orphan")

    @property
    def otp_code(self):
        return protector.decrypt(self._otp_encrypted) if self._otp_encrypted else None
    
    @otp_code.setter
    def otp_code(self, value):
        self._otp_encrypted = protector.encrypt(value) if value else None

class PhoneNumber(Base):
    __tablename__ = "phone_numbers"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    number = Column(String, unique=True, index=True, nullable=False)
    country_code = Column(String, default="IL")
    provider = Column(String, default="twilio")
    provider_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_id = Column(GUID(), ForeignKey("users.id"))
    owner = relationship("User", back_populates="phone_numbers")

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
    # Security: Indexed user_id for fast IDOR-safe queries
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Security: Encrypted PII Fields
    _name_encrypted = Column("name", String, nullable=True)
    _phone_encrypted = Column("phone_number", String, nullable=True)
    
    email = Column(String, nullable=True)
    city = Column(String, nullable=True)
    source = Column(Enum(LeadSource), default=LeadSource.MANUAL, nullable=False)
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW, nullable=False, index=True)
    
    transcription_summary = Column(Text, nullable=True)
    original_transcript = Column(Text, nullable=True)
    coach_feedback = Column(Text, nullable=True)
    suggested_reply = Column(Text, nullable=True)
    
    needs_followup = Column(Boolean, default=False)
    followup_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    user = relationship("User", back_populates="leads")
    media_files = relationship("MediaInteraction", back_populates="lead")
    sessions = relationship("CoachingSession", back_populates="lead")

    # Security: Encryption Getters/Setters
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

class CoachingSession(Base):
    __tablename__ = "coaching_sessions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="coaching_sessions")

    lead_id = Column(GUID(), ForeignKey("leads.id"), nullable=True)
    lead = relationship("Lead", back_populates="sessions")
    
    audio_file_path = Column(String, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.QUEUED)
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())