"""
Models Package
==============
Database models for AYZARA Dashboard
"""

from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy instance
db = SQLAlchemy()

# Import model initializers
from .user import init_user_model
from .packing_record import init_packing_record_model
from .pegawai import init_pegawai_model

# Initialize models (will be called after db is bound to app)
User = None
PackingRecord = None
Pegawai = None


def init_models():
    """Initialize all models with the db instance"""
    global User, PackingRecord, Pegawai
    
    User = init_user_model(db)
    PackingRecord = init_packing_record_model(db)
    Pegawai = init_pegawai_model(db)
    
    return User, PackingRecord, Pegawai


__all__ = ['db', 'init_models', 'User', 'PackingRecord', 'Pegawai']
