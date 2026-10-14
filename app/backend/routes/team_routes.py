from flask import Blueprint, request, jsonify
from models import db, User, Team, InvitationCode
from auth import require_admin, require_auth, get_current_user
from database_service import DatabaseService

team_bp = Blueprint('team', __name__)

@team_bp.route('/invitation-codes', methods=['GET'])
@require_admin
def get_invitation_codes():
    """Get all invitation codes for the team (admin only)"""
    user = get_current_user()
    
    if not user.team_id:
        return jsonify({'error': 'User does not belong to a team'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    codes = db_service.get_invitation_codes_by_team(user.team_id)
    
    return jsonify({
        'invitation_codes': codes
    }), 200

@team_bp.route('/invitation-code', methods=['POST'])
@require_admin
def generate_invitation_code():
    """Generate a new email-specific invitation code (admin only)"""
    user = get_current_user()
    data = request.get_json()
    
    if not user.team_id:
        return jsonify({'error': 'User does not belong to a team'}), 400
    
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email is required to generate invitation code'}), 400
    
    # Validate email format
    if '@' not in email or '.' not in email.split('@')[1]:
        return jsonify({'error': 'Invalid email format'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    
    # Check if there's already an unused code for this email
    existing_code = db_service.get_unused_invitation_code_by_email(user.team_id, email)
    
    if existing_code:
        return jsonify({
            'invitation_code': existing_code,
            'message': 'Existing unused invitation code for this email'
        }), 200
    
    # Generate new invitation code
    from models import InvitationCode
    new_code = InvitationCode.generate_code()
    # Ensure uniqueness
    while db_service.check_invitation_code_exists(new_code):
        new_code = InvitationCode.generate_code()
    
    # Create new invitation code
    inv_code = db_service.create_invitation_code(
        team_id=user.team_id,
        code=new_code,
        email=email,
        created_by=user.id
    )
    
    return jsonify({
        'invitation_code': inv_code,
        'message': 'New invitation code generated'
    }), 200

@team_bp.route('/promote', methods=['PUT'])
@require_admin
def promote_user():
    """Promote a user to admin role (admin only)"""
    user = get_current_user()
    data = request.get_json()
    
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    
    # Get the user to promote
    user_to_promote = db_service.get_user_by_id(user_id)
    
    if not user_to_promote:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if user is in the same team
    if user_to_promote.get('team_id') != user.team_id:
        return jsonify({'error': 'Cannot promote user from different team'}), 403
    
    # Promote to admin
    user_to_promote = db_service.update_user(user_id, role='admin')
    
    return jsonify({
        'message': 'User promoted to admin',
        'user': user_to_promote
    }), 200

@team_bp.route('/members', methods=['GET'])
@require_auth
def get_team_members():
    """Get all team members (any authenticated user can see their team members)"""
    user = get_current_user()
    
    if not user.team_id:
        return jsonify({'error': 'User does not belong to a team'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    members = db_service.get_users_by_team(user.team_id)
    
    return jsonify({
        'members': members
    }), 200

