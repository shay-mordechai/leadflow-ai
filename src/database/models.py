# src/database/models.py

from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid
from src.security.encryption import protector

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    whatsapp_number = Column(String, unique=True, index=True, nullable=True)
    personal_whatsapp = Column(String, nullable=False)
    requires_new_number = Column(Boolean, default=False)
    city_coverage = Column(String, nullable=True)
    business_type = Column(String, nullable=False, default="General Business")
    api_key_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Lead(Base):
    __tablename__ = "leads"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"))

    _name_encrypted = Column("name", String, nullable=True)
    _phone_encrypted = Column("phone_number", String, nullable=True)

    city = Column(String, nullable=True)
    status = Column(String, default="NEW")
    created_at = Column(DateTime, default=datetime.utcnow)

    summary_text = Column(Text, nullable=True)
    coach_feedback = Column(Text, nullable=True)

    # --- NEW RETENTION FEATURES ---
    # Task 1: AI Suggested Reply
    suggested_reply = Column(Text, nullable=True)

    # Task 2: Follow-up System
    needs_followup = Column(Boolean, default=False)
    followup_date = Column(DateTime, nullable=True)

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

class TimeSlot(Base):
    """
    Task 4: Smart Calendar System.
    Stores available slots defined by the Coach.
    """
    __tablename__ = "time_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), index=True)

    # The start time of the slot (e.g., 2026-01-15 10:00:00)
    start_time = Column(DateTime, nullable=False, index=True)

    # If not null, the slot is booked by this lead
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)

    # Helper to quickly check status without joining
    is_booked = Column(Boolean, default=False)

class CoachingSession(Base):
    __tablename__ = "coaching_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    session_date = Column(DateTime, default=datetime.utcnow)
    audio_file_path = Column(String, nullable=True)
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String, default="processing")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    ip_address = Column(String(45), nullable=True)
    action = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    severity = Column(String(20), default="INFO")
