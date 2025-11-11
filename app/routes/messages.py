"""
Message Hub Routes
Unified communication handling for SMS, email, WhatsApp, and in-app messages
"""

import os
import re
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import imaplib
import email
from email.header import decode_header

from app.models import db, Message, Job, User, MessageSource, MessageDirection

bp = Blueprint('messages', __name__)

# Initialize Twilio client
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)
twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')

# Initialize SendGrid client
sendgrid_client = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))

@bp.route('/', methods=['GET'])
@jwt_required()
def get_messages():
    """Get all messages for the current user"""
    try:
        current_user_id = get_jwt_identity()

        # Query parameters
        source = request.args.get('source')  # sms, email, whatsapp, app
        job_id = request.args.get('job_id')
        category = request.args.get('category')
        is_read = request.args.get('is_read')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        # Get jobs for the current user to filter messages
        user_job_ids = [job.id for job in Job.query.filter_by(user_id=current_user_id).all()]

        query = Message.query.filter(Message.job_id.in_(user_job_ids))

        if source:
            try:
                msg_source = MessageSource(source.lower())
                query = query.filter(Message.source == msg_source)
            except ValueError:
                return jsonify({'error': 'Invalid source value'}), 400

        if job_id:
            query = query.filter(Message.job_id == job_id)

        if category:
            query = query.filter(Message.category == category)

        if is_read is not None:
            query = query.filter(Message.is_read == (is_read.lower() == 'true'))

        messages = query.order_by(Message.created_at.desc()).offset(offset).limit(limit).all()

        return jsonify({
            'messages': [
                {
                    'id': str(msg.id),
                    'job_id': str(msg.job_id),
                    'source': msg.source.value,
                    'sender_info': msg.sender_info,
                    'content': msg.content,
                    'direction': msg.direction.value,
                    'is_read': msg.is_read,
                    'category': msg.category,
                    'created_at': msg.created_at.isoformat()
                }
                for msg in messages
            ]
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch messages: {str(e)}'}), 500

@bp.route('/', methods=['POST'])
@jwt_required()
def send_message():
    """Send a message via specified channel"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        # Validate required fields
        if not data.get('content'):
            return jsonify({'error': 'Message content is required'}), 400

        if not data.get('job_id'):
            return jsonify({'error': 'Job ID is required'}), 400

        # Verify job belongs to user
        job = Job.query.filter_by(id=data['job_id'], user_id=current_user_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        source = data.get('source', 'app').lower()
        recipient = data.get('recipient')
        content = data['content']

        # Determine recipient based on source if not provided
        if not recipient:
            if source == 'sms':
                recipient = job.customer_phone
            elif source == 'email':
                recipient = job.customer_email
            elif source == 'whatsapp':
                recipient = job.customer_phone  # WhatsApp uses phone numbers

        if not recipient:
            return jsonify({'error': 'Recipient is required for this message type'}), 400

        # Categorize message
        category = categorize_message(content, source, job)

        # Send message based on source
        message_sent = False
        error_message = None

        try:
            if source == 'sms':
                message_sent = send_sms(recipient, content)
            elif source == 'email':
                message_sent = send_email(recipient, content, f"Message regarding your roofing job")
            elif source == 'whatsapp':
                message_sent = send_whatsapp(recipient, content)
            elif source == 'app':
                message_sent = True  # In-app messages are stored locally
            else:
                return jsonify({'error': 'Invalid message source'}), 400

            if not message_sent:
                return jsonify({'error': error_message or 'Failed to send message'}), 500

        except Exception as send_error:
            return jsonify({'error': f'Failed to send {source} message: {str(send_error)}'}), 500

        # Create message record
        message = Message(
            job_id=job.id,
            source=MessageSource(source),
            sender_info=current_app.config.get('COMPANY_PHONE', 'system'),
            content=content,
            direction=MessageDirection.OUTBOUND,
            category=category
        )

        db.session.add(message)
        db.session.commit()

        return jsonify({
            'message': 'Message sent successfully',
            'sent_message': {
                'id': str(message.id),
                'source': message.source.value,
                'recipient': recipient,
                'content': message.content,
                'category': message.category,
                'created_at': message.created_at.isoformat()
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to send message: {str(e)}'}), 500

@bp.route('/<message_id>/read', methods=['PUT'])
@jwt_required()
def mark_message_read(message_id):
    """Mark a message as read"""
    try:
        current_user_id = get_jwt_identity()

        # Get user's job IDs to verify message ownership
        user_job_ids = [job.id for job in Job.query.filter_by(user_id=current_user_id).all()]

        message = Message.query.filter(
            Message.id == message_id,
            Message.job_id.in_(user_job_ids)
        ).first()

        if not message:
            return jsonify({'error': 'Message not found'}), 404

        message.is_read = True
        db.session.commit()

        return jsonify({'message': 'Message marked as read'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to mark message as read: {str(e)}'}), 500

@bp.route('/sync-email', methods=['POST'])
@jwt_required()
def sync_email():
    """Sync emails from user's email account"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        email_address = data.get('email_address')
        email_password = data.get('password')  # In production, use OAuth2 instead

        if not email_address or not email_password:
            return jsonify({'error': 'Email address and password are required'}), 400

        # Connect to email server
        imap_server = data.get('imap_server', 'imap.gmail.com')
        imap_port = int(data.get('imap_port', 993))

        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail.login(email_address, email_password)

        # Select inbox
        mail.select('inbox')

        # Search for recent emails (last 7 days)
        date_since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%d-%b-%Y')
        search_criteria = f'(SINCE {date_since})'

        status, messages = mail.search(None, search_criteria)
        if status != 'OK':
            return jsonify({'error': 'Failed to search emails'}), 500

        # Process emails
        email_ids = messages[0].split()
        synced_count = 0

        for email_id in email_ids[-50:]:  # Limit to last 50 emails
            try:
                status, msg_data = mail.fetch(email_id, '(RFC822)')

                if status == 'OK':
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Extract email details
                    subject = decode_header(msg["Subject"])[0][0]
                    if isinstance(subject, bytes):
                        subject = subject.decode()

                    sender = msg.get("From", "")
                    date_str = msg.get("Date", "")

                    # Parse email date
                    try:
                        email_date = email.utils.parsedate_to_datetime(date_str)
                        if email_date.tzinfo is None:
                            email_date = email_date.replace(tzinfo=timezone.utc)
                    except:
                        email_date = datetime.now(timezone.utc)

                    # Extract email body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = msg.get_payload(decode=True).decode()

                    # Try to find related job by email address
                    sender_email = re.search(r'<(.+?)>', sender)
                    if sender_email:
                        sender_email = sender_email.group(1)

                    job = Job.query.filter_by(customer_email=sender_email, user_id=current_user_id).first()

                    if job:
                        # Categorize email
                        category = categorize_email(subject, body)

                        # Check if email already exists
                        existing_message = Message.query.filter_by(
                            job_id=job.id,
                            source=MessageSource.EMAIL,
                            sender_info=sender_email,
                            created_at=email_date
                        ).first()

                        if not existing_message:
                            # Create message record
                            message = Message(
                                job_id=job.id,
                                source=MessageSource.EMAIL,
                                sender_info=sender_email,
                                content=f"Subject: {subject}\\n\\n{body}",
                                direction=MessageDirection.INBOUND,
                                category=category,
                                created_at=email_date
                            )

                            db.session.add(message)
                            synced_count += 1

            except Exception as email_error:
                current_app.logger.error(f"Error processing email {email_id}: {email_error}")
                continue

        db.session.commit()
        mail.logout()

        return jsonify({
            'message': f'Synced {synced_count} emails successfully',
            'synced_count': synced_count
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Email sync failed: {str(e)}'}), 500

@bp.route('/templates', methods=['GET'])
@jwt_required()
def get_message_templates():
    """Get message templates for quick replies"""
    try:
        templates = {
            'quotes': [
                "Thank you for your interest in our roofing services. We'll provide you with a detailed quote within 24 hours.",
                "Based on our inspection, the estimated cost for your roofing project is $X. This includes materials and labor.",
                "Your quote is ready! Please let us know if you have any questions or would like to schedule the work."
            ],
            'scheduling': [
                "We have availability on [date] for your roofing project. Does this work for you?",
                "Your job is scheduled for [date] at [time]. We'll see you then!",
                "Due to weather conditions, we need to reschedule your job. Are you available on [new date]?"
            ],
            'updates': [
                "We're starting work on your roof today. We expect to complete it by [end_time].",
                "Your roofing project is progressing well. We'll send photos once we reach the halfway point.",
                "We've completed your roofing project! Final inspection and cleanup are underway."
            ],
            'follow_up': [
                "Just checking in to see how you're satisfied with your new roof. Please let us know if you have any concerns.",
                "Your warranty information is attached. Keep this for your records.",
                "We'd appreciate your feedback on our services. Your review helps other homeowners make informed decisions."
            ]
        }

        return jsonify({'templates': templates})

    except Exception as e:
        return jsonify({'error': f'Failed to fetch templates: {str(e)}'}), 500

# Helper functions
def send_sms(phone_number, message):
    """Send SMS message via Twilio"""
    try:
        message = twilio_client.messages.create(
            body=message,
            from_=twilio_phone_number,
            to=phone_number
        )
        return True
    except Exception as e:
        current_app.logger.error(f"Twilio SMS error: {e}")
        return False

def send_email(to_email, subject, content):
    """Send email via SendGrid"""
    try:
        message = Mail(
            from_email=os.getenv('FROM_EMAIL', 'noreply@roofingbusiness.com'),
            to_emails=to_email,
            subject=subject,
            html_content=f'<p>{content.replace(chr(10), "<br>")}</p>'
        )

        response = sendgrid_client.send(message)
        return response.status_code == 202
    except Exception as e:
        current_app.logger.error(f"SendGrid error: {e}")
        return False

def send_whatsapp(phone_number, message):
    """Send WhatsApp message via Twilio WhatsApp API"""
    try:
        twilio_whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')
        message = twilio_client.messages.create(
            body=message,
            from_=f'whatsapp:{twilio_whatsapp_number}',
            to=f'whatsapp:{phone_number}'
        )
        return True
    except Exception as e:
        current_app.logger.error(f"Twilio WhatsApp error: {e}")
        return False

def categorize_message(content, source, job):
    """Categorize message based on content and context"""
    content_lower = content.lower()

    # Quote-related keywords
    if any(word in content_lower for word in ['quote', 'estimate', 'price', 'cost', 'how much']):
        return 'quotes'

    # Scheduling keywords
    elif any(word in content_lower for word in ['schedule', 'appointment', 'when', 'date', 'time']):
        return 'scheduling'

    # Question keywords
    elif any(word in content_lower for word in ['question', 'how', 'what', 'why', 'help']):
        return 'questions'

    # Job updates
    elif any(word in content_lower for word in ['progress', 'update', 'status', 'complete', 'finish']):
        return 'job_updates'

    # Lead generation
    elif any(word in content_lower for word in ['interested', 'need', 'looking for', 'service']):
        return 'leads'

    # Default category
    else:
        return 'general'

def categorize_email(subject, body):
    """Categorize email based on subject and body"""
    subject_lower = (subject or '').lower()
    body_lower = (body or '').lower()
    combined_text = f"{subject_lower} {body_lower}"

    # Similar logic to categorize_message but optimized for email patterns
    if any(word in combined_text for word in ['re:', 'fwd:', 'reply']):
        return 'conversation'
    elif any(word in combined_text for word in ['quote', 'estimate', 'proposal']):
        return 'quotes'
    elif any(word in combined_text for word in ['invoice', 'payment', 'bill']):
        return 'billing'
    else:
        return categorize_message(combined_text, 'email', None)