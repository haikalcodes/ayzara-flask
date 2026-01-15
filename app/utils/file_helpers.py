"""
File Helpers
============
Utility functions for file and folder operations
"""

import config
import os
import cv2
import hashlib

def create_recording_folder(date_obj, platform, pegawai):
    """
    Create structured recording folder: recordings/DATE/PLATFORM/PEGAWAI
    
    Args:
        date_obj: datetime object for the recording date
        platform: Platform name (e.g., 'SHOPEE', 'TOKOPEDIA')
        pegawai: Pegawai/employee name
    
    Returns:
        Path object pointing to the created folder
    """
    date_str = date_obj.strftime('%Y-%m-%d')
    platform_clean = "".join(x for x in platform if x.isalnum() or x in " -_").strip().upper()
    pegawai_clean = "".join(x for x in pegawai if x.isalnum() or x in " -_").strip()
    
    # recordings/YYYY-MM-DD/PLATFORM/PEGAWAI
    folder_path = config.RECORDINGS_FOLDER / date_str / platform_clean / pegawai_clean
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path

def generate_thumbnail(video_path, relative_path_str):
    """
    Generate thumbnail from video file
    
    Args:
        video_path: Absolute path to video file
        relative_path_str: Relative path string (used for filename hash)
    
    Returns:
        Path to generated thumbnail or None if failed
    """
    try:
        # Create thumbnails directory if not exists
        thumb_dir = config.THUMBNAILS_FOLDER
        thumb_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate filename based on hash of RELATIVE path (to match PackingRecord logic)
        # Ensure forward slashes for consistency
        path_for_hash = relative_path_str.replace('\\', '/')
        path_hash = hashlib.md5(path_for_hash.encode()).hexdigest()
        thumb_filename = f"thumb_{path_hash}.jpg"
        thumb_path = thumb_dir / thumb_filename
        
        # Open video and capture frame
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"[Thumbnail] Could not open video: {video_path}")
            return None
            
        # Try to read the 15th frame (roughly 0.5-1s mark for 20-30fps) to avoid black start frames
        # or just the first frame if video is short
        cap.set(cv2.CAP_PROP_POS_FRAMES, 15)
        ret, frame = cap.read()
        
        if not ret:
            # Fallback to frame 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            
        cap.release()
        
        if ret and frame is not None:
            # Resize for thumbnail (optional, but good for performance)
            # Maintain aspect ratio, max width 480
            h, w = frame.shape[:2]
            target_w = 480
            if w > target_w:
                ratio = target_w / w
                new_h = int(h * ratio)
                frame = cv2.resize(frame, (target_w, new_h))
            
            # Save thumbnail
            # cv2.imwrite expects string path
            cv2.imwrite(str(thumb_path), frame)
            # print(f"[Thumbnail] Generated: {thumb_path}")
            return thumb_path
        else:
            print(f"[Thumbnail] Failed to capture frame from {video_path}")
            return None
            
    except Exception as e:
        print(f"[Thumbnail] Error generating thumbnail: {e}")
        return None
