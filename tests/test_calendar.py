"""
Calendar Tests
Test job scheduling and calendar management
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from app import create_app
from app.models import db, User, Job, JobStatus

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_user(app):
    """Create a test user and return auth token"""
    user = User(
        email='test@example.com',
        name='Test User',
        company_name='Test Roofing Co',
        role='owner'
    )
    db.session.add(user)
    db.session.commit()

    # Mock token generation (in real app, use proper JWT)
    return str(user.id), 'mock_token'

@pytest.fixture
def sample_job_data():
    """Sample job data for testing"""
    return {
        'customer_name': 'John Doe',
        'customer_email': 'john@example.com',
        'customer_phone': '+1-555-0123',
        'job_address': '123 Main St, City, State 12345',
        'job_type': 'roof_replacement',
        'scheduled_start': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        'scheduled_end': (datetime.now(timezone.utc) + timedelta(days=1, hours=8)).isoformat(),
        'estimated_price': 5000.00,
        'notes': 'Full roof replacement'
    }

class TestCalendar:
    def test_create_job(self, client, auth_user, sample_job_data):
        """Test job creation"""
        user_id, token = auth_user
        headers = {'Authorization': f'Bearer {token}'}

        response = client.post('/api/calendar/jobs',
                              data=json.dumps(sample_job_data),
                              content_type='application/json',
                              headers=headers)

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['job']['customer_name'] == sample_job_data['customer_name']
        assert data['job']['job_type'] == sample_job_data['job_type']
        assert data['job']['status'] == JobStatus.SCHEDULED.value

    def test_create_job_missing_fields(self, client, auth_user):
        """Test job creation with missing required fields"""
        user_id, token = auth_user
        headers = {'Authorization': f'Bearer {token}'}

        incomplete_data = {
            'customer_name': 'John Doe',
            # Missing required fields
        }

        response = client.post('/api/calendar/jobs',
                              data=json.dumps(incomplete_data),
                              content_type='application/json',
                              headers=headers)

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'is required' in data['error']

    def test_get_jobs(self, client, auth_user, sample_job_data):
        """Test retrieving jobs"""
        user_id, token = auth_user
        headers = {'Authorization': f'Bearer {token}'}

        # Create a job first
        client.post('/api/calendar/jobs',
                   data=json.dumps(sample_job_data),
                   content_type='application/json',
                   headers=headers)

        # Get jobs
        response = client.get('/api/calendar/jobs', headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'jobs' in data
        assert len(data['jobs']) == 1
        assert data['jobs'][0]['customer_name'] == sample_job_data['customer_name']

    def test_get_jobs_with_filters(self, client, auth_user, sample_job_data):
        """Test retrieving jobs with filters"""
        user_id, token = auth_user
        headers = {'Authorization': f'Bearer {token}'}

        # Create jobs with different statuses
        completed_job = sample_job_data.copy()
        completed_job['customer_name'] = 'Jane Smith'
        completed_job['status'] = 'completed'

        client.post('/api/calendar/jobs',
                   data=json.dumps(sample_job_data),
                   content_type='application/json',
                   headers=headers)

        client.post('/api/calendar/jobs',
                   data=json.dumps(completed_job),
                   content_type='application/json',
                   headers=headers)

        # Filter by status
        response = client.get('/api/calendar/jobs?status=scheduled', headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['jobs']) == 1
        assert data['jobs'][0]['status'] == JobStatus.SCHEDULED.value

    def test_update_job(self, client, auth_user, sample_job_data):
        """Test job update"""
        user_id, token = auth_user
        headers = {'Authorization': f'Bearer {token}'}

        # Create a job first
        create_response = client.post('/api/calendar/jobs',
                                     data=json.dumps(sample_job_data),
                                     content_type='application/json',
                                     headers=headers)
        created_job = json.loads(create_response.data)
        job_id = created_job['job']['id']

        # Update the job
        update_data = {
            'customer_name': 'Updated Name',
            'status': 'completed',
            'actual_price': 5500.00
        }

        response = client.put(f'/api/calendar/jobs/{job_id}',
                             data=json.dumps(update_data),
                             content_type='application/json',
                             headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['job']['customer_name'] == 'Updated Name'
        assert data['job']['status'] == 'completed'

    def test_update_nonexistent_job(self, client, auth_user):
        """Test updating a job that doesn't exist"""
        user_id, token = auth_user
        headers = {'Authorization': f'Bearer {token}'}

        update_data = {'customer_name': 'Updated Name'}
        fake_job_id = '00000000-0000-0000-0000-000000000000'

        response = client.put(f'/api/calendar/jobs/{fake_job_id}',
                             data=json.dumps(update_data),
                             content_type='application/json',
                             headers=headers)

        assert response.status_code == 404

    def test_delete_job(self, client, auth_user, sample_job_data):
        """Test job deletion"""
        user_id, token = auth_user
        headers = {'Authorization': f'Bearer {token}'}

        # Create a job first
        create_response = client.post('/api/calendar/jobs',
                                     data=json.dumps(sample_job_data),
                                     content_type='application/json',
                                     headers=headers)
        created_job = json.loads(create_response.data)
        job_id = created_job['job']['id']

        # Delete the job
        response = client.delete(f'/api/calendar/jobs/{job_id}', headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'Job deleted successfully' in data['message']

        # Verify job is deleted
        get_response = client.get('/api/calendar/jobs', headers=headers)
        jobs_data = json.loads(get_response.data)
        assert len(jobs_data['jobs']) == 0

    def test_date_filtering(self, client, auth_user, sample_job_data):
        """Test filtering jobs by date range"""
        user_id, token = auth_user
        headers = {'Authorization': f'Bearer {token}'}

        # Create jobs for different dates
        future_job = sample_job_data.copy()
        future_job['customer_name'] = 'Future Job'
        future_job['scheduled_start'] = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

        # Create jobs
        client.post('/api/calendar/jobs',
                   data=json.dumps(sample_job_data),
                   content_type='application/json',
                   headers=headers)

        client.post('/api/calendar/jobs',
                   data=json.dumps(future_job),
                   content_type='application/json',
                   headers=headers)

        # Filter for next 5 days
        end_date = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        response = client.get(f'/api/calendar/jobs?end_date={end_date}', headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['jobs']) == 1  # Only the first job should be in range

    def test_invalid_datetime_format(self, client, auth_user):
        """Test handling of invalid datetime formats"""
        user_id, token = auth_user
        headers = {'Authorization': f'Bearer {token}'}

        invalid_job_data = {
            'customer_name': 'John Doe',
            'job_address': '123 Main St',
            'job_type': 'roof_replacement',
            'scheduled_start': 'invalid-date',
            'scheduled_end': 'invalid-date'
        }

        response = client.post('/api/calendar/jobs',
                              data=json.dumps(invalid_job_data),
                              content_type='application/json',
                              headers=headers)

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Invalid datetime format' in data['error']

if __name__ == '__main__':
    pytest.main([__file__])