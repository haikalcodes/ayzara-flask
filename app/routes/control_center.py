"""
Control Center Routes Blueprint
================================
Routes for multi-camera session management and control center

📁 dashboard_flask/app/routes/control_center.py
"""

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.services import SessionService, RecordingService, BarcodeService
from app.services.camera_service import get_camera_stream
from app.models import db, PackingRecord
import config

control_center_bp = Blueprint('control_center', __name__)
session_service = SessionService()


@control_center_bp.route('/setup-stations')
@login_required
def setup_stations():
    """Setup page for camera-employee assignment"""
    return render_template('pages/setup_stations.html', platforms=config.PLATFORMS)


@control_center_bp.route('/control-center')
@login_required
def control_center():
    """Main control center grid view"""
    session = session_service.get_active_session()
    if not session:
        return render_template('pages/control_center.html', 
                             error="Tidak ada sesi aktif. Silakan buat sesi di Setup Stations.")
    
    return render_template('pages/control_center.html')


# ============================================
# SESSION MANAGEMENT API
# ============================================

@control_center_bp.route('/api/session/create', methods=['POST'])
@login_required
def api_session_create():
    """Create a new recording session"""
    success, message, session_id = session_service.create_session(current_user.username)
    
    return jsonify({
        'success': success,
        'message': message,
        'session_id': session_id
    })


@control_center_bp.route('/api/session/status', methods=['GET'])
@login_required
def api_session_status():
    """Get current session status"""
    session = session_service.get_active_session()
    summary = session_service.get_session_summary()
    
    # Add stats for completed count
    completed_today = 0
    try:
        from app.services.stats_service import StatsService
        stats_service = StatsService(db, PackingRecord)
        stats = stats_service.get_today_stats()
        completed_today = stats.get('completed', 0)
    except Exception as e:
        print(f"[Session] Failed to get stats: {e}")
        
    # Inject completed count into summary
    summary['completed'] = completed_today
    
    return jsonify({
        'session': session,
        'summary': summary
    })


@control_center_bp.route('/api/session/end', methods=['POST'])
@login_required
def api_session_end():
    """End current session"""
    success, message = session_service.end_session()
    
    return jsonify({
        'success': success,
        'message': message
    })


@control_center_bp.route('/api/employees', methods=['GET'])
@login_required
def api_employees_list():
    """Get list of active employees"""
    from app.models import Pegawai
    
    employees = Pegawai.query.filter_by(is_active=True).all()
    
    return jsonify({
        'success': True,
        'employees': [{'id': p.id, 'nama': p.nama} for p in employees]
    })


# ============================================
# CAMERA ASSIGNMENT API
# ============================================

@control_center_bp.route('/api/session/assign-camera', methods=['POST'])
@login_required
def api_assign_camera():
    """Assign a camera to an employee"""
    data = request.get_json()
    camera_url = data.get('camera_url')
    employee_name = data.get('employee_name')
    platform = data.get('platform', 'LAINNYA')
    
    if not camera_url or not employee_name:
        return jsonify({
            'success': False,
            'message': 'Camera URL dan nama pegawai harus diisi'
        }), 400
    
    success, message = session_service.assign_camera(camera_url, employee_name, platform)
    
    return jsonify({
        'success': success,
        'message': message
    })


@control_center_bp.route('/api/session/unassign-camera', methods=['POST'])
@login_required
def api_unassign_camera():
    """Remove camera assignment"""
    data = request.get_json()
    camera_url = data.get('camera_url')
    
    if not camera_url:
        return jsonify({
            'success': False,
            'message': 'Camera URL harus diisi'
        }), 400
    
    success, message = session_service.unassign_camera(camera_url)
    
    return jsonify({
        'success': success,
        'message': message
    })


@control_center_bp.route('/api/session/cameras', methods=['GET'])
@login_required
def api_session_cameras():
    """Get all cameras in current session"""
    cameras = session_service.get_all_cameras_status()
    
    return jsonify({
        'success': True,
        'cameras': cameras
    })


# ============================================
# RECORDING CONTROL API (Session-Aware)
# ============================================

@control_center_bp.route('/api/session/start-recording', methods=['POST'])
@login_required
def api_session_start_recording():
    """Start recording for a specific camera in session"""
    data = request.get_json()
    camera_url = data.get('camera_url')
    barcode = data.get('barcode')
    
    if not camera_url or not barcode:
        return jsonify({
            'success': False,
            'message': 'Camera URL dan barcode harus diisi'
        }), 400
    
    # Get camera assignment
    cam_status = session_service.get_camera_status(camera_url)
    if not cam_status:
        return jsonify({
            'success': False,
            'message': 'Kamera tidak ditemukan dalam sesi'
        }), 404
    
    # Check if barcode is already in use by another camera
    if session_service.is_barcode_in_use(barcode, exclude_camera=camera_url):
        return jsonify({
            'success': False,
            'message': 'Barcode sedang digunakan oleh kamera lain'
        }), 400
    
    # Check if this camera is already recording
    if cam_status['status'] == 'recording':
        # If same barcode, stop recording
        if cam_status['last_barcode'] == barcode:
            return api_session_stop_recording_internal(camera_url, barcode)
        else:
            return jsonify({
                'success': False,
                'message': 'Kamera sedang merekam barcode lain'
            }), 400
    
    # Start recording
    recording_service = RecordingService(db, PackingRecord)
    success, message, recording_id = recording_service.start_recording(
        resi=barcode,
        pegawai=cam_status['employee_name'],
        platform=cam_status['platform'],
        camera_url=camera_url
    )
    
    if success:
        # Update session status
        session_service.update_camera_status(
            camera_url, 
            'recording',
            recording_id=recording_id,
            last_barcode=barcode
        )
    
    return jsonify({
        'success': success,
        'message': message,
        'recording_id': recording_id
    })


def api_session_stop_recording_internal(camera_url, barcode):
    """Internal helper to stop recording"""
    cam_status = session_service.get_camera_status(camera_url)
    if not cam_status:
        return jsonify({
            'success': False,
            'message': 'Kamera tidak ditemukan'
        }), 404
    
    recording_id = cam_status.get('recording_id')
    if not recording_id:
        return jsonify({
            'success': False,
            'message': 'Tidak ada rekaman aktif'
        }), 400
    
    # Stop recording
    recording_service = RecordingService(db, PackingRecord)
    success, message, result_data = recording_service.stop_recording(recording_id, save_video=True)
    
    if success:
        # Update session status
        session_service.update_camera_status(
            camera_url,
            'idle',
            recording_id=None,
            last_barcode=None
        )
    
    return jsonify({
        'success': success,
        'message': message,
        **result_data
    })


@control_center_bp.route('/api/session/stop-recording', methods=['POST'])
@login_required
def api_session_stop_recording():
    """Stop recording for a specific camera"""
    data = request.get_json()
    camera_url = data.get('camera_url')
    barcode = data.get('barcode')  # Optional verification
    
    if not camera_url:
        return jsonify({
            'success': False,
            'message': 'Camera URL harus diisi'
        }), 400
    
    return api_session_stop_recording_internal(camera_url, barcode)


@control_center_bp.route('/api/session/cancel-recording', methods=['POST'])
@login_required
def api_session_cancel_recording():
    """Cancel recording for a specific camera"""
    data = request.get_json()
    camera_url = data.get('camera_url')
    
    if not camera_url:
        return jsonify({
            'success': False,
            'message': 'Camera URL harus diisi'
        }), 400
    
    cam_status = session_service.get_camera_status(camera_url)
    if not cam_status:
        return jsonify({
            'success': False,
            'message': 'Kamera tidak ditemukan'
        }), 404
    
    recording_id = cam_status.get('recording_id')
    if not recording_id:
        return jsonify({
            'success': False,
            'message': 'Tidak ada rekaman aktif'
        }), 400
    
    # Cancel recording
    recording_service = RecordingService(db, PackingRecord)
    success, message, _ = recording_service.cancel_recording(recording_id)
    
    if success:
        # Update session status
        session_service.update_camera_status(
            camera_url,
            'idle',
            recording_id=None,
            last_barcode=None
        )
    
    return jsonify({
        'success': success,
        'message': message
    })
