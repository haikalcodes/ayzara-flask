"""
Camera Routes Blueprint
========================
Routes for camera operations, detection, and streaming

📁 Copy to: dashboard_flask_refactored/app/routes/camera.py
"""

from flask import Blueprint, render_template, jsonify, request, Response
from flask_login import login_required
from app.services.camera_service import (
    detect_local_cameras, perform_camera_discovery,
    get_camera_stream, gen_frames, camera_status_cache,
    status_cache_lock
)
import config

camera_bp = Blueprint('camera', __name__)


@camera_bp.route('/camera')
@login_required
def camera():
    """Camera capture page"""
    return render_template('pages/camera.html',
        rtsp_url=config.DEFAULT_RTSP_URL
    )


@camera_bp.route('/camera-settings')
@login_required
def camera_settings():
    """Camera settings/management page"""
    return render_template('pages/camera_settings.html')


@camera_bp.route('/api/cameras/detect-local')
@login_required
def api_detect_local_cameras():
    """Detect local USB/webcams"""
    cameras = detect_local_cameras()
    return jsonify({'cameras': cameras})


@camera_bp.route('/api/cameras/discover')
@login_required
def api_cameras_discover():
    """Discover IP cameras on network"""
    timeout = request.args.get('timeout', 3.0, type=float)
    cameras = perform_camera_discovery(timeout)
    return jsonify({
        'success': True,
        'cameras': cameras,
        'count': len(cameras)
    })


@camera_bp.route('/api/cameras/status')
@login_required
def api_cameras_status():
    """
    Get cached camera statuses.
    Optional: ?refresh=true to force concurrent re-check of all cameras
    """
    refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    if refresh:
        project_cfg = _load_project_config()
        cameras = project_cfg.get('camera_list', [])
        
        # Helper to check and update cache logic (similar to test endpoint)
        def check_worker(cam_url):
            try:
                # Basic connection test logic
                is_online = False
                msg = "Offline"
                
                # Check Local
                if str(cam_url).isdigit():
                    idx = int(cam_url)
                    from app.services.camera_service import safe_hardware_lock
                    try:
                        with safe_hardware_lock(idx, timeout=2.0) as acquired:
                            if not acquired:
                                is_online = False
                                msg = "Busy"
                            else:
                                import cv2
                                cap = cv2.VideoCapture(idx)
                                if cap.isOpened():
                                    ret, _ = cap.read()
                                    cap.release()
                                    is_online = ret
                                    msg = "OK" if ret else "No frame"
                    except:
                        pass
                # Check IP
                else:
                    import cv2
                    import os
                    if 'rtsp' in str(cam_url):
                        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
                    
                    # Force FFmpeg backend for consistency
                    cap = cv2.VideoCapture(cam_url, cv2.CAP_FFMPEG)
                    
                    if cap.isOpened():
                        # Retry reading frames (sometimes first frame is empty/header)
                        ret = False
                        for _ in range(3):
                            ret, _ = cap.read()
                            if ret:
                                break
                            time.sleep(0.1)
                            
                        cap.release()
                        is_online = ret
                        msg = "OK" if ret else "Stream opened but NO FRAME"
                        print(f"[Status] IP Check {cam_url} -> Opened: True, GotFrame: {ret}")
                    else:
                        is_online = False
                        msg = "Failed to connect"
                        print(f"[Status] IP Check {cam_url} -> Opened: False")
                
                # Update cache
                with status_cache_lock:
                    current = camera_status_cache.get(cam_url, {})
                    camera_status_cache[cam_url] = {
                        'url': cam_url,
                        'online': is_online,
                        'message': msg,
                        'last_checked': time.time(),
                        # Preserve existing usage info
                        'in_use': current.get('in_use', False),
                        'in_use_by': current.get('in_use_by'),
                        'purpose': current.get('purpose')
                    }
                    
            except Exception as e:
                print(f"[Status] Error checking {cam_url}: {e}")

        # Spawn threads
        threads = []
        for cam in cameras:
            url = cam.get('url')
            if url:
                t = threading.Thread(target=check_worker, args=(url,))
                t.start()
                threads.append(t)
        
        # Wait for threads (max 3 seconds total)
        for t in threads:
            t.join(timeout=3.0)

    with status_cache_lock:
        statuses = list(camera_status_cache.values())
    
    return jsonify({
        'success': True,
        'cameras': statuses,
        'count': len(statuses)
    })


@camera_bp.route('/api/camera/feed/<path:camera_url>')
@login_required
def camera_feed(camera_url):
    """Video feed endpoint"""
    camera = get_camera_stream(camera_url)
    if camera is None:
        return jsonify({'error': 'Camera not available'}), 404
    
    return Response(gen_frames(camera),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_bp.route('/video_feed')
@login_required
def video_feed():
    """Legacy video feed endpoint (for compatibility)"""
    url = request.args.get('url')
    if not url:
        return "URL parameter required", 400
        
    # Mark usage for preview/monitoring
    from flask_login import current_user
    from app.services.camera_service import mark_camera_in_use
    from flask import stream_with_context
    
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


@camera_bp.route('/api/camera/release', methods=['POST'])
@login_required
def api_camera_release():
    """Explicitly release/stop a camera stream"""
    data = request.get_json()
    url = data.get('url', '')
    
    from app.services.camera_service import (
        active_cameras, camera_lock, 
        camera_usage, camera_usage_lock
    )
    
    with camera_lock:
        if url in active_cameras:
            print(f"[Camera] Explicit release requested for: {url}")
            active_cameras[url].stop()
            del active_cameras[url]
            
            # Clear camera usage when releasing
            with camera_usage_lock:
                if url in camera_usage:
                    print(f"[Camera] Clearing usage info for: {url}")
                    del camera_usage[url]
            
            return jsonify({'success': True})
            
    return jsonify({'success': True, 'message': 'Camera not active'})


@camera_bp.route('/api/camera/check', methods=['GET'])
@login_required
def api_camera_check():
    """Check if specific camera stream is currently active and running"""
    url = request.args.get('url')
    if not url:
        return jsonify({'active': False, 'error': 'No URL provided'})
        
    from app.services.camera_service import active_cameras, camera_lock
    
    with camera_lock:
        if url in active_cameras:
            cam = active_cameras[url]
            # It is active if it exists, running, AND has received frames recently
            import time
            current_time = time.time()
            is_healthy = False
            
            # Check if camera has received a frame in the last 5 seconds
            if cam.running and cam.last_frame is not None:
                if (current_time - cam.last_update) < 5.0:
                    is_healthy = True
            
            return jsonify({'active': is_healthy})
                
    return jsonify({'active': False})


@camera_bp.route('/api/camera/capture', methods=['POST'])
@login_required
def api_camera_capture():
    """Capture single frame from camera and return as Base64 (no save)"""
    data = request.get_json() or {}
    url = data.get('url', '0')
    
    camera = get_camera_stream(url)
    if camera is None:
        return jsonify({'success': False, 'error': 'Camera not available'})
    
    # Get frame
    frame = camera.get_raw_frame()
    if frame is None:
        return jsonify({'success': False, 'error': 'Failed to capture frame'})
    
    # Encode to Base64
    import cv2
    import base64
    import time
    
    # Compress to jpg
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        return jsonify({'success': False, 'error': 'Failed to encode image'})
        
    # Valid image bytes
    jpg_as_text = base64.b64encode(buffer).decode('utf-8')
    base64_image = f"data:image/jpeg;base64,{jpg_as_text}"
    
    filename = f"capture_{int(time.time())}.jpg"
    
    return jsonify({
        'success': True,
        'filename': filename,
        'image_base64': base64_image
    })


@camera_bp.route('/api/camera/snapshot', methods=['GET'])
@login_required
def api_camera_snapshot():
    """Get single snapshot from camera as JPEG image"""
    url = request.args.get('url', '0')
    
    camera = get_camera_stream(url)
    if camera is None:
        # Return placeholder image
        from flask import send_file
        import io
        import cv2
        import numpy as np
        
        # Create a simple placeholder
        placeholder = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(placeholder, 'Camera Offline', (50, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        ret, buffer = cv2.imencode('.jpg', placeholder)
        return Response(buffer.tobytes(), mimetype='image/jpeg')
    
    # Get frame
    frame = camera.get_raw_frame()
    if frame is None:
        # Return placeholder
        import numpy as np
        placeholder = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(placeholder, 'No Frame', (80, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        ret, buffer = cv2.imencode('.jpg', placeholder)
        return Response(buffer.tobytes(), mimetype='image/jpeg')
    
    # Encode to JPEG
    import cv2
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ret:
        return "Failed to encode", 500
    
    return Response(buffer.tobytes(), mimetype='image/jpeg')


@camera_bp.route('/api/camera/zoom', methods=['POST'])
@login_required
def api_camera_zoom():
    """Set zoom level for camera"""
    data = request.get_json()
    url = data.get('url')
    level = float(data.get('level', 1.0))
    
    # Range check
    level = max(1.0, min(4.0, level))
    
    from app.services.camera_service import active_cameras, camera_lock
    
    with camera_lock:
        if url in active_cameras:
            cam = active_cameras[url]
            cam.zoom_level = level
            return jsonify({'success': True, 'zoom_level': level})
    
    return jsonify({'success': False, 'message': 'Camera not active'}), 404


@camera_bp.route('/api/camera/usage', methods=['POST'])
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

    from flask_login import current_user
    from app.services.camera_service import mark_camera_in_use
    
    username = current_user.username if current_user.is_authenticated else 'Unknown'
    mark_camera_in_use(url, username, purpose)
    return jsonify({'success': True})


# ============================================
# CAMERA MANAGEMENT API
# ============================================

import json
import threading
import time
import subprocess
import cv2

_project_config_cache = None
_config_lock = threading.Lock()

def _load_project_config():
    """Load config.json with caching"""
    global _project_config_cache
    try:
        with _config_lock:
            if _project_config_cache is None:
                if config.CONFIG_FILE.exists():
                    with open(config.CONFIG_FILE, 'r', encoding='utf-8') as f:
                        _project_config_cache = json.load(f)
                else:
                    _project_config_cache = {}
            return _project_config_cache.copy()
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def _save_project_config(cfg):
    """Save config.json with caching"""
    global _project_config_cache
    try:
        with _config_lock:
            if config.CONFIG_FILE.exists():
                with open(config.CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
                _project_config_cache = cfg.copy()
                return True
    except Exception as e:
        print(f"Error saving config: {e}")
    return False


@camera_bp.route('/api/cameras', methods=['GET'])
@login_required
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


@camera_bp.route('/api/cameras', methods=['POST'])
@login_required
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


@camera_bp.route('/api/cameras/<int:camera_id>', methods=['PUT'])
@login_required
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


@camera_bp.route('/api/cameras/<int:camera_id>', methods=['DELETE'])
@login_required
def api_cameras_delete(camera_id):
    """Delete camera from config"""
    # Load config
    project_cfg = _load_project_config()
    cameras = project_cfg.get('camera_list', [])
    
    # Find and remove camera
    camera_idx = None
    for idx, cam in enumerate(cameras):
        if cam.get('id') == camera_id:
            camera_idx = idx
            break
    
    if camera_idx is None:
        return jsonify({'success': False, 'message': 'Kamera tidak ditemukan'}), 404
    
    # Remove camera
    removed_camera = cameras.pop(camera_idx)
    
    # Save
    project_cfg['camera_list'] = cameras
    if _save_project_config(project_cfg):
        return jsonify({'success': True, 'message': 'Kamera berhasil dihapus', 'camera': removed_camera})
    else:
        return jsonify({'success': False, 'message': 'Gagal menyimpan config'}), 500


@camera_bp.route('/api/cameras/test', methods=['POST'])
@login_required
def api_cameras_test():
    """Test camera connection"""
    data = request.get_json()
    url = data.get('url', '') if data else ''
    
    if not url:
        return jsonify({'success': False, 'message': 'URL tidak valid'}), 400
    
    # Load FFmpeg path from config
    project_cfg = _load_project_config()
    ffmpeg_path = project_cfg.get('ffmpeg_path', 'ffmpeg')
    rtsp_transport = project_cfg.get('rtsp_transport', 'tcp')
    
    try:
        # Test connection
        if str(url).isdigit():
            # Local camera test
            from app.services.camera_service import safe_hardware_lock
            try:
                with safe_hardware_lock(url, timeout=10.0) as acquired:
                    if not acquired:
                        return jsonify({'success': False, 'message': 'Hardware sibuk (timeout 10s). Coba lagi.'})
                    
                    v_src = int(url)
                    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF]
                        
                    success = False
                    for backend in backends:
                        try:
                            cap = cv2.VideoCapture(v_src, backend)
                            if cap and cap.isOpened():
                                time.sleep(0.1)
                                ret, _ = cap.read()
                                if ret:
                                    success = True
                                    cap.release()
                                    break
                            if cap: cap.release()
                        except:
                            pass
            except Exception as e:
                print(f"[Camera] api_cameras_test exception: {e}")
                success = False
        else:
            # IP Camera test via FFmpeg
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
        from app.services.camera_service import camera_status_cache, status_cache_lock
        with status_cache_lock:
            camera_status_cache[url] = {
                'online': success,
                'last_checked': time.time(),
                'url': url
            }

        if success:
            return jsonify({'success': True, 'message': 'Koneksi berhasil'})
        else:
            if not str(url).isdigit() and 'result' in locals():
                stderr = result.stderr.decode('utf-8', errors='ignore')
                if 'Connection refused' in stderr:
                    msg = 'Koneksi ditolak - periksa IP dan port'
                elif 'timeout' in stderr.lower():
                    msg = 'Timeout - periksa koneksi jaringan'
                else:
                    msg = f'Error (code {result.returncode})'
            else:
                msg = 'Gagal terhubung ke kamera hardware/lokal'
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
