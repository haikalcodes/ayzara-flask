"""
SocketIO Handlers
=================
WebSocket event handlers for real-time updates

📁 Copy to: dashboard_flask_refactored/app/socketio_handlers/recording_events.py
"""

from flask_socketio import emit
from flask_login import current_user
from app.services import RecordingService
from app.models import db, PackingRecord


def register_socketio_handlers(socketio):
    """Register all SocketIO event handlers"""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        print(f'[SocketIO] Client connected: {current_user.username if current_user.is_authenticated else "Anonymous"}')
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        print(f'[SocketIO] Client disconnected')
    
    @socketio.on('request_status')
    def handle_request_status():
        """Handle status request from client"""
        recording_service = RecordingService(db, PackingRecord)
        status = recording_service.get_recording_status()
        emit('status_update', status)
    
    @socketio.on('start_recording')
    def handle_start_recording(data):
        """Handle start recording request"""
        resi = data.get('resi')
        pegawai = data.get('pegawai')
        platform = data.get('platform', 'LAINNYA')
        camera_url = data.get('camera_url', '0')
        
        recording_service = RecordingService(db, PackingRecord)
        success, message, recording_id = recording_service.start_recording(
            resi, pegawai, platform, camera_url
        )
        
        # Emit result to requesting client
        emit('recording_started', {
            'success': success,
            'message': message,
            'recording_id': recording_id
        })
        
        # Broadcast status update to all clients
        if success:
            status = recording_service.get_recording_status()
            socketio.emit('status_update', status, broadcast=True)
    
    @socketio.on('stop_recording')
    def handle_stop_recording(data):
        """Handle stop recording request"""
        recording_id = data.get('recording_id')
        
        recording_service = RecordingService(db, PackingRecord)
        success, message = recording_service.stop_recording(recording_id, save_video=True)
        
        # Emit result to requesting client
        emit('recording_stopped', {
            'success': success,
            'message': message
        })
        
        # Broadcast status update to all clients
        status = recording_service.get_recording_status()
        socketio.emit('status_update', status, broadcast=True)
    
    @socketio.on('cancel_recording')
    def handle_cancel_recording(data):
        """Handle cancel recording request"""
        recording_id = data.get('recording_id')
        
        recording_service = RecordingService(db, PackingRecord)
        success, message = recording_service.cancel_recording(recording_id)
        
        # Emit result to requesting client
        emit('recording_cancelled', {
            'success': success,
            'message': message
        })
        
        # Broadcast status update to all clients
        status = recording_service.get_recording_status()
        socketio.emit('status_update', status, broadcast=True)

    @socketio.on('detect_barcode')
    def handle_detect_barcode(data):
        """Handle barcode detection request from camera stream"""
        url = data.get('url')
        if not url:
            return
            
        try:
            from app.services.camera_service import get_camera_stream
            from app.services.barcode_service import BarcodeService
            
            # Get camera instance
            camera = get_camera_stream(url)
            if not camera:
                emit('barcode_result', {'success': False, 'found': False, 'error': 'Camera unavailable'})
                return
                
            # Get raw frame
            frame = camera.get_raw_frame()
            if frame is None:
                emit('barcode_result', {'success': False, 'found': False, 'error': 'No frame'})
                return
                
            # Detect barcode
            barcode = BarcodeService.detect_barcode_from_frame(frame)
            
            # DEBUG: Visibility for user
            print(f"[SocketIO] Scanning... Found: {barcode if barcode else 'NO'}")
            
            # DEBUG: Save frame to check quality (overwrite)
            try:
                import cv2
                cv2.imwrite('last_scan_debug.jpg', frame)
            except:
                pass

            if barcode:
                print(f"[SocketIO] ✅ BARCODE FOUND: {barcode}")
                emit('barcode_result', {
                    'success': True,
                    'found': True,
                    'barcodes': [{'data': barcode}]
                })
            else:
                emit('barcode_result', {
                    'success': True,
                    'found': False,
                    'barcodes': []
                })
                
        except Exception as e:
            print(f"[SocketIO] Barcode detection error: {e}")
            emit('barcode_result', {'success': False, 'error': str(e)})

