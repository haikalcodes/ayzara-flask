"""
Packing Record Model
====================
Model untuk tabel packing_records (existing dari terminal recorder)
"""

from datetime import datetime
import hashlib


import os

def init_packing_record_model(db):
    """Initialize PackingRecord model with database instance"""
    
    class PackingRecord(db.Model):
        """Model untuk tabel packing_records (existing dari terminal recorder)"""
        __tablename__ = 'packing_records'
        
        id = db.Column(db.Integer, primary_key=True)
        resi = db.Column(db.String(100), nullable=False)
        pegawai = db.Column(db.String(100), nullable=False)
        waktu_mulai = db.Column(db.DateTime, nullable=False)
        waktu_selesai = db.Column(db.DateTime)
        durasi_detik = db.Column(db.Integer)
        file_video = db.Column(db.String(500))
        status = db.Column(db.String(20), default='RECORDING')
        error_message = db.Column(db.Text)
        recorder_type = db.Column(db.String(20), default='ffmpeg')
        platform = db.Column(db.String(20), default='LAINNYA')
        file_size_kb = db.Column(db.Integer, default=0)
        json_metadata_path = db.Column(db.String(500))
        sha256_hash = db.Column(db.String(64))
        created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
        
        __table_args__ = (
            db.Index('idx_resi', 'resi'),
        )
        
        def to_dict(self):
            """Convert record to dictionary for JSON serialization"""
            # Calculate thumbnail name based on relative path
            video_path = self.file_video.replace('\\', '/') if self.file_video else ''
            thumb_name = ''
            if video_path:
                # Use MD5 hash of the path to ensure uniqueness
                path_hash = hashlib.md5(video_path.encode()).hexdigest()
                thumb_name = f"thumb_{path_hash}.jpg"

            # Check if actual file exists
            file_exists = False
            if self.file_video:
                # Handle both absolute and relative paths
                if os.path.isabs(self.file_video):
                    full_path = self.file_video
                else:
                    import config
                    full_path = os.path.join(config.RECORDINGS_FOLDER, self.file_video)
                
                if os.path.exists(full_path):
                    file_exists = True

            return {
                'id': self.id,
                'resi': self.resi,
                'pegawai': self.pegawai,
                'waktu_mulai': self.waktu_mulai.strftime('%Y-%m-%d %H:%M:%S') if self.waktu_mulai else None,
                'waktu_selesai': self.waktu_selesai.strftime('%Y-%m-%d %H:%M:%S') if self.waktu_selesai else None,
                'durasi_detik': self.durasi_detik,
                'file_video': self.file_video,
                'thumbnail_name': thumb_name,
                'status': self.status,
                'platform': self.platform,
                'file_size_kb': self.file_size_kb,
                'file_exists': file_exists
            }
    
    return PackingRecord
