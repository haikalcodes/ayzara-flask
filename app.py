"""
AYZARA DASHBOARD - FLASK APPLICATION
=====================================
Main Flask Application with SocketIO for real-time updates

100% FREE - SELF-HOSTED
Created for AYZARA COLLECTIONS
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import config

# ============================================
# APP INITIALIZATION
# ============================================

app = Flask(__name__)
app.config.from_object(config)

# Database
db = SQLAlchemy(app)

# SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ============================================
# DATABASE MODELS
# ============================================

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'resi': self.resi,
            'pegawai': self.pegawai,
            'waktu_mulai': self.waktu_mulai.strftime('%Y-%m-%d %H:%M:%S') if self.waktu_mulai else None,
            'waktu_selesai': self.waktu_selesai.strftime('%Y-%m-%d %H:%M:%S') if self.waktu_selesai else None,
            'durasi_detik': self.durasi_detik,
            'file_video': self.file_video,
            'status': self.status,
            'platform': self.platform,
            'file_size_kb': self.file_size_kb
        }


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


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_today_stats():
    """Get statistics for today"""
    today = datetime.now().date()
    
    total = PackingRecord.query.filter(
        db.func.date(PackingRecord.waktu_mulai) == today
    ).count()
    
    completed = PackingRecord.query.filter(
        db.func.date(PackingRecord.waktu_mulai) == today,
        PackingRecord.status == 'COMPLETED'
    ).count()
    
    errors = PackingRecord.query.filter(
        db.func.date(PackingRecord.waktu_mulai) == today,
        PackingRecord.status == 'ERROR'
    ).count()
    
    # Average duration
    avg_result = db.session.query(
        db.func.avg(PackingRecord.durasi_detik)
    ).filter(
        db.func.date(PackingRecord.waktu_mulai) == today,
        PackingRecord.durasi_detik.isnot(None)
    ).scalar()
    
    avg_duration = round(avg_result or 0, 1)
    
    # Total size
    size_result = db.session.query(
        db.func.sum(PackingRecord.file_size_kb)
    ).filter(
        db.func.date(PackingRecord.waktu_mulai) == today
    ).scalar()
    
    total_size_mb = round((size_result or 0) / 1024, 2)
    
    return {
        'total': total,
        'completed': completed,
        'errors': errors,
        'avg_duration': avg_duration,
        'total_size_mb': total_size_mb
    }


def get_active_recording():
    """Get currently active recording"""
    record = PackingRecord.query.filter_by(
        status='RECORDING'
    ).order_by(PackingRecord.waktu_mulai.desc()).first()
    
    return record.to_dict() if record else None


# ============================================
# WEB ROUTES
# ============================================

@app.route('/')
def index():
    """Homepage - Dashboard overview"""
    stats = get_today_stats()
    active = get_active_recording()
    
    # Recent recordings
    recent = PackingRecord.query.order_by(
        PackingRecord.waktu_mulai.desc()
    ).limit(10).all()
    
    return render_template('pages/dashboard.html',
        stats=stats,
        active_recording=active,
        recent_recordings=[r.to_dict() for r in recent],
        platforms=config.PLATFORMS
    )


@app.route('/monitoring')
def monitoring():
    """Live monitoring page"""
    active = get_active_recording()
    stats = get_today_stats()
    
    return render_template('pages/monitoring.html',
        active_recording=active,
        stats=stats
    )


@app.route('/videos')
def videos():
    """Video gallery page"""
    page = request.args.get('page', 1, type=int)
    platform = request.args.get('platform', '')
    search = request.args.get('search', '')
    
    query = PackingRecord.query.filter_by(status='COMPLETED')
    
    if platform:
        query = query.filter_by(platform=platform)
    
    if search:
        query = query.filter(
            db.or_(
                PackingRecord.resi.contains(search),
                PackingRecord.pegawai.contains(search)
            )
        )
    
    # Pagination
    pagination = query.order_by(
        PackingRecord.waktu_mulai.desc()
    ).paginate(page=page, per_page=config.ITEMS_PER_PAGE, error_out=False)
    
    return render_template('pages/videos.html',
        recordings=[r.to_dict() for r in pagination.items],
        pagination=pagination,
        platforms=config.PLATFORMS,
        current_platform=platform,
        search=search
    )


@app.route('/team')
def team():
    """Team/Pegawai management page"""
    pegawai_list = Pegawai.query.order_by(Pegawai.nama).all()
    
    # Stats per pegawai
    pegawai_stats = {}
    for p in pegawai_list:
        count = PackingRecord.query.filter_by(
            pegawai=p.nama,
            status='COMPLETED'
        ).count()
        pegawai_stats[p.id] = count
    
    return render_template('pages/team.html',
        pegawai_list=[p.to_dict() for p in pegawai_list],
        pegawai_stats=pegawai_stats
    )


@app.route('/camera')
def camera():
    """Camera capture page"""
    return render_template('pages/camera.html',
        rtsp_url=config.DEFAULT_RTSP_URL
    )


@app.route('/statistics')
def statistics():
    """Statistics page with charts"""
    # Weekly stats
    weekly_data = []
    for i in range(7):
        date = datetime.now().date() - timedelta(days=i)
        count = PackingRecord.query.filter(
            db.func.date(PackingRecord.waktu_mulai) == date
        ).count()
        weekly_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'day': date.strftime('%a'),
            'count': count
        })
    weekly_data.reverse()
    
    # Platform stats
    platform_data = []
    for platform in config.PLATFORMS.keys():
        count = PackingRecord.query.filter_by(
            platform=platform,
            status='COMPLETED'
        ).count()
        platform_data.append({
            'platform': platform,
            'count': count,
            'color': config.PLATFORMS[platform]['color']
        })
    
    # Pegawai leaderboard
    leaderboard = db.session.query(
        PackingRecord.pegawai,
        db.func.count(PackingRecord.id).label('count')
    ).filter_by(status='COMPLETED').group_by(
        PackingRecord.pegawai
    ).order_by(db.text('count DESC')).limit(10).all()
    
    return render_template('pages/statistics.html',
        stats=get_today_stats(),
        weekly_data=weekly_data,
        platform_data=platform_data,
        leaderboard=leaderboard
    )


@app.route('/help')
def help_page():
    """Help/Manual page"""
    return render_template('pages/help.html')


@app.route('/developer')
def developer():
    """Developer info page"""
    return render_template('pages/developer.html',
        app_version=config.APP_VERSION,
        app_author=config.APP_AUTHOR
    )


@app.route('/coming-soon/<feature>')
def coming_soon(feature):
    """Coming soon pages"""
    features = {
        'track-resi': {'title': 'Track Resi', 'icon': '📍', 'desc': 'Lacak status pengiriman resi'},
        'ai-features': {'title': 'AI Features', 'icon': '🤖', 'desc': 'Fitur AI untuk otomasi'},
        'edit-rekaman': {'title': 'Edit Rekaman', 'icon': '✂️', 'desc': 'Edit hasil rekaman video'},
        'boost-ads': {'title': 'Boost Ads', 'icon': '📢', 'desc': 'Iklan dan promosi otomatis'},
        'competitor': {'title': 'Cek Kompetitor', 'icon': '🔍', 'desc': 'Analisa kompetitor'},
        'ai-tryon': {'title': 'AI TRY ON', 'icon': '👗', 'desc': 'AI Try On/Pose/Poster'}
    }
    
    feature_info = features.get(feature, {
        'title': 'Coming Soon',
        'icon': '🚀',
        'desc': 'Fitur dalam pengembangan'
    })
    
    return render_template('pages/coming_soon.html',
        feature=feature_info
    )


@app.route('/camera-settings')
def camera_settings():
    """Camera settings/management page"""
    return render_template('pages/camera_settings.html')


def _save_project_config(cfg):
    """Save config.json ke project utama"""
    try:
        if config.CONFIG_FILE.exists():
            with open(config.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            return True
    except Exception as e:
        print(f"Error saving config: {e}")
    return False


# ============================================
# API ROUTES
# ============================================

@app.route('/api/status')
def api_status():
    """Get current recording status"""
    active = get_active_recording()
    return jsonify({
        'is_recording': active is not None,
        'recording': active
    })


# ============================================
# CAMERA MANAGEMENT API
# ============================================

@app.route('/api/cameras', methods=['GET'])
def api_cameras_list():
    """Get list of all cameras from config"""
    project_cfg = _load_project_config()
    cameras = project_cfg.get('camera_list', [])
    active_index = project_cfg.get('active_camera_index', 0)
    
    return jsonify({
        'cameras': cameras,
        'active_index': active_index,
        'auto_fallback': project_cfg.get('camera_auto_fallback', True)
    })


@app.route('/api/cameras', methods=['POST'])
def api_cameras_add():
    """Add new camera to config"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Data tidak valid'}), 400
    
    name = data.get('name', '').strip()
    url = data.get('url', '').strip()
    enabled = data.get('enabled', True)
    
    if not name:
        return jsonify({'success': False, 'message': 'Nama kamera wajib diisi'}), 400
    if not url:
        return jsonify({'success': False, 'message': 'URL kamera wajib diisi'}), 400
    
    # Load config
    project_cfg = _load_project_config()
    cameras = project_cfg.get('camera_list', [])
    
    # Generate new ID
    max_id = max([c.get('id', 0) for c in cameras], default=0)
    new_id = max_id + 1
    
    # Add new camera
    new_camera = {
        'id': new_id,
        'name': name,
        'url': url,
        'enabled': enabled
    }
    cameras.append(new_camera)
    
    # Save
    project_cfg['camera_list'] = cameras
    if _save_project_config(project_cfg):
        return jsonify({'success': True, 'id': new_id, 'camera': new_camera})
    else:
        return jsonify({'success': False, 'message': 'Gagal menyimpan config'}), 500


@app.route('/api/cameras/<int:camera_id>', methods=['PUT'])
def api_cameras_update(camera_id):
    """Update camera in config"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Data tidak valid'}), 400
    
    # Load config
    project_cfg = _load_project_config()
    cameras = project_cfg.get('camera_list', [])
    
    # Find camera
    camera_idx = None
    for idx, cam in enumerate(cameras):
        if cam.get('id') == camera_id:
            camera_idx = idx
            break
    
    if camera_idx is None:
        return jsonify({'success': False, 'message': 'Kamera tidak ditemukan'}), 404
    
    # Update fields
    if 'name' in data:
        cameras[camera_idx]['name'] = data['name'].strip()
    if 'url' in data:
        cameras[camera_idx]['url'] = data['url'].strip()
    if 'enabled' in data:
        cameras[camera_idx]['enabled'] = data['enabled']
    
    # Save
    project_cfg['camera_list'] = cameras
    if _save_project_config(project_cfg):
        return jsonify({'success': True, 'camera': cameras[camera_idx]})
    else:
        return jsonify({'success': False, 'message': 'Gagal menyimpan config'}), 500


@app.route('/api/cameras/<int:camera_id>', methods=['DELETE'])
def api_cameras_delete(camera_id):
    """Delete camera from config"""
    # Load config
    project_cfg = _load_project_config()
    cameras = project_cfg.get('camera_list', [])
    
    # Find and remove camera
    original_len = len(cameras)
    cameras = [c for c in cameras if c.get('id') != camera_id]
    
    if len(cameras) == original_len:
        return jsonify({'success': False, 'message': 'Kamera tidak ditemukan'}), 404
    
    # Save
    project_cfg['camera_list'] = cameras
    if _save_project_config(project_cfg):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Gagal menyimpan config'}), 500


@app.route('/api/cameras/test', methods=['POST'])
def api_cameras_test():
    """Test camera connection"""
    import subprocess
    
    data = request.get_json()
    url = data.get('url', '') if data else ''
    
    if not url:
        return jsonify({'success': False, 'message': 'URL tidak valid'}), 400
    
    # Load FFmpeg path from config
    project_cfg = _load_project_config()
    ffmpeg_path = project_cfg.get('ffmpeg_path', 'ffmpeg')
    rtsp_transport = project_cfg.get('rtsp_transport', 'tcp')
    
    try:
        # Test connection with 2 second timeout
        cmd = [
            ffmpeg_path,
            '-rtsp_transport', rtsp_transport,
            '-i', url,
            '-t', '2',
            '-f', 'null',
            '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'Koneksi berhasil'})
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore')
            if 'Connection refused' in stderr:
                msg = 'Koneksi ditolak - periksa IP dan port'
            elif 'timeout' in stderr.lower():
                msg = 'Timeout - periksa koneksi jaringan'
            else:
                msg = f'Error (code {result.returncode})'
            return jsonify({'success': False, 'message': msg})
    
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Timeout (15 detik)'})
    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'FFmpeg tidak ditemukan'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})



@app.route('/api/stats/today')
def api_stats_today():
    """Get today's statistics"""
    return jsonify(get_today_stats())


@app.route('/api/recordings')
def api_recordings():
    """Get recordings list"""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    
    query = PackingRecord.query.order_by(
        PackingRecord.waktu_mulai.desc()
    )
    
    pagination = query.paginate(page=page, per_page=limit, error_out=False)
    
    return jsonify({
        'recordings': [r.to_dict() for r in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })


@app.route('/api/pegawai', methods=['GET', 'POST'])
def api_pegawai():
    """Get or create pegawai with validation"""
    if request.method == 'POST':
        data = request.form
        
        # Validasi nama (wajib)
        nama = data.get('nama', '').strip()
        if not nama:
            return jsonify({'success': False, 'error': 'Nama pegawai wajib diisi'}), 400
        if len(nama) < 2:
            return jsonify({'success': False, 'error': 'Nama minimal 2 karakter'}), 400
        if len(nama) > 100:
            return jsonify({'success': False, 'error': 'Nama maksimal 100 karakter'}), 400
        
        # Handle photo upload with validation
        photo_path = None
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename:
                # Validasi ukuran file (max 5MB)
                photo.seek(0, 2)
                size = photo.tell()
                photo.seek(0)
                if size > 5 * 1024 * 1024:
                    return jsonify({'success': False, 'error': 'Ukuran foto maksimal 5MB'}), 400
                
                # Validasi tipe file
                allowed_ext = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
                ext = photo.filename.rsplit('.', 1)[-1].lower() if '.' in photo.filename else ''
                if ext not in allowed_ext:
                    return jsonify({'success': False, 'error': 'Format foto harus JPG, PNG, GIF, atau WebP'}), 400
                
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo.filename}"
                photo_path = f"uploads/photos/{filename}"
                photo.save(config.PHOTOS_FOLDER / filename)
        
        pegawai = Pegawai(
            nama=nama,
            photo=photo_path,
            jabatan=data.get('jabatan'),
            telepon=data.get('telepon'),
            email=data.get('email'),
            alamat=data.get('alamat')
        )
        db.session.add(pegawai)
        db.session.commit()
        
        return jsonify({'success': True, 'id': pegawai.id})
    
    pegawai_list = Pegawai.query.order_by(Pegawai.nama).all()
    return jsonify([p.to_dict() for p in pegawai_list])


@app.route('/api/pegawai/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def api_pegawai_detail(id):
    """Get, update or delete pegawai"""
    pegawai = Pegawai.query.get_or_404(id)
    
    # GET - return single pegawai data
    if request.method == 'GET':
        return jsonify(pegawai.to_dict())
    
    if request.method == 'DELETE':
        db.session.delete(pegawai)
        db.session.commit()
        return jsonify({'success': True})
    
    # PUT - update with validation
    data = request.form
    
    # Validasi nama
    nama = data.get('nama', '').strip()
    if nama:
        if len(nama) < 2:
            return jsonify({'success': False, 'error': 'Nama minimal 2 karakter'}), 400
        if len(nama) > 100:
            return jsonify({'success': False, 'error': 'Nama maksimal 100 karakter'}), 400
        pegawai.nama = nama
    
    pegawai.jabatan = data.get('jabatan', pegawai.jabatan)
    pegawai.telepon = data.get('telepon', pegawai.telepon)
    pegawai.email = data.get('email', pegawai.email)
    pegawai.alamat = data.get('alamat', pegawai.alamat)
    
    # Handle photo upload with validation
    if 'photo' in request.files:
        photo = request.files['photo']
        if photo.filename:
            # Validasi ukuran file (max 5MB)
            photo.seek(0, 2)
            size = photo.tell()
            photo.seek(0)
            if size > 5 * 1024 * 1024:
                return jsonify({'success': False, 'error': 'Ukuran foto maksimal 5MB'}), 400
            
            # Validasi tipe file
            allowed_ext = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
            ext = photo.filename.rsplit('.', 1)[-1].lower() if '.' in photo.filename else ''
            if ext not in allowed_ext:
                return jsonify({'success': False, 'error': 'Format foto harus JPG, PNG, GIF, atau WebP'}), 400
            
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo.filename}"
            photo_path = f"uploads/photos/{filename}"
            photo.save(config.PHOTOS_FOLDER / filename)
            pegawai.photo = photo_path
    
    db.session.commit()
    return jsonify({'success': True})


def _load_project_config():
    """Load config.json dari project utama untuk RTSP dan FFmpeg settings"""
    try:
        if config.CONFIG_FILE.exists():
            with open(config.CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


@app.route('/api/camera/capture', methods=['POST'])
def api_camera_capture():
    """Capture frame from RTSP camera dengan config dinamis"""
    import subprocess
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"capture_{timestamp}.jpg"
    filepath = config.THUMBNAILS_FOLDER / filename
    
    # Load RTSP URL dan FFmpeg path dari config.json project utama
    project_config = _load_project_config()
    rtsp_url = project_config.get('rtsp_url', config.DEFAULT_RTSP_URL)
    rtsp_transport = project_config.get('rtsp_transport', 'tcp')
    ffmpeg_path = project_config.get('ffmpeg_path', config.FFMPEG_PATH)
    
    try:
        # Capture single frame using FFmpeg
        cmd = [
            ffmpeg_path,
            '-rtsp_transport', rtsp_transport,
            '-i', rtsp_url,
            '-frames:v', '1',
            '-q:v', '2',
            '-y',
            str(filepath)
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        
        if filepath.exists() and filepath.stat().st_size > 0:
            return jsonify({
                'success': True,
                'filename': filename,
                'path': f'/uploads/thumbnails/{filename}'
            })
        else:
            # Cek stderr untuk error message
            stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ''
            error_msg = 'Capture gagal'
            if 'Connection refused' in stderr:
                error_msg = 'Kamera tidak dapat dihubungi (Connection refused)'
            elif 'timeout' in stderr.lower():
                error_msg = 'Kamera timeout - periksa koneksi jaringan'
            elif 'No such file' in stderr:
                error_msg = 'FFmpeg tidak ditemukan - install FFmpeg terlebih dahulu'
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Kamera timeout (15 detik) - periksa RTSP URL dan koneksi jaringan'
        }), 500
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': 'FFmpeg tidak ditemukan - pastikan FFmpeg sudah terinstall (winget install ffmpeg)'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error: {str(e)}'
        }), 500


@app.route('/api/generate-thumbnail/<int:record_id>', methods=['POST'])
def api_generate_thumbnail(record_id):
    """Generate thumbnail dari video recording yang existing"""
    import subprocess
    
    record = PackingRecord.query.get_or_404(record_id)
    
    if not record.file_video:
        return jsonify({'success': False, 'error': 'Video tidak ditemukan'}), 404
    
    # Path video - konversi backslash dan handle relative path
    video_path_str = record.file_video.replace('\\', '/')
    
    # Hapus prefix 'recordings/' jika ada karena kita akan tambah dari config
    if video_path_str.startswith('recordings/'):
        video_path_str = video_path_str[len('recordings/'):]
    
    video_path = config.RECORDINGS_FOLDER / video_path_str
    video_filename = Path(video_path_str).name
    
    if not video_path.exists():
        return jsonify({'success': False, 'error': f'File video tidak ada: {video_path_str}'}), 404
    
    # Path thumbnail - simpan di folder thumbnails dengan nama standar
    thumb_filename = f"thumb_{video_filename.replace('.mp4', '.jpg')}"
    thumb_path = config.THUMBNAILS_FOLDER / thumb_filename
    
    # Load FFmpeg path dari config.json
    project_config = _load_project_config()
    ffmpeg_path = project_config.get('ffmpeg_path', config.FFMPEG_PATH)
    
    try:
        # Generate thumbnail dari frame ke-2 (skip black frame awal)
        cmd = [
            ffmpeg_path,
            '-i', str(video_path),
            '-ss', '00:00:02',
            '-vframes', '1',
            '-q:v', '2',
            '-y',
            str(thumb_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if thumb_path.exists() and thumb_path.stat().st_size > 0:
            return jsonify({
                'success': True,
                'thumbnail': f'/uploads/thumbnails/{thumb_filename}'
            })
        else:
            return jsonify({'success': False, 'error': 'Gagal generate thumbnail'}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Timeout saat generate thumbnail'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate-thumbnails-batch', methods=['POST'])
def api_generate_thumbnails_batch():
    """Generate thumbnail untuk semua video yang belum punya thumbnail (batch)"""
    import subprocess
    
    project_config = _load_project_config()
    ffmpeg_path = project_config.get('ffmpeg_path', config.FFMPEG_PATH)
    
    # Ambil semua record dengan video
    records = PackingRecord.query.filter(
        PackingRecord.file_video.isnot(None),
        PackingRecord.file_video != ''
    ).all()
    
    generated = 0
    skipped = 0
    errors = []
    
    for record in records:
        try:
            # Path video - konversi backslash
            video_path_str = record.file_video.replace('\\', '/')
            if video_path_str.startswith('recordings/'):
                video_path_str = video_path_str[len('recordings/'):]
            
            video_path = config.RECORDINGS_FOLDER / video_path_str
            video_filename = Path(video_path_str).name
            
            # Path thumbnail
            thumb_filename = f"thumb_{video_filename.replace('.mp4', '.jpg')}"
            thumb_path = config.THUMBNAILS_FOLDER / thumb_filename
            
            # Skip jika thumbnail sudah ada
            if thumb_path.exists() and thumb_path.stat().st_size > 0:
                skipped += 1
                continue
            
            # Skip jika video tidak ada
            if not video_path.exists():
                errors.append(f'{video_filename}: file not found')
                continue
            
            # Generate thumbnail
            cmd = [
                ffmpeg_path,
                '-i', str(video_path),
                '-ss', '00:00:02',
                '-vframes', '1',
                '-q:v', '2',
                '-y',
                str(thumb_path)
            ]
            
            subprocess.run(cmd, capture_output=True, timeout=30)
            
            if thumb_path.exists() and thumb_path.stat().st_size > 0:
                generated += 1
            else:
                errors.append(f'{video_filename}: generation failed')
                
        except Exception as e:
            errors.append(f'{record.resi}: {str(e)}')
    
    return jsonify({
        'success': True,
        'generated': generated,
        'skipped': skipped,
        'errors': len(errors),
        'error_details': errors[:10]  # Limit error details
    })


@app.route('/api/export/csv')
def api_export_csv():
    """Export recordings to CSV"""
    from io import StringIO
    import csv
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Resi', 'Pegawai', 'Platform', 'Waktu Mulai', 'Waktu Selesai', 'Durasi', 'Status', 'Size KB'])
    
    # Data
    records = PackingRecord.query.order_by(PackingRecord.waktu_mulai.desc()).all()
    for r in records:
        waktu_mulai = str(r.waktu_mulai)[:19] if r.waktu_mulai else ''
        waktu_selesai = str(r.waktu_selesai)[:19] if r.waktu_selesai else ''
        writer.writerow([
            r.id, r.resi, r.pegawai, r.platform,
            waktu_mulai, waktu_selesai,
            r.durasi_detik, r.status, r.file_size_kb
        ])
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=recordings_{datetime.now().strftime("%Y%m%d")}.csv'}
    )


@app.route('/api/export/pdf')
def api_export_pdf():
    """Export recordings to PDF (simple HTML-based)"""
    from flask import Response
    
    # Build HTML for PDF
    records = PackingRecord.query.filter_by(status='COMPLETED').order_by(
        PackingRecord.waktu_mulai.desc()
    ).limit(100).all()
    
    stats = get_today_stats()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>AYZARA Recording Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            h1 {{ color: #FF6B35; text-align: center; }}
            .stats {{ display: flex; justify-content: space-around; margin: 20px 0; padding: 15px; background: #f5f5f5; }}
            .stat {{ text-align: center; }}
            .stat-value {{ font-size: 24px; font-weight: bold; color: #FF6B35; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th {{ background: #FF6B35; color: white; padding: 10px; text-align: left; }}
            td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
            tr:hover {{ background: #f9f9f9; }}
            .footer {{ text-align: center; margin-top: 30px; color: #888; font-size: 12px; }}
        </style>
    </head>
    <body>
        <h1>📦 AYZARA Recording Report</h1>
        <p style="text-align: center;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{stats['total']}</div>
                <div>Total Today</div>
            </div>
            <div class="stat">
                <div class="stat-value">{stats['completed']}</div>
                <div>Completed</div>
            </div>
            <div class="stat">
                <div class="stat-value">{stats['avg_duration']}s</div>
                <div>Avg Duration</div>
            </div>
            <div class="stat">
                <div class="stat-value">{stats['total_size_mb']} MB</div>
                <div>Total Size</div>
            </div>
        </div>
        
        <table>
            <tr>
                <th>Resi</th>
                <th>Pegawai</th>
                <th>Platform</th>
                <th>Waktu</th>
                <th>Durasi</th>
                <th>Size</th>
            </tr>
    """
    
    for r in records:
        waktu = str(r.waktu_mulai)[:16] if r.waktu_mulai else '-'
        html += f"""
            <tr>
                <td>{r.resi}</td>
                <td>{r.pegawai}</td>
                <td>{r.platform}</td>
                <td>{waktu}</td>
                <td>{r.durasi_detik or 0}s</td>
                <td>{r.file_size_kb or 0} KB</td>
            </tr>
        """
    
    html += """
        </table>
        <div class="footer">
            <p>AYZARA COLLECTIONS - Packing Recording System</p>
            <p>100% FREE • Self-Hosted</p>
        </div>
    </body>
    </html>
    """
    
    return Response(
        html,
        mimetype='text/html',
        headers={'Content-Disposition': f'attachment;filename=report_{datetime.now().strftime("%Y%m%d")}.html'}
    )


# ============================================
# STATIC FILES
# ============================================

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(config.UPLOAD_FOLDER, filename)


@app.route('/recordings/<path:filename>')
def recording_file(filename):
    """Serve recording video files"""
    return send_from_directory(config.RECORDINGS_FOLDER, filename)

# ============================================
# STATIC FILE SERVING (Uploads - photos, thumbnails)
# ============================================

@app.route('/uploads/<path:subpath>')
def serve_uploads(subpath):
    """Serve uploaded files (photos, thumbnails)"""
    # Parse subpath to get subfolder and filename
    parts = subpath.split('/', 1)
    if len(parts) == 2:
        subfolder, filename = parts
        if subfolder == 'photos':
            return send_from_directory(config.PHOTOS_FOLDER, filename)
        elif subfolder == 'thumbnails':
            return send_from_directory(config.THUMBNAILS_FOLDER, filename)
    # Fallback - serve from uploads folder directly
    return send_from_directory(config.UPLOAD_FOLDER, subpath)


# ============================================
# SOCKETIO EVENTS
# ============================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('[SocketIO] Client connected')
    # Send current status immediately
    emit('status_update', {
        'is_recording': get_active_recording() is not None,
        'recording': get_active_recording(),
        'stats': get_today_stats()
    })


@socketio.on('request_status')
def handle_request_status():
    """Handle status request from client"""
    emit('status_update', {
        'is_recording': get_active_recording() is not None,
        'recording': get_active_recording(),
        'stats': get_today_stats()
    })


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print(f"[Flask] Database initialized at {config.DATABASE_FILE}")
    
    print(f"[Flask] Starting {config.APP_NAME} v{config.APP_VERSION}")
    print(f"[Flask] Open http://localhost:5000")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
