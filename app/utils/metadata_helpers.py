"""
Metadata Helpers
================
Utility functions for generating and managing recording metadata
"""

import os
import json
from datetime import datetime
from .hash_helpers import calculate_sha256


def generate_metadata_json(record_data, video_path, duration, file_size):
    """
    Generate JSON metadata for recording
    
    Args:
        record_data: Dictionary containing recording information (resi, platform, pegawai, waktu_mulai)
        video_path: Path to the video file
        duration: Duration of the video in seconds
        file_size: Size of the video file in bytes
    
    Returns:
        Tuple of (json_path, file_hash)
    """
    video_filename = os.path.basename(video_path)
    file_hash = calculate_sha256(video_path)
    
    metadata = {
        "bukti_rekaman": {
            "versi": "1.0",
            "brand": "AYZARA",
            "dibuat_oleh": "Packing Recording System"
        },
        "informasi_paket": {
            "nomor_resi": record_data['resi'],
            "platform": record_data['platform'],
            "pegawai": record_data['pegawai']
        },
        "informasi_video": {
            "nama_file": video_filename,
            "durasi_detik": round(duration, 2),
            "ukuran_kb": round(file_size / 1024),
            "sha256_hash": file_hash
        },
        "waktu": {
            "rekaman_mulai": record_data['waktu_mulai'] if isinstance(record_data['waktu_mulai'], str) else record_data['waktu_mulai'].strftime('%Y-%m-%d %H:%M:%S'),
            "rekaman_selesai": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "zona_waktu": "Asia/Jakarta (WIB)"
        },
        "catatan": "File ini adalah bukti otentik rekaman packing. Hash SHA256 dapat digunakan untuk memverifikasi keaslian video."
    }
    
    # Save JSON file
    json_path = str(video_path).rsplit('.', 1)[0] + '.json'
    with open(json_path, 'w') as f:
        json.dump(metadata, f, indent=2)
        
    return json_path, file_hash
