"""
FLASK DASHBOARD CONFIGURATION
=============================
Configuration untuk AYZARA Dashboard Flask
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).parent.absolute()
PROJECT_DIR = BASE_DIR.parent  # Parent folder (main project)

# Database - NOW IN dashboard_flask FOLDER
DATABASE_FILE = BASE_DIR / "packing_records.db"  # Changed from PROJECT_DIR to BASE_DIR
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_FILE}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Recording folder
RECORDINGS_FOLDER = BASE_DIR / "recordings"

# Upload folders
UPLOAD_FOLDER = BASE_DIR / "uploads"
PHOTOS_FOLDER = UPLOAD_FOLDER / "photos"
THUMBNAILS_FOLDER = UPLOAD_FOLDER / "thumbnails"

# Static folder
STATIC_FOLDER = BASE_DIR / "static"

# Config file (dari project utama)
CONFIG_FILE = BASE_DIR / "config.json"

# Flask settings
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
DEBUG = True

# Camera/RTSP settings (akan di-load dari config.json)
DEFAULT_RTSP_URL = "http://192.168.43.1:4747/mjpegfeed"
FFMPEG_PATH = "ffmpeg"

# Platform configuration
PLATFORMS = {
    "SHOPEE": {"color": "#EE4D2D", "icon": "🛒"},
    "TOKOPEDIA": {"color": "#03AC0E", "icon": "🏪"},
    "LAZADA": {"color": "#0F1689", "icon": "🛍️"},
    "TIKTOK": {"color": "#000000", "icon": "🎵"},
    "LAINNYA": {"color": "#6B7280", "icon": "📦"},
}

# Pagination
ITEMS_PER_PAGE = 12

# App info
APP_NAME = "AYZARA Dashboard"
# APP_VERSION will be loaded from config.json below
try:
    with open(CONFIG_FILE, 'r') as f:
        config_data = json.load(f)
        APP_VERSION = config_data.get('app_version', '1.0.0')
        # [ANTIGRAVITY] Max Recording Duration (seconds)
        MAX_RECORDING_DURATION = config_data.get('max_recording_duration', 3600)
except Exception as e:
    APP_VERSION = "1.0.0"
    MAX_RECORDING_DURATION = 3600

APP_AUTHOR = "AYZARA COLLECTIONS"
BRAND_NAME = "AYZARA"

# Create directories if not exist
# [ANTIGRAVITY] SMART STORAGE LOCATION
# Auto-detect largest drive for storage
try:
    import psutil
    
    # Get all disk partitions
    partitions = psutil.disk_partitions()
    largest_drive = None
    max_size = 0
    
    for p in partitions:
        try:
            # Only check fixed/removable drives (skip cdrom, ramdisk, etc if possible)
            if 'fixed' in p.opts or 'rw' in p.opts:
                usage = psutil.disk_usage(p.mountpoint)
                # Compare total size
                if usage.total > max_size:
                    max_size = usage.total
                    largest_drive = p.mountpoint
        except:
            continue
            
    if largest_drive:
        # Normalize path
        STORAGE_ROOT = Path(largest_drive) / "AyzaraData"
        print(f"[Config] Selected Largest Drive for Storage: {largest_drive} ({max_size/1e9:.1f} GB)")
    else:
        # Fallback
        STORAGE_ROOT = BASE_DIR
        print(f"[Config] Using Default Storage: {BASE_DIR}")

except Exception as e:
    print(f"[Config] Drive detection failed: {e}")
    STORAGE_ROOT = BASE_DIR

# Redefine folders using STORAGE_ROOT
RECORDINGS_FOLDER = STORAGE_ROOT / "recordings"
UPLOAD_FOLDER = STORAGE_ROOT / "uploads"
PHOTOS_FOLDER = UPLOAD_FOLDER / "photos"
THUMBNAILS_FOLDER = UPLOAD_FOLDER / "thumbnails"

# Create directories if not exist
for folder in [UPLOAD_FOLDER, PHOTOS_FOLDER, THUMBNAILS_FOLDER, RECORDINGS_FOLDER]:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        # print(f"[Config] Verified folder: {folder}")
    except Exception as e:
        print(f"[Config] Error creating folder {folder}: {e}")
