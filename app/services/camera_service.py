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
import numpy as np


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
        self.lock = threading.Lock()
        self.running = True
        self.last_access = time.time()
        self.last_update = time.time()
        self.consecutive_errors = 0
        self.zoom_level = 1.0  # 1.0 = no zoom, 2.0 = 2x zoom
        
        # Determine backend
        is_local = str(url).isdigit()
        
        if is_local:
            # Try DirectShow first, fallback to MSMF
            try:
                self.cap = cv2.VideoCapture(int(url), cv2.CAP_DSHOW)
                if not self.cap.isOpened():
                    self.cap = cv2.VideoCapture(int(url), cv2.CAP_MSMF)
            except:
                self.cap = cv2.VideoCapture(int(url), cv2.CAP_MSMF)
        else:
            # IP camera
            self.cap = cv2.VideoCapture(url)
        
        # Set properties
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Start update thread
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()
    
    def __del__(self):
        self.stop()
    
    def stop(self):
        """Explicitly stop the camera stream and FORCE hardware release"""
        self.running = False
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        if hasattr(self, 'cap') and self.cap is not None:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None
    
    def update(self):
        """Background thread to continuously read frames"""
        while self.running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                
                if ret:
                    # Apply zoom if needed
                    if self.zoom_level > 1.0:
                        h, w = frame.shape[:2]
                        # Calculate crop dimensions
                        crop_w = int(w / self.zoom_level)
                        crop_h = int(h / self.zoom_level)
                        # Center crop
                        x = (w - crop_w) // 2
                        y = (h - crop_h) // 2
                        cropped = frame[y:y+crop_h, x:x+crop_w]
                        # Resize back to original size
                        frame = cv2.resize(cropped, (w, h))
                    
                    with self.lock:
                        self.last_frame = frame
                        self.last_update = time.time()
                        self.consecutive_errors = 0
                else:
                    self.consecutive_errors += 1
                    time.sleep(0.1)
            else:
                time.sleep(0.5)
    
    def get_frame(self):
        """Get JPEG encoded frame for streaming"""
        with self.lock:
            if self.last_frame is None:
                return None
            
            self.last_access = time.time()
            ret, jpeg = cv2.imencode('.jpg', self.last_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            if ret:
                return jpeg.tobytes()
            return None
    
    def get_raw_frame(self):
        """Get raw CV2 frame for processing (barcode detection)"""
        with self.lock:
            if self.last_frame is None:
                return None
            self.last_access = time.time()
            return self.last_frame.copy()


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
            if cam.running and (time.time() - cam.last_update < 5.0):
                return cam
            else:
                # Camera is dead, remove it
                cam.stop()
                del active_cameras[url]
        
        # Create new camera
        try:
            cam = VideoCamera(url)
            active_cameras[url] = cam
            return cam
        except Exception as e:
            print(f"[Camera] Error creating camera {url}: {e}")
            return None


def gen_frames(camera):
    """Generator function for video streaming"""
    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.1)
            continue
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


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



# ============================================
# CAMERA STATUS CHECKING
# ============================================

camera_status_cache = {}
status_cache_lock = threading.Lock()

def is_camera_online(url):
    """Check if camera is reachable"""
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


def background_camera_status_checker():
    """Background thread to check camera status periodically"""
    print("[Camera] Background status checker started")
    
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
