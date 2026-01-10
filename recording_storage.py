"""
Recording Storage Helper Module
Handles hierarchical directory structure and metadata generation
"""
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
import config

def get_recording_directory(date_str, platform, pegawai):
    """
    Generate directory path: recordings/YYYY-MM-DD/PLATFORM/pegawai/
    Creates directories if they don't exist.
    
    Args:
        date_str: Date string in format YYYY-MM-DD
        platform: Platform name (SHOPEE, TOKOPEDIA, etc.)
        pegawai: Employee username
    
    Returns:
        Path object to the directory
    """
    dir_path = config.RECORDINGS_FOLDER / date_str / platform / pegawai
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

def find_next_index(directory, resi, platform):
    """
    Find next available index for a resi number.
    Scans existing files matching pattern: RESI_PLATFORM_AYZARA_*.mp4
    
    Args:
        directory: Path object to search in
        resi: Resi number
        platform: Platform name
    
    Returns:
        String index with zero padding (e.g., "001", "002")
    """
    pattern = f"{resi}_{platform}_AYZARA_*.mp4"
    existing_files = list(directory.glob(pattern))
    
    if not existing_files:
        return "001"
    
    # Extract indices from filenames
    indices = []
    for f in existing_files:
        try:
            # Extract index from filename: RESI_PLATFORM_AYZARA_INDEX.mp4
            index_str = f.stem.split('_')[-1]
            indices.append(int(index_str))
        except:
            pass
    
    next_index = max(indices) + 1 if indices else 1
    return f"{next_index:03d}"

def calculate_sha256(filepath):
    """
    Calculate SHA256 hash of a file
    
    Args:
        filepath: Path to file
    
    Returns:
        Hexadecimal SHA256 hash string
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def generate_metadata_json(video_info):
    """
    Generate metadata JSON structure
    
    Args:
        video_info: dict with keys:
            - resi, platform, pegawai
            - filename, durasi_detik, ukuran_kb
            - waktu_mulai, waktu_selesai
            - sha256_hash
    
    Returns:
        Dictionary with metadata structure
    """
    return {
        "bukti_rekaman": {
            "versi": "1.0",
            "brand": "AYZARA",
            "dibuat_oleh": "Packing Recording System"
        },
        "informasi_paket": {
            "nomor_resi": video_info['resi'],
            "platform": video_info['platform'],
            "pegawai": video_info['pegawai']
        },
        "informasi_video": {
            "nama_file": video_info['filename'],
            "durasi_detik": video_info['durasi_detik'],
            "ukuran_kb": video_info['ukuran_kb'],
            "sha256_hash": video_info['sha256_hash']
        },
        "waktu": {
            "rekaman_mulai": video_info['waktu_mulai'],
            "rekaman_selesai": video_info['waktu_selesai'],
            "zona_waktu": "Asia/Jakarta (WIB)"
        },
        "catatan": "File ini adalah bukti otentik rekaman packing. Hash SHA256 dapat digunakan untuk memverifikasi keaslian video."
    }

def save_metadata_json(json_filepath, metadata):
    """
    Save metadata to JSON file
    
    Args:
        json_filepath: Path to save JSON file
        metadata: Dictionary with metadata
    """
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
