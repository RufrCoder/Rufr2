"""
Payment Processing Routes
Stripe integration for subscription management and billing
"""

import os
import stripe
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models import db, User, Subscription

bp = Blueprint('payments', __name__)

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Subscription plans configuration
SUBSCRIPTION_PLANS = {
    'monthly': {
        'price_id': os.getenv('STRIPE_MONTHLY_PRICE_ID'),
        'amount': 1999,  # $19.99 in cents
        'currency': 'usd',
        'interval': 'month',
        'trial_period_days': 14,
        'features': [
            'Unlimited job scheduling',
            'Message hub integration',
            'Checklist management',
            'Basic analytics',
            'Email support'
        ]
    },
    'yearly': {
        'price_id': os.getenv('STRIPE_YEARLY_PRICE_ID'),
        'amount': 16900,  # $169.00 in cents
        'currency': 'usd',
        'interval': 'year',
        'trial_period_days': 14,
        'features': [
            'Unlimited job scheduling',
            'Message hub integration',
            'Checklist management',
            'Advanced analytics',
            'AI-powered automation',
            'Priority support',
            '30% savings vs monthly'
        ]
    },
    'lifetime': {
        'price_id': os.getenv('STRIPE_LIFETIME_PRICE_ID'),
        'amount': 149900,  # $1499.00 in cents
        'currency': 'usd',
        'interval': 'one_time',
        'features': [
            'Lifetime access to all features',
            'Unlimited job scheduling',
            'Message hub integration',
            'Checklist management',
            'Advanced analytics',
            'AI-powered automation',
            'Voice commands (experimental)',
            'Priority support',
            'Free future updates'
        ]
    }
}

@bp.route('/plans', methods=['GET'])
def get_subscription_plans():
    """Get available subscription plans"""
    try:
        return jsonify({
            'plans': SUBSCRIPTION_PLANS
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch plans: {str(e)}'}), 500

@bp.route('/create-checkout-session', methods=['POST'])
@jwt_required()
def create_checkout_session():
    """Create Stripe checkout session for subscription"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        plan_type = data.get('plan_type')
        if not plan_type or plan_type not in SUBSCRIPTION_PLANS:
            return jsonify({'error': 'Invalid plan type'}), 400

        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        plan = SUBSCRIPTION_PLANS[plan_type]

        # For lifetime plan (one-time payment)
        if plan_type == 'lifetime':
            checkout_params = {
                'payment_method_types': ['card'],
                'line_items': [{
                    'price': plan['price_id'],
                    'quantity': 1,
                }],
                'mode': 'payment',
                'success_url': request.host_url + 'payment/success?session_id={CHECKOUT_SESSION_ID}',
                'cancel_url': request.host_url + 'payment/cancelled',
                'customer_email': user.email,
                'metadata': {
                    'user_id': str(current_user_id),
                    'plan_type': plan_type
                }
            }
        else:
            # For recurring subscriptions
            checkout_params = {
                'payment_method_types': ['card'],
                'line_items': [{
                    'price': plan['price_id'],
                    'quantity': 1,
                }],
                'mode': 'subscription',
                'success_url': request.host_url + 'payment/success?session_id={CHECKOUT_SESSION_ID}',
                'cancel_url': request.host_url + 'payment/cancelled',
                'customer_email': user.email,
                'subscription_data': {
                    'trial_period_days': plan['trial_period_days'],
                    'metadata': {
                        'user_id': str(current_user_id),
                        'plan_type': plan_type
                    }
                }
            }

        session = stripe.checkout.Session.create(**checkout_params)

        return jsonify({
            'checkout_session_id': session.id,
            'checkout_url': session.url
        })

    except Exception as e:
        current_app.logger.error(f"Stripe checkout session creation failed: {e}")
        return jsonify({'error': f'Failed to create checkout session: {str(e)}'}), 500

@bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    try:
        payload = request.data
        sig_header = request.headers.get('STRIPE_SIGNATURE')
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

        if not webhook_secret:
            current_app.logger.error("Stripe webhook secret not configured")
            return jsonify({'error': 'Webhook secret not configured'}), 500

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            current_app.logger.error(f"Webhook error: {e}")
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError as e:
            current_app.logger.error(f"Webhook signature verification failed: {e}")
            return jsonify({'error': 'Invalid signature'}), 400

        # Handle different event types
        if event['type'] == 'checkout.session.completed':
            handle_checkout_session_completed(event['data']['object'])
        elif event['type'] == 'invoice.payment_succeeded':
            handle_invoice_payment_succeeded(event['data']['object'])
        elif event['type'] == 'invoice.payment_failed':
            handle_invoice_payment_failed(event['data']['object'])
        elif event['type'] == 'customer.subscription.deleted':
            handle_subscription_deleted(event['data']['object'])
        elif event['type'] == 'payment_intent.succeeded':
            handle_payment_intent_succeeded(event['data']['object'])

        return jsonify({'status': 'success'})

    except Exception as e:
        current_app.logger.error(f"Webhook processing failed: {e}")
        return jsonify({'error': 'Webhook processing failed'}), 500

@bp.route('/subscription', methods=['GET'])
@jwt_required()
def get_subscription():
    """Get current user's subscription status"""
    try:
        current_user_id = get_jwt_identity()

        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        subscription = Subscription.query.filter_by(user_id=current_user_id).first()

        subscription_data = None
        if subscription:
            # Get latest subscription data from Stripe if it's an active subscription
            stripe_subscription = None
            if subscription.stripe_subscription_id:
                try:
                    stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                except Exception as stripe_error:
                    current_app.logger.error(f"Failed to retrieve Stripe subscription: {stripe_error}")

            subscription_data = {
                'id': str(subscription.id),
                'plan_type': subscription.plan_type,
                'status': subscription.status,
                'current_period_start': subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                'current_period_end': subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                'cancel_at_period_end': subscription.cancel_at_period_end,
                'stripe_subscription_id': subscription.stripe_subscription_id,
                'features': SUBSCRIPTION_PLANS.get(subscription.plan_type, {}).get('features', [])
            }

            # Update with real Stripe data if available
            if stripe_subscription:
                subscription_data.update({
                    'status': stripe_subscription['status'],
                    'current_period_start': datetime.fromtimestamp(stripe_subscription['current_period_start'], tz=timezone.utc).isoformat(),
                    'current_period_end': datetime.fromtimestamp(stripe_subscription['current_period_end'], tz=timezone.utc).isoformat(),
                    'cancel_at_period_end': stripe_subscription['cancel_at_period_end']
                })

        return jsonify({
            'subscription_plan': user.subscription_plan,
            'subscription': subscription_data
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch subscription: {str(e)}'}), 500

@bp.route('/subscription/cancel', methods=['POST'])
@jwt_required()
def cancel_subscription():
    """Cancel user's subscription"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        cancel_immediately = data.get('immediately', False)

        subscription = Subscription.query.filter_by(user_id=current_user_id).first()
        if not subscription or not subscription.stripe_subscription_id:
            return jsonify({'error': 'No active subscription found'}), 404

        # Cancel in Stripe
        if cancel_immediately:
            stripe_subscription = stripe.Subscription.delete(subscription.stripe_subscription_id)
            subscription.status = 'cancelled'
            user = User.query.get(current_user_id)
            user.subscription_plan = 'cancelled'
        else:
            stripe_subscription = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            subscription.cancel_at_period_end = True

        subscription.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            'message': 'Subscription cancelled successfully',
            'effective_date': (
                datetime.fromtimestamp(stripe_subscription['current_period_end'], tz=timezone.utc).isoformat()
                if not cancel_immediately else 'immediately'
            )
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to cancel subscription: {str(e)}'}), 500

@bp.route('/subscription/reactivate', methods=['POST'])
@jwt_required()
def reactivate_subscription():
    """Reactivate cancelled subscription"""
    try:
        current_user_id = get_jwt_identity()

        subscription = Subscription.query.filter_by(user_id=current_user_id).first()
        if not subscription or not subscription.stripe_subscription_id:
            return jsonify({'error': 'No subscription found to reactivate'}), 404

        # Reactivate in Stripe
        stripe_subscription = stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=False
        )

        subscription.cancel_at_period_end = False
        subscription.status = 'active'
        subscription.updated_at = datetime.now(timezone.utc)

        # Update user subscription plan
        user = User.query.get(current_user_id)
        user.subscription_plan = subscription.plan_type

        db.session.commit()

        return jsonify({
            'message': 'Subscription reactivated successfully',
            'subscription': {
                'status': 'active',
                'current_period_end': datetime.fromtimestamp(
                    stripe_subscription['current_period_end'], tz=timezone.utc
                ).isoformat()
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to reactivate subscription: {str(e)}'}), 500

@bp.route('/billing-history', methods=['GET'])
@jwt_required()
def get_billing_history():
    """Get user's billing history"""
    try:
        current_user_id = get_jwt_identity()

        # Get user's subscription
        subscription = Subscription.query.filter_by(user_id=current_user_id).first()
        if not subscription:
            return jsonify({'billing_history': []})

        billing_history = []

        if subscription.stripe_subscription_id:
            try:
                # Get invoices from Stripe
                invoices = stripe.Invoice.list(subscription=subscription.stripe_subscription_id, limit=50)

                for invoice in invoices['data']:
                    billing_history.append({
                        'id': invoice.id,
                        'date': datetime.fromtimestamp(invoice.created, tz=timezone.utc).isoformat(),
                        'amount': invoice.amount_paid / 100,  # Convert from cents
                        'currency': invoice.currency.upper(),
                        'status': invoice.status,
                        'description': invoice.description,
                        'invoice_url': invoice.hosted_invoice_url
                    })

            except Exception as stripe_error:
                current_app.logger.error(f"Failed to fetch billing history from Stripe: {stripe_error}")

        return jsonify({
            'billing_history': billing_history
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch billing history: {str(e)}'}), 500

@bp.route('/usage-limits', methods=['GET'])
@jwt_required()
def get_usage_limits():
    """Get current usage limits for user's plan"""
    try:
        current_user_id = get_jwt_identity()

        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get current usage statistics
        from app.models import Job, Message

        current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        jobs_this_month = Job.query.filter(
            Job.user_id == current_user_id,
            Job.created_at >= current_month_start
        ).count()

        messages_this_month = Message.query.join(Job).filter(
            Job.user_id == current_user_id,
            Message.created_at >= current_month_start
        ).count()

        # Define limits based on subscription plan
        if user.subscription_plan == 'trial':
            limits = {
                'jobs_per_month': 10,
                'messages_per_month': 100,
                'ai_features': False,
                'advanced_analytics': False
            }
        elif user.subscription_plan in ['monthly', 'yearly', 'lifetime']:
            limits = {
                'jobs_per_month': float('inf'),  # Unlimited
                'messages_per_month': float('inf'),  # Unlimited
                'ai_features': True,
                'advanced_analytics': True
            }
        else:
            limits = {
                'jobs_per_month': 0,
                'messages_per_month': 0,
                'ai_features': False,
                'advanced_analytics': False
            }

        return jsonify({
            'current_usage': {
                'jobs_this_month': jobs_this_month,
                'messages_this_month': messages_this_month
            },
            'limits': limits,
            'subscription_plan': user.subscription_plan
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch usage limits: {str(e)}'}), 500

# Webhook event handlers
def handle_checkout_session_completed(session):
    """Handle successful checkout session"""
    try:
        user_id = session.get('metadata', {}).get('user_id')
        plan_type = session.get('metadata', {}).get('plan_type')

        if not user_id or not plan_type:
            current_app.logger.error("Missing metadata in checkout session")
            return

        user = User.query.get(user_id)
        if not user:
            current_app.logger.error(f"User not found: {user_id}")
            return

        # Update user subscription plan
        user.subscription_plan = plan_type

        # Create or update subscription record
        subscription = Subscription.query.filter_by(user_id=user_id).first()

        if session['mode'] == 'subscription':
            # Recurring subscription
            if not subscription:
                subscription = Subscription(user_id=user_id)
                db.session.add(subscription)

            subscription.plan_type = plan_type
            subscription.stripe_subscription_id = session.get('subscription')
            subscription.status = 'active'
            subscription.cancel_at_period_end = False

            # Get subscription details from Stripe
            stripe_subscription = stripe.Subscription.retrieve(session['subscription'])
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription['current_period_start'], tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription['current_period_end'], tz=timezone.utc
            )

        elif session['mode'] == 'payment':
            # One-time payment (lifetime plan)
            if not subscription:
                subscription = Subscription(user_id=user_id)
                db.session.add(subscription)

            subscription.plan_type = plan_type
            subscription.status = 'active'
            subscription.current_period_end = None  # No expiry for lifetime

        db.session.commit()

    except Exception as e:
        current_app.logger.error(f"Checkout session completion error: {e}")
        db.session.rollback()

def handle_invoice_payment_succeeded(invoice):
    """Handle successful invoice payment"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return

        # Update subscription in database
        subscription = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first()
        if subscription:
            subscription.status = 'active'
            subscription.updated_at = datetime.now(timezone.utc)
            db.session.commit()

    except Exception as e:
        current_app.logger.error(f"Invoice payment success handling error: {e}")

def handle_invoice_payment_failed(invoice):
    """Handle failed invoice payment"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return

        # Update subscription in database
        subscription = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first()
        if subscription:
            subscription.status = 'past_due'
            subscription.updated_at = datetime.now(timezone.utc)
            db.session.commit()

    except Exception as e:
        current_app.logger.error(f"Invoice payment failure handling error: {e}")

def handle_subscription_deleted(subscription):
    """Handle subscription deletion"""
    try:
        # Update subscription in database
        db_subscription = Subscription.query.filter_by(stripe_subscription_id=subscription.id).first()
        if db_subscription:
            db_subscription.status = 'cancelled'
            db_subscription.updated_at = datetime.now(timezone.utc)

            # Update user subscription plan
            user = User.query.get(db_subscription.user_id)
            if user:
                user.subscription_plan = 'cancelled'

            db.session.commit()

    except Exception as e:
        current_app.logger.error(f"Subscription deletion handling error: {e}")

def handle_payment_intent_succeeded(payment_intent):
    """Handle successful payment (for one-time purchases like lifetime plan)"""
    try:
        # This handles lifetime plan payments
        user_id = payment_intent.get('metadata', {}).get('user_id')
        plan_type = payment_intent.get('metadata', {}).get('plan_type')

        if user_id and plan_type == 'lifetime':
            user = User.query.get(user_id)
            if user:
                user.subscription_plan = 'lifetime'
                db.session.commit()

    except Exception as e:
        current_app.logger.error(f"Payment intent success handling error: {e}")