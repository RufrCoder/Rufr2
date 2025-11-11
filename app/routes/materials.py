"""
Materials Management Routes
Inventory tracking, auto-ordering, and supplier management
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from bs4 import BeautifulSoup

from app.models import db, Material, Shipment, Job

bp = Blueprint('materials', __name__)

# Mock supplier APIs (in production, these would be real integrations)
SUPPLIER_APIS = {
    'home_depot': {
        'base_url': 'https://www.homedepot.com/s/',
        'search_endpoint': 'https://www.homedepot.com/s/',
        'headers': {'User-Agent': 'Mozilla/5.0'}
    },
    'lowes': {
        'base_url': 'https://www.lowes.com/search',
        'search_endpoint': 'https://www.lowes.com/search',
        'headers': {'User-Agent': 'Mozilla/5.0'}
    }
}

@bp.route('/inventory', methods=['GET'])
@jwt_required()
def get_materials_inventory():
    """Get materials inventory"""
    try:
        current_user_id = get_jwt_identity()

        # Query parameters
        low_stock = request.args.get('low_stock', 'false').lower() == 'true'
        supplier = request.args.get('supplier')

        query = Material.query.filter_by(user_id=current_user_id)

        if low_stock:
            # Filter for materials with stock below minimum
            query = query.filter(
                Material.current_stock <= Material.minimum_stock
            )

        if supplier:
            query = query.filter(Material.supplier == supplier)

        materials = query.order_by(Material.material_name).all()

        return jsonify({
            'materials': [
                {
                    'id': str(material.id),
                    'material_name': material.material_name,
                    'supplier': material.supplier,
                    'current_stock': material.current_stock,
                    'minimum_stock': material.minimum_stock,
                    'unit_price': float(material.unit_price) if material.unit_price else None,
                    'unit_type': material.unit_type,
                    'last_ordered_at': material.last_ordered_at.isoformat() if material.last_ordered_at else None,
                    'auto_order_enabled': material.auto_order_enabled,
                    'stock_status': 'low' if material.current_stock <= material.minimum_stock else 'adequate',
                    'created_at': material.created_at.isoformat()
                }
                for material in materials
            ]
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch materials inventory: {str(e)}'}), 500

@bp.route('/inventory', methods=['POST'])
@jwt_required()
def add_material():
    """Add new material to inventory"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        # Validate required fields
        required_fields = ['material_name', 'current_stock', 'minimum_stock']
        for field in required_fields:
            if data.get(field) is None:
                return jsonify({'error': f'{field} is required'}), 400

        # Check if material already exists
        existing_material = Material.query.filter_by(
            user_id=current_user_id,
            material_name=data['material_name']
        ).first()

        if existing_material:
            return jsonify({'error': 'Material already exists in inventory'}), 400

        material = Material(
            user_id=current_user_id,
            material_name=data['material_name'],
            supplier=data.get('supplier'),
            current_stock=data['current_stock'],
            minimum_stock=data['minimum_stock'],
            unit_price=data.get('unit_price'),
            unit_type=data.get('unit_type', 'units'),
            auto_order_enabled=data.get('auto_order_enabled', False)
        )

        db.session.add(material)
        db.session.commit()

        return jsonify({
            'message': 'Material added successfully',
            'material': {
                'id': str(material.id),
                'material_name': material.material_name,
                'supplier': material.supplier,
                'current_stock': material.current_stock,
                'minimum_stock': material.minimum_stock,
                'unit_price': float(material.unit_price) if material.unit_price else None,
                'unit_type': material.unit_type,
                'auto_order_enabled': material.auto_order_enabled
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to add material: {str(e)}'}), 500

@bp.route('/materials/<material_id>', methods=['PUT'])
@jwt_required()
def update_material(material_id):
    """Update material information"""
    try:
        current_user_id = get_jwt_identity()

        material = Material.query.filter_by(id=material_id, user_id=current_user_id).first()
        if not material:
            return jsonify({'error': 'Material not found'}), 404

        data = request.get_json()

        # Update allowed fields
        updatable_fields = [
            'material_name', 'supplier', 'current_stock', 'minimum_stock',
            'unit_price', 'unit_type', 'auto_order_enabled'
        ]

        for field in updatable_fields:
            if field in data:
                setattr(material, field, data[field])

        material.updated_at = datetime.now(timezone.utc)

        # Check if auto-order should trigger
        if (material.auto_order_enabled and
            material.current_stock <= material.minimum_stock and
            data.get('trigger_auto_order', False)):

            # Schedule auto-order
            schedule_auto_order(material, current_user_id)

        db.session.commit()

        return jsonify({
            'message': 'Material updated successfully',
            'material': {
                'id': str(material.id),
                'material_name': material.material_name,
                'supplier': material.supplier,
                'current_stock': material.current_stock,
                'minimum_stock': material.minimum_stock,
                'unit_price': float(material.unit_price) if material.unit_price else None,
                'unit_type': material.unit_type,
                'auto_order_enabled': material.auto_order_enabled
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update material: {str(e)}'}), 500

@bp.route('/materials/<material_id>', methods=['DELETE'])
@jwt_required()
def delete_material(material_id):
    """Delete material from inventory"""
    try:
        current_user_id = get_jwt_identity()

        material = Material.query.filter_by(id=material_id, user_id=current_user_id).first()
        if not material:
            return jsonify({'error': 'Material not found'}), 404

        db.session.delete(material)
        db.session.commit()

        return jsonify({'message': 'Material deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete material: {str(e)}'}), 500

@bp.route('/shipments', methods=['GET'])
@jwt_required()
def get_shipments():
    """Get material shipments"""
    try:
        current_user_id = get_jwt_identity()

        status = request.args.get('status')  # ordered, shipped, delivered, cancelled

        query = Shipment.query.filter_by(user_id=current_user_id)

        if status:
            query = query.filter(Shipment.status == status)

        shipments = query.order_by(Shipment.created_at.desc()).all()

        return jsonify({
            'shipments': [
                {
                    'id': str(shipment.id),
                    'material_id': str(shipment.material_id),
                    'material_name': shipment.material.material_name if shipment.material else None,
                    'supplier': shipment.supplier,
                    'quantity': shipment.quantity,
                    'tracking_number': shipment.tracking_number,
                    'status': shipment.status,
                    'expected_delivery': shipment.expected_delivery.isoformat() if shipment.expected_delivery else None,
                    'actual_delivery': shipment.actual_delivery.isoformat() if shipment.actual_delivery else None,
                    'created_at': shipment.created_at.isoformat()
                }
                for shipment in shipments
            ]
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch shipments: {str(e)}'}), 500

@bp.route('/shipments/<shipment_id>', methods=['PUT'])
@jwt_required()
def update_shipment(shipment_id):
    """Update shipment status"""
    try:
        current_user_id = get_jwt_identity()

        shipment = Shipment.query.filter_by(id=shipment_id, user_id=current_user_id).first()
        if not shipment:
            return jsonify({'error': 'Shipment not found'}), 404

        data = request.get_json()

        if 'status' in data:
            shipment.status = data['status']

            if data['status'] == 'delivered':
                shipment.actual_delivery = datetime.now(timezone.utc)
                # Update material inventory
                if shipment.material:
                    shipment.material.current_stock += shipment.quantity

        if 'tracking_number' in data:
            shipment.tracking_number = data['tracking_number']

        db.session.commit()

        return jsonify({
            'message': 'Shipment updated successfully',
            'shipment': {
                'id': str(shipment.id),
                'status': shipment.status,
                'tracking_number': shipment.tracking_number,
                'actual_delivery': shipment.actual_delivery.isoformat() if shipment.actual_delivery else None
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update shipment: {str(e)}'}), 500

@bp.route('/supplier-prices', methods=['POST'])
@jwt_required()
def compare_supplier_prices():
    """Compare prices across suppliers"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        material_name = data.get('material_name')
        if not material_name:
            return jsonify({'error': 'Material name is required'}), 400

        # Search for prices across different suppliers
        price_comparisons = []

        for supplier_name, supplier_config in SUPPLIER_APIS.items():
            try:
                prices = search_supplier_prices(material_name, supplier_config)
                price_comparisons.extend(prices)
            except Exception as search_error:
                current_app.logger.error(f"Price search failed for {supplier_name}: {search_error}")
                continue

        # Sort by price (lowest first)
        price_comparisons.sort(key=lambda x: x['price'] if x['price'] else float('inf'))

        return jsonify({
            'material_name': material_name,
            'price_comparisons': price_comparisons[:10]  # Return top 10 results
        })

    except Exception as e:
        return jsonify({'error': f'Price comparison failed: {str(e)}'}), 500

@bp.route('/usage-report', methods=['GET'])
@jwt_required()
def get_materials_usage_report():
    """Get materials usage report"""
    try:
        current_user_id = get_jwt_identity()

        # Date range
        end_date = datetime.now(timezone.utc)
        start_date = request.args.get('start_date', (end_date - timedelta(days=90)).isoformat())
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))

        # Get completed jobs in date range
        completed_jobs = Job.query.filter(
            Job.user_id == current_user_id,
            Job.status == 'completed',
            Job.updated_at >= start_date,
            Job.updated_at <= end_date
        ).all()

        # Estimate material usage based on job types
        # This is a simplified calculation - in production, you'd track actual material usage
        usage_report = {}
        total_estimated_cost = 0

        for job in completed_jobs:
            estimated_materials = estimate_materials_for_job(job.job_type, job.estimated_price)
            for material, quantity in estimated_materials.items():
                if material not in usage_report:
                    usage_report[material] = {
                        'total_quantity': 0,
                        'job_count': 0,
                        'estimated_cost': 0
                    }

                usage_report[material]['total_quantity'] += quantity
                usage_report[material]['job_count'] += 1
                usage_report[material]['estimated_cost'] += quantity * 50  # Mock unit price

        total_estimated_cost = sum(material['estimated_cost'] for material in usage_report.values())

        return jsonify({
            'usage_report': usage_report,
            'summary': {
                'total_jobs': len(completed_jobs),
                'total_estimated_cost': total_estimated_cost,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }
        })

    except Exception as e:
        return jsonify({'error': f'Usage report failed: {str(e)}'}), 500

@bp.route('/auto-order-config', methods=['POST'])
@jwt_required()
def configure_auto_order():
    """Configure automatic ordering settings"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        material_id = data.get('material_id')
        enabled = data.get('enabled', False)
        order_quantity = data.get('order_quantity')
        reorder_threshold = data.get('reorder_threshold')

        if not material_id:
            return jsonify({'error': 'Material ID is required'}), 400

        material = Material.query.filter_by(id=material_id, user_id=current_user_id).first()
        if not material:
            return jsonify({'error': 'Material not found'}), 404

        material.auto_order_enabled = enabled
        if reorder_threshold is not None:
            material.minimum_stock = reorder_threshold

        db.session.commit()

        # Set up scheduler job if enabled
        if enabled:
            setup_auto_order_scheduler(material, current_user_id)

        return jsonify({
            'message': 'Auto-order configuration updated',
            'material': {
                'id': str(material.id),
                'auto_order_enabled': material.auto_order_enabled,
                'minimum_stock': material.minimum_stock
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Auto-order configuration failed: {str(e)}'}), 500

# Helper functions
def search_supplier_prices(material_name, supplier_config):
    """Search for material prices at supplier (mock implementation)"""
    try:
        # In production, integrate with real supplier APIs
        # For now, return mock data

        # Mock web scraping simulation
        search_url = f"{supplier_config['search_endpoint']}?q={material_name}"

        # Mock price data
        mock_prices = [
            {
                'supplier': supplier_config['base_url'].split('.')[1],
                'product_name': f"{material_name} - Premium Quality",
                'price': 49.99,
                'unit': 'sq ft',
                'in_stock': True,
                'url': search_url
            },
            {
                'supplier': supplier_config['base_url'].split('.')[1],
                'product_name': f"{material_name} - Standard Quality",
                'price': 39.99,
                'unit': 'sq ft',
                'in_stock': True,
                'url': search_url
            }
        ]

        return mock_prices

    except Exception as e:
        current_app.logger.error(f"Supplier price search error: {e}")
        return []

def estimate_materials_for_job(job_type, estimated_price):
    """Estimate material quantities needed for a job type"""
    # Simplified estimation - in production, use more sophisticated calculations
    base_materials = {
        'inspection': {'roofing nails': 100, 'safety harness': 1},
        'repair': {'shingles': 50, 'roofing cement': 5, 'nails': 200},
        'replacement': {'shingles': 500, 'underlayment': 10, 'nails': 1000},
        'gutter_installation': {'gutter sections': 20, 'downspouts': 4, 'brackets': 40}
    }

    return base_materials.get(job_type, {})

def schedule_auto_order(material, user_id):
    """Schedule automatic material ordering"""
    # In production, integrate with scheduling system and supplier APIs
    current_app.logger.info(f"Auto-order scheduled for material {material.material_name}")

def setup_auto_order_scheduler(material, user_id):
    """Set up recurring auto-order check"""
    # In production, integrate with APScheduler or similar
    pass

def check_inventory_levels():
    """Background job to check inventory levels and trigger auto-orders"""
    # This would run periodically to check for materials that need reordering
    # and automatically place orders if configured
    pass