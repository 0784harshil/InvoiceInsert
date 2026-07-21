"""
Image Preprocessing Module for Invoice Processing
Uses OpenCV to enhance image quality before OCR:
- Orientation detection & auto-rotation (90/180/270 degrees)
- Noise reduction
- Deskewing
- Contrast enhancement
- Adaptive binarization
"""

import cv2
import numpy as np
from PIL import Image
import os
import pytesseract


class ImagePreprocessor:
    """
    Preprocesses images for optimal OCR accuracy.
    Applies auto-orientation, noise reduction, skew correction, contrast enhancement, and binarization.
    """
    
    def __init__(self, debug=False):
        self.debug = debug

    def preprocess(self, image_input) -> np.ndarray:
        """Main preprocessing pipeline returning preprocessed numpy array."""
        image = self._load_as_cv2(image_input)
        
        # Step 0: Auto-orientation check (rotate sideways/upside-down images)
        oriented = self._auto_rotate(image)
        
        # Convert to grayscale
        if len(oriented.shape) == 3:
            gray = cv2.cvtColor(oriented, cv2.COLOR_BGR2GRAY)
        else:
            gray = oriented
        
        # Step 1: Denoise
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)
        denoised = cv2.medianBlur(denoised, 3)
        
        # Step 2: Deskew
        deskewed = self._deskew(denoised)
        
        # Step 3: Contrast enhancement (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(deskewed)
        
        # Step 4: Binarization
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        return binary

    def preprocess_for_pil(self, image_input) -> Image.Image:
        """Convenience method returning PIL Image."""
        processed_np = self.preprocess(image_input)
        return Image.fromarray(processed_np)

    def _load_as_cv2(self, image_input) -> np.ndarray:

        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Image not found: {image_input}")
            img = cv2.imread(image_input)
        elif isinstance(image_input, np.ndarray):
            img = image_input
        elif isinstance(image_input, Image.Image):
            img = np.array(image_input)
            if len(img.shape) == 3:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        else:
            raise ValueError(f"Unsupported image type: {type(image_input)}")
            
        if img is None:
            raise ValueError("Could not decode image")
        return img

    def _auto_rotate(self, image: np.ndarray) -> np.ndarray:
        """Detect image orientation using Tesseract OSD (Orientation and Script Detection) or aspect ratio."""
        h, w = image.shape[:2]
        
        # If height < width significantly, it might be a vertical document scanned sideways
        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if len(image.shape) == 3 else image
            osd = pytesseract.image_to_osd(rgb, output_type=pytesseract.Output.DICT)
            rotate_angle = osd.get('rotate', 0)
            
            if rotate_angle == 90:
                return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            elif rotate_angle == 180:
                return cv2.rotate(image, cv2.ROTATE_180)
            elif rotate_angle == 270:
                return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        except Exception:
            # Fallback heuristic: If image is significantly wider than tall, rotate 90 degrees clockwise
            if w > h * 1.3:
                return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
                
        return image

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """Detect and correct small skew angles using Hough transform."""
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
        
        if lines is None:
            return image
            
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 == 0:
                continue
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(angle) < 45:
                angles.append(angle)
                
        if not angles:
            return image
            
        median_angle = float(np.median(angles))
        if abs(median_angle) < 0.5:
            return image
            
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        deskewed = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return deskewed
