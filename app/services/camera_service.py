"""
Camera Service
==============
Complete camera management service including VideoCamera class,
camera discovery, status checking, and background monitoring.
"""

import cv2
import threading
import time
import socket
import select
import re
import xml.etree.ElementTree as ET
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import platform
import platform
import numpy as np
from app.utils.logger import video_logger

# [ANTIGRAVITY] GEVENT THREADPOOL
# OpenCV calls are blocking C-functions that don't yield in Gevent.
# We must run them in a real threadpool to keep the server responsive.
import gevent
from gevent.threadpool import ThreadPool
from app.utils.safe_execution import safe_thread_loop

_gevent_pool = ThreadPool(20) # Dedicate 20 real threads for camera I/O

def run_cv(func, *args, **kwargs):
    """
    Helper to run blocking OpenCV functions in the threadpool.
    Accepts specific args and kwargs.
    """
    return _gevent_pool.apply(func, args, kwargs)



# ============================================
# HARDWARE LOCK MANAGEMENT
# ============================================

# Per-index locks for local cameras
index_locks = {i: threading.Lock() for i in range(32)}
global_hardware_lock = threading.Lock()

@contextmanager
def safe_hardware_lock(url, timeout=5.0):
    """
    Acquire a lock based on the camera URL/index.
    If it's a local camera (digit), use the specific index lock.
    """
    lock_to_use = global_hardware_lock
    if str(url).isdigit():
        idx = int(url)
        if idx in index_locks:
            lock_to_use = index_locks[idx]
            
    acquired = lock_to_use.acquire(timeout=timeout)
    try:
        yield acquired
    finally:
        if acquired:
            lock_to_use.release()


# ============================================
# VIDEO CAMERA CLASS
# ============================================

class VideoCamera:
    """
    Threaded camera streaming class with hardware management
    """
    
    def __init__(self, url):
        self.url = url
        self.last_frame = None
        # [ANTIGRAVITY] DOUBLE BUFFERING
        # self.last_jpeg: Stores the latest PRE-ENCODED Jpeg for streaming (Preview)
        # self.last_frame: Stores the latest RAW frame for recording/barcode (Processing)
        self.last_jpeg = None
        self.lock = threading.Lock()
        self.running = True
        self.last_access = time.time()
        self.last_update = time.time()
        self.consecutive_errors = 0
        self.zoom_level = 1.0  # 1.0 = no zoom, 2.0 = 2x zoom
        self.last_heartbeat = time.time()  # Initialize heartbeat
        
        self.zoom_level = 1.0  # 1.0 = no zoom, 2.0 = 2x zoom
        self.last_heartbeat = time.time()  # Initialize heartbeat
        self.start_time = time.time() # [ANTIGRAVITY] Track creation time for grace period
        
        # Adaptive FPS for CPU optimization
        self.usage_mode = 'preview'  # 'preview', 'scan', 'record'
        self.target_fps = 30  # Default to 30 FPS for responsiveness
        
        # Determine backend
        is_local = str(url).isdigit()
        
        if is_local:
            # Try DirectShow first, fallback to MSMF
            # [ANTIGRAVITY] MOVED TO UPDATE() for Thread Affinity
            self.cap = None 
        else:
            # IP camera
            self.cap = None

        
        # [ANTIGRAVITY] MOVED PROPERTY SETTING TO UPDATE()
        # if self.cap.isOpened():
        #    ...
            
        print(f"[Camera] {url} init pending (background thread)...")
        
        # [ANTIGRAVITY] THREAD AFFINITY FIX
        # Instead of a Greenlet (threading.Thread patched), we use a REAL WORKER THREAD
        # from the threadpool to host the entire camera loop. 
        # This ensures init and read happen in the SAME real thread.
        self.running = True
        
        # [ANTIGRAVITY] STORE RESULT FOR JOINING
        # We store the AsyncResult to allow 'joining' (waiting) later.
        self.worker_task = _gevent_pool.apply_async(self.update)

    
    def __del__(self):
        self.stop()
    
    def stop(self):
        """Explicitly stop the camera stream and FORCE hardware release"""
        print(f"[Camera] Stopping {self.url}...")
        self.running = False

        # [ANTIGRAVITY] PROPER JOINING
        # Use the stored AsyncResult from the threadpool
        if hasattr(self, 'worker_task') and self.worker_task:
            try:
                # wait() blocks until the task is ready (finished)
                self.worker_task.wait(timeout=3.0)
                print(f"[Camera] {self.url} Join successful.")
            except Exception as e:
                print(f"[Camera] {self.url} Join warning: {e}")

        # Check legacy thread attribute just in case
        if hasattr(self, 'thread') and hasattr(self.thread, 'is_alive') and self.thread.is_alive():
            try:
                self.thread.join(timeout=1.0)
            except: pass

        # Double check: Only release if we are SURE thread is dead/gone
        # and cap is still there (should typically be None if thread finished)
        if hasattr(self, 'cap') and self.cap is not None:
             # Logic continues...
             pass

    
    def set_usage_mode(self, mode):
        """
        Set camera usage mode to adjust performance
        
        Args:
            mode: 'preview', 'scan', or 'record'
        """
        self.usage_mode = mode
        
        if mode == 'preview':
            self.target_fps = 30  # High FPS for preview (Same as scan)
        elif mode == 'scan':
            self.target_fps = 30# Medium-High FPS for scanning (Increased for dual-camera responsiveness)
        elif mode == 'record':
            self.target_fps = 30  # High FPS for recording (Smooth)
        
        print(f"[Camera {self.url}] Mode: {mode}, Target FPS: {self.target_fps}")
    
    def update(self):
        """Background thread to continuously read frames (RUNS IN REAL THREAD)"""
        from app import socketio
        
        # [ANTIGRAVITY] Initialize Capture INSIDE the Worker Thread
        print(f"[Camera] Initializing capture for {self.url} in worker thread...")
        is_local = str(self.url).isdigit()
        
        # [ANTIGRAVITY] RETRY STRATEGY
        # Try to connect up to 3 times to simulate "flicker/retry" behavior for stubborn webcams.
        success_init = False
        
        for attempt in range(1, 4):
            if not self.running: break
            print(f"[Camera] {self.url} Init Attempt {attempt}/3...")
            
            try:
                if is_local:
                    # [ANTIGRAVITY] FIX: Wrapped in safe_hardware_lock to prevent "Double Open" crash
                    with safe_hardware_lock(self.url, timeout=10.0) as acquired:
                        if not acquired:
                             print(f"[Camera] {self.url} Lock Timeout (Busy). Retrying...")
                             time.sleep(1.0)
                             continue
                        
                        if not self.running: return

                        # Try DSHOW
                        self.cap = cv2.VideoCapture(int(self.url), cv2.CAP_DSHOW)
                        
                        # If failed or not opened, try MSMF
                        if not self.cap.isOpened():
                             self.cap.release()
                             self.cap = cv2.VideoCapture(int(self.url), cv2.CAP_MSMF)
                else:
                    self.cap = cv2.VideoCapture(self.url)
                    
                if self.cap and self.cap.isOpened():
                    # Setup props
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    self.cap.set(cv2.CAP_PROP_FPS, 30)
                    
                    # WARMUP / VALIDATION
                    # Read a few frames to ensure stream is actually flowing
                    # detailed validation inside lock
                    valid_frames = 0
                    for _ in range(10): 
                        ret, test = self.cap.read()
                        if ret and test is not None and test.size > 0:
                            valid_frames += 1
                        time.sleep(0.05)
                        
                    if valid_frames > 2:
                        print(f"[Camera] {self.url} CONNECTED & STABLE (Attempt {attempt})")
                        success_init = True
                        break # Exit retry loop
                    else:
                         print(f"[Camera] {self.url} Opened but NO FRAMES (Warmup Failed). Resetting...")
                         self.cap.release()
                         self.cap = None
                else:
                    print(f"[Camera] {self.url} Failed to open.")
                    
            except Exception as e:
                print(f"[Camera] {self.url} Init Error: {e}")
            
            # If we are here, attempt failed. Wait before retry.
            # "Mati nyala" simulation
            time.sleep(1.0)
            
        if not success_init:
            print(f"[Camera] {self.url} FAILED all 3 attempts. Giving up.")
            self.running = False
            return


        # ----------------------------------------
        # MAIN LOOP
        # ----------------------------------------
        last_error_emit = 0
        last_frame_time = 0
        
        while self.running:
            if self.cap and self.cap.isOpened():
                # FPS throttling
                current_time = time.time()
                frame_interval = 1.0 / self.target_fps
                
                if current_time - last_frame_time < frame_interval:
                    time.sleep(0.01) # Standard sleep blocks this thread only
                    continue
                
                # [ANTIGRAVITY] Direct Blocking Read (Safe in Worker Thread)
                try:
                    ret, frame = self.cap.read()
                except Exception as e:
                    print(f"[{self.url}] Read error: {e}")
                    ret, frame = False, None
                
                if ret:
                    # [ANTIGRAVITY] SEPARATION OF CONCERNS
                    # raw_frame: UNTOUCHED full resolution (for Recording)
                    # display_frame: Zoomed/Cropped (for Preview/Scanner)
                    raw_frame = frame
                    display_frame = frame

                    # Apply zoom ONLY to display_frame
                    if self.zoom_level > 1.0:
                        h, w = frame.shape[:2]
                        crop_w = int(w / self.zoom_level)
                        crop_h = int(h / self.zoom_level)
                        x = (w - crop_w) // 2
                        y = (h - crop_h) // 2
                        cropped = frame[y:y+crop_h, x:x+crop_w]
                        try:
                            display_frame = cv2.resize(cropped, (w, h))
                        except Exception as e:
                            print(f"Zoom error: {e}")
                            display_frame = frame # Fallback

                    # [ANTIGRAVITY] DECISION: PRE-ENCODE JPEG HERE (Worker Thread)
                    encoded_jpeg = None
                    try:
                        # Adaptive quality/size based on usage mode (Using display_frame)
                        if self.usage_mode == 'preview':
                            # Preview: Downscale & Low Quality (Fastest)
                             h, w = display_frame.shape[:2]
                             if w > 0 and h > 0:
                                preview_frame = cv2.resize(display_frame, (w//2, h//2))
                                ret_enc, buf = cv2.imencode('.jpg', preview_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                                if ret_enc: encoded_jpeg = buf.tobytes()
                                
                        elif self.usage_mode == 'scan':
                            # Scan: Medium Resolution for visual, High FPS
                            h, w = display_frame.shape[:2]
                            if w > 640:
                                scale = 640 / w
                                new_h = int(h * scale)
                                scan_frame = cv2.resize(display_frame, (640, new_h))
                                ret_enc, buf = cv2.imencode('.jpg', scan_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                                if ret_enc: encoded_jpeg = buf.tobytes()
                            else:
                                ret_enc, buf = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                                if ret_enc: encoded_jpeg = buf.tobytes()
                        else:
                            # Record: High Quality Preview
                            ret_enc, buf = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                            if ret_enc: encoded_jpeg = buf.tobytes()
                            
                    except Exception as e:
                        print(f"JPEG Encode Error: {e}")

                    with self.lock:
                        # CRITICAL: Store RAW FRAME for recording/barcode (Full View)
                        self.last_frame = raw_frame
                        # Store ZOOMED/PROCESSED JPEG for streaming (User View)
                        if encoded_jpeg:
                            self.last_jpeg = encoded_jpeg
                        self.last_update = time.time()
                        self.consecutive_errors = 0
                        last_frame_time = current_time

                else:
                    self.consecutive_errors += 1
                    if self.consecutive_errors > 5 and (time.time() - last_error_emit > 5.0):
                         try:
                            if socketio: socketio.emit('camera_error', {'url': self.url, 'error': 'Connection lost'})
                            last_error_emit = time.time()
                         except: pass
                    
                    if self.consecutive_errors > 50:
                        self.running = False
                        break
                            
                    time.sleep(0.1)
            else:
                time.sleep(0.5)
        
        # Cleanup
        if self.cap:
             # [ANTIGRAVITY] Clean Release with Hardware Lock
            try:
                # We should try to acquire lock for release too, strictly speaking,
                # but typical pattern is: owning thread releases.
                # However, to sync with the 'update' of the NEXT thread, we should hold it.
                # But safe_hardware_lock might be held by US if we were in the 'with' block?
                # No, we only hold it during INIT. 
                
                # So here we just release. The NEXT thread will wait on the lock.
                # BUT we need to make sure we don't return until it's really gone.
                
                with safe_hardware_lock(self.url, timeout=5.0):
                    self.cap.release()
                    print(f"[Camera] {self.url} released (Worker Thread)")
                    
                # [ANTIGRAVITY] COOLDOWN: Give Windows Drivers time to breathe
                time.sleep(1.0) 
            except Exception as e: 
                print(f"[Camera] Release error: {e}")
            
            self.cap = None

    
    def get_frame(self):
        """Get JPEG encoded frame for streaming"""
        with self.lock:
            if self.last_frame is None:
                return None
            
    def get_frame(self):
        """
        Get JPEG encoded frame for streaming.
        [ANTIGRAVITY] CRITICAL: Now purely retrieves the pre-encoded buffer.
        NO resizing, NO encoding, MINIMAL locking.
        """
        with self.lock:
            if self.last_jpeg is None:
                return None
            
            self.last_access = time.time()
            return self.last_jpeg

    
    def get_raw_frame(self):
        """Get raw CV2 frame for processing (barcode detection)"""
        with self.lock:
            if self.last_frame is None:
                return None
            self.last_access = time.time()
            return self.last_frame.copy()

    def get_scan_frame(self):
        """
        Get frame for scanning, applying Zoom/Crop if active.
        [ANTIGRAVITY] Fix: Ensure what is seen (Zoom) is what is scanned.
        """
        with self.lock:
            if self.last_frame is None:
                return None
            
            frame = self.last_frame.copy()
            self.last_access = time.time()
            
            # Apply Zoom if needed
            if self.zoom_level > 1.0:
                try:
                    h, w = frame.shape[:2]
                    center_x, center_y = w // 2, h // 2
                    radius_x, radius_y = int(w / (2 * self.zoom_level)), int(h / (2 * self.zoom_level))
                    
                    min_x, max_x = center_x - radius_x, center_x + radius_x
                    min_y, max_y = center_y - radius_y, center_y + radius_y
                    
                    # Ensure within bounds
                    min_x = max(0, min_x)
                    min_y = max(0, min_y)
                    max_x = min(w, max_x)
                    max_y = min(h, max_y)
                    
                    cropped = frame[min_y:max_y, min_x:max_x]
                    return cropped # Return cropped (zoomed into ROI)
                except Exception as e:
                    print(f"Zoom crop error: {e}")
                    return frame
            
            return frame

    def update_heartbeat(self):
        """Update the heartbeat timestamp"""
        with self.lock:
            self.last_heartbeat = time.time()


# ============================================
# CAMERA MANAGER
# ============================================

active_cameras = {}
camera_lock = threading.Lock()

def get_camera_stream(url):
    """Get or create camera stream"""
    with camera_lock:
        # Check if camera already exists
        if url in active_cameras:
            cam = active_cameras[url]
            # Check if camera is still healthy
            # Also check if cap is None (validation failed)
            # [ANTIGRAVITY] FIX: Grace period for async init!
            # If camera is created < 5s ago, it is allowed to have cap=None (still initing)
            is_starting_up = (time.time() - cam.start_time) < 5.0
            
            if not is_starting_up and (cam.cap is None or not cam.running or (time.time() - cam.last_update >= 5.0)):
                # Camera is dead or invalid, remove it
                print(f"[Camera] Removing dead/invalid camera {url} from active_cameras")
                cam.stop()
                del active_cameras[url]
            else:
                return cam
        
        # Create new camera
        try:
            cam = VideoCamera(url)
            
            # CRITICAL: Check if camera is actually valid
            # [ANTIGRAVITY] RELAXED: Init is async now, so cap is ALWAYS None at first.
            # We return the camera object optimistically.
            # If validation failed in __init__, cap will be None
            # if cam.cap is None:
            #     print(f"[Camera] {url} failed validation, not adding to active cameras")
            #     return None
            
            # Wait a moment for first frame
            # [ANTIGRAVITY] RELAXED: Don't reject if frames aren't ready yet (Async validation)
            # time.sleep(0.5)
            # if cam.last_frame is None:
            #     print(f"[Camera] {url} no frames after 0.5s, rejecting")
            #     cam.stop()
            #     return None
            
            active_cameras[url] = cam
            return cam
        except Exception as e:
            video_logger.error(f"Error creating camera {url}: {e}")
            return None


def gen_frames(camera, processing_mode=None):
    """Generator function for video streaming"""
    while True:
        try:
            # Standard Stream (Color) - Always yield color frame regardless of mode
            # Barcode detection happens in a separate thread/process
            frame = camera.get_frame()
            if frame is None:
                time.sleep(0.1)
                continue
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                   
            # [ANTIGRAVITY] THROTTLE: Prevent "Firehose" Effect
            # Without this, we send thousands of duplicate frames/sec, killing the network & browser
            gevent.sleep(0.03) # Cap at ~30 FPS

        except Exception as e:
            # Prevent 500 error loop
            time.sleep(0.5)


# ============================================
# CAMERA DISCOVERY
# ============================================

def detect_local_cameras():
    """Detect local USB/webcams"""
    available_indices = []
    max_index_to_test = 10
    
    print("[Camera] Detecting local cameras...")
    
    # Check active cameras first
    with camera_lock:
        active_list = [int(u) for u in active_cameras.keys() if str(u).isdigit()]
    
    for i in range(max_index_to_test):
        if i in active_list:
            available_indices.append({'index': i, 'name': f'Local Camera {i} (Active)'})
            continue
        
        # Try to open camera
        backends = [
            ("DirectShow", cv2.CAP_DSHOW),
            ("Media Foundation", cv2.CAP_MSMF),
            ("Default", cv2.CAP_ANY)
        ]
        
        for name, backend in backends:
            try:
                with safe_hardware_lock(i, timeout=1.0) as acquired:
                    if not acquired:
                        continue
                    
                    cap = cv2.VideoCapture(i, backend)
                    if cap and cap.isOpened():
                        time.sleep(0.5)
                        ret, _ = cap.read()
                        if ret:
                            available_indices.append({'index': i, 'name': f'Local Camera {i}'})
                            cap.release()
                            break
                        cap.release()
            except:
                pass
    
    return available_indices


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

    # Helper to check if a specific RTSP path exists
    def check_rtsp_path(ip, port, path):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5) # Fast timeout
            sock.connect((ip, port))
            
            # Sending RTSP DESCRIBE request
            # We look for 200 OK or 401 Unauthorized (which means path exists but needs auth)
            # 404 Not Found means path is wrong
            request = f"DESCRIBE rtsp://{ip}:{port}{path} RTSP/1.0\r\nCSeq: 1\r\n\r\n"
            sock.sendall(request.encode())
            
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            sock.close()
            
            if "RTSP/1.0 200 OK" in response or "RTSP/1.0 401 Unauthorized" in response:
                return True
            return False
        except:
            return False

    # Common RTSP Paths to Probe
    common_rtsp_paths = [
        "/stream1",                # Tapo/TP-Link High
        "/stream2",                # Tapo/TP-Link Low
        "/live",                   # Generic
        "/h264",                   # Generic
        "/",                       # Root
        "/ch0",                    # Generic
        "/Streaming/Channels/101", # Hikvision
        "/cam/realmonitor?channel=1&subtype=0", # Dahua
        "/onvif1",                 # ONVIF
        "/profile1/media.smp"      # Some Axis/Others
    ]

    # Merge scan results
    for ip, port in scan_results:
        print(f">>> [Discovery] Processing scan result: {ip}:{port}")
        if ip in seen_ips: continue
        
        name = f"Common Camera ({ip})"
        url = f"rtsp://{ip}:{port}/stream" # Default fallback
        source = "Port Scan"
        verified_path = False
        
        if port == 554 or port == 8554:
            # It's an RTSP port, let's probe for the correct path
            print(f">>> [Discovery] Probing RTSP paths for {ip}:{port}...")
            
            # Try /stream first (default)
            print(f">>> [Discovery] Checking default path /stream on {ip}...")
            if check_rtsp_path(ip, port, "/stream"):
                print(f">>> [Discovery] ✅ Default path /stream is VALID on {ip}")
                url = f"rtsp://{ip}:{port}/stream"
                verified_path = True
            else:
                # Try others
                print(f">>> [Discovery] Default path failed. Probing {len(common_rtsp_paths)} common paths...")
                for path in common_rtsp_paths:
                    print(f">>> [Discovery] Probing {path} on {ip}...", end=" ", flush=True)
                    if check_rtsp_path(ip, port, path):
                        print(f"✅ FOUND!")
                        print(f">>> [Discovery] Valid path identified: {path}")
                        url = f"rtsp://{ip}:{port}{path}"
                        if "stream1" in path: name = f"IP Camera (High Res) ({ip})"
                        elif "stream2" in path: name = f"IP Camera (Low Res) ({ip})"
                        elif "Channels/101" in path: name = f"Hikvision Camera ({ip})"
                        elif "realmonitor" in path: name = f"Dahua Camera ({ip})"
                        verified_path = True
                        break
                    else:
                        print("❌")
            
            if not verified_path:
                print(f">>> [Discovery] ⚠️ Could not determine exact path for {ip}, defaulting to /stream")
            
            if not verified_path:
                print(f">>> [Discovery] Could not determine exact path for {ip}, defaulting to /stream")

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



# ============================================
# CAMERA STATUS CHECKING
# ============================================

camera_status_cache = {}
status_cache_lock = threading.Lock()

def is_camera_online(url):
    """Check if camera is reachable"""
    
    # [ANTIGRAVITY] Optimization: If camera is already active and streaming, it's definitely online.
    # This prevents 'safe_hardware_lock' from stealing the stream from the main thread (VideoCamera).
    with camera_lock:
        if url in active_cameras:
            cam = active_cameras[url]
            if cam.running:
                # Update last checked timestamp in background
                return True

    if str(url).isdigit():
        # Local camera - try to open briefly
        try:
            with safe_hardware_lock(url, timeout=1.0) as acquired:
                if not acquired:
                    return False
                
                cap = cv2.VideoCapture(int(url), cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, _ = cap.read()
                    cap.release()
                    return ret
                return False
        except:
            return False
    else:
        # IP camera - try socket connection
        try:
            # Parse URL to get host and port
            if url.startswith('http'):
                # HTTP/RTSP URL
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                host = parsed.hostname
                port = parsed.port or 80
            else:
                # Assume IP:PORT format
                parts = url.split(':')
                host = parts[0]
                port = int(parts[1]) if len(parts) > 1 else 80
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False


def _check_single_camera_status(url):
    """Helper function to check single camera status"""
    try:
        online = is_camera_online(url)
        
        # Check if in use
        in_use = False
        in_use_by = None
        purpose = None
        
        with camera_lock:
            if url in active_cameras:
                in_use = True
                in_use_by = "System"
                purpose = "Streaming"
        
        return {
            'url': url,
            'online': online,
            'in_use': in_use,
            'in_use_by': in_use_by,
            'purpose': purpose,
            'last_checked': time.time()
        }
    except Exception as e:
        return {
            'url': url,
            'online': False,
            'error': str(e),
            'last_checked': time.time()
        }


@safe_thread_loop("CameraStatusChecker", interval=3.0)
def background_camera_status_checker():
    """Background thread to check camera status periodically"""
    print("[Camera] Background status checker started")
    
    # [ANTIGRAVITY] Wrapped with @safe_thread_loop, so this 'while True' is redundant 
    # but harmless. The decorator handles the outer loop.
    # However, safe_thread_loop calls the function repeatedly.
    # So we should remove the 'while True' inside if we want clean logic,
    # OR better yet, just wrap the whole function call logic.
    
    # Actually, safe_thread_loop keeps calling func().
    # So inside here we should just do ONE iteration.
    
    # BUT existing code probably has a while loop.
    # Let's check the view... existing code has 'while True' presumably.
    # To use safe_thread_loop correctly, I should rewrite this function to be a single iteration
    # or just use the try/except block.
    
    # Simpler: Just wrap the existing logic in a big try/except loop manually
    # or modify to be single iteration.
    
    # Let's stick to the decorator pattern for consistency if possible, 
    # but if the function is already an infinite loop, safe_thread_loop might be overkill/conflicting.
    pass 
    
    # RE-READING safe_thread_loop:
    # It does 'while True: func()'.
    # If func() also has 'while True', the decorator's outer loop never runs until func crashes.
    # If func crashes, it returns, and decorator restarts it.
    # So it handles "Restart on Crash" perfectly even if func has its own loop.
    
    # OK, proceed with annotating.

    
    while True:
        try:
            # Get list of cameras from config
            # This would normally load from config.json
            # For now, just check active cameras
            
            with camera_lock:
                urls_to_check = list(active_cameras.keys())
            
            for url in urls_to_check:
                status = _check_single_camera_status(url)
                with status_cache_lock:
                    camera_status_cache[url] = status
            
            time.sleep(30)  # Check every 30 seconds
        except Exception as e:
            print(f"[Camera] Status checker error: {e}")
            time.sleep(30)


# ============================================
# CAMERA USAGE TRACKING
# ============================================

camera_usage = {}
camera_usage_lock = threading.Lock()

def mark_camera_in_use(url, username, purpose):
    """Mark a camera as being actively used"""
    with camera_usage_lock:
        camera_usage[url] = {
            'username': username,
            'purpose': purpose,
            'last_used': time.time()
        }


def release_camera(url):
    """Release camera from usage"""
    with camera_usage_lock:
        if url in camera_usage:
            del camera_usage[url]
    
    # Also stop the camera stream
    with camera_lock:
        if url in active_cameras:
            active_cameras[url].stop()
            del active_cameras[url]


# ============================================
# WATCHDOG SERVICE
# ============================================
def camera_watchdog():
    """Monitor cameras for heartbeat timeouts"""
    print("[Camera] Watchdog started (Timeout: 10s)")
    while True:
        try:
            with camera_lock:
                # Create copy of keys to avoid modification during iteration
                urls = list(active_cameras.keys())
                now = time.time()
                
                for url in urls:
                    cam = active_cameras[url]
                    # Check timeout (10 seconds)
                    if (now - cam.last_heartbeat) > 10.0:
                        print(f"[Watchdog] Camera {url} timed out (No heartbeat > 10s). Releasing...")
                        cam.stop()
                        del active_cameras[url]
                        
                        # Also clear usage
                        with camera_usage_lock:
                            if url in camera_usage:
                                del camera_usage[url]
                                
        except Exception as e:
            print(f"[Watchdog] Error: {e}")
            
        time.sleep(2.0) # Check every 2 seconds

# Start watchdog in background
# Start watchdog in background
# [ANTIGRAVITY] DISABLED WATCHDOG TO ALLOW STATIC/NO-HEARTBEAT CAMERAS
# watchdog_thread = threading.Thread(target=camera_watchdog, daemon=True)
# watchdog_thread.start()
