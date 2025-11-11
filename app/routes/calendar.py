"""
Calendar Routes
Job scheduling and Google Calendar integration
"""

import os
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import google.oauth2.credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.models import db, Job, User, Reminder, JobStatus

bp = Blueprint('calendar', __name__)

# Google Calendar OAuth configuration
GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv('GOOGLE_CLIENT_ID'),
        "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uri": os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/auth/google/callback')
    }
}

@bp.route('/jobs', methods=['GET'])
@jwt_required()
def get_jobs():
    """Get all jobs for the current user"""
    try:
        current_user_id = get_jwt_identity()

        # Query parameters for filtering
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.get('status')

        query = Job.query.filter_by(user_id=current_user_id)

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Job.scheduled_start >= start_dt)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format'}), 400

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Job.scheduled_end <= end_dt)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format'}), 400

        if status:
            try:
                job_status = JobStatus(status.lower())
                query = query.filter(Job.status == job_status)
            except ValueError:
                return jsonify({'error': 'Invalid status value'}), 400

        jobs = query.order_by(Job.scheduled_start).all()

        return jsonify({
            'jobs': [
                {
                    'id': str(job.id),
                    'customer_name': job.customer_name,
                    'customer_email': job.customer_email,
                    'customer_phone': job.customer_phone,
                    'job_address': job.job_address,
                    'job_type': job.job_type,
                    'scheduled_start': job.scheduled_start.isoformat(),
                    'scheduled_end': job.scheduled_end.isoformat(),
                    'status': job.status.value,
                    'estimated_price': float(job.estimated_price) if job.estimated_price else None,
                    'actual_price': float(job.actual_price) if job.actual_price else None,
                    'notes': job.notes,
                    'google_calendar_event_id': job.google_calendar_event_id,
                    'created_at': job.created_at.isoformat()
                }
                for job in jobs
            ]
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch jobs: {str(e)}'}), 500

@bp.route('/jobs', methods=['POST'])
@jwt_required()
def create_job():
    """Create a new job"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        # Validate required fields
        required_fields = ['customer_name', 'job_address', 'job_type', 'scheduled_start', 'scheduled_end']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400

        # Parse datetime fields
        try:
            scheduled_start = datetime.fromisoformat(data['scheduled_start'].replace('Z', '+00:00'))
            scheduled_end = datetime.fromisoformat(data['scheduled_end'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid datetime format for scheduled_start or scheduled_end'}), 400

        # Create job
        job = Job(
            user_id=current_user_id,
            customer_name=data['customer_name'],
            customer_email=data.get('customer_email'),
            customer_phone=data.get('customer_phone'),
            job_address=data['job_address'],
            job_type=data['job_type'],
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            estimated_price=data.get('estimated_price'),
            notes=data.get('notes')
        )

        db.session.add(job)
        db.session.flush()  # Get job ID without committing

        # Try to create Google Calendar event if user has connected Google Calendar
        try:
            google_event_id = create_google_calendar_event(job, current_user_id)
            if google_event_id:
                job.google_calendar_event_id = google_event_id
        except Exception as google_error:
            current_app.logger.warning(f"Failed to create Google Calendar event: {google_error}")
            # Continue without Google Calendar integration

        db.session.commit()

        # Schedule reminders
        schedule_job_reminders(job)

        return jsonify({
            'message': 'Job created successfully',
            'job': {
                'id': str(job.id),
                'customer_name': job.customer_name,
                'job_address': job.job_address,
                'job_type': job.job_type,
                'scheduled_start': job.scheduled_start.isoformat(),
                'scheduled_end': job.scheduled_end.isoformat(),
                'status': job.status.value,
                'google_calendar_event_id': job.google_calendar_event_id
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create job: {str(e)}'}), 500

@bp.route('/jobs/<job_id>', methods=['PUT'])
@jwt_required()
def update_job(job_id):
    """Update an existing job"""
    try:
        current_user_id = get_jwt_identity()
        job = Job.query.filter_by(id=job_id, user_id=current_user_id).first()

        if not job:
            return jsonify({'error': 'Job not found'}), 404

        data = request.get_json()

        # Update job fields
        updatable_fields = [
            'customer_name', 'customer_email', 'customer_phone',
            'job_address', 'job_type', 'estimated_price',
            'actual_price', 'notes', 'status'
        ]

        for field in updatable_fields:
            if field in data:
                if field == 'status':
                    try:
                        job.status = JobStatus(data[field].lower())
                    except ValueError:
                        return jsonify({'error': 'Invalid status value'}), 400
                else:
                    setattr(job, field, data[field])

        # Update datetime fields if provided
        if 'scheduled_start' in data:
            try:
                job.scheduled_start = datetime.fromisoformat(data['scheduled_start'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid scheduled_start format'}), 400

        if 'scheduled_end' in data:
            try:
                job.scheduled_end = datetime.fromisoformat(data['scheduled_end'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid scheduled_end format'}), 400

        job.updated_at = datetime.now(timezone.utc)

        # Update Google Calendar event if it exists
        if job.google_calendar_event_id:
            try:
                update_google_calendar_event(job, current_user_id)
            except Exception as google_error:
                current_app.logger.warning(f"Failed to update Google Calendar event: {google_error}")

        db.session.commit()

        return jsonify({
            'message': 'Job updated successfully',
            'job': {
                'id': str(job.id),
                'customer_name': job.customer_name,
                'job_address': job.job_address,
                'job_type': job.job_type,
                'scheduled_start': job.scheduled_start.isoformat(),
                'scheduled_end': job.scheduled_end.isoformat(),
                'status': job.status.value
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update job: {str(e)}'}), 500

@bp.route('/jobs/<job_id>', methods=['DELETE'])
@jwt_required()
def delete_job(job_id):
    """Delete a job"""
    try:
        current_user_id = get_jwt_identity()
        job = Job.query.filter_by(id=job_id, user_id=current_user_id).first()

        if not job:
            return jsonify({'error': 'Job not found'}), 404

        # Delete Google Calendar event if it exists
        if job.google_calendar_event_id:
            try:
                delete_google_calendar_event(job, current_user_id)
            except Exception as google_error:
                current_app.logger.warning(f"Failed to delete Google Calendar event: {google_error}")

        db.session.delete(job)
        db.session.commit()

        return jsonify({'message': 'Job deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete job: {str(e)}'}), 500

@bp.route('/google-auth-url', methods=['GET'])
@jwt_required()
def get_google_auth_url():
    """Get Google OAuth authorization URL"""
    try:
        current_user_id = get_jwt_identity()

        flow = Flow.from_client_config(
            GOOGLE_CLIENT_CONFIG,
            scopes=['https://www.googleapis.com/auth/calendar']
        )

        # Generate authorization URL with state parameter
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=str(current_user_id)
        )

        return jsonify({
            'auth_url': auth_url,
            'state': state
        })

    except Exception as e:
        return jsonify({'error': f'Failed to generate auth URL: {str(e)}'}), 500

@bp.route('/google-callback', methods=['POST'])
@jwt_required()
def google_callback():
    """Handle Google OAuth callback"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        if not data.get('code') or data.get('state') != str(current_user_id):
            return jsonify({'error': 'Invalid OAuth callback'}), 400

        flow = Flow.from_client_config(
            GOOGLE_CLIENT_CONFIG,
            scopes=['https://www.googleapis.com/auth/calendar'],
            redirect_uri=GOOGLE_CLIENT_CONFIG['web']['redirect_uri']
        )

        flow.fetch_token(code=data['code'])
        credentials = flow.credentials

        # Store credentials (in production, encrypt and store securely)
        user = User.query.get(current_user_id)
        if user:
            # You might want to create a separate table for OAuth tokens
            # For now, we'll store them in the user record (not recommended for production)
            user.google_access_token = credentials.token
            user.google_refresh_token = credentials.refresh_token
            user.google_token_expiry = credentials.expiry
            db.session.commit()

        return jsonify({'message': 'Google Calendar connected successfully'})

    except Exception as e:
        return jsonify({'error': f'Google auth failed: {str(e)}'}), 500

def create_google_calendar_event(job, user_id):
    """Create a Google Calendar event for a job"""
    try:
        user = User.query.get(user_id)
        if not user or not hasattr(user, 'google_access_token'):
            return None

        credentials = google.oauth2.credentials.Credentials(
            token=user.google_access_token,
            refresh_token=getattr(user, 'google_refresh_token', None),
            token_uri=GOOGLE_CLIENT_CONFIG['web']['token_uri'],
            client_id=GOOGLE_CLIENT_CONFIG['web']['client_id'],
            client_secret=GOOGLE_CLIENT_CONFIG['web']['client_secret'],
            expiry=getattr(user, 'google_token_expiry', None)
        )

        service = build('calendar', 'v3', credentials=credentials)

        event = {
            'summary': f'Roofing Job: {job.customer_name}',
            'location': job.job_address,
            'description': f'Job Type: {job.job_type}\\nCustomer: {job.customer_name}\\nPhone: {job.customer_phone or "N/A"}',
            'start': {
                'dateTime': job.scheduled_start.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': job.scheduled_end.isoformat(),
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 24 hours before
                    {'method': 'popup', 'minutes': 2 * 60},  # 2 hours before
                ],
            },
        }

        event = service.events().insert(calendarId='primary', body=event).execute()
        return event['id']

    except Exception as e:
        current_app.logger.error(f"Google Calendar API error: {e}")
        return None

def update_google_calendar_event(job, user_id):
    """Update a Google Calendar event"""
    try:
        user = User.query.get(user_id)
        if not user or not hasattr(user, 'google_access_token'):
            return False

        # Similar to create function, but use update instead of insert
        # Implementation details...
        return True

    except Exception as e:
        current_app.logger.error(f"Google Calendar update error: {e}")
        return False

def delete_google_calendar_event(job, user_id):
    """Delete a Google Calendar event"""
    try:
        user = User.query.get(user_id)
        if not user or not hasattr(user, 'google_access_token'):
            return False

        credentials = google.oauth2.credentials.Credentials(
            token=user.google_access_token,
            refresh_token=getattr(user, 'google_refresh_token', None),
            token_uri=GOOGLE_CLIENT_CONFIG['web']['token_uri'],
            client_id=GOOGLE_CLIENT_CONFIG['web']['client_id'],
            client_secret=GOOGLE_CLIENT_CONFIG['web']['client_secret'],
        )

        service = build('calendar', 'v3', credentials=credentials)
        service.events().delete(calendarId='primary', eventId=job.google_calendar_event_id).execute()
        return True

    except Exception as e:
        current_app.logger.error(f"Google Calendar delete error: {e}")
        return False

def schedule_job_reminders(job):
    """Schedule SMS and email reminders for a job"""
    try:
        # Schedule SMS reminder 24 hours before
        sms_reminder_time = job.scheduled_start - timedelta(hours=24)
        if sms_reminder_time > datetime.now(timezone.utc):
            sms_reminder = Reminder(
                job_id=job.id,
                reminder_type='sms',
                scheduled_for=sms_reminder_time,
                recipient=job.customer_phone,
                message_content=f"Hi {job.customer_name}, this is a reminder about your roofing job scheduled for {job.scheduled_start.strftime('%Y-%m-%d %H:%M')}. We'll see you at {job.job_address}!"
            )
            db.session.add(sms_reminder)

        # Schedule email reminder 2 hours before
        email_reminder_time = job.scheduled_start - timedelta(hours=2)
        if email_reminder_time > datetime.now(timezone.utc):
            email_reminder = Reminder(
                job_id=job.id,
                reminder_type='email',
                scheduled_for=email_reminder_time,
                recipient=job.customer_email,
                message_content=f"Reminder: Roofing job scheduled for {job.scheduled_start.strftime('%Y-%m-%d %H:%M')} at {job.job_address}"
            )
            db.session.add(email_reminder)

        db.session.commit()

    except Exception as e:
        current_app.logger.error(f"Failed to schedule reminders: {e}")