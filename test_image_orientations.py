"""
Test all 4 rotation angles (0, 90, 180, 270 degrees) on unnamed.jpg
"""

import cv2
import pytesseract
import os
import re

possible_paths = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    os.path.join(os.getenv('LOCALAPPDATA', ''), r'Tesseract-OCR\tesseract.exe'),
]
for p in possible_paths:
    if os.path.exists(p):
        pytesseract.pytesseract.tesseract_cmd = p
        break

img_path = r"C:\Users\harsh\Downloads\unnamed.jpg"
img = cv2.imread(img_path)

rotations = {
    0: img,
    90: cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE),
    180: cv2.rotate(img, cv2.ROTATE_180),
    270: cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
}

for angle, rot_img in rotations.items():
    txt = pytesseract.image_to_string(rot_img)
    
    # Count valid product lines
    lines = txt.splitlines()
    items = []
    for l in lines:
        if l.strip():
            # Check if line contains a 5-6 digit item number and a product description or UPC
            if re.search(r'\b\d{5,6}\b', l) and (re.search(r'[A-Z]{3,}', l) or re.search(r'\b\d{10,14}\b', l)):
                items.append(l.strip())
                
    print(f"Angle {angle:3d}°: Found {len(items)} items | Total text lines: {len(lines)}")
    if len(items) > 10:
        print(f"--- SAMPLE EXTRACTED LINES FOR ANGLE {angle}° ---")
        for it in items[:10]:
            print(f"  {repr(it)}")
