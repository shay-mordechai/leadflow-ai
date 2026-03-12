# src/database/models.py
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, ForeignKey, Enum, Integer, func, Table, JSON
)
from sqlalchemy.orm import relationship

# --- IMPORT BASE & GUID FROM SESSION ---
from src.database.session import Base, GUID

# FIXED: Exposing AuditLog through the central models file to prevent ImportErrors
from .audit_model import AuditLog

# Security: Encryption wrapper for OTPs (Kept for security)
from src.security.encryption import protector 

# --- ENUMS ---
class UserRole(str, enum.Enum):
    CLIENT = "CLIENT"     # End-user (e.g., coach, clinic)
    PARTNER = "PARTNER"   # Agency/Campaigner providing leads
    ADMIN = "ADMIN"       # System administrator (You)

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
    FACEBOOK_AD = "FACEBOOK_AD"   
    INSTAGRAM = "INSTAGRAM"
    WHATSAPP = "WHATSAPP"
    GOOGLE_ADS = "GOOGLE_ADS"     
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

class WebhookProvider(str, enum.Enum):
    TWILIO = "TWILIO"
    VONAGE = "VONAGE"
    META = "META"
    CUSTOM = "CUSTOM"


# --- ASSOCIATION TABLES ---
# Many-to-Many relationship between Leads and Tags
lead_tag_association = Table(
    'lead_tag_association',
    Base.metadata,
    Column('lead_id', GUID(), ForeignKey('leads.id', ondelete="CASCADE"), primary_key=True),
    Column('tag_id', GUID(), ForeignKey('tags.id', ondelete="CASCADE"), primary_key=True)
)


# --- MODELS ---

class User(Base):
    __tablename__ = "users"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    
    # Security: Never query this column directly in responses. Use Pydantic to exclude it.
    hashed_password = Column(String, nullable=False)
    
    # NEW: Role-based Access Control (RBAC)
    role = Column(Enum(UserRole), default=UserRole.CLIENT, nullable=False, index=True)
    
    plan_tier = Column(Enum(PlanTier), default=PlanTier.STARTER, nullable=False)
    subscription_status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL, nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    last_login_ip = Column(String, nullable=True)
    last_known_city = Column(String, nullable=True)
    last_known_country = Column(String, nullable=True)

    # --- Business & Usage Limits (Tier 2) ---
    monthly_ai_messages = Column(Integer, default=0, nullable=False)

    # Security: OTP is encrypted at rest
    _otp_encrypted = Column("otp_code", String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)

    business_name = Column(String, nullable=True)
    business_type = Column(String, nullable=True) 
    assigned_phone_number = Column(String, unique=True, index=True, nullable=True)
    personal_whatsapp = Column(String, nullable=True) 
    
    # NEW: Partner/Agency specific fields
    agency_name = Column(String, nullable=True)
    
    # NEW: Self-referential relationship (Map Clients to their Partner)
    partner_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    partner = relationship("User", remote_side=[id], backref="managed_clients")
    
    openai_api_key = Column(String, nullable=True)

    # Relationships with Cascade Delete (GDPR: Delete user = Delete all their data)
    leads = relationship("Lead", back_populates="user", cascade="all, delete-orphan")
    media_files = relationship("MediaInteraction", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    business_profile = relationship("BusinessProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    ai_agent = relationship("AIAgent", uselist=False, back_populates="user", cascade="all, delete-orphan")
    phone_numbers = relationship("PhoneNumber", back_populates="owner", cascade="all, delete-orphan")
    coaching_sessions = relationship("CoachingSession", back_populates="user", cascade="all, delete-orphan")
    tags = relationship("Tag", back_populates="user", cascade="all, delete-orphan")

    @property
    def otp_code(self):
        return protector.decrypt(self._otp_encrypted) if self._otp_encrypted else None
    
    @otp_code.setter
    def otp_code(self, value):
        self._otp_encrypted = protector.encrypt(value) if value else None

# ... (rest of the file remains exactly the same: Tag, PhoneNumber, BusinessProfile, AIAgent, Lead, Message, WebhookDLQ, MediaInteraction, Integration, CoachingSession) ...

class Tag(Base):
    __tablename__ = "tags"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="tags")
    leads = relationship("Lead", secondary=lead_tag_association, back_populates="tags")


class PhoneNumber(Base):
    __tablename__ = "phone_numbers"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    number = Column(String, unique=True, index=True, nullable=False)
    country_code = Column(String, default="IL")
    provider = Column(String, default="twilio")
    provider_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    
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
    
    summary_template = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="business_profile")


class AIAgent(Base):
    __tablename__ = "ai_agents"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    system_prompt = Column(Text, nullable=True)
    voice_id = Column(String, default="default_voice_1")
    language = Column(String, default="he-IL")
    phone_number_id = Column(GUID(), ForeignKey("phone_numbers.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="ai_agent")
    phone_number = relationship("PhoneNumber")


class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    idempotency_key = Column(String, index=True, nullable=True)
    
    name = Column(String, nullable=True)
    phone_number = Column(String, index=True, nullable=True)
    email = Column(String, index=True, nullable=True)
    city = Column(String, nullable=True)
    
    source = Column(Enum(LeadSource), default=LeadSource.MANUAL, nullable=False)
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW, nullable=False, index=True)

    bot_active = Column(Boolean, default=True, nullable=False)
    requires_human = Column(Boolean, default=False, nullable=False, index=True)
    
    transcription_summary = Column(Text, nullable=True)
    original_transcript = Column(Text, nullable=True)
    coach_feedback = Column(Text, nullable=True)
    suggested_reply = Column(Text, nullable=True)
    
    needs_followup = Column(Boolean, default=False, index=True)
    followup_date = Column(DateTime(timezone=True), nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    ai_rating = Column(Integer, nullable=True)
    ai_feedback_note = Column(Text, nullable=True) 

    user = relationship("User", back_populates="leads")
    media_files = relationship("MediaInteraction", back_populates="lead")
    sessions = relationship("CoachingSession", back_populates="lead")
    messages = relationship("Message", back_populates="lead", cascade="all, delete-orphan", order_by="Message.created_at")
    tags = relationship("Tag", secondary=lead_tag_association, back_populates="leads")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(GUID(), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type = Column(String(10), nullable=False) 
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    lead = relationship("Lead", back_populates="messages")


class WebhookDLQ(Base):
    __tablename__ = "webhook_dlq"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    provider = Column(Enum(WebhookProvider), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    error_reason = Column(Text, nullable=True)
    
    is_resolved = Column(Boolean, default=False, index=True)
    retry_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MediaInteraction(Base):
    __tablename__ = "media_interactions"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(GUID(), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    
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
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    platform_name = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    webhook_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="integrations")


class CoachingSession(Base):
    __tablename__ = "coaching_sessions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(GUID(), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    
    audio_file_path = Column(String, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.QUEUED, index=True)
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    user = relationship("User", back_populates="coaching_sessions")
    lead = relationship("Lead", back_populates="sessions")