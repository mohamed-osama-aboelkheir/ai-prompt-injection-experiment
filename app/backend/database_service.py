"""
Database service abstraction layer for all database operations.
Provides a unified interface for both SQLAlchemy (Flask routes) and psycopg2 (MCP server).
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from typing import Optional, List, Dict, Any
from datetime import datetime


class DatabaseService:
    """
    Database service class that abstracts all database interactions.
    Supports both SQLAlchemy (for Flask routes) and psycopg2 (for MCP server).
    """
    
    def __init__(self, db_session=None, db_connection=None):
        """
        Initialize database service.
        
        Args:
            db_session: SQLAlchemy session (for Flask routes)
            db_connection: psycopg2 connection (for MCP server)
        """
        self.db_session = db_session
        self.db_connection = db_connection
        self._use_orm = db_session is not None
    
    # ==================== User Operations ====================
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        if self._use_orm:
            from models import User
            user = self.db_session.query(User).get(user_id)
            return user.to_dict() if user else None
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, email, team_id, role, created_at FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()
                return dict(user) if user else None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        if self._use_orm:
            from models import User
            user = self.db_session.query(User).filter_by(email=email.lower()).first()
            return user.to_dict() if user else None
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, email, team_id, role, created_at FROM users WHERE email = %s", (email.lower(),))
                user = cur.fetchone()
                return dict(user) if user else None
    
    def create_user(self, email: str, password_hash: str, team_id: Optional[int] = None, 
                   role: str = 'member') -> Dict[str, Any]:
        """Create a new user"""
        if self._use_orm:
            from models import User
            user = User(
                email=email.lower(),
                password_hash=password_hash,
                team_id=team_id,
                role=role
            )
            self.db_session.add(user)
            self.db_session.flush()
            return user.to_dict()
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO users (email, password_hash, team_id, role)
                       VALUES (%s, %s, %s, %s)
                       RETURNING id, email, team_id, role, created_at""",
                    (email.lower(), password_hash, team_id, role)
                )
                user = cur.fetchone()
                self.db_connection.commit()
                return dict(user)
    
    def update_user(self, user_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Update user fields"""
        if self._use_orm:
            from models import User
            user = self.db_session.query(User).get(user_id)
            if not user:
                return None
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            self.db_session.commit()
            return user.to_dict()
        else:
            # Build update query dynamically using safe SQL composition
            allowed_fields = ['email', 'password_hash', 'team_id', 'role']
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in allowed_fields:
                    updates.append(sql.Identifier(key))
                    values.append(value)
            if not updates:
                return self.get_user_by_id(user_id)
            
            values.append(user_id)
            query = sql.SQL("UPDATE users SET {} WHERE id = %s RETURNING id, email, team_id, role, created_at").format(
                sql.SQL(", ").join(sql.SQL("{} = %s").format(field) for field in updates)
            )
            
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, values)
                user = cur.fetchone()
                self.db_connection.commit()
                return dict(user) if user else None
    
    def get_users_by_team(self, team_id: int) -> List[Dict[str, Any]]:
        """Get all users in a team"""
        if self._use_orm:
            from models import User
            users = self.db_session.query(User).filter_by(team_id=team_id).all()
            return [user.to_dict() for user in users]
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, email, team_id, role, created_at FROM users WHERE team_id = %s", (team_id,))
                users = cur.fetchall()
                return [dict(user) for user in users]
    
    # ==================== Team Operations ====================
    
    def get_team_by_id(self, team_id: int) -> Optional[Dict[str, Any]]:
        """Get team by ID"""
        if self._use_orm:
            from models import Team
            team = self.db_session.query(Team).get(team_id)
            return team.to_dict() if team else None
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, name, created_by, created_at FROM teams WHERE id = %s", (team_id,))
                team = cur.fetchone()
                return dict(team) if team else None
    
    def create_team(self, name: str, created_by: Optional[int] = None) -> Dict[str, Any]:
        """Create a new team"""
        if self._use_orm:
            from models import Team
            team = Team(name=name, created_by=created_by)
            self.db_session.add(team)
            self.db_session.flush()
            return team.to_dict()
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO teams (name, created_by)
                       VALUES (%s, %s)
                       RETURNING id, name, created_by, created_at""",
                    (name, created_by)
                )
                team = cur.fetchone()
                self.db_connection.commit()
                return dict(team)
    
    def update_team(self, team_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Update team fields"""
        if self._use_orm:
            from models import Team
            team = self.db_session.query(Team).get(team_id)
            if not team:
                return None
            for key, value in kwargs.items():
                if hasattr(team, key):
                    setattr(team, key, value)
            self.db_session.commit()
            return team.to_dict()
        else:
            # Build update query dynamically using safe SQL composition
            allowed_fields = ['name', 'created_by']
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in allowed_fields:
                    updates.append(sql.Identifier(key))
                    values.append(value)
            if not updates:
                return self.get_team_by_id(team_id)
            
            values.append(team_id)
            query = sql.SQL("UPDATE teams SET {} WHERE id = %s RETURNING id, name, created_by, created_at").format(
                sql.SQL(", ").join(sql.SQL("{} = %s").format(field) for field in updates)
            )
            
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, values)
                team = cur.fetchone()
                self.db_connection.commit()
                return dict(team) if team else None
    
    def get_all_teams(self) -> List[Dict[str, Any]]:
        """Get all teams"""
        if self._use_orm:
            from models import Team
            teams = self.db_session.query(Team).all()
            return [team.to_dict() for team in teams]
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, name, created_by, created_at FROM teams")
                teams = cur.fetchall()
                return [dict(team) for team in teams]
    
    # ==================== Task Operations ====================
    
    def get_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get task by ID"""
        if self._use_orm:
            from models import Task
            task = self.db_session.query(Task).get(task_id)
            return task.to_dict() if task else None
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT id, team_id, title, description, assigned_to, created_by, status, created_at, updated_at
                       FROM tasks WHERE id = %s""",
                    (task_id,)
                )
                task = cur.fetchone()
                return dict(task) if task else None
    
    def get_tasks_by_team(self, team_id: int) -> List[Dict[str, Any]]:
        """Get all tasks for a team"""
        if self._use_orm:
            from models import Task
            tasks = self.db_session.query(Task).filter_by(team_id=team_id).all()
            return [task.to_dict() for task in tasks]
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT id, team_id, title, description, assigned_to, created_by, status, created_at, updated_at
                       FROM tasks WHERE team_id = %s""",
                    (team_id,)
                )
                tasks = cur.fetchall()
                return [dict(task) for task in tasks]
    
    def create_task(self, team_id: int, title: str, description: str = "", 
                   created_by: int = None, assigned_to: Optional[int] = None, 
                   status: str = 'pending') -> Dict[str, Any]:
        """Create a new task"""
        if self._use_orm:
            from models import Task
            task = Task(
                team_id=team_id,
                title=title,
                description=description,
                created_by=created_by,
                assigned_to=assigned_to,
                status=status
            )
            self.db_session.add(task)
            self.db_session.commit()
            return task.to_dict()
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO tasks (team_id, title, description, created_by, assigned_to, status)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       RETURNING id, team_id, title, description, assigned_to, created_by, status, created_at, updated_at""",
                    (team_id, title, description, created_by, assigned_to, status)
                )
                task = cur.fetchone()
                self.db_connection.commit()
                return dict(task)
    
    def update_task(self, task_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Update task fields"""
        if self._use_orm:
            from models import Task
            task = self.db_session.query(Task).get(task_id)
            if not task:
                return None
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            # Update updated_at timestamp
            task.updated_at = datetime.utcnow()
            self.db_session.commit()
            return task.to_dict()
        else:
            # Build update query dynamically using safe SQL composition
            allowed_fields = ['title', 'description', 'assigned_to', 'status']
            field_updates = []
            values = []
            for key, value in kwargs.items():
                if key in allowed_fields:
                    field_updates.append(sql.Identifier(key))
                    values.append(value)
            
            # Always update updated_at
            all_updates = []
            for field in field_updates:
                all_updates.append(sql.SQL("{} = %s").format(field))
            all_updates.append(sql.SQL("updated_at = CURRENT_TIMESTAMP"))
            
            if not field_updates:
                # Even if no fields to update, we still update updated_at
                all_updates = [sql.SQL("updated_at = CURRENT_TIMESTAMP")]
            
            values.append(task_id)
            query = sql.SQL("""UPDATE tasks SET {} WHERE id = %s
                       RETURNING id, team_id, title, description, assigned_to, created_by, status, created_at, updated_at""").format(
                sql.SQL(", ").join(all_updates)
            )
            
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, values)
                task = cur.fetchone()
                self.db_connection.commit()
                return dict(task) if task else None
    
    def delete_task(self, task_id: int) -> bool:
        """Delete a task"""
        if self._use_orm:
            from models import Task
            task = self.db_session.query(Task).get(task_id)
            if not task:
                return False
            self.db_session.delete(task)
            self.db_session.commit()
            return True
        else:
            with self.db_connection.cursor() as cur:
                cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                deleted = cur.rowcount > 0
                self.db_connection.commit()
                return deleted
    
    # ==================== Invitation Code Operations ====================
    
    def get_invitation_code_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get invitation code by code string"""
        if self._use_orm:
            from models import InvitationCode
            inv_code = self.db_session.query(InvitationCode).filter_by(code=code).first()
            return inv_code.to_dict() if inv_code else None
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT id, team_id, code, email, used, created_by, created_at
                       FROM invitation_codes WHERE code = %s""",
                    (code,)
                )
                inv_code = cur.fetchone()
                return dict(inv_code) if inv_code else None
    
    def get_invitation_codes_by_team(self, team_id: int) -> List[Dict[str, Any]]:
        """Get all invitation codes for a team"""
        if self._use_orm:
            from models import InvitationCode
            codes = self.db_session.query(InvitationCode).filter_by(team_id=team_id).order_by(InvitationCode.created_at.desc()).all()
            return [code.to_dict() for code in codes]
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT id, team_id, code, email, used, created_by, created_at
                       FROM invitation_codes WHERE team_id = %s
                       ORDER BY created_at DESC""",
                    (team_id,)
                )
                codes = cur.fetchall()
                return [dict(code) for code in codes]
    
    def get_unused_invitation_code_by_email(self, team_id: int, email: str) -> Optional[Dict[str, Any]]:
        """Get unused invitation code for a specific email and team"""
        if self._use_orm:
            from models import InvitationCode
            inv_code = self.db_session.query(InvitationCode).filter_by(
                team_id=team_id,
                email=email.lower(),
                used=False
            ).first()
            return inv_code.to_dict() if inv_code else None
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT id, team_id, code, email, used, created_by, created_at
                       FROM invitation_codes
                       WHERE team_id = %s AND email = %s AND used = FALSE""",
                    (team_id, email.lower())
                )
                inv_code = cur.fetchone()
                return dict(inv_code) if inv_code else None
    
    def check_invitation_code_exists(self, code: str) -> bool:
        """Check if an invitation code exists"""
        if self._use_orm:
            from models import InvitationCode
            return self.db_session.query(InvitationCode).filter_by(code=code).first() is not None
        else:
            with self.db_connection.cursor() as cur:
                cur.execute("SELECT 1 FROM invitation_codes WHERE code = %s", (code,))
                return cur.fetchone() is not None
    
    def create_invitation_code(self, team_id: int, code: str, email: str, 
                              created_by: Optional[int] = None) -> Dict[str, Any]:
        """Create a new invitation code"""
        if self._use_orm:
            from models import InvitationCode
            inv_code = InvitationCode(
                team_id=team_id,
                code=code,
                email=email.lower(),
                created_by=created_by
            )
            self.db_session.add(inv_code)
            self.db_session.commit()
            return inv_code.to_dict()
        else:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO invitation_codes (team_id, code, email, created_by)
                       VALUES (%s, %s, %s, %s)
                       RETURNING id, team_id, code, email, used, created_by, created_at""",
                    (team_id, code, email.lower(), created_by)
                )
                inv_code = cur.fetchone()
                self.db_connection.commit()
                return dict(inv_code)
    
    def update_invitation_code(self, code_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Update invitation code fields"""
        if self._use_orm:
            from models import InvitationCode
            inv_code = self.db_session.query(InvitationCode).get(code_id)
            if not inv_code:
                return None
            for key, value in kwargs.items():
                if hasattr(inv_code, key):
                    setattr(inv_code, key, value)
            self.db_session.commit()
            return inv_code.to_dict()
        else:
            # Build update query dynamically using safe SQL composition
            allowed_fields = ['used', 'email']
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in allowed_fields:
                    updates.append(sql.Identifier(key))
                    values.append(value)
            if not updates:
                return None
            
            values.append(code_id)
            query = sql.SQL("""UPDATE invitation_codes SET {} WHERE id = %s
                       RETURNING id, team_id, code, email, used, created_by, created_at""").format(
                sql.SQL(", ").join(sql.SQL("{} = %s").format(field) for field in updates)
            )
            
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, values)
                inv_code = cur.fetchone()
                self.db_connection.commit()
                return dict(inv_code) if inv_code else None
    
    def mark_invitation_code_as_used(self, code: str) -> bool:
        """Mark an invitation code as used"""
        if self._use_orm:
            from models import InvitationCode
            inv_code = self.db_session.query(InvitationCode).filter_by(code=code).first()
            if not inv_code:
                return False
            inv_code.used = True
            self.db_session.commit()
            return True
        else:
            with self.db_connection.cursor() as cur:
                cur.execute("UPDATE invitation_codes SET used = TRUE WHERE code = %s", (code,))
                updated = cur.rowcount > 0
                self.db_connection.commit()
                return updated
    
    # ==================== Transaction Management ====================
    
    def commit(self):
        """Commit current transaction"""
        if self._use_orm:
            self.db_session.commit()
        else:
            self.db_connection.commit()
    
    def rollback(self):
        """Rollback current transaction"""
        if self._use_orm:
            self.db_session.rollback()
        else:
            self.db_connection.rollback()
    
    def flush(self):
        """Flush changes without committing (ORM only)"""
        if self._use_orm:
            self.db_session.flush()

