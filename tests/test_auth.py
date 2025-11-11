"""
Authentication Tests
Test user registration, login, and token management
"""

import pytest
import json
from app import create_app
from app.models import db, User

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
def auth_headers():
    # Test user credentials
    user_data = {
        'email': 'test@example.com',
        'password': 'testpassword123',
        'name': 'Test User',
        'company_name': 'Test Roofing Co'
    }
    return user_data

class TestAuth:
    def test_user_registration(self, client, auth_headers):
        """Test user registration endpoint"""
        response = client.post('/api/auth/register',
                              data=json.dumps(auth_headers),
                              content_type='application/json')

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'access_token' in data
        assert 'user' in data
        assert data['user']['email'] == auth_headers['email']

    def test_duplicate_registration(self, client, auth_headers):
        """Test registration with duplicate email"""
        # Register user first time
        client.post('/api/auth/register',
                   data=json.dumps(auth_headers),
                   content_type='application/json')

        # Try to register again
        response = client.post('/api/auth/register',
                              data=json.dumps(auth_headers),
                              content_type='application/json')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'User already exists' in data['error']

    def test_user_login(self, client, auth_headers):
        """Test user login endpoint"""
        # Register user first
        client.post('/api/auth/register',
                   data=json.dumps(auth_headers),
                   content_type='application/json')

        # Login with credentials
        login_data = {
            'email': auth_headers['email'],
            'password': auth_headers['password']
        }

        response = client.post('/api/auth/login',
                              data=json.dumps(login_data),
                              content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'access_token' in data
        assert 'refresh_token' in data

    def test_invalid_login(self, client):
        """Test login with invalid credentials"""
        login_data = {
            'email': 'nonexistent@example.com',
            'password': 'wrongpassword'
        }

        response = client.post('/api/auth/login',
                              data=json.dumps(login_data),
                              content_type='application/json')

        assert response.status_code == 401

    def test_get_current_user(self, client, auth_headers):
        """Test getting current user info"""
        # Register and login user
        register_response = client.post('/api/auth/register',
                                       data=json.dumps(auth_headers),
                                       content_type='application/json')
        register_data = json.loads(register_response.data)
        token = register_data['access_token']

        # Get current user
        headers = {'Authorization': f'Bearer {token}'}
        response = client.get('/api/auth/me', headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['user']['email'] == auth_headers['email']

    def test_unauthorized_access(self, client):
        """Test accessing protected endpoints without token"""
        response = client.get('/api/auth/me')
        assert response.status_code == 401

    def test_token_refresh(self, client, auth_headers):
        """Test token refresh endpoint"""
        # Register and login user
        register_response = client.post('/api/auth/register',
                                       data=json.dumps(auth_headers),
                                       content_type='application/json')
        register_data = json.loads(register_response.data)
        refresh_token = register_data['refresh_token']

        # Refresh token
        response = client.post('/api/auth/refresh',
                              headers={'Authorization': f'Bearer {refresh_token}'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'access_token' in data

    def test_logout(self, client, auth_headers):
        """Test user logout"""
        # Register and login user
        register_response = client.post('/api/auth/register',
                                       data=json.dumps(auth_headers),
                                       content_type='application/json')
        register_data = json.loads(register_response.data)
        token = register_data['access_token']

        # Logout
        response = client.post('/api/auth/logout',
                              headers={'Authorization': f'Bearer {token}'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'Logout successful' in data['message']

if __name__ == '__main__':
    pytest.main([__file__])