# TEMPORARY: Comment out eventlet due to issues with SocketIO event handlers
# import eventlet
# eventlet.monkey_patch()

"""
AYZARA DASHBOARD - FLASK APPLICATION
=====================================
Main Flask Application with SocketIO for real-time updates

100% FREE - SELF-HOSTED
Created for AYZARA COLLECTIONS
"""

from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, flash, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
import threading
import time
import hashlib
import cv2
from datetime import datetime, timedelta
from pathlib import Path

import config
from pyzbar.pyzbar import decode
import numpy as np
import socket
import uuid
import select
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================
# APP INITIALIZATION
# ============================================

app = Flask(__name__)

@app.before_request
def log_request_info():
    if request.path.startswith('/api/'):
        print(f">>> [GLOBAL] {request.method} {request.path}")

app.config.from_object(config)
app.config['SECRET_KEY'] = 'ayzara-secret-key-123' # Added SECRET_KEY as it's required for Flask-Login and was likely intended.

# Database
db = SQLAlchemy(app)

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Silakan login terlebih dahulu'

# SocketIO for real-time updates - CHANGED TO THREADING MODE
print("[SocketIO] Initializing with threading mode...")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)

# Camera status & usage cache (in-memory)
camera_status_cache = {}  # url -> {online, last_checked, url, in_use, in_use_by, purpose}
camera_status_lock = threading.Lock()

# Camera usage tracker: url -> {username, purpose, last_used}
camera_usage = {}
camera_usage_lock = threading.Lock()


# ============================================
# DATABASE MODELS
# ============================================

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
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'


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

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))

def admin_required(f):
    """Decorator to require admin role"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Akses ditolak. Hanya admin yang dapat mengakses halaman ini.', 'danger')
            return redirect(url_for('videos'))  # Redirect to videos instead of index
        return f(*args, **kwargs)
    return decorated_function


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


def create_recording_folder(date_obj, platform, pegawai):
    """Create structured recording folder: recordings/DATE/PLATFORM/PEGAWAI"""
    date_str = date_obj.strftime('%Y-%m-%d')
    platform_clean = "".join(x for x in platform if x.isalnum() or x in " -_").strip().upper()
    pegawai_clean = "".join(x for x in pegawai if x.isalnum() or x in " -_").strip()
    
    # recordings/YYYY-MM-DD/PLATFORM/PEGAWAI
    folder_path = config.RECORDINGS_FOLDER / date_str / platform_clean / pegawai_clean
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


def calculate_sha256(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def generate_metadata_json(record_data, video_path, duration, file_size):
    """Generate JSON metadata for recording"""
    video_filename = os.path.basename(video_path)
    file_hash = calculate_sha256(video_path)
    
    metadata = {
        "bukti_rekaman": {
            "versi": "1.0",
            "brand": "AYZARA",
            "dibuat_oleh": "Packing Recording System"
        },
        "informasi_paket": {
            "nomor_resi": record_data['resi'],
            "platform": record_data['platform'],
            "pegawai": record_data['pegawai']
        },
        "informasi_video": {
            "nama_file": video_filename,
            "durasi_detik": round(duration, 2),
            "ukuran_kb": round(file_size / 1024),
            "sha256_hash": file_hash
        },
        "waktu": {
            "rekaman_mulai": record_data['waktu_mulai'].strftime('%Y-%m-%d %H:%M:%S'),
            "rekaman_selesai": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "zona_waktu": "Asia/Jakarta (WIB)"
        },
        "catatan": "File ini adalah bukti otentik rekaman packing. Hash SHA256 dapat digunakan untuk memverifikasi keaslian video."
    }
    
    # Save JSON file
    json_path = str(video_path).rsplit('.', 1)[0] + '.json'
    with open(json_path, 'w') as f:
        json.dump(metadata, f, indent=2)
        
    return json_path, file_hash


def get_active_recording():
    """Get currently active recording with validation against zombies"""
    record = PackingRecord.query.filter_by(
        status='RECORDING'
    ).order_by(PackingRecord.waktu_mulai.desc()).first()
    
    if not record:
        return None
        
    # 1. Validation for Dashboard Recordings
    # If it was started by the dashboard, it MUST be in the active_recordings map
    if record.recorder_type == 'dashboard':
        found_in_memory = False
        with recording_lock:
            for rid, info in active_recordings.items():
                if info.get('db_id') == record.id:
                    found_in_memory = True
                    break
        
        if not found_in_memory:
            # It's a zombie from a previous crash/restart
            print(f">>> [Status] Detected zombie dashboard recording (ID: {record.id}, Resi: {record.resi}). Cleaning up...")
            _mark_record_as_zombie(record, "Server restarted/Process missing")
            return None

    # 2. Validation for ANY recording (Staleness Timeout)
    # If started more than 4 hours ago, it's definitely a zombie
    if record.waktu_mulai:
        elapsed = (datetime.now() - record.waktu_mulai).total_seconds()
        if elapsed > 14400: # 4 Hours
            print(f">>> [Status] Detected stale recording (ID: {record.id}, Started: {record.waktu_mulai}). Cleaning up...")
            _mark_record_as_zombie(record, "Recording timed out (4 hours limit)")
            return None
    
    return record.to_dict()

def _mark_record_as_zombie(record, reason):
    """Internal helper to cleanup record in DB"""
    try:
        record.status = 'ERROR'
        record.error_message = f"Auto-clean: {reason}"
        record.waktu_selesai = datetime.now()
        db.session.commit()
    except Exception as e:
        print(f"Error marking zombie: {e}")
        db.session.rollback()


# ============================================
# WEB ROUTES
# ============================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Username atau password salah', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout handler"""
    logout_user()
    flash('Anda telah logout', 'success')
    return redirect(url_for('login'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password page"""
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(old_password):
            flash('Password lama salah', 'danger')
        elif new_password != confirm_password:
            flash('Password baru tidak cocok', 'danger')
        elif len(new_password) < 4:
            flash('Password minimal 4 karakter', 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password berhasil diubah', 'success')
            return redirect(url_for('index'))
    
    return render_template('change_password.html')


@app.route('/')
@login_required
@admin_required
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
@login_required
@admin_required
def monitoring():
    """Live monitoring page"""
    active = get_active_recording()
    stats = get_today_stats()
    
    return render_template('pages/monitoring.html',
        active_recording=active,
        stats=stats
    )


@app.route('/videos')
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


@app.route('/team')
@login_required
@admin_required
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
@login_required
def camera():
    """Camera capture page"""
    return render_template('pages/camera.html',
        rtsp_url=config.DEFAULT_RTSP_URL
    )


@app.route('/rekam-packing')
@login_required
def rekam_packing():
    """Packing recording page"""
    return render_template('pages/recording.html',
        platforms=config.PLATFORMS,
        default_rtsp_url=config.DEFAULT_RTSP_URL
    )


@app.route('/statistics')
@login_required
@admin_required
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
@login_required
def help_page():
    """Help/Manual page"""
    return render_template('pages/help.html')


@app.route('/developer')
@login_required
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


@app.route('/camera-settings')
@login_required
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
# CAMERA DISCOVERY
# ============================================

def perform_camera_discovery(timeout=3.0):
    """
    Find IP cameras on the local network using WS-Discovery (ONVIF), SSDP,
    and a fast port scan for DroidCam/others.
    """
    discovered_cameras = []
    seen_ips = set()
    
    # helper for socket probe
    def probe_camera(ip, port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex((ip, port)) == 0:
                    return ip, port
        except:
            pass
        return None

    # Determine local subnet
    def get_local_ips():
        ips = []
        try:
            # Create a dummy connection to get primary IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            primary_ip = s.getsockname()[0]
            s.close()
            
            print(f">>> [Discovery] Detected primary IP: {primary_ip}")
            
            if primary_ip:
                base = primary_ip.rsplit('.', 1)[0]
                # Scan common range .1 to .254
                ips = [f"{base}.{i}" for i in range(1, 255)]
        except Exception as e:
            print(f">>> [Discovery] Failed to detect primary IP: {e}")
            # Fallback to a common subnet if 8.8.8.8 fails but we know we are usually on 192.168.x.x
            ips = []
            
        return ips

    # 1. WS-Discovery (ONVIF) Probe
    ws_discovery_msg = f"""<?xml version="1.0" encoding="utf-8"?>
    <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing">
        <s:Header>
            <a:Action s:mustUnderstand="1">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action>
            <a:MessageID>urn:uuid:{uuid.uuid4()}</a:MessageID>
            <a:ReplyTo><a:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:Address></a:ReplyTo>
            <a:To s:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>
        </s:Header>
        <s:Body>
            <Probe xmlns="http://schemas.xmlsoap.org/ws/2005/04/discovery"><Types>dn:NetworkVideoTransmitter</Types></Probe>
        </s:Body>
    </s:Envelope>"""

    # 2. SSDP (UPnP) Probe
    ssdp_msg = (
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'MX: 3\r\n'
        'ST: upnp:rootdevice\r\n'
        '\r\n'
    )

    # Set up broadcast sockets
    sockets = []
    try:
        onvif_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        onvif_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        onvif_sock.setblocking(False)
        onvif_sock.sendto(ws_discovery_msg.encode('utf-8'), ('239.255.255.250', 3702))
        sockets.append(onvif_sock)
        
        ssdp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        ssdp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        ssdp_sock.setblocking(False)
        ssdp_sock.sendto(ssdp_msg.encode('utf-8'), ('239.255.255.250', 1900))
        sockets.append(ssdp_sock)
    except:
        pass

    # 3. Start Subnet Scan (Multithreaded) for DroidCam and common cameras
    local_ips = get_local_ips()
    common_ports = [4747, 8080, 554, 8554] # 4747 is DroidCam
    
    scan_results = []
    if local_ips:
        # Increase workers to 200 for faster coverage
        with ThreadPoolExecutor(max_workers=200) as executor:
            futures = []
            for ip in local_ips:
                for port in common_ports:
                    futures.append(executor.submit(probe_camera, ip, port))
            
            # Wait for some results (up to 2.5 seconds)
            try:
                for future in as_completed(futures, timeout=2.5):
                    try:
                        res = future.result()
                        if res:
                            scan_results.append(res)
                    except:
                        pass
            except TimeoutError:
                print(f">>> [Discovery] Subnet scan partially completed (timeout). Found {len(scan_results)} devices.")
            except Exception as e:
                print(f">>> [Discovery] Scanner error: {e}")

    # Collect broadcast responses
    start_time = time.time()
    while time.time() - start_time < 0.5: # short window for broadcasts
        readable, _, _ = select.select(sockets, [], [], 0.1)
        for s in readable:
            try:
                data, addr = s.recvfrom(4096)
                ip = addr[0]
                if ip in seen_ips: continue
                
                resp = data.decode('utf-8', errors='ignore').lower()
                name = f"Camera {ip}"
                url = f"rtsp://{ip}:554/stream"
                source = "WS-Discovery" if s == onvif_sock else "SSDP"
                
                if 'networkvideotransmitter' in resp or 'onvif' in resp:
                    name = f"ONVIF Camera ({ip})"
                    discovered_cameras.append({'ip': ip, 'name': name, 'url': url, 'source': source})
                    seen_ips.add(ip)
                elif 'camera' in resp or 'video' in resp:
                    name = f"Found Camera ({ip})"
                    discovered_cameras.append({'ip': ip, 'name': name, 'url': url, 'source': source})
                    seen_ips.add(ip)
            except:
                pass

    # Merge scan results
    for ip, port in scan_results:
        if ip in seen_ips: continue
        
        name = f"Common Camera ({ip})"
        url = f"rtsp://{ip}:{port}/stream"
        source = "Port Scan"
        
        if port == 4747:
            name = f"DroidCam ({ip})"
            url = f"http://{ip}:4747/mjpegfeed" # Correct for DroidCam
        elif port == 8080:
            name = f"IP Webcam ({ip})"
            url = f"http://{ip}:8080/video"
            
        discovered_cameras.append({'ip': ip, 'name': name, 'url': url, 'source': source})
        seen_ips.add(ip)

    for s in sockets: s.close()
    return discovered_cameras

@app.route('/api/cameras/discover', methods=['GET'])
@login_required
@admin_required
def api_cameras_discover():
    """Discover cameras on the local network"""
    print(">>> [Discovery] Starting camera discovery...")
    found = perform_camera_discovery()
    print(f">>> [Discovery] Found {len(found)} potential devices")
    return jsonify({
        'success': True,
        'cameras': found
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

    # Check for duplicate URL
    for cam in cameras:
        if cam.get('url') == url:
            return jsonify({'success': False, 'message': f'URL sudah terdaftar dengan nama: {cam.get("name")}'}), 400
    
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
        new_url = data['url'].strip()
        # Check for duplicate URL (excluding itself)
        for cam in cameras:
            if cam.get('id') != camera_id and cam.get('url') == new_url:
                return jsonify({'success': False, 'message': f'URL sudah terdaftar dengan nama: {cam.get("name")}'}), 400
        cameras[camera_idx]['url'] = new_url
    if 'enabled' in data:
        cameras[camera_idx]['enabled'] = data['enabled']
    
    # Save
    project_cfg['camera_list'] = cameras
    if _save_project_config(project_cfg):
        return jsonify({'success': True, 'camera': cameras[camera_idx]})
    else:
        return jsonify({'success': False, 'message': 'Gagal menyimpan config'}), 500


# ============================================
# BACKGROUND WORKERS
# ============================================

camera_status_cache = {}
status_cache_lock = threading.Lock()


def mark_camera_in_use(url, username, purpose):
    """Mark a camera as being actively used by a user for a specific purpose"""
    try:
        if not url:
            return
        if not username:
            username = 'Unknown'
        if not purpose:
            purpose = 'unknown'

        now = time.time()
        with camera_usage_lock:
            prev = camera_usage.get(url)
            # Jika sudah ada usage dan purpose baru adalah 'preview' sementara sebelumnya 'scan' atau 'record',
            # jangan turunkan secara paksa kecuali caller memang ingin override (dalam kasus ini kita tetap override).
            camera_usage[url] = {
                'username': username,
                'purpose': purpose,
                'last_used': now
            }
    except Exception as e:
        print(f"[CameraUsage] Failed to mark usage for {url}: {e}")

def is_camera_online(url):
    """Perform a quick probe to see if camera is reachable using ffprobe or socket"""
    import subprocess
    import socket
    from urllib.parse import urlparse

    # 1. Try socket check first (fastest)
    try:
        parsed = urlparse(url)
        if parsed.hostname and parsed.port:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((parsed.hostname, parsed.port))
            s.close()
            # If socket succeeds, proceed to probe if it's RTSP or MJPEG
        elif parsed.hostname:
            # Default ports
            port = 554 if url.startswith('rtsp') else (80 if url.startswith('http') else None)
            if port:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect((parsed.hostname, port))
                s.close()
    except:
        # If socket fails, it might be UDP or blocked, but usually means offline
        pass

    # 2. Use ffprobe for a definitive check (short timeout)
    try:
        project_cfg = _load_project_config()
        ffmpeg_path = project_cfg.get('ffmpeg_path', 'ffmpeg')
        ffprobe_path = ffmpeg_path.replace('ffmpeg', 'ffprobe')
        rtsp_transport = project_cfg.get('rtsp_transport', 'tcp')

        cmd = [
            ffprobe_path,
            '-v', 'error',
            '-show_entries', 'format=format_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
        ]

        if url.lower().startswith('rtsp'):
            cmd.extend(['-rtsp_transport', rtsp_transport])

        # Use -analyzeduration and -probesize to make it faster
        cmd.extend(['-analyzeduration', '1000000', '-probesize', '1000000', url])

        # Run with short timeout
        subprocess.run(cmd, capture_output=True, timeout=5, check=True)
        return True
    except:
        return False

def _check_single_camera_status(url):
    """Helper function to check single camera status (non-blocking)"""
    # optimization: check if camera is currently streaming in app
    with camera_lock:
        if url in active_cameras and active_cameras[url].running:
            # When stream is active in-app, always treat as online
            base_status = {'online': True, 'last_checked': time.time()}
        else:
            base_status = None

    if base_status is None:
        # Actually check if online
        online = is_camera_online(url)
        base_status = {
            'online': online,
            'last_checked': time.time(),
            'standby': True
        }

    # Enrich with usage info
    in_use = False
    in_use_by = None
    purpose = None

    # If there is an active stream, mark as in-use
    with camera_lock:
        if url in active_cameras and active_cameras[url].running:
            in_use = True

    # Attach last known user purpose if recently used (within 10 seconds)
    with camera_usage_lock:
        usage = camera_usage.get(url)
        if usage and (time.time() - usage.get('last_used', 0) <= 10):  # Reduced from 60 to 10 seconds
            in_use = True
            in_use_by = usage.get('username')
            purpose = usage.get('purpose')

    base_status.update({
        'url': url,
        'in_use': in_use,
        'in_use_by': in_use_by,
        'purpose': purpose
    })

    return base_status

def background_camera_status_checker():
    """Background thread to check camera status periodically"""
    while True:
        try:
            project_cfg = _load_project_config()
            cameras = project_cfg.get('camera_list', [])
            
            now = time.time()
            for cam in cameras:
                if not cam.get('enabled', True):
                    continue
                    
                url = cam.get('url')
                if url:
                    status = _check_single_camera_status(url)
                    with status_cache_lock:
                        camera_status_cache[url] = status
            
            # Cek tiap 30 detik agar tidak terlalu membebani sistem
            time.sleep(30)
        except Exception as e:
            print(f"[Background] Error in status checker: {e}")
            time.sleep(30)

@app.route('/api/cameras/status', methods=['GET'])
def api_cameras_status():
    """Get cached camera statuses"""
    # Mulai dari cache background
    with status_cache_lock:
        status_snapshot = dict(camera_status_cache)

    now = time.time()

    # Overlay dengan kondisi real-time dari active_cameras (kalau stream sudah jalan)
    with camera_lock:
        for url, cam in active_cameras.items():
            if not cam.running:
                continue

            # Pastikan entry ada
            if url not in status_snapshot:
                status_snapshot[url] = {
                    'online': True,
                    'last_checked': now,
                    'url': url
                }
            else:
                status_snapshot[url]['online'] = True
                status_snapshot[url]['last_checked'] = now
                status_snapshot[url]['url'] = url

            # Tambah info penggunaan (user & purpose) jika ada
            in_use_by = None
            effective_purpose = 'preview'  # default jika stream aktif tapi tidak ada info lain
            with camera_usage_lock:
                usage = camera_usage.get(url)
                if usage:
                    age = now - usage.get('last_used', 0)
                    purpose = usage.get('purpose') or 'preview'
                    # Jika purpose terakhir "scan" tapi sudah lama (>5s) dan stream masih hidup,
                    # anggap kembali ke mode "preview" biasa
                    if purpose == 'scan' and age > 5:
                        effective_purpose = 'preview'
                    else:
                        effective_purpose = purpose
                    in_use_by = usage.get('username')

            status_snapshot[url].update({
                'in_use': True,
                'in_use_by': in_use_by,
                'purpose': effective_purpose
            })

    # status is a mapping: url -> {online, last_checked, url, in_use, in_use_by, purpose}
    return jsonify({'success': True, 'status': status_snapshot})




# ============================================
# CAMERA STREAMING (PERSISTENT & THREADED)
# ============================================

class VideoCamera(object):
    def __init__(self, url):
        self.url = url
        self.last_frame = None
        self.lock = threading.Lock()
        self.running = True
        self.last_access = time.time()
        self.consecutive_errors = 0 # Track errors
        
        print(f"[Camera] Initializing stream for: {url}")
        self.video = cv2.VideoCapture(url)
        if not self.video.isOpened():
             print(f"[Camera] FAILED to open stream: {url}")
             self.running = False
             return

        # FORCE VERIFY: Read one frame to ensure stream is actually alive
        # Many IP cameras return True for isOpened() even if stream is dead
        print(f"[Camera] Verifying stream content for: {url}")
        success, frame = self.video.read()
        if not success:
             print(f"[Camera] FAILED to read initial frame: {url}")
             self.running = False
             self.video.release()
             return

        print(f"[Camera] Stream verification SUCCESS: {url}")
        
        # Start background thread
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()

    def __del__(self):
        self.stop()

    def stop(self):
        """Explicitly stop the camera stream"""
        self.running = False
        if self.video and self.video.isOpened():
            self.video.release()

    def update(self):
        while self.running:
            try:
                # If no one accessed this camera for 30 seconds, stop to save resources
                # reduced to 10s for snappier cleanup
                if time.time() - self.last_access > 10:
                    print(f"[Camera] Stopping inactive stream: {self.url}")
                    self.running = False
                    break
                    
                success, frame = self.video.read()
                if success:
                    with self.lock:
                        self.last_frame = frame
                        self.consecutive_errors = 0 # Reset error count
                else:
                    self.consecutive_errors += 1
                    
                    
                    # Stop if too many errors (camera disconnected)
                    # FAST TIMEOUT: > 2 errors (approx 2-3 seconds)
                    if self.consecutive_errors > 2:
                        print(f"[Camera] Too many errors ({self.consecutive_errors}), camera disconnected: {self.url}")
                        self.running = False
                        break
                    
                    # Reconnection logic
                    self.video.release()
                    time.sleep(1) # Reduced from 2s
                    self.video = cv2.VideoCapture(self.url)
                    print(f"[Camera] Reconnecting... ({self.consecutive_errors})")
            except Exception as e:
                print(f"[Camera] Error: {e}")
                self.consecutive_errors += 1
                
                self.consecutive_errors += 1
                
                # Stop if too many errors
                if self.consecutive_errors > 2:
                    print(f"[Camera] Too many errors, stopping stream: {self.url}")
                    self.running = False
                    break
                    
                time.sleep(1)
            
            time.sleep(0.05) # Limit to ~20 FPS reading

    def get_frame(self):
        self.last_access = time.time()
        
        # If too many errors, assume dead
        if self.consecutive_errors > 10:
            return None
            
        with self.lock:
            if self.last_frame is None:
                return None
            
            # Encode to JPEG
            ret, jpeg = cv2.imencode('.jpg', self.last_frame)
            return jpeg.tobytes()
            
    def get_raw_frame(self):
        """Get raw CV2 frame for processing (barcode detection)"""
        self.last_access = time.time()
        with self.lock:
            return self.last_frame.copy() if self.last_frame is not None else None


# Camera Manager
active_cameras = {}
camera_lock = threading.Lock()

def get_camera_stream(url):
    with camera_lock:
        # Check if exists and is running
        if url in active_cameras:
            cam = active_cameras[url]
            if cam.running:
                # print(f"[Camera] Reusing existing stream: {url}")
                return cam
            else:
                # It stopped, remove and recreate
                print(f"[Camera] Stream stopped, removing: {url}")
                del active_cameras[url]
        
        print(f"[Camera] Starting new stream: {url}")
        new_cam = VideoCamera(url)
        
        # Check if initialization succeeded
        if not new_cam.running:
            print(f"[Camera] Failed to initialize camera: {url}")
            return None
            
        active_cameras[url] = new_cam
        return new_cam

def gen_frames(camera):
    error_count = 0
    try:
        while True:
            # Check if camera stopped running by itself (e.g. timeout)
            if not camera.running:
                break
                
            frame = camera.get_frame()
            if frame:
                error_count = 0
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
            else:
                error_count += 1
                # If we can't get frames for 5 seconds (10 FPS * 5), break stream
                if error_count > 50: 
                    break
                time.sleep(0.1)
    except GeneratorExit:
        pass # Client disconnected
    except Exception as e:
        print(f"[Stream] Client error: {e}")

@app.route('/video_feed')
@login_required
def video_feed():
    url = request.args.get('url')
    if not url:
        return "URL parameter required", 400
        
    # Mark usage for preview/monitoring
    try:
        username = current_user.username if current_user.is_authenticated else 'Unknown'
    except Exception:
        username = 'Unknown'
    mark_camera_in_use(url, username, 'preview')

    camera = get_camera_stream(url)
    
    if not camera:
        return "Camera connection failed", 500
        
    return Response(stream_with_context(gen_frames(camera)),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
                    
@app.route('/api/camera/release', methods=['POST'])
def api_camera_release():
    """Explicitly release/stop a camera stream"""
    data = request.get_json()
    url = data.get('url', '')
    
    with camera_lock:
        if url in active_cameras:
            print(f"[Camera] Explicit release requested for: {url}")
            active_cameras[url].stop()
            del active_cameras[url]
            
            # ADDED: Clear camera usage when releasing
            with camera_usage_lock:
                if url in camera_usage:
                    print(f"[Camera] Clearing usage info for: {url}")
                    del camera_usage[url]
            
            return jsonify({'success': True})
            
    return jsonify({'success': True, 'message': 'Camera not active'})

@app.route('/api/camera/check', methods=['GET'])
def api_camera_check():
    """Check if specific camera stream is currently active and running"""
    url = request.args.get('url')
    if not url:
        return jsonify({'active': False, 'error': 'No URL provided'})
        
    with camera_lock:
        if url in active_cameras:
            cam = active_cameras[url]
            # It is active if it exists and running flag is True
            # Note: consecutive_errors logic in VideoCamera will set running=False if dead
            if cam.running:
                return jsonify({'active': True})
                
    return jsonify({'active': False})


@app.route('/api/camera/usage', methods=['POST'])
@login_required
def api_camera_usage():
    """Explicitly update camera usage purpose (preview/scan/record/capture) from frontend"""
    try:
        data = request.get_json() or {}
    except Exception:
        data = {}

    url = data.get('url')
    purpose = data.get('purpose')

    if not url or not isinstance(url, str):
        return jsonify({'success': False, 'message': 'URL tidak valid'}), 400
    if not purpose or not isinstance(purpose, str):
        return jsonify({'success': False, 'message': 'Purpose tidak valid'}), 400

    username = current_user.username if current_user.is_authenticated else 'Unknown'
    mark_camera_in_use(url, username, purpose)
    return jsonify({'success': True})

# ============================================
# BARCODE & RECORDING LOGIC
# ============================================

from pyzbar.pyzbar import decode
import os
from datetime import datetime
from flask_login import login_required, current_user
from opencv_recorder import record_from_camera_stream
from recording_storage import get_recording_directory, find_next_index, calculate_sha256, generate_metadata_json, save_metadata_json

@app.route('/api/barcode/detect', methods=['POST'])
@login_required
def api_barcode_detect():
    """Detect barcode from active camera stream"""
    data = request.get_json()
    url = data.get('url')
    
    print(f">>> [API] Barcode detect request received for: {url}")
    
    if not url:
        print(">>> [API] ERROR: URL missing")
        return jsonify({'success': False, 'message': 'URL missing'}), 400
        
    # Mark usage for scan
    try:
        username = current_user.username if current_user.is_authenticated else 'Unknown'
    except Exception:
        username = 'Unknown'
    mark_camera_in_use(url, username, 'scan')

    # Get camera instance
    with camera_lock:
        if url not in active_cameras:
             print(f">>> [API] ERROR: Camera {url} not in active_cameras. Available: {list(active_cameras.keys())}")
             return jsonify({'success': False, 'message': 'Camera not active'}), 400
        camera = active_cameras[url]
        
    # Get raw frame
    frame = camera.get_raw_frame()
    if frame is None:
        print(">>> [API] ERROR: No frame available from camera")
        return jsonify({'success': False, 'message': 'No frame available'}), 503
        
    # Detect barcode
    try:
        # Gray scale for better detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # DEBUG LOGGING
        height, width = gray.shape
        # print(f">>> [Barcode] Scanning frame {width}x{height}...") 
        
        barcodes = decode(gray)
        
        if barcodes:
            print(f">>> [Barcode] FOUND {len(barcodes)} barcodes!")
        
        results = []
        for barcode in barcodes:
            try:
                data_str = barcode.data.decode('utf-8')
                print(f">>> [Barcode] DECODED: {data_str} ({barcode.type})")
                results.append({
                    'data': data_str,
                    'type': barcode.type
                })
            except:
                pass
            
        if results:
            return jsonify({'success': True, 'found': True, 'barcodes': results})
        else:
             # print(">>> [Barcode] No barcodes found in this frame")
             return jsonify({'success': True, 'found': False})
             
    except Exception as e:
        print(f">>> [Barcode] CRITICAL ERROR: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Recording Manager
active_recordings = {} # recording_id -> subprocess/info
recording_lock = threading.Lock()

def _run_recording_process(command, recording_id, filepath, duration_limit=300):
    """Background process helper"""
    import subprocess
    print(f"[Recording] Starting thread for {recording_id}")
    print(f"[Recording] Target Filepath: {filepath}")
    
    try:
        # Start FFmpeg
        print(f"[Recording] Executing: {' '.join(command)}")
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"[Recording] Process started with PID: {process.pid}")
        
        # Register process
        with recording_lock:
            if recording_id in active_recordings:
                active_recordings[recording_id]['process'] = process
        
        # Wait for completion or stop
        try:
            stdout, stderr = process.communicate(timeout=duration_limit)
            stderr_text = stderr.decode('utf-8', errors='ignore')
            if stderr_text:
                print(f"[Recording] FFmpeg output for {recording_id}:")
                print(stderr_text)
        except subprocess.TimeoutExpired:
            print(f"[Recording] Timeout reached for {recording_id}")
            process.kill()
            
        returncode = process.returncode
        print(f"[Recording] Finished {recording_id} with code {returncode}")
        if returncode != 0:
             print(f"[Recording] WARNING: Non-zero exit code! File may be missing or corrupt.")
        
    except Exception as e:
        print(f"[Recording] Failed {recording_id}: {e}")
        
    # Cleanup is handled by stop route usually, but ensure removal
    with recording_lock:
        if recording_id in active_recordings:
            # Mark as done if not already
            pass

@app.route('/api/recording/start', methods=['POST'])
@login_required
def api_recording_start():
    """Start recording process"""
    print(f">>> [API] /api/recording/start called") # Debug log
    data = request.get_json()
    url = data.get('url')
    resi = data.get('resi')
    platform = data.get('platform')
    
    if not url or not resi:
        return jsonify({'success': False, 'message': 'Missing data'}), 400
        
    # Generate hierarchical directory structure
    date_str = datetime.now().strftime('%Y-%m-%d')
    pegawai = current_user.username
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    recording_id = f"rec_{timestamp}"
    
    # Get directory and create if needed
    recording_dir = get_recording_directory(date_str, platform, pegawai)
    
    # Find next index for this resi
    index = find_next_index(recording_dir, resi, platform)
    
    # Generate filename: RESI_PLATFORM_AYZARA_INDEX.mp4
    filename = f"{resi}_{platform}_AYZARA_{index}.mp4"
    filepath = str(recording_dir / filename)
    
    # Store relative path for database: YYYY-MM-DD/PLATFORM/pegawai/filename
    relative_path = f"{date_str}/{platform}/{pegawai}/{filename}"
    
    # Save record to DB FIRST (before starting thread to avoid race condition)
    new_rec = PackingRecord(
        resi=resi,
        platform=platform or 'LAINNYA',
        pegawai=current_user.username,
        file_video=relative_path,  # Store relative path
        waktu_mulai=datetime.now(),
        status='RECORDING',
        recorder_type='dashboard'
    )
    db.session.add(new_rec)
    db.session.commit()
    
    # Register in active_recordings BEFORE starting thread
    with recording_lock:
        active_recordings[recording_id] = {
            'db_id': new_rec.id,
            'start_time': time.time(),
            'filename': filename,
            'resi': resi,
            'platform': platform,
            'user_id': current_user.id
        }
    
    # Detect stream type and choose recording method
    is_mjpeg = 'mjpeg' in url.lower() or (url.startswith('http') and not url.lower().startswith('rtsp'))
    
    if is_mjpeg:
        # Use OpenCV recording for MJPEG streams
        print(f"[Recording] Using OpenCV recording for MJPEG stream")
        
        # Ensure camera is active
        camera = get_camera_stream(url)
        if not camera or not camera.running:
            # Cleanup on error
            with recording_lock:
                del active_recordings[recording_id]
            db.session.delete(new_rec)
            db.session.commit()
            return jsonify({'success': False, 'error': 'Camera stream not active'}), 400
        
        # Mark usage for recording
        try:
            username = current_user.username if current_user.is_authenticated else 'Unknown'
        except Exception:
            username = 'Unknown'
        mark_camera_in_use(url, username, 'record')

        # Start OpenCV recording thread
        t = threading.Thread(
            target=record_from_camera_stream, 
            args=(camera, filepath, recording_id, active_recordings, recording_lock)
        )
        t.daemon = True
        t.start()
    else:
        # Use FFmpeg for RTSP streams
        print(f"[Recording] Using FFmpeg recording for RTSP stream")
        
        project_cfg = _load_project_config()
        ffmpeg_path = project_cfg.get('ffmpeg_path', 'ffmpeg')
        rtsp_transport = project_cfg.get('rtsp_transport', 'tcp')
        
        cmd = [ffmpeg_path]
        cmd.append('-y') # Force overwrite

        if url.lower().startswith('rtsp'):
            cmd.extend(['-rtsp_transport', rtsp_transport])
            
        cmd.extend([
            '-i', url,
            '-t', '1800', # Max 30 mins
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            filepath
        ])
        
        # Start FFmpeg thread
        t = threading.Thread(target=_run_recording_process, args=(cmd, recording_id, filepath))
        t.daemon = True
        t.start()
        
    return jsonify({
        'success': True, 
        'recording_id': recording_id,
        'start_time': active_recordings[recording_id]['start_time']
    })

@app.route('/recordings/<path:filename>')
def serve_recording(filename):
    """Serve recording video files from hierarchical structure"""
    # filename is relative path: 2026-01-06/SHOPEE/test/RESI_PLATFORM_AYZARA_001.mp4
    print(f">>> [Serving] Request for: {filename}")
    print(f">>> [Serving] From folder: {config.RECORDINGS_FOLDER}")
    
    # Construct full path
    full_path = config.RECORDINGS_FOLDER / filename
    
    if not full_path.exists():
        print(f">>> [Serving] File not found: {full_path}")
        return "File not found", 404
    
    # Get file extension
    file_ext = full_path.suffix.lower()
    
    # Set proper MIME type for videos
    mimetype = 'video/mp4' if file_ext == '.mp4' else 'application/octet-stream'
    
    # Serve with proper headers for video streaming
    response = send_from_directory(full_path.parent, full_path.name, mimetype=mimetype)
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Content-Type'] = mimetype
    
    return response


@app.route('/api/recording/stop', methods=['POST'])
@login_required
def api_recording_stop():
    """Stop recording"""
    data = request.get_json()
    recording_id = data.get('recording_id')
    
    Process = None
    db_id = None
    
    # 1. Signal Stop (Critical Section)
    with recording_lock:
        if recording_id not in active_recordings:
             return jsonify({'success': False, 'message': 'Recording not found'}), 404
             
        info = active_recordings[recording_id]
        
        # Verify ownership
        if info.get('user_id') != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized: Not your recording'}), 403
            
        db_id = info['db_id']
        process = info.get('process')
        
        if process:
            # Graceful stop - send 'q' to FFmpeg stdin
            try:
                print(f"[Recording] Sending graceful shutdown signal to {recording_id}")
                process.stdin.write(b'q')
                process.stdin.flush()
            except Exception as e:
                print(f"[Recording] Failed to send q signal: {e}")
        else:
            # OpenCV mode: Set flag
            print(f"[Recording] Setting stop_requested flag for {recording_id}")
            info['stop_requested'] = True

    # 2. Wait for Completion (OUTSIDE LOCK to prevent deadlock)
    # The recording thread needs to acquire the lock to check stop_requested or set completed
    if process:
        try:
            # Wait up to 5 seconds for graceful shutdown
            process.wait(timeout=5)
            print(f"[Recording] Graceful shutdown completed for {recording_id}")
        except:
            print(f"[Recording] Graceful shutdown failed, force killing")
            process.kill()
            try: process.wait(timeout=2)
            except: pass
    else:
        # Wait for OpenCV thread to finish (including FFmpeg conversion)
        print(f"[Recording] Waiting for thread completion (conversion)...")
        start_wait = time.time()
        timeout = 25 # Allow 25s for conversion on slow machines
        completed = False
        
        while time.time() - start_wait < timeout:
            with recording_lock:
                # Check if marked completed
                if recording_id in active_recordings and active_recordings[recording_id].get('completed'):
                    completed = True
                    break
            time.sleep(0.5)
            
        if not completed:
            print(f"[Recording] WARNING: Timed out waiting for recording thread {recording_id}")
            
    # 3. Cleanup and Finalize
    rec = None
    # Remove from active dict - Clean up resources properly
    with recording_lock:
        if recording_id in active_recordings:
            del active_recordings[recording_id]
            
    # Update DB and Generate Metadata
    rec = PackingRecord.query.get(db_id)
    if rec:
        rec.waktu_selesai = datetime.now()
        rec.status = 'COMPLETED'
        # Calculate duration
        rec.durasi_detik = int((rec.waktu_selesai - rec.waktu_mulai).total_seconds())
        
        # File verification and size
        fp = str(config.RECORDINGS_FOLDER / rec.file_video)
        
        # Force check file existence
        # Check carefully since conversion might have just finished
        if os.path.exists(fp):
            file_size = os.path.getsize(fp)
            if file_size > 0:
                rec.file_size_kb = int(file_size / 1024)
                print(f"[Recording] File saved successfully: {fp} ({rec.file_size_kb} KB)")
                
                # Calculate SHA256 hash
                try:
                    sha256_hash = calculate_sha256(fp)
                    print(f"[Recording] SHA256 calculated: {sha256_hash}")
                    
                    # Generate metadata JSON
                    metadata = generate_metadata_json({
                        'resi': rec.resi,
                        'platform': rec.platform,
                        'pegawai': rec.pegawai,
                        'filename': os.path.basename(rec.file_video),
                        'durasi_detik': rec.durasi_detik,
                        'ukuran_kb': rec.file_size_kb,
                        'sha256_hash': sha256_hash,
                        'waktu_mulai': rec.waktu_mulai.strftime('%Y-%m-%d %H:%M:%S'),
                        'waktu_selesai': rec.waktu_selesai.strftime('%Y-%m-%d %H:%M:%S')
                    })
                    
                    # Save JSON metadata (replace .mp4 with .json)
                    json_filepath = fp.replace('.mp4', '.json')
                    save_metadata_json(json_filepath, metadata)
                    print(f"[Recording] Metadata saved: {json_filepath}")
                except Exception as e:
                    print(f"[Recording] Error generating metadata: {e}")
            else:
                print(f"[Recording] WARNING: File exists but is empty: {fp}")
                rec.status = 'ERROR'
        else:
            print(f"[Recording] ERROR: File not found: {fp}")
            rec.status = 'ERROR'
            
        db.session.commit()
        
        # Construct video URL
        video_url = url_for('serve_recording', filename=rec.file_video)
        
        response_data = rec.to_dict()
        response_data['video_url'] = video_url
            
        return jsonify({'success': True, 'recording': response_data, 'video_url': video_url})
    
    return jsonify({'success': False, 'error': 'Record not found in DB'}), 500

@app.route('/api/recording/cancel', methods=['POST'])
@login_required
def api_recording_cancel():
    """Cancel and delete recording"""
    """Cancel and delete recording"""
    # Create robust JSON parser for Beacon support
    try:
        data = request.get_json(force=True, silent=True)
        if not data and request.data:
            data = json.loads(request.data)
    except:
        return jsonify({'success': False, 'message': 'Invalid data'}), 400
        
    if not data:
        return jsonify({'success': False, 'message': 'No data'}), 400
        
    recording_id = data.get('recording_id')
    
    with recording_lock:
        if recording_id not in active_recordings:
             return jsonify({'success': False, 'message': 'Recording not found'}), 404
             
        info = active_recordings[recording_id]
        
        # Verify ownership
        if info.get('user_id') != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized: Not your recording'}), 403
            
        process = info.get('process')
        if process:
            process.kill()
            
        # Delete file
        fp = str(config.RECORDINGS_FOLDER / info['filename'])
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except:
                pass
                
        # Update DB
        rec = PackingRecord.query.get(info['db_id'])
        if rec:
            rec.status = 'CANCELLED'
            db.session.commit()
            
        del active_recordings[recording_id]
        
        return jsonify({'success': True})

@app.route('/api/recordings/active', methods=['GET'])
@login_required
def api_recordings_active():
    """Check if there is an active recording for CURRENT USER"""
    with recording_lock:
        # Filter by current_user.id
        for rid, info in active_recordings.items():
            # Check ownership
            if info.get('user_id') == current_user.id:
                return jsonify({
                    'active': True,
                    'recording_id': rid,
                    'resi': info['resi'],
                    'platform': info.get('platform') or 'Unknown',
                    'start_time': info['start_time'],
                    'duration': time.time() - info['start_time']
                })
        
        return jsonify({'active': False})



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
        # Prepare command
        cmd = [ffmpeg_path]
        
        # Only add rtsp_transport if URL starts with rtsp
        if url.lower().startswith('rtsp'):
            cmd.extend(['-rtsp_transport', rtsp_transport])
            
        cmd.extend([
            '-i', url,
            '-t', '2',
            '-f', 'null',
            '-'
        ])
        
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        
        success = result.returncode == 0
        
        # UPDATE CACHE
        with status_cache_lock:
            camera_status_cache[url] = {
                'online': success,
                'last_checked': time.time(),
                'url': url
            }

        if success:
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
        print("TIMED OUT")
        return jsonify({'success': False, 'message': 'Timeout (15 detik)'})
    except FileNotFoundError:
        print("FILE NOT FOUND")
        return jsonify({'success': False, 'message': 'FFmpeg tidak ditemukan'})
    except Exception as e:
        print("EXCEPTION", str(e))
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
        
        # Auto-create user account for pegawai
        username = nama.lower().replace(' ', '')
        password = data.get('telepon', 'pegawai123')  # Use phone or default
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if not existing_user:
            user = User(
                username=username,
                role='pegawai',
                pegawai_id=pegawai.id
            )
            user.set_password(password)
            db.session.add(user)
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
        cfg_path = Path(config.CONFIG_FILE)
        if cfg_path.exists():
            with open(cfg_path, 'r') as f:
                # print(f"Loading config from: {cfg_path}")
                return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        pass
    return {}


@app.route('/api/camera/capture', methods=['POST'])
@login_required
def api_camera_capture():
    """Get latest frame from persistent background stream"""
    print(">>> [API] /api/camera/capture CALLED") # DEBUG LOG
    import base64
    
    # Load RTSP URL dan FFmpeg path dari config.json project utama
    project_config = _load_project_config()
    
    # Get URL from request or fallback to config
    data = request.get_json() or {}
    rtsp_url = data.get('url')
    print(f">>> [API] Capture Request URL: {rtsp_url}") # DEBUG LOG
    
    if not rtsp_url:
        rtsp_url = project_config.get('rtsp_url', config.DEFAULT_RTSP_URL)
        print(f">>> [API] Fallback URL: {rtsp_url}") # DEBUG LOG
        
    try:
        # Mark usage for capture
        try:
            username = current_user.username if current_user.is_authenticated else 'Unknown'
        except Exception:
            username = 'Unknown'
        mark_camera_in_use(rtsp_url, username, 'capture')

        # Get frame from memory
        camera = get_camera_stream(rtsp_url)
        # Ensure camera is running
        if not camera:
            print(f">>> [API] ERROR: Camera not found for {rtsp_url}")
            return jsonify({
                'success': False,
                'error': 'Kamera belum siap (Instance not found)'
            }), 503
            
        if not camera.running:
             print(f">>> [API] ERROR: Camera instance found but NOT RUNNING")
             return jsonify({
                'success': False,
                'error': 'Kamera tidak aktif (Stopped)'
            }), 503

        print(">>> [API] Camera is running, attempting to get frame...")
        frame_bytes = camera.get_frame()
        
        if frame_bytes:
            print(f">>> [API] Frame retrieved! Size: {len(frame_bytes)} bytes")
            # Generate filename
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"capture_{timestamp}.jpg"
            
            # Save to thumbnails folder (as per UI hint) or snapshots
            # Using thumbnails folder as requested "appropriate folder (yg code sudah ada)"
            filepath = config.THUMBNAILS_FOLDER / filename
            print(f">>> [API] Saving to: {filepath}")
            
            try:
                with open(filepath, 'wb') as f:
                    f.write(frame_bytes)
                print(">>> [API] File saved successfully")
            except Exception as e:
                print(f">>> [API] ERROR Saving file: {e}")
                raise e
            
            b64_img = base64.b64encode(frame_bytes).decode('utf-8')
            return jsonify({
                'success': True,
                'image': f'data:image/jpeg;base64,{b64_img}',
                'saved_path': f'/uploads/thumbnails/{filename}',
                'filename': filename
            })
        else:
            print(">>> [API] ERROR: Frame bytes is Empty/None")
            return jsonify({
                'success': False,
                'error': 'Gagal mengambil frame (Stream aktif tapi frame kosong / timeout)'
            }), 503
            
    except Exception as e:
        print(f">>> [API] EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
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
def handle_connect(auth=None):
    """Handle client connection"""
    print(f'[SocketIO] Client connected: {request.sid}')
    # Send current status immediately
    emit('status_update', {
        'is_recording': get_active_recording() is not None,
        'recording': get_active_recording(),
        'stats': get_today_stats()
    })

@socketio.on('ping_test')
def handle_ping_test(data):
    print(f">>> [SocketIO] PING RECEIVED from {request.sid}: {data}")
    emit('pong_test', {'message': 'Server reached!'})

@socketio.on('request_status')
def handle_request_status():
    """Handle status request from client"""
    emit('status_update', {
        'is_recording': get_active_recording() is not None,
        'recording': get_active_recording(),
        'stats': get_today_stats()
    })

@socketio.on('detect_barcode')
def handle_detect_barcode(data):
    """Detect barcode via SocketIO to bypass HTTP blocking"""
    print("\n" + "="*50)
    print(f">>> [SOCKET] Barcode Request Received!")
    print(f">>> Data received: {data}")
    print(f">>> Request SID: {request.sid}")
    print("="*50 + "\n")
    
    url = data.get('url') if data else None
    print(f">>> Target URL: {url}")
    
    if not url:
        print(">>> [SOCKET] ERROR: No URL provided")
        emit('barcode_result', {'success': False, 'message': 'No URL provided'})
        return
        
    # Mark usage for scan via Socket
    try:
        username = current_user.username if current_user.is_authenticated else 'Unknown'
    except Exception:
        username = 'Unknown'
    mark_camera_in_use(url, username, 'scan')

    # Get camera instance using the unified helper
    print(f">>> [SOCKET] Getting camera stream for: {url}")
    camera = get_camera_stream(url)
    if not camera:
        print(">>> [SOCKET] ERROR: Camera not found in active_cameras")
        emit('barcode_result', {'success': False, 'message': 'Camera not active'})
        return
        
    # Get raw frame
    print(">>> [SOCKET] Getting raw frame from camera...")
    frame = camera.get_raw_frame()
    if frame is None:
        print(">>> [SOCKET] ERROR: No frame available")
        emit('barcode_result', {'success': False, 'message': 'Frame not available'})
        return
        
    # Detect barcode
    try:
        print(">>> [SOCKET] Converting frame to grayscale...")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        print(">>> [SOCKET] Decoding barcodes...")
        barcodes = decode(gray)
        
        print(f">>> [SOCKET] Found {len(barcodes)} barcode(s)")
        
        if barcodes:
            results = []
            for barcode in barcodes:
                try:
                    data_str = barcode.data.decode('utf-8')
                    print(f">>> [SocketIO] FOUND: {data_str} (type: {barcode.type})")
                    results.append({
                        'data': data_str,
                        'type': barcode.type
                    })
                except Exception as e:
                    print(f">>> [SOCKET] Error decoding barcode: {e}")
                    pass
            
            if results:
                print(f">>> [SOCKET] Sending success response with {len(results)} barcode(s)")
                emit('barcode_result', {'success': True, 'found': True, 'barcodes': results})
            else:
                print(">>> [SOCKET] No valid barcodes decoded, sending not found")
                emit('barcode_result', {'success': True, 'found': False})
        else:
            # ALWAYS RESPOND so client gate resets
            print(">>> [SOCKET] No barcodes detected, sending not found")
            emit('barcode_result', {'success': True, 'found': False})
             
    except Exception as e:
        print(f">>> [SocketIO] Critical Error: {e}")
        import traceback
        traceback.print_exc()
        emit('barcode_result', {'success': False, 'error': str(e)})

# Test handler to verify SocketIO is working
@socketio.on('test_event')
def handle_test_event(data):
    print(f">>> [SOCKET] TEST EVENT RECEIVED: {data}")
    emit('test_response', {'message': 'Test successful!', 'data': data})


# ============================================
# MAIN
# ============================================

def check_and_migrate_db():
    """Check database schema and migrate if necessary"""
    with app.app_context():
        inspector = db.inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('packing_records')]
        
        with db.engine.connect() as conn:
            # Check and add json_metadata_path
            if 'json_metadata_path' not in columns:
                print("[Migration] Adding json_metadata_path column...")
                conn.execute(db.text('ALTER TABLE packing_records ADD COLUMN json_metadata_path VARCHAR(500)'))
                
            # Check and add sha256_hash
            if 'sha256_hash' not in columns:
                print("[Migration] Adding sha256_hash column...")
                conn.execute(db.text('ALTER TABLE packing_records ADD COLUMN sha256_hash VARCHAR(64)'))
                
            # Check and add created_at
            if 'created_at' not in columns:
                print("[Migration] Adding created_at column...")
                conn.execute(db.text('ALTER TABLE packing_records ADD COLUMN created_at DATETIME'))
                conn.execute(db.text('UPDATE packing_records SET created_at = waktu_mulai WHERE created_at IS NULL'))
            
            # Check for indices (SQLite doesn't support IF NOT EXISTS for index in all versions nicely, so we try/except or check)
            # Simplified: Let code run, if index creation fails usually it's fine or we check via inspector.get_indexes
            # But simpler here: just ensuring columns exist is critical. Indices can be recreated if needed or ignored for now.
            conn.commit()


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        check_and_migrate_db()  # Run migration check
        print(f"[Flask] Database initialized at {config.DATABASE_FILE}")
        
        # Create default admin if no users exist
        if User.query.count() == 0:
            admin = User(
                username='admin',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("[Flask] Default admin created (username: admin, password: admin123)")
            print("[Flask] IMPORTANT: Please change the default password after first login!")
    
    # Start background camera status checker
    status_thread = threading.Thread(target=background_camera_status_checker, daemon=True)
    status_thread.start()
    print("[Flask] Background camera status checker started")
    
    print(f"[Flask] Starting {config.APP_NAME} v{config.APP_VERSION}")
    print(f"[Flask] >>> SERVER VERSION: 2.1 - DEBUG MODE <<<") # Version check
    print(f"[Flask] Open http://localhost:5000")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
