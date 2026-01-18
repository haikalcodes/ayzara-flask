"""
Barcode Service
===============
Business logic for barcode detection and validation
"""

import cv2
import numpy as np
from pyzbar.pyzbar import decode


class BarcodeService:
    """Service for handling barcode detection and validation"""
    
    @staticmethod
    def detect_barcode_from_frame(frame):
        """
        Detect barcode from a camera frame
        
        Args:
            frame: OpenCV frame (numpy array)
        
        Returns:
            String containing the detected barcode, or None if no barcode found
        """
        if frame is None:
            return None
        
        try:
            # Decode barcodes from frame
            barcodes = decode(frame)
            
            if barcodes:
                # Return the first detected barcode
                barcode_data = barcodes[0].data.decode('utf-8')
                return barcode_data
            
            return None
        except Exception as e:
            print(f"[Barcode] Error detecting barcode: {e}")
            return None
    
    @staticmethod
    def validate_barcode(barcode, expected_resi=None):
        """
        Validate barcode format and optionally match against expected resi
        
        Args:
            barcode: Barcode string to validate
            expected_resi: Optional expected resi to match against
        
        Returns:
            Tuple of (is_valid, message)
        """
        if not barcode or len(barcode.strip()) == 0:
            return False, "Barcode kosong"
        
        if expected_resi:
            if barcode.strip() != expected_resi.strip():
                return False, f"Barcode tidak cocok. Expected: {expected_resi}, Got: {barcode}"
        
        return True, "Barcode valid"
