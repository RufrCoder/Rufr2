"""
Roofing Business Management Application
Main Flask application entry point
"""

import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)

    # Basic Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/roofing_db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')

    # Initialize extensions
    CORS(app, origins=['*'])  # Configure for production
    JWTManager(app)

    # Rate limiting
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )

    # Import and register blueprints
    from app.routes import auth, calendar, messages, checklists, analytics, ai, materials, payments

    app.register_blueprint(auth.bp, url_prefix='/api/auth')
    app.register_blueprint(calendar.bp, url_prefix='/api/calendar')
    app.register_blueprint(messages.bp, url_prefix='/api/messages')
    app.register_blueprint(checklists.bp, url_prefix='/api/checklists')
    app.register_blueprint(analytics.bp, url_prefix='/api/analytics')
    app.register_blueprint(ai.bp, url_prefix='/api/ai')
    app.register_blueprint(materials.bp, url_prefix='/api/materials')
    app.register_blueprint(payments.bp, url_prefix='/api/payments')

    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return {'status': 'healthy', 'message': 'Roofing Business API is running'}

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)