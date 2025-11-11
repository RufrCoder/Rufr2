"""
Analytics Routes
Business performance metrics and reporting
"""

import os
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, extract
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models import db, Job, Checklist, Message, User, Material, Reminder

bp = Blueprint('analytics', __name__)

@bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_metrics():
    """Get main dashboard metrics"""
    try:
        current_user_id = get_jwt_identity()

        # Date range filtering
        period = request.args.get('period', '30days')  # 7days, 30days, 90days, ytd
        end_date = datetime.now(timezone.utc)

        if period == '7days':
            start_date = end_date - timedelta(days=7)
        elif period == '30days':
            start_date = end_date - timedelta(days=30)
        elif period == '90days':
            start_date = end_date - timedelta(days=90)
        elif period == 'ytd':
            start_date = datetime(end_date.year, 1, 1, tzinfo=timezone.utc)
        else:
            start_date = end_date - timedelta(days=30)

        # Jobs booked per week
        jobs_per_week = db.session.query(
            func.date_trunc('week', Job.created_at).label('week'),
            func.count(Job.id).label('job_count')
        ).filter(
            Job.user_id == current_user_id,
            Job.created_at >= start_date,
            Job.created_at <= end_date
        ).group_by(
            func.date_trunc('week', Job.created_at)
        ).order_by('week').all()

        # Job completion metrics
        total_jobs = Job.query.filter(
            Job.user_id == current_user_id,
            Job.created_at >= start_date,
            Job.created_at <= end_date
        ).count()

        completed_jobs = Job.query.filter(
            Job.user_id == current_user_id,
            Job.status == 'completed',
            Job.created_at >= start_date,
            Job.created_at <= end_date
        ).count()

        # Jobs completed on time
        on_time_jobs = Job.query.filter(
            Job.user_id == current_user_id,
            Job.status == 'completed',
            Job.scheduled_end >= Job.created_at,
            Job.created_at >= start_date,
            Job.created_at <= end_date
        ).count()

        # Reminder metrics
        total_reminders = Reminder.query.join(Job).filter(
            Job.user_id == current_user_id,
            Reminder.created_at >= start_date,
            Reminder.created_at <= end_date
        ).count()

        sent_reminders = Reminder.query.join(Job).filter(
            Job.user_id == current_user_id,
            Reminder.status == 'sent',
            Reminder.created_at >= start_date,
            Reminder.created_at <= end_date
        ).count()

        # Checklist completion metrics
        total_checklist_items = Checklist.query.join(Job).filter(
            Job.user_id == current_user_id,
            Checklist.created_at >= start_date,
            Checklist.created_at <= end_date
        ).count()

        completed_checklist_items = Checklist.query.join(Job).filter(
            Job.user_id == current_user_id,
            Checklist.is_completed == True,
            Checklist.created_at >= start_date,
            Checklist.created_at <= end_date
        ).count()

        # Revenue calculations
        completed_jobs_with_revenue = Job.query.filter(
            Job.user_id == current_user_id,
            Job.status == 'completed',
            Job.actual_price.isnot(None),
            Job.created_at >= start_date,
            Job.created_at <= end_date
        ).all()

        total_revenue = sum(job.actual_price for job in completed_jobs_with_revenue)
        estimated_revenue = sum(job.estimated_price or 0 for job in completed_jobs_with_revenue)

        # Calculate metrics
        jobs_completed_per_week = [
            {
                'week': job.week.isoformat(),
                'count': job.job_count
            }
            for job in jobs_per_week
        ]

        completion_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
        on_time_completion_rate = (on_time_jobs / completed_jobs * 100) if completed_jobs > 0 else 0
        reminder_delivery_rate = (sent_reminders / total_reminders * 100) if total_reminders > 0 else 0
        checklist_completion_rate = (completed_checklist_items / total_checklist_items * 100) if total_checklist_items > 0 else 0

        return jsonify({
            'period': period,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'metrics': {
                'jobs_booked_per_week': jobs_completed_per_week,
                'total_jobs': total_jobs,
                'completed_jobs': completed_jobs,
                'completion_rate': round(completion_rate, 2),
                'on_time_completion_rate': round(on_time_completion_rate, 2),
                'reminder_delivery_rate': round(reminder_delivery_rate, 2),
                'checklist_completion_rate': round(checklist_completion_rate, 2),
                'total_revenue': float(total_revenue),
                'estimated_revenue': float(estimated_revenue),
                'revenue_accuracy': round((total_revenue / estimated_revenue * 100) if estimated_revenue > 0 else 0, 2)
            }
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch dashboard metrics: {str(e)}'}), 500

@bp.route('/job-types', methods=['GET'])
@jwt_required()
def get_job_type_analytics():
    """Get analytics by job type"""
    try:
        current_user_id = get_jwt_identity()

        # Date range
        end_date = datetime.now(timezone.utc)
        start_date = request.args.get('start_date', (end_date - timedelta(days=90)).isoformat())
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))

        # Job counts and revenue by type
        job_type_stats = db.session.query(
            Job.job_type,
            func.count(Job.id).label('job_count'),
            func.sum(Job.estimated_price).label('estimated_total'),
            func.sum(Job.actual_price).label('actual_total'),
            func.avg(func.extract('epoch', Job.scheduled_end - Job.scheduled_start) / 3600).label('avg_duration_hours')
        ).filter(
            Job.user_id == current_user_id,
            Job.created_at >= start_date,
            Job.created_at <= end_date
        ).group_by(Job.job_type).all()

        job_type_data = []
        for stat in job_type_stats:
            completion_rate = db.session.query(func.count(Job.id)).filter(
                Job.user_id == current_user_id,
                Job.job_type == stat.job_type,
                Job.status == 'completed',
                Job.created_at >= start_date,
                Job.created_at <= end_date
            ).scalar() / stat.job_count * 100 if stat.job_count > 0 else 0

            job_type_data.append({
                'job_type': stat.job_type,
                'job_count': stat.job_count,
                'estimated_total': float(stat.estimated_total or 0),
                'actual_total': float(stat.actual_total or 0),
                'average_duration_hours': round(float(stat.avg_duration_hours or 0), 2),
                'completion_rate': round(completion_rate, 2)
            })

        return jsonify({
            'job_type_analytics': job_type_data,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch job type analytics: {str(e)}'}), 500

@bp.route('/revenue', methods=['GET'])
@jwt_required()
def get_revenue_analytics():
    """Get revenue analytics and trends"""
    try:
        current_user_id = get_jwt_identity()

        # Date range
        end_date = datetime.now(timezone.utc)
        start_date = request.args.get('start_date', (end_date - timedelta(days=365)).isoformat())
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))

        # Monthly revenue trend
        monthly_revenue = db.session.query(
            func.date_trunc('month', Job.created_at).label('month'),
            func.sum(Job.actual_price).label('revenue'),
            func.count(Job.id).label('job_count')
        ).filter(
            Job.user_id == current_user_id,
            Job.status == 'completed',
            Job.actual_price.isnot(None),
            Job.created_at >= start_date,
            Job.created_at <= end_date
        ).group_by(
            func.date_trunc('month', Job.created_at)
        ).order_by('month').all()

        # Profit calculations (using estimated costs)
        completed_jobs = Job.query.filter(
            Job.user_id == current_user_id,
            Job.status == 'completed',
            Job.estimated_price.isnot(None),
            Job.actual_price.isnot(None),
            Job.created_at >= start_date,
            Job.created_at <= end_date
        ).all()

        # Assume 40% cost for materials and labor
        total_revenue = sum(job.actual_price for job in completed_jobs)
        total_estimated_cost = sum(job.estimated_price * 0.4 for job in completed_jobs)
        estimated_profit = total_revenue - total_estimated_cost

        revenue_trend = [
            {
                'month': rev.month.isoformat(),
                'revenue': float(rev.revenue or 0),
                'job_count': rev.job_count
            }
            for rev in monthly_revenue
        ]

        return jsonify({
            'revenue_trend': revenue_trend,
            'summary': {
                'total_revenue': float(total_revenue),
                'estimated_costs': float(total_estimated_cost),
                'estimated_profit': float(estimated_profit),
                'profit_margin': round((estimated_profit / total_revenue * 100) if total_revenue > 0 else 0, 2),
                'total_completed_jobs': len(completed_jobs),
                'average_job_value': round(total_revenue / len(completed_jobs) if completed_jobs else 0, 2)
            },
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch revenue analytics: {str(e)}'}), 500

@bp.route('/worker-performance', methods=['GET'])
@jwt_required()
def get_worker_performance():
    """Get worker performance metrics"""
    try:
        current_user_id = get_jwt_identity()

        # Date range
        end_date = datetime.now(timezone.utc)
        start_date = request.args.get('start_date', (end_date - timedelta(days=90)).isoformat())
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))

        # Get workers (in real app, you'd have proper worker relationships)
        workers = User.query.filter_by(user_id=current_user_id, role='worker').all()
        if not workers:
            # Include the owner as a worker for demo purposes
            owner = User.query.get(current_user_id)
            if owner:
                workers = [owner]

        worker_performance = []

        for worker in workers:
            # Assigned checklist items
            assigned_items = Checklist.query.filter(
                Checklist.assigned_worker_id == worker.id,
                Checklist.created_at >= start_date,
                Checklist.created_at <= end_date
            ).all()

            completed_items = [item for item in assigned_items if item.is_completed]

            # Jobs associated with the worker
            worker_jobs = Job.query.filter(
                Job.user_id == current_user_id,
                Job.created_at >= start_date,
                Job.created_at <= end_date
            ).all()  # In real app, you'd have worker-job relationships

            completed_jobs = [job for job in worker_jobs if job.status == 'completed']

            performance = {
                'worker_id': str(worker.id),
                'worker_name': worker.name,
                'assigned_checklist_items': len(assigned_items),
                'completed_checklist_items': len(completed_items),
                'checklist_completion_rate': round((len(completed_items) / len(assigned_items) * 100) if assigned_items else 0, 2),
                'total_jobs': len(worker_jobs),
                'completed_jobs': len(completed_jobs),
                'job_completion_rate': round((len(completed_jobs) / len(worker_jobs) * 100) if worker_jobs else 0, 2)
            }

            worker_performance.append(performance)

        return jsonify({
            'worker_performance': worker_performance,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch worker performance: {str(e)}'}), 500

@bp.route('/communication', methods=['GET'])
@jwt_required()
def get_communication_analytics():
    """Get communication analytics"""
    try:
        current_user_id = get_jwt_identity()

        # Date range
        end_date = datetime.now(timezone.utc)
        start_date = request.args.get('start_date', (end_date - timedelta(days=30)).isoformat())
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))

        # Message volume by source
        message_volume = db.session.query(
            Message.source,
            func.count(Message.id).label('message_count')
        ).join(Job).filter(
            Job.user_id == current_user_id,
            Message.created_at >= start_date,
            Message.created_at <= end_date
        ).group_by(Message.source).all()

        # Message categories
        message_categories = db.session.query(
            Message.category,
            func.count(Message.id).label('category_count')
        ).join(Job).filter(
            Job.user_id == current_user_id,
            Message.created_at >= start_date,
            Message.created_at <= end_date,
            Message.category.isnot(None)
        ).group_by(Message.category).all()

        # Read rate
        total_messages = Message.query.join(Job).filter(
            Job.user_id == current_user_id,
            Message.direction == 'inbound',
            Message.created_at >= start_date,
            Message.created_at <= end_date
        ).count()

        read_messages = Message.query.join(Job).filter(
            Job.user_id == current_user_id,
            Message.direction == 'inbound',
            Message.is_read == True,
            Message.created_at >= start_date,
            Message.created_at <= end_date
        ).count()

        read_rate = (read_messages / total_messages * 100) if total_messages > 0 else 0

        communication_data = {
            'message_volume': [
                {
                    'source': msg.source.value,
                    'count': msg.message_count
                }
                for msg in message_volume
            ],
            'message_categories': [
                {
                    'category': cat.category,
                    'count': cat.category_count
                }
                for cat in message_categories
            ],
            'read_rate': round(read_rate, 2),
            'total_messages': total_messages,
            'read_messages': read_messages
        }

        return jsonify({
            'communication_analytics': communication_data,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch communication analytics: {str(e)}'}), 500

@bp.route('/export', methods=['POST'])
@jwt_required()
def export_analytics():
    """Export analytics data (CSV/Excel format)"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        export_type = data.get('type', 'csv')  # csv, excel
        report_type = data.get('report_type', 'dashboard')  # dashboard, revenue, jobs, workers

        # Generate report data based on type
        if report_type == 'dashboard':
            # Re-use dashboard metrics logic
            pass
        elif report_type == 'revenue':
            # Generate revenue report data
            pass
        elif report_type == 'jobs':
            # Generate jobs report data
            pass
        elif report_type == 'workers':
            # Generate worker performance report
            pass

        # In a real implementation, you would:
        # 1. Generate the data
        # 2. Create CSV/Excel file
        # 3. Upload to cloud storage
        # 4. Return download URL

        # For now, return a mock download URL
        download_url = f"https://storage.example.com/reports/{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_type}"

        return jsonify({
            'message': f'{report_type.title()} report generated successfully',
            'download_url': download_url,
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        })

    except Exception as e:
        return jsonify({'error': f'Failed to export analytics: {str(e)}'}), 500