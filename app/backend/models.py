from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets
import string

db = SQLAlchemy()

class Team(db.Model):
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', primaryjoin='Team.id == User.team_id', backref='team', lazy=True)
    tasks = db.relationship('Task', backref='team', lazy=True, cascade='all, delete-orphan')
    invitation_codes = db.relationship('InvitationCode', backref='team', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class InvitationCode(db.Model):
    __tablename__ = 'invitation_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(255), nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @staticmethod
    def generate_code():
        """Generate a random invitation code"""
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(8))
    
    def to_dict(self):
        return {
            'id': self.id,
            'team_id': self.team_id,
            'code': self.code,
            'email': self.email,
            'used': self.used,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    role = db.Column(db.Enum('admin', 'member', name='user_role'), default='member')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    created_tasks = db.relationship('Task', foreign_keys='Task.created_by', backref='creator', lazy=True)
    assigned_tasks = db.relationship('Task', foreign_keys='Task.assigned_to', backref='assignee', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'team_id': self.team_id,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.Enum('pending', 'in_progress', 'completed', name='task_status'), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'team_id': self.team_id,
            'title': self.title,
            'description': self.description,
            'assigned_to': self.assigned_to,
            'created_by': self.created_by,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

