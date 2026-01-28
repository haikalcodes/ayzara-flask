"""
Main Routes Blueprint
=====================
Routes for dashboard, monitoring, videos, and team management

📁 Copy to: dashboard_flask_refactored/app/routes/main.py
"""

from flask import Blueprint, render_template, request, send_from_directory
from flask_login import login_required, current_user
from app.utils import admin_required
from app.services import StatsService
from app.models import db, PackingRecord, Pegawai
import config

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    """Homepage - Dashboard overview"""
    stats_service = StatsService(db, PackingRecord)
    
    # --- ADMIN DASHBOARD ---
    if current_user.role == 'admin':
        stats = stats_service.get_today_stats()
        
        # Get active recording
        active = None  # TODO: Implement with RecordingService
        
        # Recent recordings (Global)
        recent = PackingRecord.query.order_by(
            PackingRecord.waktu_mulai.desc()
        ).limit(10).all()
        
        return render_template('pages/dashboard.html',
            stats=stats,
            active_recording=active,
            recent_recordings=[r.to_dict() for r in recent],
            platforms=config.PLATFORMS
        )
    
    # --- EMPLOYEE DASHBOARD ---
    else:
        # Get stats specific to this user/pegawai
        # Need to implement logic to filter stats by pegawai name
        username = current_user.username
        
        # Get today's stats for this user
        # Note: We need to filter manually or extend StatsService. 
        # For simplicity, let's query directly here for now.
        from datetime import datetime
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        base_query = PackingRecord.query.filter(
            PackingRecord.waktu_mulai >= today_start,
            PackingRecord.pegawai == username  # Assuming username matches pegawai name
        )
        
        
        # Count UNIQUE resi (packages), not total records
        total = base_query.with_entities(PackingRecord.resi).distinct().count()
        completed = base_query.filter_by(status='COMPLETED').with_entities(PackingRecord.resi).distinct().count()
        
        # Avg Duration
        completed_records = base_query.filter_by(status='COMPLETED').all()
        total_duration = sum(r.durasi_detik or 0 for r in completed_records)
        avg_duration = round(total_duration / len(completed_records)) if completed_records else 0
        
        # All Time Stats
        total_recordings_all_time = PackingRecord.query.filter_by(
            pegawai=username,
            status='COMPLETED'
        ).count()
        
        # Unique Resi (Packages)
        # Using distinct count on resi
        total_packages_all_time = PackingRecord.query.with_entities(
            PackingRecord.resi
        ).filter_by(
            pegawai=username,
            status='COMPLETED'
        ).distinct().count()

        user_stats = {
            'total': total,
            'completed': completed,
            'avg_duration': avg_duration,
            'total_recordings_all_time': total_recordings_all_time,
            'total_packages_all_time': total_packages_all_time
        }
        
        # Recent recordings (Personal)
        recent = PackingRecord.query.filter_by(pegawai=username).order_by(
            PackingRecord.waktu_mulai.desc()
        ).limit(5).all()
        
        # Custom Date Formatter for Indonesian
        now = datetime.now()
        days_id = {'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu', 'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'}
        months_id = {'January': 'Januari', 'February': 'Februari', 'March': 'Maret', 'April': 'April', 'May': 'Mei', 'June': 'Juni', 'July': 'Juli', 'August': 'Agustus', 'September': 'September', 'October': 'Oktober', 'November': 'November', 'December': 'Desember'}
        
        day_name = days_id[now.strftime('%A')]
        day_date = now.strftime('%d')
        month_name = months_id[now.strftime('%B')]
        year = now.strftime('%Y')
        time_str = now.strftime('%H:%M')
        
        # Format: "Rabu, 28 Januari 2026 | 12:14"
        current_time = f"{day_name}, {day_date} {month_name} {year} | {time_str}"
        
        return render_template('pages/employee_dashboard.html',
            user_stats=user_stats,
            recent_recordings=[r.to_dict() for r in recent],
            current_time=current_time,
            platforms=config.PLATFORMS
        )


@main_bp.route('/monitoring')
@login_required
@admin_required
def monitoring():
    """Live monitoring page"""
    stats_service = StatsService(db, PackingRecord)
    stats = stats_service.get_today_stats()
    active = None  # TODO: Implement with RecordingService
    
    return render_template('pages/monitoring.html',
        active_recording=active,
        stats=stats
    )


@main_bp.route('/videos')
@login_required
def videos():
    """Video gallery page"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    platform = request.args.get('platform', '')
    pegawai = request.args.get('pegawai', '')
    
    query = PackingRecord.query.filter_by(status='COMPLETED')
    
    # Filters
    if search:
        query = query.filter(
            db.or_(
                PackingRecord.resi.ilike(f'%{search}%'),
                PackingRecord.pegawai.ilike(f'%{search}%')
            )
        )
        
    if platform:
        query = query.filter(PackingRecord.platform == platform)
        
    if pegawai:
        query = query.filter(PackingRecord.pegawai == pegawai)
        
    # Order by date desc
    pagination = query.order_by(
        PackingRecord.waktu_mulai.desc()
    ).paginate(page=page, per_page=12, error_out=False)
    
    # Get list of pegawai for filter
    pegawai_list = db.session.query(PackingRecord.pegawai).distinct().order_by(PackingRecord.pegawai).all()
    pegawai_list = [p[0] for p in pegawai_list if p[0]]
    
    return render_template('pages/videos.html',
        recordings=[r.to_dict() for r in pagination.items],
        pagination=pagination,
        platforms=config.PLATFORMS,
        current_platform=platform,
        current_pegawai=pegawai,
        search=search,
        pegawai_list=pegawai_list
    )


@main_bp.route('/team')
@login_required
@admin_required
def team():
    """Team/Pegawai management page"""
    page = request.args.get('page', 1, type=int)
    
    pagination = Pegawai.query.order_by(Pegawai.nama).paginate(
        page=page, per_page=12, error_out=False
    )
    
    pegawai_list = pagination.items
    
    # Stats per pegawai
    pegawai_stats = {}
    for p in pegawai_list:
        # Count unique resi per pegawai
        count = PackingRecord.query.filter_by(
            pegawai=p.nama,
            status='COMPLETED'
        ).with_entities(PackingRecord.resi).distinct().count()
        pegawai_stats[p.id] = count
    
    return render_template('pages/team.html',
        pegawai_list=[p.to_dict() for p in pegawai_list],
        pagination=pagination,
        pegawai_stats=pegawai_stats
    )


@main_bp.route('/statistics')
@login_required
@admin_required
def statistics():
    """Statistics page with charts"""
    stats_service = StatsService(db, PackingRecord)
    
    weekly_data = stats_service.get_weekly_stats()
    platform_data = stats_service.get_platform_stats(config.PLATFORMS)
    leaderboard = stats_service.get_pegawai_leaderboard()
    
    return render_template('pages/statistics.html',
        stats=stats_service.get_today_stats(),
        weekly_data=weekly_data,
        platform_data=platform_data,
        leaderboard=leaderboard
    )


@main_bp.route('/help')
@login_required
def help_page():
    """Help/Manual page"""
    return render_template('pages/help.html')


@main_bp.route('/developer')
@login_required
def developer():
    """Developer info page"""
    return render_template('pages/developer.html',
        app_version=config.APP_VERSION,
        app_author=config.APP_AUTHOR
    )


@main_bp.route('/coming-soon/<feature>')
def coming_soon(feature):
    """Coming soon pages"""
    features = {
        'track-resi': {'title': 'Lacak Resi', 'icon': '📍', 'desc': 'Lacak status pengiriman resi'},
        'ai-features': {'title': 'Fitur AI', 'icon': '🤖', 'desc': 'Fitur AI untuk otomasi'},
        'edit-rekaman': {'title': 'Edit Rekaman', 'icon': '✂️', 'desc': 'Edit hasil rekaman video'},
        'boost-ads': {'title': 'Iklan Boost', 'icon': '📢', 'desc': 'Iklan dan promosi otomatis'},
        'competitor': {'title': 'Kompetitor', 'icon': '🔍', 'desc': 'Analisa kompetitor'},
        'ai-tryon': {'title': 'AI TRY ON', 'icon': '👗', 'desc': 'AI Try On/Pose/Poster'}
    }
    
    feature_info = features.get(feature, {
        'title': 'Segera Hadir',
        'icon': '🚀',
        'desc': 'Fitur dalam pengembangan'
    })
    
    return render_template('pages/coming_soon.html',
        feature=feature_info
    )


# ============================================
# STATIC FILE SERVING
# ============================================

@main_bp.route('/photos/<path:filename>')
def serve_photos(filename):
    """Serve photo uploads"""
    return send_from_directory(config.PHOTOS_FOLDER, filename)

@main_bp.route('/thumbnails/<path:filename>')
def serve_thumbnails(filename):
    """Serve video thumbnails"""
    return send_from_directory(config.THUMBNAILS_FOLDER, filename)

@main_bp.route('/recordings/<path:filename>')
def serve_recordings(filename):
    """Serve video recordings"""
    return send_from_directory(config.RECORDINGS_FOLDER, filename)

