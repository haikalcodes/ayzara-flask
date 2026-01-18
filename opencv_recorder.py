"""
OpenCV-based recording module for MJPEG streams
"""
import cv2
import time
import os
import threading

import subprocess

def record_from_camera_stream(camera, filepath, recording_id, active_recordings, recording_lock, duration_limit=1800):
    """
    Record video from an existing camera stream using OpenCV VideoWriter (MJPEG -> FFmpeg H.264)
    Strategies:
    1. Record to temporary .avi file using robust MJPEG codec.
    2. Convert .avi to .mp4 (H.264) using FFmpeg for browser compatibility.
    """
    
    # Use AVI container for the temporary standard MJPEG stream
    temp_filepath = str(filepath).replace('.mp4', '.avi')
    
    print(f"[Recording] Starting capture for {recording_id}")
    print(f"[Recording] Temp storage: {temp_filepath}")
    print(f"[Recording] Final target: {filepath}")
    
    out = None
    frame_count = 0
    
    try:
        # We record as MJPEG first (Very reliable in OpenCV)
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        fps = 20.0  # Frame rate targets
        frame_size = None
        
        start_time = time.time()
        
        print(f"[Recording] Starting frame capture loop...")
        
        while True:
            # Check duration limit
            if time.time() - start_time > duration_limit:
                print(f"[Recording] Duration limit reached for {recording_id}")
                break
            
            # Check if recording was stopped externally
            with recording_lock:
                if recording_id not in active_recordings:
                    print(f"[Recording] Recording {recording_id} was stopped externally")
                    break
                # Check for stop flag
                if active_recordings[recording_id].get('stop_requested', False):
                    print(f"[Recording] Stop requested for {recording_id}")
                    break
            
            # Get frame from camera
            frame = camera.get_raw_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            
            # Initialize video writer on first frame
            if out is None:
                frame_size = (frame.shape[1], frame.shape[0])
                print(f"[Recording] Initializing MJPEG Writer: {frame_size} @ {fps} fps")
                out = cv2.VideoWriter(temp_filepath, fourcc, fps, frame_size)
                
                if not out.isOpened():
                    print(f"[Recording] ERROR: Failed to open VideoWriter (MJPEG)")
                    return
            
            # Write frame
            out.write(frame)
            frame_count += 1
            
            # Small delay to control frame rate
            time.sleep(1.0 / fps)
        
        # Cleanup Writer
        if out is not None:
            out.release()
            out = None
            print(f"[Recording] MJPEG capture finished. Frames: {frame_count}")
        
        # ---------------------------------------------------------
        # POST-PROCESSING: Convert AVI (MJPEG) -> MP4 (H.264)
        # ---------------------------------------------------------
        if os.path.exists(temp_filepath) and frame_count > 0:
            print(f"[Recording] Converting to H.264 MP4: {filepath}")
            
            # FFmpeg command: High compatibility for browsers
            # -pix_fmt yuv420p is REQUIRED for QuickTime/Chrome support
            # -movflags +faststart helps with streaming
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_filepath,
                '-c:v', 'libx264',
                '-preset', 'ultrafast', # Fast encoding
                '-crf', '23',           # Good quality
                '-pix_fmt', 'yuv420p',  # Critical for browser playback
                '-movflags', '+faststart',
                filepath
            ]
            
            # Run FFmpeg
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if process.returncode == 0:
                print(f"[Recording] Conversion SUCCESS!")
                # Remove temp file
                try:
                    os.remove(temp_filepath)
                    print(f"[Recording] Temp file removed")
                except:
                    pass
            else:
                print(f"[Recording] Conversion FAILED. Error: {process.stderr.decode()}")
                # If conversion failed, maybe just rename the AVI to MP4? No, keep AVI.
                # Or move AVI to safe place.
                pass
        else:
             print(f"[Recording] No frames recorded or file missing.")

        # Verify final file
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            print(f"[Recording] Final file ready: {filepath} ({file_size} bytes)")
        else:
             print(f"[Recording] Final file is missing!")
            
    except Exception as e:
        print(f"[Recording] Failed {recording_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure writer is closed
        if out is not None:
            out.release()
            
        # Mark as completed
        with recording_lock:
            if recording_id in active_recordings:
                active_recordings[recording_id]['completed'] = True
