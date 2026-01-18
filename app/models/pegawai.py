"""
Pegawai Model
=============
Model untuk pegawai/team management
"""

from datetime import datetime


def init_pegawai_model(db):
    """Initialize Pegawai model with database instance"""
    
    class Pegawai(db.Model):
        """Model untuk pegawai/team"""
        __tablename__ = 'pegawai'
        
        id = db.Column(db.Integer, primary_key=True)
        nama = db.Column(db.String(100), nullable=False)
        photo = db.Column(db.String(500))  # Path ke foto
        jabatan = db.Column(db.String(100))
        telepon = db.Column(db.String(20))
        email = db.Column(db.String(100))
        alamat = db.Column(db.Text)
        is_active = db.Column(db.Boolean, default=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        def to_dict(self):
            """Convert pegawai to dictionary for JSON serialization"""
            return {
                'id': self.id,
                'nama': self.nama,
                'photo': self.photo,
                'jabatan': self.jabatan,
                'telepon': self.telepon,
                'email': self.email,
                'alamat': self.alamat,
                'is_active': self.is_active
            }
    
    return Pegawai
