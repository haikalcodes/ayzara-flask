"""
Session Service
================
Manages multi-camera recording sessions with employee assignments

This service handles:
- Session creation and lifecycle
- Camera-to-employee pairing
- Platform assignment per camera
- Real-time status tracking for all active cameras
"""

import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ============================================
# SESSION STATE MANAGEMENT
# ============================================

# Active session data structure
# {
#   'session_id': {
#       'created_at': datetime,
#       'created_by': str,
#       'cameras': {
#           'camera_url': {
#               'employee_name': str,
#               'platform': str,
#               'status': 'idle|scanning|recording|completed|error',
#               'recording_id': str|None,
#               'last_barcode': str|None,
#               'last_scan_time': float|None,
#               'error_message': str|None
#           }
#       }
#   }
# }

active_session = None
session_lock = threading.Lock()


class SessionService:
    """Service for managing multi-camera recording sessions"""
    
    def __init__(self):
        """Initialize session service"""
        pass
    
    def create_session(self, created_by: str) -> Tuple[bool, str, Optional[str]]:
        """
        Create a new recording session
        
        Args:
            created_by: Username of session creator (admin/supervisor)
        
        Returns:
            Tuple of (success, message, session_id)
        """
        global active_session
        
        with session_lock:
            if active_session is not None:
                return False, "Sesi rekam sudah aktif", None
            
            session_id = f"session_{int(time.time())}"
            active_session = {
                'session_id': session_id,
                'created_at': datetime.now(),
                'created_by': created_by,
                'cameras': {}
            }
            
            print(f"[Session] Created new session: {session_id} by {created_by}")
            return True, "Sesi rekam berhasil dibuat", session_id
    
    def get_active_session(self) -> Optional[Dict]:
        """
        Get current active session
        
        Returns:
            Session dictionary or None
        """
        with session_lock:
            return active_session.copy() if active_session else None
    
    def assign_camera(self, camera_url: str, employee_name: str, platform: str = 'LAINNYA') -> Tuple[bool, str]:
        """
        Assign a camera to an employee with platform
        
        Args:
            camera_url: Camera URL or index
            employee_name: Employee name
            platform: Default platform for this camera
        
        Returns:
            Tuple of (success, message)
        """
        global active_session
        
        with session_lock:
            if active_session is None:
                return False, "Tidak ada sesi aktif. Buat sesi terlebih dahulu."
            
            # Check if camera already assigned
            if camera_url in active_session['cameras']:
                existing = active_session['cameras'][camera_url]
                return False, f"Kamera sudah di-assign ke {existing['employee_name']}"
            
            # Check if employee already has a camera
            for cam_url, cam_data in active_session['cameras'].items():
                if cam_data['employee_name'] == employee_name:
                    return False, f"Pegawai {employee_name} sudah di-assign ke kamera lain"
            
            # Assign camera
            active_session['cameras'][camera_url] = {
                'employee_name': employee_name,
                'platform': platform,
                'status': 'idle',
                'recording_id': None,
                'last_barcode': None,
                'last_scan_time': None,
                'error_message': None,
                # Anti-looping protection
                'previous_barcode': None, 
                'previous_stop_time': 0
            }
            
            print(f"[Session] Camera {camera_url} assigned to {employee_name} (Platform: {platform})")
            return True, f"Kamera berhasil di-assign ke {employee_name}"
    
    def unassign_camera(self, camera_url: str) -> Tuple[bool, str]:
        """
        Remove camera assignment
        
        Args:
            camera_url: Camera URL to unassign
        
        Returns:
            Tuple of (success, message)
        """
        global active_session
        
        with session_lock:
            if active_session is None:
                return False, "Tidak ada sesi aktif"
            
            if camera_url not in active_session['cameras']:
                return False, "Kamera tidak ditemukan dalam sesi"
            
            cam_data = active_session['cameras'][camera_url]
            
            # Check if recording is active
            if cam_data['status'] == 'recording':
                return False, "Tidak bisa unassign saat sedang merekam"
            
            employee_name = cam_data['employee_name']
            del active_session['cameras'][camera_url]
            
            # Release hardware resources
            try:
                from app.services.camera_service import release_camera
                release_camera(camera_url)
            except Exception as e:
                print(f"[Session] Warning: Failed to release camera hardware: {e}")
            
            print(f"[Session] Camera {camera_url} unassigned from {employee_name}")
            return True, f"Kamera berhasil di-unassign dari {employee_name}"
    
    def update_camera_status(self, camera_url: str, status: str, **kwargs) -> Tuple[bool, str]:
        """
        Update camera status
        
        Args:
            camera_url: Camera URL
            status: New status (idle|scanning|recording|completed|error)
            **kwargs: Additional fields to update (recording_id, last_barcode, error_message)
        
        Returns:
            Tuple of (success, message)
        """
        global active_session
        
        with session_lock:
            if active_session is None:
                return False, "Tidak ada sesi aktif"
            
            if camera_url not in active_session['cameras']:
                return False, "Kamera tidak ditemukan dalam sesi"
            
            cam_data = active_session['cameras'][camera_url]
            
            # Update status logic
            if status == 'recording' and cam_data['status'] != 'recording':
                # Starting recording - capture start time locally for fallback
                cam_data['last_scan_time'] = time.time()
            elif status == 'idle' and cam_data['status'] == 'recording':
                # Stopping recording - save history to prevent immediate re-trigger
                cam_data['previous_barcode'] = cam_data['last_barcode']
                cam_data['previous_stop_time'] = time.time()
                
            cam_data['status'] = status
            
            # Update optional fields
            if 'recording_id' in kwargs:
                cam_data['recording_id'] = kwargs['recording_id']
            if 'last_barcode' in kwargs:
                cam_data['last_barcode'] = kwargs['last_barcode']
                # Update timestamp if provided, else use current time if starting
                if not cam_data.get('last_scan_time'):
                    cam_data['last_scan_time'] = time.time()
            if 'error_message' in kwargs:
                cam_data['error_message'] = kwargs['error_message']
            
            print(f"[Session] Camera {camera_url} status updated to: {status}")
            return True, "Status updated"

    def get_camera_status(self, camera_url: str) -> Optional[Dict]:
        """
        Get status of a specific camera
        
        Args:
            camera_url: Camera URL
        
        Returns:
            Camera status dictionary or None
        """
        with session_lock:
            if active_session is None:
                return None
            
            return active_session['cameras'].get(camera_url, None)
    
    def get_all_cameras_status(self) -> List[Dict]:
        """
        Get status of all cameras in session
        
        Returns:
            List of camera status dictionaries with camera_url included
        """
        with session_lock:
            if active_session is None:
                return []
            
            result = []
            for camera_url, cam_data in active_session['cameras'].items():
                result.append({
                    'camera_url': camera_url,
                    **cam_data
                })
            
            return result
    
    def is_barcode_in_use(self, barcode: str, exclude_camera: Optional[str] = None) -> bool:
        """
        Check if a barcode is currently being used by any camera
        
        Args:
            barcode: Barcode to check
            exclude_camera: Camera URL to exclude from check (for same-camera re-scan)
        
        Returns:
            True if barcode is in use, False otherwise
        """
        with session_lock:
            if active_session is None:
                return False
            
            for camera_url, cam_data in active_session['cameras'].items():
                if exclude_camera and camera_url == exclude_camera:
                    continue
                
                if cam_data['status'] == 'recording' and cam_data['last_barcode'] == barcode:
                    return True
            
            return False
    
    def end_session(self) -> Tuple[bool, str]:
        """
        End the current session
        
        Returns:
            Tuple of (success, message)
        """
        global active_session
        
        with session_lock:
            if active_session is None:
                return False, "Tidak ada sesi aktif"
            
            # Check for active recordings
            active_recordings = []
            for camera_url, cam_data in active_session['cameras'].items():
                if cam_data['status'] == 'recording':
                    active_recordings.append(cam_data['employee_name'])
            
            if active_recordings:
                return False, f"Masih ada rekaman aktif: {', '.join(active_recordings)}"
            
            session_id = active_session['session_id']
            
            # Release all cameras
            try:
                from app.services.camera_service import release_camera
                for camera_url in list(active_session['cameras'].keys()):
                    release_camera(camera_url)
            except Exception as e:
                print(f"[Session] Warning: Failed to release cameras during session end: {e}")
                
            active_session = None
            
            print(f"[Session] Session ended: {session_id}")
            return True, "Sesi berhasil diakhiri"
    
    def get_session_summary(self) -> Dict:
        """
        Get summary of current session
        
        Returns:
            Dictionary with session statistics
        """
        with session_lock:
            if active_session is None:
                return {
                    'active': False,
                    'total_cameras': 0,
                    'idle': 0,
                    'recording': 0,
                    'completed': 0,
                    'error': 0
                }
            
            status_counts = {
                'idle': 0,
                'scanning': 0,
                'recording': 0,
                'completed': 0,
                'error': 0
            }
            
            for cam_data in active_session['cameras'].values():
                status = cam_data['status']
                if status in status_counts:
                    status_counts[status] += 1
            
            return {
                'active': True,
                'session_id': active_session['session_id'],
                'created_at': active_session['created_at'].isoformat(),
                'created_by': active_session['created_by'],
                'total_cameras': len(active_session['cameras']),
                **status_counts
            }
