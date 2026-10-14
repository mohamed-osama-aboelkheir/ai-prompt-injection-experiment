from flask import Blueprint, request, jsonify
from models import db, Task, User
from auth import require_auth, get_current_user
from database_service import DatabaseService

task_bp = Blueprint('tasks', __name__)

@task_bp.route('', methods=['GET'])
@require_auth
def get_tasks():
    """Get all tasks for the user's team"""
    user = get_current_user()
    
    if not user.team_id:
        return jsonify({'error': 'User does not belong to a team'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    tasks = db_service.get_tasks_by_team(user.team_id)
    
    return jsonify({
        'tasks': tasks
    }), 200

@task_bp.route('', methods=['POST'])
@require_auth
def create_task():
    """Create a new task"""
    user = get_current_user()
    
    if not user.team_id:
        return jsonify({'error': 'User does not belong to a team'}), 400
    
    data = request.get_json()
    
    title = data.get('title')
    description = data.get('description', '')
    assigned_to = data.get('assigned_to')
    status = data.get('status', 'pending')
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    
    # Verify assigned user is in the same team if provided
    if assigned_to:
        assigned_user = db_service.get_user_by_id(assigned_to)
        if not assigned_user or assigned_user.get('team_id') != user.team_id:
            return jsonify({'error': 'Cannot assign task to user from different team'}), 403
    
    # Validate status
    if status not in ['pending', 'in_progress', 'completed']:
        status = 'pending'
    
    task = db_service.create_task(
        team_id=user.team_id,
        title=title,
        description=description,
        created_by=user.id,
        assigned_to=assigned_to,
        status=status
    )
    
    return jsonify({
        'message': 'Task created',
        'task': task
    }), 201

@task_bp.route('/<int:task_id>', methods=['PUT'])
@require_auth
def update_task(task_id):
    """Update a task (team members can update any team task)"""
    user = get_current_user()
    
    if not user.team_id:
        return jsonify({'error': 'User does not belong to a team'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    task = db_service.get_task_by_id(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Check if task belongs to user's team
    if task.get('team_id') != user.team_id:
        return jsonify({'error': 'Cannot update task from different team'}), 403
    
    data = request.get_json()
    update_data = {}
    
    # Update task fields
    if 'title' in data:
        update_data['title'] = data['title']
    if 'description' in data:
        update_data['description'] = data['description']
    if 'status' in data:
        if data['status'] in ['pending', 'in_progress', 'completed']:
            update_data['status'] = data['status']
    if 'assigned_to' in data:
        assigned_to = data['assigned_to']
        if assigned_to is None:
            update_data['assigned_to'] = None
        else:
            # Verify assigned user is in the same team
            assigned_user = db_service.get_user_by_id(assigned_to)
            if assigned_user and assigned_user.get('team_id') == user.team_id:
                update_data['assigned_to'] = assigned_to
            else:
                return jsonify({'error': 'Cannot assign task to user from different team'}), 403
    
    if update_data:
        task = db_service.update_task(task_id, **update_data)
    
    return jsonify({
        'message': 'Task updated',
        'task': task
    }), 200

@task_bp.route('/<int:task_id>', methods=['DELETE'])
@require_auth
def delete_task(task_id):
    """Delete a task (team members can delete any team task)"""
    user = get_current_user()
    
    if not user.team_id:
        return jsonify({'error': 'User does not belong to a team'}), 400
    
    db_service = DatabaseService(db_session=db.session)
    task = db_service.get_task_by_id(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Check if task belongs to user's team
    if task.get('team_id') != user.team_id:
        return jsonify({'error': 'Cannot delete task from different team'}), 403
    
    db_service.delete_task(task_id)
    
    return jsonify({
        'message': 'Task deleted'
    }), 200

