"""
Recording Routes Blueprint
===========================
Routes for video recording operations

📁 Copy to: dashboard_flask_refactored/app/routes/recording.py
"""

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.services import RecordingService, BarcodeService
from app.services.camera_service import get_camera_stream
from app.models import db, PackingRecord
import config

recording_bp = Blueprint('recording', __name__)


@recording_bp.route('/rekam-packing')
@login_required
def rekam_packing():
    """Packing recording page"""
    return render_template('pages/recording.html',
        platforms=config.PLATFORMS,
        default_rtsp_url=config.DEFAULT_RTSP_URL
    )


@recording_bp.route('/api/recording/start', methods=['POST'])
@login_required
def api_recording_start():
    """Start new recording"""
    data = request.get_json()
    resi = data.get('resi')
    pegawai = data.get('pegawai')
    
    # Auto-fill pegawai from current user if missing
    if not pegawai and current_user.is_authenticated:
        # Try 'nama' attribute first (if custom User model), else 'username'
        pegawai = getattr(current_user, 'nama', current_user.username)
        
    platform = data.get('platform', 'LAINNYA')
    camera_url = data.get('camera_url', '0')
    
    if not resi or not pegawai:
        return jsonify({
            'success': False,
            'error': 'Resi dan pegawai harus diisi'
        }), 400
    
    recording_service = RecordingService(db, PackingRecord)
    success, message, recording_id = recording_service.start_recording(
        resi, pegawai, platform, camera_url
    )
    
    return jsonify({
        'success': success,
        'message': message,
        'recording_id': recording_id
    })


@recording_bp.route('/api/recording/stop', methods=['POST'])
@login_required
def api_recording_stop():
    """Stop active recording"""
    data = request.get_json() or {}
    recording_id = data.get('recording_id')
    
    recording_service = RecordingService(db, PackingRecord)
    success, message, result_data = recording_service.stop_recording(recording_id, save_video=True)
    
    response = {
        'success': success,
        'message': message
    }
    if result_data:
        response.update(result_data)
        
    return jsonify(response)


@recording_bp.route('/api/recording/cancel', methods=['POST'])
@login_required
def api_recording_cancel():
    """Cancel active recording"""
    data = request.get_json() or {}
    recording_id = data.get('recording_id')
    
    recording_service = RecordingService(db, PackingRecord)
    # Ignore data for cancel
    success, message, _ = recording_service.cancel_recording(recording_id)
    
    return jsonify({
        'success': success,
        'message': message
    })





@recording_bp.route('/api/recordings/active', methods=['GET'])
@login_required
def api_recordings_active():
    """Check if there is an active recording"""
    from app.services.recording_service import active_recordings, recording_lock
    import time
    
    with recording_lock:
        # Check active recordings
        if active_recordings:
            # Get the first one (assuming single user/station for now)
            # Or filter by user_id if we had that in memory dict
            rid = list(active_recordings.keys())[0]
            info = active_recordings[rid]
            
            return jsonify({
                'active': True,
                'recording_id': rid,
                'resi': info['resi'],
                'platform': info.get('platform') or 'Unknown',
                'start_time': info['start_time'],
                'duration': time.time() - info['start_time']
            })
        
        return jsonify({'active': False})


@recording_bp.route('/api/barcode/detect', methods=['POST'])
@login_required
def api_barcode_detect():
    """Detect barcode from camera frame"""
    data = request.get_json()
    camera_url = data.get('camera_url', '0')
    
    # Get camera stream
    camera = get_camera_stream(camera_url)
    if camera is None:
        return jsonify({
            'success': False,
            'error': 'Camera not available'
        })
    
    # Get frame
    frame = camera.get_raw_frame()
    if frame is None:
        return jsonify({
            'success': False,
            'error': 'Failed to get frame'
        })
    
    # Detect barcode
    barcode = BarcodeService.detect_barcode_from_frame(frame)
    
    if barcode:
        return jsonify({
            'success': True,
            'barcode': barcode
        })
    else:
        return jsonify({
            'success': False,
            'error': 'No barcode detected'
        })

