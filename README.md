# Roofing Business Management App

A comprehensive, easy-to-use, minimalistic business management application designed specifically for small roofing companies. This cross-platform app helps streamline operations with intelligent automation, unified communication, and powerful analytics.

## 🏠 Features

### 📅 **Calendar & Scheduling**
- Simple, clean calendar interface (month/week/day views)
- Google Calendar two-way sync
- Automated SMS/email reminders (24h before, 2h before)
- Job scheduling with customer and worker assignment
- Color-coded job status tracking

### 💬 **Message Hub**
- Unified inbox from SMS, Email, WhatsApp, and in-app messages
- Auto-categorization (leads, quotes, job updates, questions)
- Quick reply templates for roofing-specific communications
- AI-powered prioritization of urgent messages

### ✅ **Smart Checklists**
- Pre-built roofing job templates (inspection, repair, replacement)
- Custom checklist creation
- Photo attachment capability
- Progress tracking with completion percentages
- Worker assignment and time tracking

### 📊 **Analytics Dashboard**
- Jobs booked per week (trend analysis)
- Job completion rates and on-time performance
- Revenue tracking and profit analysis
- Material usage and cost optimization
- Worker productivity metrics

### 🤖 **AI Agent**
- Calendar intelligence and conflict detection
- Automated customer responses
- Materials inventory management and auto-ordering
- Voice commands (experimental)
- Quote generation assistance

### 📦 **Materials Management**
- Real-time inventory tracking
- Automatic reordering when stock runs low
- Supplier price comparison
- Shipment tracking and delivery coordination

### 💳 **Subscription Management**
- **Monthly**: $19.99/month - Full access
- **Yearly**: $169/year (30% savings) - Full access
- **Lifetime**: $1,499 one-time - Full access forever

## 🛠 Technology Stack

### Backend
- **Framework**: Flask (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Firebase Auth
- **Real-time**: Socket.io
- **External APIs**: Twilio (SMS), SendGrid (Email), Stripe (Payments), OpenAI (AI)
- **Background Jobs**: Celery with Redis

### Frontend
- **Framework**: Flutter (cross-platform)
- **State Management**: BLoC Pattern
- **Architecture**: Clean Architecture
- **Navigation**: GoRouter

### Infrastructure
- **Deployment**: Docker containers with docker-compose
- **Web Server**: Nginx reverse proxy
- **SSL**: HTTPS with security headers
- **Monitoring**: Health checks and logging

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Flutter 3.0+
- PostgreSQL 15+
- Redis 7+
- Node.js 16+ (for some tools)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd Rufr2
```

### 2. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys and configuration
nano .env
```

### 3. Backend Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up database
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Seed database with sample data
python database/seed.py
```

### 4. Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install Flutter dependencies
flutter pub get

# Run app
flutter run -d web-server --web-port 3000
```

### 5. Docker Deployment (Recommended)
```bash
# Build and start all services
docker-compose up --build -d

# Check logs
docker-compose logs -f
```

## 📁 Project Structure

```
Rufr2/
├── app/                          # Flask application
│   ├── models.py                # Database models
│   ├── routes/                  # API endpoints
│   │   ├── auth.py             # Authentication
│   │   ├── calendar.py         # Job scheduling
│   │   ├── messages.py         # Message hub
│   │   ├── checklists.py       # Checklists
│   │   ├── analytics.py        # Business analytics
│   │   ├── ai.py               # AI agent
│   │   ├── materials.py        # Materials management
│   │   └── payments.py         # Stripe integration
│   └── services/               # Business logic
├── frontend/                    # Flutter app
│   ├── lib/                   # Dart source code
│   │   ├── core/              # App core utilities
│   │   ├── features/          # Feature modules
│   │   └── services/          # API services
│   └── pubspec.yaml           # Flutter dependencies
├── database/                   # Database setup
│   ├── seed.py               # Sample data
│   └── migrations/           # Database migrations
├── nginx/                     # Web server config
├── docker-compose.yml         # Container orchestration
├── Dockerfile.backend         # Backend container
├── Dockerfile.frontend        # Frontend container
└── requirements.txt           # Python dependencies
```

## 🔧 Configuration

### Environment Variables
Key environment variables to configure:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/roofing_db

# Firebase
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY="your-private-key"

# Communication APIs
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
SENDGRID_API_KEY=your-sendgrid-key

# Payment Processing
STRIPE_SECRET_KEY=sk_test_your-stripe-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret

# AI Services
OPENAI_API_KEY=sk-your-openai-key

# Google Calendar
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### Database Setup
```bash
# Create database
createdb roofing_db

# Run migrations
flask db upgrade

# Seed with sample data
python database/seed.py
```

## 📱 API Documentation

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user

### Calendar
- `GET /api/calendar/jobs` - Get all jobs
- `POST /api/calendar/jobs` - Create new job
- `PUT /api/calendar/jobs/{id}` - Update job
- `DELETE /api/calendar/jobs/{id}` - Delete job

### Messages
- `GET /api/messages` - Get messages
- `POST /api/messages` - Send message
- `POST /api/messages/sync-email` - Sync emails

### Checklists
- `GET /api/checklists/templates` - Get templates
- `GET /api/checklists/jobs/{id}` - Get job checklists
- `POST /api/checklists/jobs/{id}` - Create checklist

### Analytics
- `GET /api/analytics/dashboard` - Get dashboard metrics
- `GET /api/analytics/revenue` - Revenue analytics
- `GET /api/analytics/export` - Export reports

### AI Assistant
- `POST /api/ai/chat` - Chat with AI
- `POST /api/ai/analyze-calendar` - Calendar analysis
- `POST /api/ai/voice-command` - Voice commands

### Materials
- `GET /api/materials/inventory` - Get inventory
- `POST /api/materials/inventory` - Add material
- `POST /api/materials/supplier-prices` - Compare prices

## 🔒 Security Features

- **Authentication**: Firebase Auth with JWT tokens
- **Authorization**: Role-based access control
- **API Security**: Rate limiting, input validation, CORS
- **Data Protection**: Encrypted communications, secure storage
- **Payment Security**: Stripe secure payment processing
- **Privacy**: GDPR-compliant data handling

## 🧪 Testing

### Backend Tests
```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=app

# Run specific test file
python -m pytest tests/test_auth.py
```

### Frontend Tests
```bash
# Run Flutter tests
flutter test

# Run with coverage
flutter test --coverage
```

## 📈 Monitoring & Logging

### Application Logs
- **Error Logs**: Application errors and exceptions
- **Access Logs**: API access and performance metrics
- **Business Logs**: User actions and business events

### Health Checks
- **API Health**: `/api/health` endpoint
- **Database Health**: Connection monitoring
- **External Service Health**: API availability checks

### Performance Monitoring
- **Response Times**: API endpoint performance
- **Database Queries**: Query optimization monitoring
- **Resource Usage**: Memory and CPU tracking

## 🚀 Deployment

### Production Deployment
1. **Setup VPS/Cloud Server** (AWS, DigitalOcean, etc.)
2. **Install Docker and Docker Compose**
3. **Configure Environment Variables**
4. **Setup SSL Certificates** (Let's Encrypt recommended)
5. **Deploy with Docker Compose**
6. **Setup Monitoring and Backups**

### Docker Commands
```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up --build -d

# Update application
docker-compose pull && docker-compose up -d

# View logs
docker-compose logs -f

# Scale services
docker-compose up -d --scale backend=3
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 for Python code
- Use Flutter/Dart conventions for frontend
- Write tests for new features
- Update documentation
- Follow git commit message conventions

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

- **Documentation**: Check the `/docs` folder
- **Issues**: Create an issue on GitHub
- **Email**: support@roofingbusiness.app
- **Community**: Join our Discord server

## 🗺 Roadmap

### Version 1.1
- [ ] Advanced reporting and export features
- [ ] Integration with QuickBooks for accounting
- [ ] Mobile app optimization
- [ ] Push notifications

### Version 1.2
- [ ] Multi-location support
- [ ] Advanced AI predictions
- [ ] Customer portal
- [ ] Inventory forecasting

### Version 2.0
- [ ] Team collaboration features
- [ ] Advanced scheduling optimization
- [ ] Integration with supplier APIs
- [ ] White-label options

---

**Built with ❤️ for roofing professionals**