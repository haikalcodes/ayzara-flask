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
from app.utils.logger import video_logger, audit_logger, get_trace_id

# [ANTIGRAVITY] GEVENT THREADPOOL
import gevent
from gevent.threadpool import ThreadPool
_rec_pool = ThreadPool(10) # 10 threads for recording writes


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
                video_logger.warning(f"Detected zombie recording", extra={'context': {'id': record.id, 'resi': record.resi}})
                self._mark_record_as_zombie(record, "Server restarted/Process missing")
                return None

        # Validation for staleness (4 hours timeout)
        if record.waktu_mulai:
            elapsed = (datetime.now() - record.waktu_mulai).total_seconds()
            if elapsed > 14400:  # 4 Hours
                video_logger.warning(f"Detected stale recording (timeout)", extra={'context': {'id': record.id}})
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
            video_logger.error(f"Error marking zombie: {e}")
            self.db.session.rollback()
    
    def _record_video_thread(self, recording_id, camera_url, output_path, stop_event):
        """
        Background thread for video recording.
        """
        video_logger.info(f"Thread STARTED for {recording_id}", extra={'context': {'camera': camera_url}})
        
        # Temp file for MJPEG recording
        temp_path = str(output_path).replace('.mp4', '.avi')
        
        try:
            import traceback
            import subprocess
            from app.services.camera_service import get_camera_stream
            
            # Wait for camera
            camera = get_camera_stream(camera_url)
            retries = 0
            while not camera and retries < 5:
                time.sleep(0.5)
                camera = get_camera_stream(camera_url)
                retries += 1
                
            if not camera:
                video_logger.error(f"Thread abort: Camera {camera_url} unavailable")
                return

            # Wait for first frame
            frame = camera.get_raw_frame()
            wait_frame = 0
            while frame is None and wait_frame < 20:
                time.sleep(0.1)
                frame = camera.get_raw_frame()
                wait_frame += 1
            
            if frame is None:
                video_logger.error(f"Thread abort: No frame received")
                return

            h, w = frame.shape[:2]
            fps = 30.0  # MATCH CAMERA FPS for 1:1 capture
            
            # MJPEG Writer (100% reliable in OpenCV)
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            # [ANTIGRAVITY] Direct Blocking Init (Safe in Worker Thread)
            out = cv2.VideoWriter(temp_path, fourcc, fps, (w, h))
            
            if not out.isOpened():
                video_logger.error(f"Failed to open MJPEG writer at {temp_path}")
                return
                
            video_logger.info(f"MJPEG writer initialized", extra={'context': {'path': temp_path, 'res': f"{w}x{h}", 'fps': fps}})
            
            # Recording loop
            last_ts = 0
            frames_written = 0
            
            try:
                while not stop_event.is_set():
                    # SYNC STRATEGY: Poll faster than FPS, write only new frames
                    current_ts = camera.last_update
                    
                    if current_ts > last_ts:
                        frame = camera.get_raw_frame()
                        if frame is not None:
                            # [ANTIGRAVITY] Direct Blocking Write (Safe in Worker Thread)
                            out.write(frame)
                            
                            last_ts = current_ts
                            frames_written += 1
                            # Burst protection: If we write a frame, don't sleep essentially, 
                            # just yield to let other threads run
                            time.sleep(0.001) 
                    else:
                        # Wait for new frame (poll)
                        time.sleep(0.005) # 5ms poll is fast enough for 30fps (33ms)
            except Exception as e:
                print(f"[Recording] ❌ Loop error: {e}")
            finally:
                # CRITICAL: Always release the file handle
                if out:
                    out.release()
                print(f"[Recording] MJPEG capture finished/stopped. Frames: {frames_written}")
            
            # ============================================================
            # FFmpeg Conversion: MJPEG (.avi) → H.264 (.mp4)
            # ============================================================
            if os.path.exists(temp_path) and frames_written > 0:
                print(f"[Recording] Converting to H.264 MP4: {output_path}")
                
                # FFmpeg command - OPTIMIZED for speed and lower resource usage
                # CRF 26 = Good quality, smaller files (was 23)
                # preset veryfast = 3x faster encoding (was medium)
                # threads 2 = Limit CPU usage
                # max_muxing_queue_size = Prevent buffer overflow
                cmd = [
                    'ffmpeg', '-y',
                    '-i', temp_path,
                    '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',  # Force even dimensions
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',  # Faster encoding
                    '-crf', '26',  # Lower quality = smaller files, still good
                    '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart',
                    '-threads', '2',  # Limit CPU usage
                    '-max_muxing_queue_size', '1024',  # Prevent buffer overflow
                    output_path
                ]
                
                print(f"[Recording] Running FFmpeg: {' '.join(cmd)}")

                # Run FFmpeg with lower priority (Windows)
                import sys
                if sys.platform == 'win32':
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS
                    )
                else:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                
                # Wait 0.5s for FFmpeg to open the file
                time.sleep(0.5)
                
                # Delete temp file EARLY while FFmpeg is reading it
                # FFmpeg keeps file handle open, so it can still read
                try:
                    os.remove(temp_path)
                    print(f"[Recording] ✅ Temp file deleted early (FFmpeg still reading)")
                except Exception as e:
                    print(f"[Recording] Temp file locked by FFmpeg: {e}")
                
                # Wait for FFmpeg to finish
                stdout, stderr = process.communicate(timeout=60)
                returncode = process.returncode
                
                if returncode == 0:
                    print(f"[Recording] ✅ Conversion SUCCESS!")
                    
                    # Final cleanup if temp file still exists
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                            print(f"[Recording] Final cleanup: Removed temp file")
                        except:
                            pass
                    
                    # Verify final file
                    if os.path.exists(output_path):
                        file_size = os.path.getsize(output_path)
                        print(f"[Recording] ✅ Final file ready: {output_path} ({file_size} bytes, {frames_written} frames)")
                    else:
                        print(f"[Recording] ❌ Final file missing after conversion!")
                else:
                    error_msg = stderr.decode('utf-8', errors='ignore')
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
        # Check if THIS CAMERA is already recording
        with recording_lock:
            for rid, info in active_recordings.items():
                # Normalize to string for comparison (user might send int 0 or str "0")
                if str(info.get('camera_url')) == str(camera_url):
                    return False, f"Kamera {camera_url} sedang digunakan untuk merekam", None
        
        # [ANTIGRAVITY] ALLOW MULTIPLE RECORDINGS
        # We removed the global self.get_active_recording() check here.

        
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
            
            # [ANTIGRAVITY] THREAD AFFINITY FIX
            # Use real worker thread instead of Greenlet/ThreadPool.apply wrapper
            # Capture the AsyncResult so we can wait for it later!
            async_result = _rec_pool.apply_async(self._record_video_thread, args=(recording_id, camera_url, output_path, stop_event))
            
            # NOTE: We don't get a handle to the thread easily with apply_async.
            # But we use stop_event to control it.
            # The 't' variable is less useful now, but we keep the dict structure valid.
            

            
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
                    'thread': async_result 
                }
            
            audit_logger.info(f"RECORDING STARTED", extra={'context': {'resi': resi, 'pegawai': pegawai, 'rec_id': recording_id}})
            return True, "Recording started", recording_id
            
        except Exception as e:
            video_logger.error(f"Error starting recording: {e}", exc_info=True)
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
                    return False, "No active recording found", {}
            
            # Stop the thread
            if 'stop_event' in rec_info:
                rec_info['stop_event'].set()
                rec_info['stop_event'].set()
                if 'thread' in rec_info and rec_info['thread']:
                     try:
                        # Wait for thread to finish (including FFmpeg)
                        # This yields to other greenlets, so it's safe.
                        # We give it plenty of time (e.g. 60s) for encoding.
                        rec_info['thread'].get(timeout=60.0)
                     except Exception as e:
                        video_logger.error(f"Waiting for recording thread failed: {e}")
            
            # Get database record
            record = self.PackingRecord.query.get(rec_info['db_id'])
            if not record:
                return False, "Recording not found in database", {}
            
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
            
            # Check file existence explicitly using the absolute path we already have
            file_exists_status = os.path.exists(video_path_abs) if video_path_abs else False

            result_data = {
                'video_url': f"/recordings/{record.file_video}" if record.file_video else None,
                'duration': record.durasi_detik,
                'size_kb': record.file_size_kb,
                'file_exists': file_exists_status
            }
            

            
            video_logger.info(f"Stopped recording {recording_id}")
            audit_logger.info(f"RECORDING STOPPED", extra={'context': {
                'resi': record.resi, 
                'duration': record.durasi_detik,
                'size_kb': record.file_size_kb,
                'status': record.status
            }})
            return True, "Recording stopped successfully", result_data
            
        except Exception as e:
            video_logger.error(f"Error stopping recording: {e}", exc_info=True)
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
