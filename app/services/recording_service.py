"""
Recording Service
=================
Complete recording lifecycle management service

📁 Copy to: dashboard_flask_refactored/app/services/recording_service.py
"""

import threading
import time
from datetime import datetime
from app.models import db, PackingRecord
from app.utils import create_recording_folder, generate_metadata_json
import os
import cv2
import subprocess


# ============================================
# RECORDING STATE MANAGEMENT
# ============================================

active_recordings = {}
recording_lock = threading.Lock()


class RecordingService:
    """Service for managing video recording lifecycle"""
    
    def __init__(self, db_instance, packing_record_model):
        """
        Initialize recording service
        
        Args:
            db_instance: SQLAlchemy database instance
            packing_record_model: PackingRecord model class
        """
        self.db = db_instance
        self.PackingRecord = packing_record_model
    
    def get_active_recording(self):
        """
        Get currently active recording with validation against zombies
        
        Returns:
            Dictionary with recording info or None
        """
        record = self.PackingRecord.query.filter_by(
            status='RECORDING'
        ).order_by(self.PackingRecord.waktu_mulai.desc()).first()
        
        if not record:
            return None
            
        # Validation for Dashboard Recordings
        if record.recorder_type == 'dashboard':
            found_in_memory = False
            with recording_lock:
                for rid, info in active_recordings.items():
                    if info.get('db_id') == record.id:
                        found_in_memory = True
                        break
            
            if not found_in_memory:
                # It's a zombie from a previous crash/restart
                print(f"[Recording] Detected zombie recording (ID: {record.id}, Resi: {record.resi})")
                self._mark_record_as_zombie(record, "Server restarted/Process missing")
                return None

        # Validation for staleness (4 hours timeout)
        if record.waktu_mulai:
            elapsed = (datetime.now() - record.waktu_mulai).total_seconds()
            if elapsed > 14400:  # 4 Hours
                print(f"[Recording] Detected stale recording (ID: {record.id})")
                self._mark_record_as_zombie(record, "Recording timed out (4 hours limit)")
                return None
        
        return record.to_dict()
    
    def _mark_record_as_zombie(self, record, reason):
        """Mark record as error (zombie cleanup)"""
        try:
            record.status = 'ERROR'
            record.error_message = f"Auto-clean: {reason}"
            record.waktu_selesai = datetime.now()
            self.db.session.commit()
        except Exception as e:
            print(f"[Recording] Error marking zombie: {e}")
            self.db.session.rollback()
    
    def _record_video_thread(self, recording_id, camera_url, output_path, stop_event):
        """
        Background thread for video recording using MJPEG + FFmpeg conversion
        Strategy: Record to MJPEG .avi (reliable) → Convert to H.264 .mp4 (browser-compatible)
        """
        print(f"[Recording] ⚡ Thread STARTED for {recording_id}")
        
        # Temp file for MJPEG recording
        temp_path = str(output_path).replace('.mp4', '.avi')
        
        try:
            import traceback
            import subprocess
            from app.services.camera_service import get_camera_stream
            
            print(f"[Recording] Imports successful, connecting to camera: {camera_url}")
            
            # Wait for camera
            camera = get_camera_stream(camera_url)
            retries = 0
            while not camera and retries < 5:
                time.sleep(0.5)
                camera = get_camera_stream(camera_url)
                retries += 1
                
            if not camera:
                print(f"[Recording] Thread abort: Camera {camera_url} unavailable")
                return

            # Wait for first frame
            frame = camera.get_raw_frame()
            wait_frame = 0
            while frame is None and wait_frame < 20:
                time.sleep(0.1)
                frame = camera.get_raw_frame()
                wait_frame += 1
            
            if frame is None:
                print(f"[Recording] Thread abort: No frame received")
                return

            h, w = frame.shape[:2]
            fps = 20.0
            
            # MJPEG Writer (100% reliable in OpenCV)
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            out = cv2.VideoWriter(temp_path, fourcc, fps, (w, h))
            
            if not out.isOpened():
                print(f"[Recording] ❌ Failed to open MJPEG writer at {temp_path}")
                return
                
            print(f"[Recording] ✅ MJPEG writer initialized: {temp_path} ({w}x{h} @ {fps}fps)")
            
            # Recording loop
            last_ts = 0
            frames_written = 0
            
            while not stop_event.is_set():
                current_ts = camera.last_update
                if current_ts > last_ts:
                    frame = camera.get_raw_frame()
                    if frame is not None:
                        out.write(frame)
                        last_ts = current_ts
                        frames_written += 1
                        if frames_written % 30 == 0:
                            print(f"[Recording] {recording_id}: Written {frames_written} frames")
                        time.sleep(1.0/fps)
                    else:
                        time.sleep(0.01)
                else:
                    time.sleep(0.005)
            
            # Close MJPEG writer
            out.release()
            print(f"[Recording] MJPEG capture finished. Frames: {frames_written}")
            
            # ============================================================
            # FFmpeg Conversion: MJPEG (.avi) → H.264 (.mp4)
            # ============================================================
            if os.path.exists(temp_path) and frames_written > 0:
                print(f"[Recording] Converting to H.264 MP4: {output_path}")
                
                # FFmpeg command with optimized compression and compatibility
                # CRF 23 = Good quality/size balance
                # preset medium = Balanced speed
                # pix_fmt yuv420p = REQUIRED for browser playback
                # scale filter = REQUIRED for H.264 (dimensions must be divisible by 2)
                cmd = [
                    'ffmpeg', '-y',
                    '-i', temp_path,
                    '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', # Force even dimensions
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '23',
                    '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart',
                    output_path
                ]
                
                print(f"[Recording] Running FFmpeg: {' '.join(cmd)}")

                # Run FFmpeg
                process = subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    timeout=60  # 60 second timeout
                )
                
                if process.returncode == 0:
                    print(f"[Recording] ✅ Conversion SUCCESS!")
                    
                    # Remove temp file
                    try:
                        os.remove(temp_path)
                        print(f"[Recording] Temp file removed: {temp_path}")
                    except Exception as e:
                        print(f"[Recording] Warning: Could not remove temp file: {e}")
                    
                    # Verify final file
                    if os.path.exists(output_path):
                        file_size = os.path.getsize(output_path)
                        print(f"[Recording] ✅ Final file ready: {output_path} ({file_size} bytes, {frames_written} frames)")
                    else:
                        print(f"[Recording] ❌ Final file missing after conversion!")
                else:
                    error_msg = process.stderr.decode('utf-8', errors='ignore')
                    print(f"[Recording] ❌ FFmpeg conversion FAILED!")
                    print(f"[Recording] Command: {' '.join(cmd)}")
                    print(f"[Recording] Error Output:\n{error_msg}")
            else:
                print(f"[Recording] ❌ No frames recorded or temp file missing")
            
        except subprocess.TimeoutExpired:
            print(f"[Recording] ❌ FFmpeg conversion timeout (>60s)")
        except Exception as e:
            import traceback
            print(f"[Recording] ❌ Thread exception: {e}")
            print(f"[Recording] Traceback:\n{traceback.format_exc()}")
        finally:
            # Cleanup: Ensure temp file is removed
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    print(f"[Recording] Cleanup: Removed temp file")
                except:
                    pass

    def start_recording(self, resi, pegawai, platform, camera_url):
        """
        Start a new recording
        
        Args:
            resi: Package tracking number
            pegawai: Employee name
            platform: Platform name (SHOPEE, TOKOPEDIA, etc)
            camera_url: Camera URL or index
        
        Returns:
            Tuple of (success, message, recording_id)
        """
        # Check if there's already an active recording
        active = self.get_active_recording()
        if active:
            return False, "Ada rekaman yang sedang berjalan", None
        
        try:
            # Create database record
            now = datetime.now()
            record = self.PackingRecord(
                resi=resi,
                pegawai=pegawai,
                platform=platform,
                waktu_mulai=now,
                status='RECORDING',
                recorder_type='dashboard'
            )
            self.db.session.add(record)
            self.db.session.commit()
            
            # Create recording folder
            folder_path = create_recording_folder(now, platform, pegawai)
            
            # Prepare file path
            video_filename = f"{resi}_{int(time.time())}.mp4"
            output_path = os.path.join(str(folder_path), video_filename)
            
            # Start background recording thread
            stop_event = threading.Event()
            recording_id = f"rec_{record.id}_{int(time.time())}"
            
            t = threading.Thread(
                target=self._record_video_thread,
                args=(recording_id, camera_url, output_path, stop_event)
            )
            t.daemon = True
            t.start()
            
            # Add to active recordings
            with recording_lock:
                active_recordings[recording_id] = {
                    'db_id': record.id,
                    'resi': resi,
                    'pegawai': pegawai,
                    'platform': platform,
                    'camera_url': camera_url,
                    'folder_path': str(folder_path),
                    'output_path': output_path,
                    'start_time': time.time(),
                    'stop_event': stop_event,
                    'thread': t
                }
            
            print(f"[Recording] Started recording {recording_id} for {resi}")
            return True, "Recording started", recording_id
            
        except Exception as e:
            print(f"[Recording] Error starting recording: {e}")
            self.db.session.rollback()
            return False, f"Error: {str(e)}", None
    
    def stop_recording(self, recording_id=None, save_video=True):
        """
        Stop active recording
        
        Args:
            recording_id: Recording ID (optional, will use active if None)
            save_video: Whether to save the video
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get recording info
            with recording_lock:
                if recording_id and recording_id in active_recordings:
                    rec_info = active_recordings[recording_id]
                    del active_recordings[recording_id]
                elif active_recordings:
                    # Get the first active recording
                    recording_id = list(active_recordings.keys())[0]
                    rec_info = active_recordings[recording_id]
                    del active_recordings[recording_id]
                else:
                    return False, "No active recording found"
            
            # Stop the thread
            if 'stop_event' in rec_info:
                rec_info['stop_event'].set()
                if 'thread' in rec_info:
                     rec_info['thread'].join(timeout=5.0) # Wait up to 5s
            
            # Get database record
            record = self.PackingRecord.query.get(rec_info['db_id'])
            if not record:
                return False, "Recording not found in database"
            
            # Update record
            record.waktu_selesai = datetime.now()
            record.durasi_detik = int((datetime.now() - record.waktu_mulai).total_seconds())
            
            if save_video:
                # Video file is already at output_path (absolute)
                video_path_abs = rec_info.get('output_path')
                
                # Convert to relative path for database storage
                import config
                from pathlib import Path
                
                if video_path_abs:
                    try:
                        abs_path = Path(video_path_abs)
                        base_path = Path(config.RECORDINGS_FOLDER)
                        video_path_rel = abs_path.relative_to(base_path)
                        video_path_str = str(video_path_rel).replace('\\', '/')
                        print(f"[Recording] Path: {video_path_abs} -> {video_path_str}")
                    except Exception as e:
                        print(f"[Recording] Path conversion failed: {e}")
                        video_path_str = video_path_abs
                else:
                    video_path_str = None
                
                # Check if file exists
                if video_path_abs and os.path.exists(video_path_abs):
                     size = os.path.getsize(video_path_abs)
                     record.file_size_kb = int(size / 1024)
                else:
                     print(f"[Recording] Warning: Video missing at {video_path_abs}")
                     record.file_size_kb = 0

                record.file_video = video_path_str
                record.status = 'COMPLETED'
                
                # Metadata generation
                if video_path_abs and os.path.exists(video_path_abs):
                     try:
                        # 1. Generate Metadata JSON
                        json_path_abs, file_hash = generate_metadata_json(
                            record.to_dict(), video_path_abs, record.durasi_detik, record.file_size_kb
                        )
                        try:
                            json_rel = Path(json_path_abs).relative_to(base_path)
                            json_path_str = str(json_rel).replace('\\', '/')
                        except:
                            json_path_str = json_path_abs
                            
                        record.json_metadata_path = json_path_str
                        record.sha256_hash = file_hash
                        
                        # 2. Generate Thumbnail
                        # video_path_str is already the relative path we need for the hash
                        from app.utils import generate_thumbnail
                        generate_thumbnail(video_path_abs, video_path_str)
                        
                     except Exception as e:
                        print(f"[Recording] Metadata/Thumbnail failed: {e}")

            else:
                record.status = 'CANCELLED'
                # Delete video file
                video_path = rec_info.get('output_path')
                if video_path and os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                        print(f"[Recording] Deleted cancelled video: {video_path}")
                    except Exception as e:
                        print(f"[Recording] Error deleting cancelled video: {e}")
            
            self.db.session.commit()
            
            # Check file existence explicitly (since it's not a model property)
            import config
            full_path_check = os.path.join(config.RECORDINGS_FOLDER, record.file_video) if record.file_video else ''
            file_exists_status = os.path.exists(full_path_check) if full_path_check else False

            result_data = {
                'video_url': f"/recordings/{record.file_video}" if record.file_video else None,
                'duration': record.durasi_detik,
                'size_kb': record.file_size_kb,
                'file_exists': file_exists_status
            }
            
            print(f"[Recording] Stopped recording {recording_id}")
            return True, "Recording stopped successfully", result_data
            
        except Exception as e:
            print(f"[Recording] Error stopping recording: {e}")
            self.db.session.rollback()
            return False, f"Error: {str(e)}", {}
    
    def cancel_recording(self, recording_id=None):
        """
        Cancel active recording without saving
        
        Args:
            recording_id: Recording ID (optional)
        
        Returns:
            Tuple of (success, message)
        """
        return self.stop_recording(recording_id, save_video=False)
    
    def get_recording_status(self):
        """
        Get current recording status
        
        Returns:
            Dictionary with status information
        """
        active = self.get_active_recording()
        
        # Get full stats using StatsService to ensure all fields exist
        # This prevents "undefined" errors in the frontend
        from app.services.stats_service import StatsService
        stats_service = StatsService(self.db, self.PackingRecord)
        stats = stats_service.get_today_stats()
        
        return {
            'is_recording': active is not None,
            'active_recording': active,
            'stats': stats
        }

