from flask import Blueprint, request, jsonify
from models import db, User, Team, InvitationCode
from auth import hash_password, verify_password, generate_token, require_auth, get_current_user
from database_service import DatabaseService

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user as team admin and create a team"""
    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    team_name = data.get('team_name')
    
    if not email or not password or not team_name:
        return jsonify({'error': 'Email, password, and team name are required'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    
    # Check if user already exists
    if db_service.get_user_by_email(email):
        return jsonify({'error': 'User with this email already exists'}), 400
    
    # Create team without invitation code (codes are generated on-demand)
    team = db_service.create_team(name=team_name)
    db_service.flush()  # Get team ID
    
    # Create user as admin
    password_hash = hash_password(password)
    user = db_service.create_user(
        email=email,
        password_hash=password_hash,
        team_id=team['id'],
        role='admin'
    )
    db_service.flush()  # Get user ID
    
    # Update team created_by
    team = db_service.update_team(team['id'], created_by=user['id'])
    
    db_service.commit()
    
    token = generate_token(user['id'])
    
    return jsonify({
        'token': token,
        'user': user,
        'team': team
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login and get JWT token"""
    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    user_dict = db_service.get_user_by_email(email)
    
    if not user_dict:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Need to get password_hash for verification - use ORM for this
    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    token = generate_token(user_dict['id'])
    
    return jsonify({
        'token': token,
        'user': user_dict
    }), 200

@auth_bp.route('/join-with-code', methods=['POST'])
def join_with_invitation_code():
    """Join a team using invitation code - handles registration/login and joining in one step"""
    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    invitation_code = data.get('invitation_code')
    
    if not email or not password or not invitation_code:
        return jsonify({'error': 'Email, password, and invitation code are required'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    
    # Find invitation code (check both used and unused to prevent information disclosure)
    inv_code = db_service.get_invitation_code_by_code(invitation_code)
    
    # Generic error message to prevent information disclosure
    # Don't reveal if code exists, is used, or email mismatch
    if not inv_code or inv_code.get('used') or inv_code.get('email', '').lower() != email.lower():
        return jsonify({'error': 'Invalid invitation code or email mismatch'}), 400
    
    team = db_service.get_team_by_id(inv_code['team_id'])
    
    if not team:
        return jsonify({'error': 'Team not found'}), 404
    
    # Check if user exists - need password_hash for verification, so use ORM
    user = User.query.filter_by(email=email).first()
    
    if user:
        # User exists - verify password
        if not verify_password(password, user.password_hash):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check if user already belongs to a team
        if user.team_id:
            return jsonify({'error': 'User already belongs to a team'}), 400
        
        # Add user to team
        user_dict = db_service.update_user(user.id, team_id=team['id'])
    else:
        # User doesn't exist - create new user and add to team
        password_hash = hash_password(password)
        user_dict = db_service.create_user(
            email=email,
            password_hash=password_hash,
            team_id=team['id'],
            role='member'
        )
    
    # Mark invitation code as used (single-use)
    db_service.mark_invitation_code_as_used(invitation_code)
    
    db_service.commit()
    
    # Generate token for the user
    token = generate_token(user_dict['id'])
    
    return jsonify({
        'message': 'Successfully joined team',
        'token': token,
        'user': user_dict,
        'team': team
    }), 200

