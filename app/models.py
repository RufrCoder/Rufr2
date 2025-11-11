"""
Database Models for Roofing Business Management App
"""

from datetime import datetime, timezone
from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
import uuid

db = SQLAlchemy()

class UserRole(Enum):
    OWNER = "owner"
    WORKER = "worker"
    ADMIN = "admin"

class JobStatus(Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class MessageSource(Enum):
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    APP = "app"

class MessageDirection(Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

# User Model
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.OWNER)
    phone = db.Column(db.String(20))
    company_name = db.Column(db.String(255))
    subscription_plan = db.Column(db.String(50), default='trial')
    firebase_uid = db.Column(db.String(128), unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    jobs = db.relationship('Job', backref='user', lazy=True, cascade='all, delete-orphan')
    materials = db.relationship('Material', backref='user', lazy=True, cascade='all, delete-orphan')

# Job Model
class Job(db.Model):
    __tablename__ = 'jobs'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    customer_name = db.Column(db.String(255), nullable=False)
    customer_email = db.Column(db.String(255))
    customer_phone = db.Column(db.String(20))
    job_address = db.Column(db.Text, nullable=False)
    job_type = db.Column(db.String(100), nullable=False)  # inspection, repair, replacement, etc.
    scheduled_start = db.Column(db.DateTime, nullable=False)
    scheduled_end = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum(JobStatus), default=JobStatus.SCHEDULED)
    estimated_price = db.Column(db.Numeric(10, 2))
    actual_price = db.Column(db.Numeric(10, 2))
    notes = db.Column(db.Text)
    google_calendar_event_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    messages = db.relationship('Message', backref='job', lazy=True, cascade='all, delete-orphan')
    checklists = db.relationship('Checklist', backref='job', lazy=True, cascade='all, delete-orphan')

# Message Model
class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = db.Column(UUID(as_uuid=True), db.ForeignKey('jobs.id'), nullable=False)
    source = db.Column(db.Enum(MessageSource), nullable=False)
    sender_info = db.Column(db.String(255))  # phone number, email, etc.
    content = db.Column(db.Text, nullable=False)
    direction = db.Column(db.Enum(MessageDirection), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(100))  # leads, quotes, job_updates, questions
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# Checklist Model
class Checklist(db.Model):
    __tablename__ = 'checklists'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = db.Column(UUID(as_uuid=True), db.ForeignKey('jobs.id'), nullable=False)
    template_name = db.Column(db.String(100), nullable=False)
    item_text = db.Column(db.String(255), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    assigned_worker_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    photo_url = db.Column(db.String(500))
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship for assigned worker
    assigned_worker = db.relationship('User', foreign_keys=[assigned_worker_id])

# Material Model
class Material(db.Model):
    __tablename__ = 'materials'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    material_name = db.Column(db.String(255), nullable=False)
    supplier = db.Column(db.String(255))
    current_stock = db.Column(db.Integer, default=0)
    minimum_stock = db.Column(db.Integer, default=10)
    unit_price = db.Column(db.Numeric(10, 2))
    unit_type = db.Column(db.String(50))  # sqft, linear ft, pieces, etc.
    last_ordered_at = db.Column(db.DateTime)
    auto_order_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# Shipment Model
class Shipment(db.Model):
    __tablename__ = 'shipments'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    material_id = db.Column(UUID(as_uuid=True), db.ForeignKey('materials.id'), nullable=False)
    tracking_number = db.Column(db.String(100))
    supplier = db.Column(db.String(255))
    quantity = db.Column(db.Integer, nullable=False)
    expected_delivery = db.Column(db.DateTime)
    actual_delivery = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='ordered')  # ordered, shipped, delivered, cancelled
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    material = db.relationship('Material', backref='shipments')

# Subscription Model
class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String(255))
    plan_type = db.Column(db.String(50), nullable=False)  # monthly, yearly, lifetime
    status = db.Column(db.String(50), default='active')  # active, cancelled, past_due
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# AI Conversation Model
class AIConversation(db.Model):
    __tablename__ = 'ai_conversations'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String(255), nullable=False)
    message_type = db.Column(db.String(50))  # user_query, ai_response, system_action
    content = db.Column(db.Text, nullable=False)
    context = db.Column(db.JSON)  # Additional context about the conversation
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# Reminder Model
class Reminder(db.Model):
    __tablename__ = 'reminders'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = db.Column(UUID(as_uuid=True), db.ForeignKey('jobs.id'), nullable=False)
    reminder_type = db.Column(db.String(50), nullable=False)  # sms, email
    scheduled_for = db.Column(db.DateTime, nullable=False)
    sent_at = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='pending')  # pending, sent, failed
    recipient = db.Column(db.String(255), nullable=False)  # email or phone number
    message_content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))