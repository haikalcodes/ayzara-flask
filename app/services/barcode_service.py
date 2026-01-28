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
            # OPTIMIZATION: Resize large frames to speed up processing
            # Max width 800px maintains readability while reducing CPU load
            height, width = frame.shape[:2]
            if width > 800:
                scale = 800 / width
                frame = cv2.resize(frame, (800, int(height * scale)))

            # STRATEGY 1: Detect on Original Frame (Fastest)
            barcodes = decode(frame)
            if barcodes:
                print("[Barcode] ✅ FOUND in Stage 1 (Original)")
                return barcodes[0].data.decode('utf-8')

            # --- OPTIMIZATION PIPELINE ---
            
            # 1. Convert to Grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # STRATEGY 2: Detect on Grayscale
            barcodes = decode(gray)
            if barcodes:
                print("[Barcode] ✅ FOUND in Stage 2 (Grayscale)")
                return barcodes[0].data.decode('utf-8')

            # 2. Enhance Contrast (Alpha=1.5, Beta=10)
            enhanced_gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=10)
            
            # STRATEGY 3: Detect on Enhanced Grayscale
            barcodes = decode(enhanced_gray)
            if barcodes:
                 print("[Barcode] ✅ FOUND in Stage 3 (Enhanced Contrast)")
                 return barcodes[0].data.decode('utf-8')

            # 3. Thresholding (Otsu's Binarization) - High Contrast B&W
            _, thresh = cv2.threshold(enhanced_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # STRATEGY 4: Detect on Thresholded Image (Best for tough lighting)
            barcodes = decode(thresh)
            if barcodes:
                print("[Barcode] ✅ FOUND in Stage 4 (Threshold)")
                return barcodes[0].data.decode('utf-8')
            
            # If we reach here, all stages failed
            pass
            
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
