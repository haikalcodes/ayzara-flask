"""
User Model
==========
Model untuk user authentication dan authorization
"""

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


def init_user_model(db):
    """Initialize User model with database instance"""
    
    class User(UserMixin, db.Model):
        """Model untuk user authentication"""
        __tablename__ = 'users'
        
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(100), unique=True, nullable=False)
        password_hash = db.Column(db.String(255), nullable=False)
        role = db.Column(db.String(20), nullable=False)  # 'admin' or 'pegawai'
        pegawai_id = db.Column(db.Integer, db.ForeignKey('pegawai.id'), nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        # Relationship
        pegawai = db.relationship('Pegawai', backref='user', uselist=False)
        
        def set_password(self, password):
            """Hash and set password"""
            self.password_hash = generate_password_hash(password)
        
        def check_password(self, password):
            """Verify password against hash"""
            return check_password_hash(self.password_hash, password)
        
        def is_admin(self):
            """Check if user has admin role"""
            return self.role == 'admin'
    
    return User
