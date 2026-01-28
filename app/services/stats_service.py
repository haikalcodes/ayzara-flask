"""
Statistics Service
==================
Business logic for statistics and analytics
"""

from datetime import datetime, timedelta


class StatsService:
    """Service for handling statistics and analytics"""
    
    def __init__(self, db, packing_record_model):
        """
        Initialize stats service
        
        Args:
            db: SQLAlchemy database instance
            packing_record_model: PackingRecord model class
        """
        self.db = db
        self.PackingRecord = packing_record_model
    
    def get_today_stats(self):
        """
        Get statistics for today
        
        Returns:
            Dictionary containing today's statistics
        """
        today = datetime.now().date()
        
        # Count UNIQUE resi (packages), not total records
        total = self.PackingRecord.query.filter(
            self.db.func.date(self.PackingRecord.waktu_mulai) == today
        ).with_entities(self.PackingRecord.resi).distinct().count()
        
        completed = self.PackingRecord.query.filter(
            self.db.func.date(self.PackingRecord.waktu_mulai) == today,
            self.PackingRecord.status == 'COMPLETED'
        ).with_entities(self.PackingRecord.resi).distinct().count()
        
        errors = self.PackingRecord.query.filter(
            self.db.func.date(self.PackingRecord.waktu_mulai) == today,
            self.PackingRecord.status == 'ERROR'
        ).with_entities(self.PackingRecord.resi).distinct().count()
        
        # Average duration
        avg_result = self.db.session.query(
            self.db.func.avg(self.PackingRecord.durasi_detik)
        ).filter(
            self.db.func.date(self.PackingRecord.waktu_mulai) == today,
            self.PackingRecord.durasi_detik.isnot(None)
        ).scalar()
        
        avg_duration = round(avg_result or 0, 1)
        
        # Total size
        size_result = self.db.session.query(
            self.db.func.sum(self.PackingRecord.file_size_kb)
        ).filter(
            self.db.func.date(self.PackingRecord.waktu_mulai) == today
        ).scalar()
        
        total_size_mb = round((size_result or 0) / 1024, 2)
        
        return {
            'total': total,
            'completed': completed,
            'errors': errors,
            'avg_duration': avg_duration,
            'total_size_mb': total_size_mb
        }
    
    def get_weekly_stats(self):
        """
        Get statistics for the past 7 days
        
        Returns:
            List of dictionaries containing daily statistics
        """
        weekly_data = []
        for i in range(7):
            date = datetime.now().date() - timedelta(days=i)
            # Count unique resi per day
            count = self.PackingRecord.query.filter(
                self.db.func.date(self.PackingRecord.waktu_mulai) == date
            ).with_entities(self.PackingRecord.resi).distinct().count()
            weekly_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'day': date.strftime('%a'),
                'count': count
            })
        weekly_data.reverse()
        return weekly_data
    
    def get_platform_stats(self, platforms):
        """
        Get statistics by platform
        
        Args:
            platforms: Dictionary of platform configurations
        
        Returns:
            List of dictionaries containing platform statistics
        """
        platform_data = []
        for platform in platforms.keys():
            # Count unique resi per platform
            count = self.PackingRecord.query.filter_by(
                platform=platform,
                status='COMPLETED'
            ).with_entities(self.PackingRecord.resi).distinct().count()
            platform_data.append({
                'platform': platform,
                'count': count,
                'color': platforms[platform]['color']
            })
        return platform_data
    
    def get_pegawai_leaderboard(self, limit=10):
        """
        Get top pegawai by recording count
        
        Args:
            limit: Maximum number of results
        
        Returns:
            List of tuples (pegawai_name, count)
        """
        # Count unique resi per pegawai (not total records)
        leaderboard = self.db.session.query(
            self.PackingRecord.pegawai,
            self.db.func.count(self.db.distinct(self.PackingRecord.resi)).label('count')
        ).filter_by(status='COMPLETED').group_by(
            self.PackingRecord.pegawai
        ).order_by(self.db.text('count DESC')).limit(limit).all()
        
        return leaderboard
