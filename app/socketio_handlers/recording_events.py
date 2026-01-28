"""
SocketIO Handlers
=================
WebSocket event handlers for real-time updates

📁 Copy to: dashboard_flask_refactored/app/socketio_handlers/recording_events.py
"""

from flask_socketio import emit
from flask_login import current_user
from app.services import RecordingService, SessionService
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
        success, message, _ = recording_service.stop_recording(recording_id, save_video=True)
        
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
        success, message, _ = recording_service.cancel_recording(recording_id)
        
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
            # print(f"[SocketIO] Scanning... Found: {barcode if barcode else 'NO'}")
            
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

    @socketio.on('session_barcode_scan')
    def handle_session_barcode_scan(data):
        """
        Handle barcode scan in session mode (Control Center)
        Automatically starts/stops recording based on camera state
        """
        camera_url = data.get('camera_url')
        image_data = data.get('image')  # Support base64 image from client
        
        if not camera_url:
            emit('session_scan_result', {'success': False, 'error': 'Camera URL required'})
            return
        
        try:
            from app.services.camera_service import get_camera_stream
            from app.services.barcode_service import BarcodeService
            import time
            import base64
            import cv2
            import numpy as np
            
            frame = None
            
            # Case 1: Client sent image (Base64) - PREFERRED for non-blocking
            if image_data:
                try:
                    # Remove header if present (data:image/jpeg;base64,...)
                    if ',' in image_data:
                        image_data = image_data.split(',')[1]
                    
                    img_bytes = base64.b64decode(image_data)
                    nparr = np.frombuffer(img_bytes, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                except Exception as e:
                    print(f"[SocketIO] Failed to decode client image: {e}")
            
            # Case 2: Fallback to server-side frame capture
            if frame is None:
                # Get camera instance
                camera = get_camera_stream(camera_url)
                if not camera:
                    emit('session_scan_result', {'success': False, 'error': 'Camera unavailable'})
                    return
                # Get raw frame
                frame = camera.get_raw_frame()
            
            if frame is None:
                # Silent fail if no frame available
                return
            
            # Detect barcode
            barcode = BarcodeService.detect_barcode_from_frame(frame)
            
            if not barcode:
                # No barcode found, just return silently
                return
            
            print(f"[Scanning] Barcode detected: {barcode} on camera {camera_url}")
            
            # Get session service
            session_service = SessionService()
            cam_status = session_service.get_camera_status(camera_url)
            
            if not cam_status:
                emit('session_scan_result', {'success': False, 'error': 'Camera not in session'})
                return
            
            # Check if barcode is in use by another camera
            if session_service.is_barcode_in_use(barcode, exclude_camera=camera_url):
                print(f"[Scanning] Conflict: Barcode {barcode} already in use")
                emit('session_scan_result', {
                    'success': False,
                    'error': 'Barcode sedang digunakan oleh kamera lain'
                })
                socketio.emit('camera_event', {
                    'camera_url': camera_url,
                    'event_type': 'error',
                    'message': 'Barcode conflict'
                }, broadcast=True)
                return
            
            current_time = time.time()
            
            # Determine action based on current status
            # Determine action based on current status

            if cam_status['status'] == 'idle':
                # ANTI-LOOP CHECK: Prevent restarting recording for same barcode immediately after stop
                prev_barcode = cam_status.get('previous_barcode')
                prev_time = cam_status.get('previous_stop_time', 0)
                
                if prev_barcode == barcode and (current_time - prev_time < 5.0):
                    print(f"[Scanning] Ignored START request for {barcode} (Cooldown active after Stop: {current_time - prev_time:.1f}s)")
                    emit('session_scan_result', {'success': True, 'found': True, 'action': 'ignored_cooldown'})
                    return

                print(f"[Scanning] STARTING recording for {barcode}")
                
                # Start recording
                recording_service = RecordingService(db, PackingRecord)
                
                success, message, recording_id = recording_service.start_recording(
                    resi=barcode,
                    pegawai=cam_status['employee_name'],
                    platform=cam_status['platform'],
                    camera_url=camera_url
                )
                
                if success:
                    session_service.update_camera_status(
                        camera_url,
                        'recording',
                        recording_id=recording_id,
                        last_barcode=barcode
                    )
                    
                    emit('session_scan_result', {
                        'success': True,
                        'action': 'start',
                        'barcode': barcode,
                        'recording_id': recording_id
                    })
                    
                    # Broadcast to all clients
                    socketio.emit('camera_event', {
                        'camera_url': camera_url,
                        'event_type': 'recording_start',
                        'barcode': barcode
                    }, broadcast=True)
                else:
                    print(f"[Scanning] Failed to start: {message}")
                    emit('session_scan_result', {'success': False, 'error': message})

            elif cam_status['status'] == 'recording':
                # Check if same barcode (stop) or different (error)
                last_barcode = cam_status.get('last_barcode')
                
                if last_barcode == barcode:
                    
                    # DEBOUNCE CHECK: Prevent stopping immediately after start
                    # Use last_scan_time which is updated when status changes to recording
                    last_scan_time = cam_status.get('last_scan_time')
                    if last_scan_time and (current_time - last_scan_time < 5.0): # 5 seconds cooldown
                        print(f"[Scanning] Ignored STOP request for {barcode} (Cooldown active: {current_time - last_scan_time:.1f}s)")
                        # Do nothing, emit success (ignored)
                        emit('session_scan_result', {'success': True, 'found': True, 'action': 'ignored_cooldown'})
                        return

                    print(f"[Scanning] STOPPING recording for {barcode}")
                    
                    # Stop recording
                    recording_id = cam_status['recording_id']
                    recording_service = RecordingService(db, PackingRecord)
                    success, message, result_data = recording_service.stop_recording(recording_id, save_video=True)
                    
                    if success:
                        session_service.update_camera_status(
                            camera_url,
                            'idle',
                            recording_id=None,
                            last_barcode=None,
                            previous_barcode=barcode,
                            previous_stop_time=current_time
                        )
                        
                        emit('session_scan_result', {
                            'success': True,
                            'action': 'stop',
                            'barcode': barcode,
                            **result_data
                        })
                        
                        # Broadcast to all clients
                        socketio.emit('camera_event', {
                            'camera_url': camera_url,
                            'event_type': 'recording_stop',
                            'barcode': barcode
                        }, broadcast=True)
                    else:
                        print(f"[Scanning] Failed to stop: {message}")
                        emit('session_scan_result', {'success': False, 'error': message})
                else:
                    # Different barcode while recording
                    print(f"[Scanning] Conflict: Recording {last_barcode} but scanned {barcode}")
                    emit('session_scan_result', {
                        'success': False,
                        'error': f'Kamera sedang merekam {last_barcode}'
                    })
                    socketio.emit('camera_event', {
                        'camera_url': camera_url,
                        'event_type': 'error',
                        'message': 'Barcode mismatch/Sedang Merekam'
                    }, broadcast=True)
            else:
                emit('session_scan_result', {
                    'success': False,
                    'error': f'Camera status tidak valid: {cam_status["status"]}'
                })
                
        except Exception as e:
            import traceback
            print(f"[SocketIO Session] Error: {e}")
            print(traceback.format_exc())
            emit('session_scan_result', {'success': False, 'error': str(e)})
