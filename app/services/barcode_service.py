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
    def sharpen_image(image):
        gaussian = cv2.GaussianBlur(image, (0, 0), 3.0)
        return cv2.addWeighted(image, 1.5, gaussian, -0.5, 0)
    
    @staticmethod
    def crop_center(frame, crop_percent=0.6):
        """Crop center of the frame (Digital Zoom effect)"""
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cw, ch = int(w * crop_percent), int(h * crop_percent)
        
        x1 = max(0, cx - cw // 2)
        y1 = max(0, cy - ch // 2)
        x2 = min(w, x1 + cw)
        y2 = min(h, y1 + ch)
        
        return frame[y1:y2, x1:x2]
    
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
            # STRATEGY 0: Center Crop at ORIGINAL Resolution (High Detail)
            # This fixes the issue where resizing destroys small barcodes
            center = BarcodeService.crop_center(frame)
            barcodes = decode(center)
            if barcodes:
                print("[Barcode] ✅ FOUND in Stage 0 (Center Crop High-Res)")
                return barcodes[0].data.decode('utf-8')

            # OPTIMIZATION: Resize large frames to speed up processing
            # [ANTIGRAVITY] RELAXED LIMIT TO 2000px (Support 1080p)
            height, width = frame.shape[:2]
            if width > 2000:
                scale = 2000 / width
                frame = cv2.resize(frame, (2000, int(height * scale)))

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

            # --- ANTIGRAVITY UPGRADES ---

            # 4. Sharpening (Fixes soft IP cam focus)
            sharpened = BarcodeService.sharpen_image(enhanced_gray)
            
            # STRATEGY 5: Sharpened
            barcodes = decode(sharpened)
            if barcodes:
                print("[Barcode] ✅ FOUND in Stage 5 (Sharpened)")
                return barcodes[0].data.decode('utf-8')

            # 5. Adaptive Threshold (Fixes uneven lighting/shadows)
            # Block size 11, C=2
            adaptive = cv2.adaptiveThreshold(enhanced_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                           cv2.THRESH_BINARY, 11, 2)
            
            # STRATEGY 6: Adaptive Threshold
            barcodes = decode(adaptive)
            if barcodes:
                print("[Barcode] ✅ FOUND in Stage 6 (Adaptive)")
                return barcodes[0].data.decode('utf-8')

            # 6. Inversion (Fixes glare/specular highlights on black bars)
            # Sometimes glare makes black bars look white. Inverting flips this.
            inverted = cv2.bitwise_not(thresh)
            
            # STRATEGY 7: Inverted Threshold
            barcodes = decode(inverted)
            if barcodes:
                print("[Barcode] ✅ FOUND in Stage 7 (Inverted)")
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
