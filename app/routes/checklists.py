"""
Checklist Routes
Job completion tracking with templates and progress monitoring
"""

import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models import db, Checklist, Job, User

bp = Blueprint('checklists', __name__)

# Pre-built checklist templates for roofing jobs
CHECKLIST_TEMPLATES = {
    'roof_inspection': [
        'Exterior roof inspection',
        'Check for missing or damaged shingles',
        'Inspect flashing around vents and chimneys',
        'Check gutters and downspouts',
        'Inspect attic for water damage',
        'Document photos of problem areas',
        'Create detailed inspection report'
    ],
    'leak_repair': [
        'Locate source of leak',
        'Remove damaged shingles in affected area',
        'Inspect underlying decking for damage',
        'Replace damaged decking if needed',
        'Install new underlayment',
        'Install new shingles',
        'Apply sealant around flashing',
        'Test for water tightness',
        'Clean up work area'
    ],
    'full_replacement': [
        'Remove old roofing materials',
        'Inspect and repair decking',
        'Install new underlayment',
        'Install drip edge',
        'Install new shingles starting from bottom',
        'Install ridge cap shingles',
        'Install new flashing around vents and chimneys',
        'Clean up debris',
        'Final inspection',
        'Document before/after photos'
    ],
    'gutter_installation': [
        'Measure and cut gutter sections',
        'Install gutter hangers',
        'Attach gutter sections',
        'Install downspout connections',
        'Ensure proper drainage slope',
        'Test water flow',
        'Seal joints and connections',
        'Clean up work area'
    ]
}

@bp.route('/templates', methods=['GET'])
@jwt_required()
def get_checklist_templates():
    """Get available checklist templates"""
    try:
        return jsonify({
            'templates': {
                template_id: {
                    'name': template_id.replace('_', ' ').title(),
                    'items': items
                }
                for template_id, items in CHECKLIST_TEMPLATES.items()
            }
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch templates: {str(e)}'}), 500

@bp.route('/jobs/<job_id>/checklists', methods=['GET'])
@jwt_required()
def get_job_checklists(job_id):
    """Get all checklists for a specific job"""
    try:
        current_user_id = get_jwt_identity()

        # Verify job belongs to user
        job = Job.query.filter_by(id=job_id, user_id=current_user_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        checklists = Checklist.query.filter_by(job_id=job_id).order_by(Checklist.order_index).all()

        return jsonify({
            'checklists': [
                {
                    'id': str(checklist.id),
                    'template_name': checklist.template_name,
                    'item_text': checklist.item_text,
                    'is_completed': checklist.is_completed,
                    'assigned_worker_id': str(checklist.assigned_worker_id) if checklist.assigned_worker_id else None,
                    'assigned_worker_name': checklist.assigned_worker.name if checklist.assigned_worker else None,
                    'completed_at': checklist.completed_at.isoformat() if checklist.completed_at else None,
                    'notes': checklist.notes,
                    'photo_url': checklist.photo_url,
                    'order_index': checklist.order_index,
                    'created_at': checklist.created_at.isoformat()
                }
                for checklist in checklists
            ]
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch checklists: {str(e)}'}), 500

@bp.route('/jobs/<job_id>/checklists', methods=['POST'])
@jwt_required()
def create_checklist(job_id):
    """Create a new checklist for a job"""
    try:
        current_user_id = get_jwt_identity()

        # Verify job belongs to user
        job = Job.query.filter_by(id=job_id, user_id=current_user_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        data = request.get_json()

        # Handle template-based creation or individual item creation
        if 'template_name' in data:
            # Create checklist from template
            template_name = data['template_name']
            if template_name not in CHECKLIST_TEMPLATES:
                return jsonify({'error': 'Template not found'}), 400

            template_items = CHECKLIST_TEMPLATES[template_name]
            created_checklists = []

            # Get current max order_index
            max_order = Checklist.query.filter_by(job_id=job_id).count()

            for index, item_text in enumerate(template_items):
                checklist = Checklist(
                    job_id=job_id,
                    template_name=template_name,
                    item_text=item_text,
                    order_index=max_order + index
                )
                db.session.add(checklist)
                created_checklists.append(checklist)

            db.session.commit()

            return jsonify({
                'message': f'Created {len(created_checklists)} checklist items from template',
                'checklists': [
                    {
                        'id': str(checklist.id),
                        'item_text': checklist.item_text,
                        'template_name': checklist.template_name,
                        'order_index': checklist.order_index
                    }
                    for checklist in created_checklists
                ]
            }), 201

        else:
            # Create individual checklist item
            if not data.get('item_text'):
                return jsonify({'error': 'item_text is required'}), 400

            checklist = Checklist(
                job_id=job_id,
                template_name=data.get('template_name', 'custom'),
                item_text=data['item_text'],
                assigned_worker_id=data.get('assigned_worker_id'),
                order_index=data.get('order_index', 0)
            )

            db.session.add(checklist)
            db.session.commit()

            return jsonify({
                'message': 'Checklist item created successfully',
                'checklist': {
                    'id': str(checklist.id),
                    'item_text': checklist.item_text,
                    'template_name': checklist.template_name,
                    'assigned_worker_id': str(checklist.assigned_worker_id) if checklist.assigned_worker_id else None,
                    'order_index': checklist.order_index
                }
            }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create checklist: {str(e)}'}), 500

@bp.route('/checklists/<checklist_id>', methods=['PUT'])
@jwt_required()
def update_checklist(checklist_id):
    """Update a checklist item"""
    try:
        current_user_id = get_jwt_identity()

        # Get checklist and verify job ownership
        checklist = Checklist.query.join(Job).filter(
            Checklist.id == checklist_id,
            Job.user_id == current_user_id
        ).first()

        if not checklist:
            return jsonify({'error': 'Checklist not found'}), 404

        data = request.get_json()

        # Update checklist fields
        updatable_fields = ['item_text', 'assigned_worker_id', 'notes', 'photo_url', 'order_index']
        for field in updatable_fields:
            if field in data:
                setattr(checklist, field, data[field])

        # Handle completion status
        if 'is_completed' in data:
            checklist.is_completed = data['is_completed']
            if data['is_completed'] and not checklist.completed_at:
                checklist.completed_at = datetime.now(timezone.utc)
            elif not data['is_completed']:
                checklist.completed_at = None

        db.session.commit()

        return jsonify({
            'message': 'Checklist updated successfully',
            'checklist': {
                'id': str(checklist.id),
                'item_text': checklist.item_text,
                'is_completed': checklist.is_completed,
                'completed_at': checklist.completed_at.isoformat() if checklist.completed_at else None,
                'assigned_worker_id': str(checklist.assigned_worker_id) if checklist.assigned_worker_id else None,
                'notes': checklist.notes,
                'photo_url': checklist.photo_url,
                'order_index': checklist.order_index
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update checklist: {str(e)}'}), 500

@bp.route('/checklists/<checklist_id>', methods=['DELETE'])
@jwt_required()
def delete_checklist(checklist_id):
    """Delete a checklist item"""
    try:
        current_user_id = get_jwt_identity()

        # Get checklist and verify job ownership
        checklist = Checklist.query.join(Job).filter(
            Checklist.id == checklist_id,
            Job.user_id == current_user_id
        ).first()

        if not checklist:
            return jsonify({'error': 'Checklist not found'}), 404

        db.session.delete(checklist)
        db.session.commit()

        return jsonify({'message': 'Checklist deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete checklist: {str(e)}'}), 500

@bp.route('/checklists/<checklist_id>/photo', methods=['POST'])
@jwt_required()
def upload_checklist_photo(checklist_id):
    """Upload photo for checklist item"""
    try:
        current_user_id = get_jwt_identity()

        # Get checklist and verify job ownership
        checklist = Checklist.query.join(Job).filter(
            Checklist.id == checklist_id,
            Job.user_id == current_user_id
        ).first()

        if not checklist:
            return jsonify({'error': 'Checklist not found'}), 404

        if 'photo' not in request.files:
            return jsonify({'error': 'No photo file provided'}), 400

        photo = request.files['photo']

        if photo.filename == '':
            return jsonify({'error': 'No photo file selected'}), 400

        if not allowed_file(photo.filename):
            return jsonify({'error': 'File type not allowed'}), 400

        # Generate unique filename
        filename = secure_filename(f"{checklist_id}_{datetime.now().timestamp()}_{photo.filename}")

        # Upload to cloud storage (AWS S3 in production)
        try:
            photo_url = upload_photo_to_storage(photo, filename)
            checklist.photo_url = photo_url
            db.session.commit()

            return jsonify({
                'message': 'Photo uploaded successfully',
                'photo_url': photo_url
            })

        except Exception as upload_error:
            return jsonify({'error': f'Failed to upload photo: {str(upload_error)}'}), 500

    except Exception as e:
        return jsonify({'error': f'Photo upload failed: {str(e)}'}), 500

@bp.route('/jobs/<job_id>/progress', methods=['GET'])
@jwt_required()
def get_job_progress(job_id):
    """Get overall progress for a job"""
    try:
        current_user_id = get_jwt_identity()

        # Verify job belongs to user
        job = Job.query.filter_by(id=job_id, user_id=current_user_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        checklists = Checklist.query.filter_by(job_id=job_id).all()

        total_items = len(checklists)
        completed_items = len([item for item in checklists if item.is_completed])

        # Group by template
        template_progress = {}
        for checklist in checklists:
            template = checklist.template_name
            if template not in template_progress:
                template_progress[template] = {'total': 0, 'completed': 0}

            template_progress[template]['total'] += 1
            if checklist.is_completed:
                template_progress[template]['completed'] += 1

        # Calculate completion percentage
        completion_percentage = (completed_items / total_items * 100) if total_items > 0 else 0

        # Get recent activity
        recent_activity = Checklist.query.filter_by(job_id=job_id).filter(
            Checklist.completed_at.isnot(None)
        ).order_by(Checklist.completed_at.desc()).limit(5).all()

        return jsonify({
            'job_id': job_id,
            'total_items': total_items,
            'completed_items': completed_items,
            'completion_percentage': round(completion_percentage, 2),
            'template_progress': {
                template: {
                    'total': data['total'],
                    'completed': data['completed'],
                    'percentage': round(data['completed'] / data['total'] * 100, 2) if data['total'] > 0 else 0
                }
                for template, data in template_progress.items()
            },
            'recent_activity': [
                {
                    'item_text': item.item_text,
                    'completed_at': item.completed_at.isoformat(),
                    'assigned_worker_name': item.assigned_worker.name if item.assigned_worker else None
                }
                for item in recent_activity
            ]
        })

    except Exception as e:
        return jsonify({'error': f'Failed to get job progress: {str(e)}'}), 500

@bp.route('/workers', methods=['GET'])
@jwt_required()
def get_workers():
    """Get list of workers for assignment"""
    try:
        current_user_id = get_jwt_identity()

        # Get all workers for the user's company
        workers = User.query.filter_by(
            user_id=current_user_id,
            role='worker'
        ).all()

        # In a real app, you might have company relationships
        # For now, return just the current user as a worker
        user = User.query.get(current_user_id)

        worker_list = []
        if user:
            worker_list.append({
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'phone': user.phone
            })

        return jsonify({'workers': worker_list})

    except Exception as e:
        return jsonify({'error': f'Failed to fetch workers: {str(e)}'}), 500

# Helper functions
def allowed_file(filename):
    """Check if file type is allowed for upload"""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def secure_filename(filename):
    """Create a secure filename"""
    import re
    # Remove any path separators and replace with underscores
    filename = re.sub(r'[^\w\s.-]', '', filename)
    filename = re.sub(r'[-\s]+', '_', filename)
    return filename.strip('_')

def upload_photo_to_storage(photo_file, filename):
    """
    Upload photo to cloud storage
    In production, this would upload to AWS S3, Google Cloud Storage, or similar
    For now, return a mock URL
    """
    # Mock implementation - in production, integrate with actual storage service
    storage_url = f"https://storage.example.com/checklist-photos/{filename}"

    # Here you would:
    # 1. Upload photo_file.to S3 using boto3
    # 2. Generate presigned URL or public URL
    # 3. Return the URL

    return storage_url