"""
FLASK DASHBOARD CONFIGURATION
=============================
Configuration untuk AYZARA Dashboard Flask
"""

import os
from pathlib import Path

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
SECRET_KEY = os.environ.get('SECRET_KEY', 'ayzara-flask-secret-key-2026')
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
APP_VERSION = "2.0.0"
APP_AUTHOR = "AYZARA COLLECTIONS"
BRAND_NAME = "AYZARA"

# Create directories if not exist
for folder in [UPLOAD_FOLDER, PHOTOS_FOLDER, THUMBNAILS_FOLDER, RECORDINGS_FOLDER]:
    folder.mkdir(parents=True, exist_ok=True)
