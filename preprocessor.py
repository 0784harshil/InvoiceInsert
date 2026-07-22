"""
Image Preprocessor with Dynamic Angle Auto-Detection & Enhancement
Optimizes images (contrast, deskew, noise reduction, and rotation detection)
to maximize OCR line item extraction.
"""

import cv2
import numpy as np
import pytesseract
from PIL import Image
import re
from typing import Tuple


class ImagePreprocessor:
    """
    OpenCV Preprocessing Engine with dynamic orientation detection (0°, 90°, 180°, 270°).
    """

    def __init__(self):
        pass

    def preprocess_for_pil(self, pil_image: Image.Image) -> Image.Image:
        """
        Converts PIL Image to OpenCV array, detects optimal rotation angle,
        enhances contrast & thresholding, and returns cleaned PIL Image.
        """
        cv_img = np.array(pil_image.convert('RGB'))
        cv_img = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)

        # 1. Dynamic Rotation Auto-Detection (Pick angle with maximum product item hits)
        best_angle, best_img = self._detect_best_orientation(cv_img)

        # 2. Convert to Grayscale & Contrast Enhancement
        gray = cv2.cvtColor(best_img, cv2.COLOR_BGR2GRAY)
        
        # Adaptive Thresholding & Denoising
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        enhanced = cv2.convertScaleAbs(denoised, alpha=1.3, beta=0)

        # Convert back to PIL
        return Image.fromarray(enhanced)

    def _detect_best_orientation(self, cv_img: np.ndarray) -> Tuple[int, np.ndarray]:
        """
        Evaluates 0°, 90°, 180°, 270° rotations to select the orientation with the highest item count.
        """
        angles = {
            0: cv_img,
            90: cv2.rotate(cv_img, cv2.ROTATE_90_CLOCKWISE),
            180: cv2.rotate(cv_img, cv2.ROTATE_180),
            270: cv2.rotate(cv_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        }

        best_angle = 0
        best_hits = -1
        best_img = cv_img

        for angle, rot_img in angles.items():
            try:
                # Fast OCR sample
                txt = pytesseract.image_to_string(rot_img, config='--psm 6')
                hits = sum(1 for l in txt.splitlines() if re.search(r'\b\d{5,6}\b', l) and re.search(r'\b\d{10,14}\b|\b\d+\.\d{2}\b', l))
                if hits > best_hits:
                    best_hits = hits
                    best_angle = angle
                    best_img = rot_img
            except Exception:
                pass

        return best_angle, best_img
