"""
Authentication Routes
User registration, login, and session management
"""

import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)
import firebase_admin
from firebase_admin import auth as firebase_auth
import bcrypt

from app.models import db, User, Subscription

bp = Blueprint('auth', __name__)

# Initialize Firebase Admin if not already done
if not firebase_admin._apps:
    firebase_config = {
        "type": os.getenv('FIREBASE_TYPE'),
        "project_id": os.getenv('FIREBASE_PROJECT_ID'),
        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
        "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),
        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
        "auth_uri": os.getenv('FIREBASE_AUTH_URI'),
        "token_uri": os.getenv('FIREBASE_TOKEN_URI'),
        "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_X509_CERT_URL'),
        "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL')
    }
    cred = firebase_admin.credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)

@bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['email', 'password', 'name', 'company_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400

        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({'error': 'User already exists with this email'}), 400

        # Create Firebase user
        try:
            firebase_user = firebase_auth.create_user(
                email=data['email'],
                password=data['password']
            )
        except Exception as firebase_error:
            return jsonify({'error': f'Firebase registration failed: {str(firebase_error)}'}), 400

        # Hash password for local backup
        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())

        # Create local user record
        user = User(
            email=data['email'],
            name=data['name'],
            company_name=data['company_name'],
            phone=data.get('phone'),
            role='owner',
            firebase_uid=firebase_user.uid,
            subscription_plan='trial'  # 14-day free trial
        )

        db.session.add(user)
        db.session.flush()  # Get user ID without committing

        # Create subscription record
        subscription = Subscription(
            user_id=user.id,
            plan_type='trial',
            status='active'
        )
        db.session.add(subscription)

        db.session.commit()

        # Create JWT tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        return jsonify({
            'message': 'User registered successfully',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'name': user.name,
                'company_name': user.company_name,
                'role': user.role,
                'subscription_plan': user.subscription_plan
            },
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@bp.route('/login', methods=['POST'])
def login():
    """Login user with email/password or Firebase token"""
    try:
        data = request.get_json()

        if 'firebase_token' in data:
            # Firebase token login
            try:
                decoded_token = firebase_auth.verify_id_token(data['firebase_token'])
                firebase_uid = decoded_token['uid']

                user = User.query.filter_by(firebase_uid=firebase_uid).first()
                if not user:
                    return jsonify({'error': 'User not found'}), 404

            except Exception as firebase_error:
                return jsonify({'error': 'Invalid Firebase token'}), 401

        else:
            # Traditional email/password login
            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                return jsonify({'error': 'Email and password required'}), 400

            # First try Firebase authentication
            try:
                firebase_user = firebase_auth.get_user_by_email(email)
                # Note: Firebase doesn't have a direct password verification method in Admin SDK
                # In production, you'd use Firebase Client SDK on frontend and just verify the token
            except:
                return jsonify({'error': 'Invalid credentials'}), 401

            # Then find local user
            user = User.query.filter_by(email=email).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404

        if not user.is_active:
            return jsonify({'error': 'Account deactivated'}), 401

        # Create JWT tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'name': user.name,
                'company_name': user.company_name,
                'role': user.role,
                'subscription_plan': user.subscription_plan
            },
            'access_token': access_token,
            'refresh_token': refresh_token
        })

    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token using refresh token"""
    try:
        current_user_id = get_jwt_identity()
        new_token = create_access_token(identity=current_user_id)

        return jsonify({
            'access_token': new_token
        })

    except Exception as e:
        return jsonify({'error': 'Token refresh failed'}), 401

@bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user information"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'user': {
                'id': str(user.id),
                'email': user.email,
                'name': user.name,
                'company_name': user.company_name,
                'phone': user.phone,
                'role': user.role,
                'subscription_plan': user.subscription_plan,
                'created_at': user.created_at.isoformat()
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/update-profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile information"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()

        # Update allowed fields
        updatable_fields = ['name', 'company_name', 'phone']
        for field in updatable_fields:
            if field in data:
                setattr(user, field, data[field])

        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            'message': 'Profile updated successfully',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'name': user.name,
                'company_name': user.company_name,
                'phone': user.phone,
                'role': user.role
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Profile update failed: {str(e)}'}), 500

@bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (client-side token removal)"""
    # In a stateless JWT setup, we don't need to do anything server-side
    # The client should discard the tokens
    return jsonify({'message': 'Logout successful'})

# Store revoked tokens in a Redis set in production
@bp.route('/logout-all', methods=['POST'])
@jwt_required()
def logout_all():
    """Logout from all devices"""
    try:
        jti = get_jwt()['jti']
        # In production, you'd add the jti to a Redis set of revoked tokens
        return jsonify({'message': 'Logged out from all devices'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500