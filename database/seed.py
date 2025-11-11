"""
Database seeding script
Create initial data for development and testing
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import (
    db, User, Job, Message, Checklist, Material,
    Shipment, Subscription, AIConversation, Reminder,
    JobStatus, MessageSource, MessageDirection, UserRole
)

def seed_database():
    """Seed the database with sample data"""

    # Sample users
    users = [
        User(
            email="demo@roofingbusiness.com",
            name="Demo Roofing Company",
            company_name="Demo Roofing Co.",
            phone="+1-555-0123",
            role=UserRole.OWNER,
            subscription_plan="yearly",
            firebase_uid="demo_firebase_uid",
            is_active=True
        ),
        User(
            email="worker@roofingbusiness.com",
            name="John Worker",
            company_name="Demo Roofing Co.",
            phone="+1-555-0124",
            role=UserRole.WORKER,
            subscription_plan="yearly",
            firebase_uid="worker_firebase_uid",
            is_active=True
        )
    ]

    # Sample jobs
    jobs = [
        Job(
            customer_name="Alice Johnson",
            customer_email="alice@example.com",
            customer_phone="+1-555-0101",
            job_address="123 Maple St, Springfield, IL 62701",
            job_type="roof_replacement",
            scheduled_start=datetime.now(timezone.utc) + timedelta(days=1),
            scheduled_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
            status=JobStatus.SCHEDULED,
            estimated_price=8500.00,
            notes="Full roof replacement with architectural shingles"
        ),
        Job(
            customer_name="Bob Smith",
            customer_email="bob@example.com",
            customer_phone="+1-555-0102",
            job_address="456 Oak Ave, Springfield, IL 62702",
            job_type="leak_repair",
            scheduled_start=datetime.now(timezone.utc) + timedelta(days=2),
            scheduled_end=datetime.now(timezone.utc) + timedelta(days=2, hours=4),
            status=JobStatus.SCHEDULED,
            estimated_price=1200.00,
            notes="Kitchen ceiling leak repair"
        ),
        Job(
            customer_name="Carol Davis",
            customer_email="carol@example.com",
            customer_phone="+1-555-0103",
            job_address="789 Pine Rd, Springfield, IL 62703",
            job_type="roof_inspection",
            scheduled_start=datetime.now(timezone.utc) + timedelta(days=3),
            scheduled_end=datetime.now(timezone.utc) + timedelta(days=3, hours=2),
            status=JobStatus.COMPLETED,
            estimated_price=300.00,
            actual_price=300.00,
            notes="Annual roof inspection and maintenance report"
        )
    ]

    # Sample messages
    messages = [
        Message(
            job_id=1,  # Alice Johnson's job
            source=MessageSource.EMAIL,
            sender_info="alice@example.com",
            content="Hi, I'd like to get a quote for a roof replacement. My current roof is about 20 years old and showing signs of wear.",
            direction=MessageDirection.INBOUND,
            category="leads"
        ),
        Message(
            job_id=1,
            source=MessageSource.EMAIL,
            sender_info="demo@roofingbusiness.com",
            content="Thank you for your interest! I'd be happy to provide a quote. Can you tell me approximately how many square feet your roof is?",
            direction=MessageDirection.OUTBOUND,
            category="conversation"
        ),
        Message(
            job_id=2,  # Bob Smith's job
            source=MessageSource.SMS,
            sender_info="+1-555-0102",
            content="We have a leak in our kitchen ceiling that seems to be coming from the roof. Can you help?",
            direction=MessageDirection.INBOUND,
            category="questions"
        ),
        Message(
            job_id=3,  # Carol Davis's job
            source=MessageSource.APP,
            sender_info="worker@roofingbusiness.com",
            content="Inspection completed. Found some minor wear on the north side but overall good condition. Provided maintenance recommendations to the homeowner.",
            direction=MessageDirection.OUTBOUND,
            category="job_updates"
        )
    ]

    # Sample checklists
    checklists = []
    checklist_templates = {
        'roof_replacement': [
            'Remove old roofing materials',
            'Inspect and repair decking',
            'Install new underlayment',
            'Install drip edge',
            'Install new shingles',
            'Install ridge cap shingles',
            'Install new flashing',
            'Clean up debris',
            'Final inspection'
        ],
        'leak_repair': [
            'Locate source of leak',
            'Remove damaged shingles',
            'Inspect underlying decking',
            'Replace damaged decking',
            'Install new underlayment',
            'Install new shingles',
            'Apply sealant around flashing',
            'Test for water tightness'
        ],
        'roof_inspection': [
            'Exterior roof inspection',
            'Check for missing or damaged shingles',
            'Inspect flashing around vents and chimneys',
            'Check gutters and downspouts',
            'Inspect attic for water damage',
            'Document photos of problem areas',
            'Create detailed inspection report'
        ]
    }

    for job in jobs:
        template_name = job.job_type
        if template_name in checklist_templates:
            for index, item_text in enumerate(checklist_templates[template_name]):
                checklist = Checklist(
                    job_id=job.id,
                    template_name=template_name,
                    item_text=item_text,
                    is_completed=(job.status == JobStatus.COMPLETED),
                    completed_at=datetime.now(timezone.utc) if job.status == JobStatus.COMPLETED else None,
                    order_index=index
                )
                checklists.append(checklist)

    # Sample materials
    materials = [
        Material(
            material_name="Architectural Shingles",
            supplier="Home Depot",
            current_stock=5000,
            minimum_stock=1000,
            unit_price=0.85,
            unit_type="sq ft",
            auto_order_enabled=True
        ),
        Material(
            material_name="Roofing Underlayment",
            supplier="Lowes",
            current_stock=200,
            minimum_stock=50,
            unit_price=0.25,
            unit_type="sq ft",
            auto_order_enabled=True
        ),
        Material(
            material_name="Roofing Nails",
            supplier="Home Depot",
            current_stock=10000,
            minimum_stock=2000,
            unit_price=0.02,
            unit_type="each",
            auto_order_enabled=True
        ),
        Material(
            material_name="Roofing Cement",
            supplier="Lowes",
            current_stock=50,
            minimum_stock=10,
            unit_price=12.99,
            unit_type="tube",
            auto_order_enabled=False
        )
    ]

    # Sample shipments
    shipments = [
        Shipment(
            material_id=1,  # Architectural Shingles
            supplier="Home Depot",
            quantity=2000,
            tracking_number="1Z999AA10123456784",
            expected_delivery=datetime.now(timezone.utc) + timedelta(days=3),
            status="shipped"
        ),
        Shipment(
            material_id=2,  # Roofing Underlayment
            supplier="Lowes",
            quantity=100,
            tracking_number="1Z999AA10123456785",
            expected_delivery=datetime.now(timezone.utc) + timedelta(days=2),
            status="delivered",
            actual_delivery=datetime.now(timezone.utc) - timedelta(days=1)
        )
    ]

    # Sample subscriptions
    subscriptions = [
        Subscription(
            user_id=1,  # Demo user
            plan_type="yearly",
            status="active",
            current_period_start=datetime.now(timezone.utc) - timedelta(days=30),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=335),
            stripe_subscription_id="sub_demo_yearly"
        )
    ]

    # Sample AI conversations
    ai_conversations = [
        AIConversation(
            user_id=1,
            session_id="session_1",
            message_type="user_query",
            content="What's the best way to schedule multiple jobs in one day?"
        ),
        AIConversation(
            user_id=1,
            session_id="session_1",
            message_type="ai_response",
            content="For scheduling multiple jobs in one day, consider: 1) Group jobs by location to minimize travel time, 2) Buffer 30-60 minutes between jobs for unexpected delays, 3) Check weather forecasts, 4) Schedule longer/more complex jobs earlier in the day."
        )
    ]

    # Sample reminders
    reminders = [
        Reminder(
            job_id=1,  # Alice Johnson's job
            reminder_type="sms",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=20),
            recipient="+1-555-0101",
            message_content="Reminder: Your roof replacement is scheduled for tomorrow at 8:00 AM. We'll see you at 123 Maple St!",
            status="pending"
        ),
        Reminder(
            job_id=1,
            reminder_type="email",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=22),
            recipient="alice@example.com",
            message_content="Reminder: Your roof replacement is scheduled for tomorrow at 8:00 AM at 123 Maple St. Please ensure the area is accessible.",
            status="pending"
        )
    ]

    # Add all data to database
    try:
        # Add users
        for user in users:
            db.session.add(user)
        db.session.flush()  # Get user IDs

        # Assign jobs to first user
        for job in jobs:
            job.user_id = 1
            db.session.add(job)
        db.session.flush()  # Get job IDs

        # Add messages
        for message in messages:
            db.session.add(message)

        # Add checklists
        for checklist in checklists:
            db.session.add(checklist)

        # Add materials
        for material in materials:
            material.user_id = 1
            db.session.add(material)
        db.session.flush()  # Get material IDs

        # Add shipments
        for shipment in shipments:
            shipment.user_id = 1
            db.session.add(shipment)

        # Add subscriptions
        for subscription in subscriptions:
            db.session.add(subscription)

        # Add AI conversations
        for conversation in ai_conversations:
            db.session.add(conversation)

        # Add reminders
        for reminder in reminders:
            db.session.add(reminder)

        # Commit everything
        db.session.commit()

        print("Database seeded successfully!")
        print(f"Created {len(users)} users")
        print(f"Created {len(jobs)} jobs")
        print(f"Created {len(messages)} messages")
        print(f"Created {len(checklists)} checklist items")
        print(f"Created {len(materials)} materials")
        print(f"Created {len(shipments)} shipments")
        print(f"Created {len(subscriptions)} subscriptions")
        print(f"Created {len(ai_conversations)} AI conversations")
        print(f"Created {len(reminders)} reminders")

    except Exception as e:
        db.session.rollback()
        print(f"Error seeding database: {e}")
        raise

if __name__ == "__main__":
    # Set up database connection
    database_url = os.getenv('DATABASE_URL', 'postgresql://username:password@localhost:5432/roofing_db')

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Bind the session to the models
    db.session = session

    try:
        seed_database()
    finally:
        session.close()