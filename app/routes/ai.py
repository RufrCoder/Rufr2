"""
AI Agent Routes
Intelligent automation, materials management, and voice commands
"""

import os
import json
import speech_recognition as sr
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import openai
from apscheduler.schedulers.background import BackgroundScheduler

from app.models import db, AIConversation, Job, Material, Shipment, User, Checklist

bp = Blueprint('ai', __name__)

# Initialize OpenAI client
openai.api_key = os.getenv('OPENAI_API_KEY')

# Initialize scheduler for automated tasks
scheduler = BackgroundScheduler()
scheduler.start()

# AI Agent contexts and prompts
CALENDAR_ANALYSIS_PROMPT = """
You are an AI assistant for a roofing business. Analyze the provided calendar data and provide insights about:
1. Scheduling conflicts or potential issues
2. Optimal job scheduling recommendations
3. Weather-related considerations
4. Workload balancing among jobs
5. Material ordering needs based on upcoming jobs

Calendar data: {calendar_data}
"""

MATERIALS_ANALYSIS_PROMPT = """
You are an AI assistant for roofing materials management. Analyze the current inventory and upcoming jobs to:
1. Predict material needs for the next 30 days
2. Identify materials that need reordering
3. Suggest optimal ordering quantities
4. Find cost-saving opportunities
5. Recommend suppliers based on pricing and availability

Current inventory: {materials_data}
Upcoming jobs: {jobs_data}
"""

CUSTOMER_COMMUNICATION_PROMPT = """
You are an AI assistant for customer communication in a roofing business. Generate professional, friendly responses to customer inquiries:
1. Provide accurate information about roofing services
2. Address common questions and concerns
3. Schedule appointments when needed
4. Explain technical concepts in simple terms
5. Maintain professional and helpful tone

Customer inquiry: {customer_message}
Context: {context}
"""

@bp.route('/chat', methods=['POST'])
@jwt_required()
def ai_chat():
    """Chat with AI assistant"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        message = data.get('message', '')
        context = data.get('context', {})
        session_id = data.get('session_id', f"session_{current_user_id}_{datetime.now().timestamp()}")

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        # Save user message
        user_conversation = AIConversation(
            user_id=current_user_id,
            session_id=session_id,
            message_type='user_query',
            content=message,
            context=context
        )
        db.session.add(user_conversation)

        # Get conversation history for context
        recent_conversations = AIConversation.query.filter_by(
            user_id=current_user_id,
            session_id=session_id
        ).order_by(AIConversation.created_at.desc()).limit(10).all()

        # Build conversation context
        conversation_history = []
        for conv in reversed(recent_conversations[-5:]):  # Last 5 exchanges
            role = 'user' if conv.message_type == 'user_query' else 'assistant'
            conversation_history.append({
                'role': role,
                'content': conv.content
            })

        try:
            # Get user's business context
            user = User.query.get(current_user_id)
            user_context = {
                'company_name': user.company_name,
                'subscription_plan': user.subscription_plan,
                'upcoming_jobs': get_upcoming_jobs_summary(current_user_id)
            }

            # Construct system prompt
            system_prompt = f"""
            You are a helpful AI assistant for {user_context['company_name']}, a roofing business.
            Your role is to help manage scheduling, customer communication, materials ordering, and business operations.
            Be professional, friendly, and provide practical advice for roofing business management.
            """

            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *conversation_history,
                    {"role": "user", "content": message}
                ],
                max_tokens=500,
                temperature=0.7
            )

            ai_response = response.choices[0].message.content

            # Save AI response
            ai_conversation = AIConversation(
                user_id=current_user_id,
                session_id=session_id,
                message_type='ai_response',
                content=ai_response,
                context=context
            )
            db.session.add(ai_conversation)
            db.session.commit()

            return jsonify({
                'response': ai_response,
                'session_id': session_id
            })

        except Exception as openai_error:
            current_app.logger.error(f"OpenAI API error: {openai_error}")

            # Fallback response
            fallback_response = "I'm having trouble connecting to my AI services right now. Please try again later or contact support if the issue persists."

            # Save fallback response
            fallback_conversation = AIConversation(
                user_id=current_user_id,
                session_id=session_id,
                message_type='ai_response',
                content=fallback_response,
                context={'error': str(openai_error)}
            )
            db.session.add(fallback_conversation)
            db.session.commit()

            return jsonify({
                'response': fallback_response,
                'session_id': session_id
            })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'AI chat failed: {str(e)}'}), 500

@bp.route('/analyze-calendar', methods=['POST'])
@jwt_required()
def analyze_calendar():
    """AI analysis of calendar and scheduling"""
    try:
        current_user_id = get_jwt_identity()

        # Get upcoming jobs
        upcoming_jobs = Job.query.filter(
            Job.user_id == current_user_id,
            Job.scheduled_start >= datetime.now(timezone.utc),
            Job.scheduled_start <= datetime.now(timezone.utc) + timedelta(days=30)
        ).order_by(Job.scheduled_start).all()

        calendar_data = {
            'jobs': [
                {
                    'customer_name': job.customer_name,
                    'job_type': job.job_type,
                    'scheduled_start': job.scheduled_start.isoformat(),
                    'scheduled_end': job.scheduled_end.isoformat(),
                    'estimated_price': float(job.estimated_price) if job.estimated_price else None,
                    'status': job.status.value
                }
                for job in upcoming_jobs
            ]
        }

        # Get AI analysis
        try:
            prompt = CALENDAR_ANALYSIS_PROMPT.format(calendar_data=json.dumps(calendar_data, indent=2))

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI assistant specialized in roofing business scheduling and optimization."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.3
            )

            analysis = response.choices[0].message.content

            # Extract actionable recommendations
            recommendations = extract_recommendations(analysis)

            return jsonify({
                'analysis': analysis,
                'recommendations': recommendations,
                'calendar_data': calendar_data
            })

        except Exception as openai_error:
            current_app.logger.error(f"Calendar analysis error: {openai_error}")
            return jsonify({'error': 'AI analysis temporarily unavailable'}), 500

    except Exception as e:
        return jsonify({'error': f'Calendar analysis failed: {str(e)}'}), 500

@bp.route('/analyze-materials', methods=['POST'])
@jwt_required()
def analyze_materials():
    """AI analysis of materials inventory and needs"""
    try:
        current_user_id = get_jwt_identity()

        # Get current materials inventory
        materials = Material.query.filter_by(user_id=current_user_id).all()

        # Get upcoming jobs that might require materials
        upcoming_jobs = Job.query.filter(
            Job.user_id == current_user_id,
            Job.scheduled_start >= datetime.now(timezone.utc),
            Job.scheduled_start <= datetime.now(timezone.utc) + timedelta(days=30)
        ).all()

        materials_data = {
            'inventory': [
                {
                    'material_name': material.material_name,
                    'current_stock': material.current_stock,
                    'minimum_stock': material.minimum_stock,
                    'unit_price': float(material.unit_price) if material.unit_price else None,
                    'auto_order_enabled': material.auto_order_enabled
                }
                for material in materials
            ]
        }

        jobs_data = {
            'upcoming_jobs': [
                {
                    'job_type': job.job_type,
                    'estimated_price': float(job.estimated_price) if job.estimated_price else None,
                    'scheduled_start': job.scheduled_start.isoformat()
                }
                for job in upcoming_jobs
            ]
        }

        # Get AI analysis
        try:
            prompt = MATERIALS_ANALYSIS_PROMPT.format(
                materials_data=json.dumps(materials_data, indent=2),
                jobs_data=json.dumps(jobs_data, indent=2)
            )

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI assistant specialized in roofing materials management and inventory optimization."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.3
            )

            analysis = response.choices[0].message.content

            # Extract material ordering recommendations
            order_recommendations = extract_material_recommendations(analysis)

            return jsonify({
                'analysis': analysis,
                'order_recommendations': order_recommendations,
                'materials_data': materials_data
            })

        except Exception as openai_error:
            current_app.logger.error(f"Materials analysis error: {openai_error}")
            return jsonify({'error': 'AI analysis temporarily unavailable'}), 500

    except Exception as e:
        return jsonify({'error': f'Materials analysis failed: {str(e)}'}), 500

@bp.route('/order-materials', methods=['POST'])
@jwt_required()
def auto_order_materials():
    """Automatically order materials based on AI recommendations"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        material_id = data.get('material_id')
        quantity = data.get('quantity', 1)
        confirm_order = data.get('confirm_order', False)

        if not material_id:
            return jsonify({'error': 'Material ID is required'}), 400

        # Get material
        material = Material.query.filter_by(id=material_id, user_id=current_user_id).first()
        if not material:
            return jsonify({'error': 'Material not found'}), 404

        if not confirm_order:
            # Return order confirmation request
            return jsonify({
                'confirmation_required': True,
                'order_details': {
                    'material_name': material.material_name,
                    'current_stock': material.current_stock,
                    'minimum_stock': material.minimum_stock,
                    'proposed_quantity': quantity,
                    'estimated_cost': float(material.unit_price * quantity) if material.unit_price else None,
                    'supplier': material.supplier
                }
            })

        # Process the order
        try:
            # In a real implementation, integrate with supplier APIs
            order_result = process_material_order(material, quantity, current_user_id)

            # Create shipment record
            shipment = Shipment(
                user_id=current_user_id,
                material_id=material.id,
                supplier=material.supplier,
                quantity=quantity,
                status='ordered',
                expected_delivery=datetime.now(timezone.utc) + timedelta(days=3)  # Estimated delivery
            )

            db.session.add(shipment)

            # Update material stock (optimistically)
            material.current_stock += quantity
            material.last_ordered_at = datetime.now(timezone.utc)

            db.session.commit()

            return jsonify({
                'message': 'Material order placed successfully',
                'order_details': {
                    'shipment_id': str(shipment.id),
                    'material_name': material.material_name,
                    'quantity': quantity,
                    'supplier': material.supplier,
                    'expected_delivery': shipment.expected_delivery.isoformat()
                }
            })

        except Exception as order_error:
            db.session.rollback()
            return jsonify({'error': f'Order processing failed: {str(order_error)}'}), 500

    except Exception as e:
        return jsonify({'error': f'Material ordering failed: {str(e)}'}), 500

@bp.route('/voice-command', methods=['POST'])
@jwt_required()
def voice_command():
    """Process voice commands (experimental)"""
    try:
        current_user_id = get_jwt_identity()

        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']

        # Transcribe audio
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)

        try:
            # Use speech recognition
            text = recognizer.recognize_google(audio_data)
        except sr.UnknownValueError:
            return jsonify({'error': 'Could not understand audio'}), 400
        except sr.RequestError as e:
            return jsonify({'error': f'Speech recognition error: {e}'}), 500

        # Process command
        command_result = process_voice_command(text, current_user_id)

        # Save voice command interaction
        conversation = AIConversation(
            user_id=current_user_id,
            session_id='voice_commands',
            message_type='voice_command',
            content=f"Voice: {text}",
            context={'transcription': text, 'command_result': command_result}
        )
        db.session.add(conversation)
        db.session.commit()

        return jsonify({
            'transcription': text,
            'command_result': command_result
        })

    except Exception as e:
        return jsonify({'error': f'Voice command processing failed: {str(e)}'}), 500

@bp.route('/generate-response', methods=['POST'])
@jwt_required()
def generate_customer_response():
    """Generate AI-powered customer responses"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        customer_message = data.get('customer_message', '')
        response_type = data.get('response_type', 'general')  # quote, scheduling, general
        job_context = data.get('job_context', {})

        if not customer_message:
            return jsonify({'error': 'Customer message is required'}), 400

        # Get user context
        user = User.query.get(current_user_id)

        prompt = CUSTOMER_COMMUNICATION_PROMPT.format(
            customer_message=customer_message,
            context=json.dumps({
                'company_name': user.company_name,
                'response_type': response_type,
                'job_context': job_context
            })
        )

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional customer service representative for a roofing business. Be helpful, accurate, and friendly."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.6
            )

            ai_response = response.choices[0].message.content

            return jsonify({
                'generated_response': ai_response,
                'customer_message': customer_message,
                'response_type': response_type
            })

        except Exception as openai_error:
            current_app.logger.error(f"Response generation error: {openai_error}")
            return jsonify({'error': 'AI response generation temporarily unavailable'}), 500

    except Exception as e:
        return jsonify({'error': f'Response generation failed: {str(e)}'}), 500

# Helper functions
def get_upcoming_jobs_summary(user_id):
    """Get summary of upcoming jobs for AI context"""
    upcoming_jobs = Job.query.filter(
        Job.user_id == user_id,
        Job.scheduled_start >= datetime.now(timezone.utc),
        Job.scheduled_start <= datetime.now(timezone.utc) + timedelta(days=7)
    ).count()

    return f"{upcoming_jobs} jobs scheduled in the next 7 days"

def extract_recommendations(analysis_text):
    """Extract actionable recommendations from AI analysis"""
    # Simple extraction - in production, use more sophisticated NLP
    recommendations = []
    lines = analysis_text.split('\n')

    for line in lines:
        if any(keyword in line.lower() for keyword in ['recommend', 'suggest', 'should', 'consider']):
            recommendations.append(line.strip())

    return recommendations[:5]  # Return top 5 recommendations

def extract_material_recommendations(analysis_text):
    """Extract material ordering recommendations from AI analysis"""
    order_recommendations = []
    lines = analysis_text.split('\n')

    for line in lines:
        if any(keyword in line.lower() for keyword in ['order', 'reorder', 'stock', 'inventory']):
            order_recommendations.append(line.strip())

    return order_recommendations[:5]

def process_material_order(material, quantity, user_id):
    """Process material order with supplier (mock implementation)"""
    # In production, integrate with actual supplier APIs
    # For now, return a mock order result
    return {
        'order_id': f"ORD_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        'status': 'confirmed',
        'estimated_delivery': (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    }

def process_voice_command(text, user_id):
    """Process voice commands and return structured response"""
    text_lower = text.lower()

    # Simple command parsing - in production, use more sophisticated NLP
    if 'schedule' in text_lower and 'job' in text_lower:
        return {'command': 'schedule_job', 'action': 'Navigate to calendar scheduling'}
    elif 'order' in text_lower and 'material' in text_lower:
        return {'command': 'order_materials', 'action': 'Open materials ordering'}
    elif 'message' in text_lower or 'text' in text_lower:
        return {'command': 'send_message', 'action': 'Open message composer'}
    elif 'analytics' in text_lower or 'reports' in text_lower:
        return {'command': 'view_analytics', 'action': 'Navigate to analytics dashboard'}
    elif 'checklist' in text_lower:
        return {'command': 'view_checklists', 'action': 'Open checklist view'}
    else:
        return {'command': 'unknown', 'action': 'Voice command not recognized. Please try again.'}