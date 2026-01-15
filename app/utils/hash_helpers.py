"""
Hash Helpers
============
Utility functions for file hashing and verification
"""

import hashlib


def calculate_sha256(file_path):
    """
    Calculate SHA256 hash of a file
    
    Args:
        file_path: Path to the file to hash
    
    Returns:
        Hexadecimal string representation of the SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
