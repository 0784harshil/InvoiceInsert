"""
Debug line item extraction on unnamed.jpg (Core-Mark invoice image)
"""

import cv2
import pytesseract
import numpy as np
from PIL import Image
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

# Rotate 90 degrees clockwise (unnamed.jpg is scanned sideways)
rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

# Run OCR with psm 6 (assume uniform block of text) and psm 4
text_psm6 = pytesseract.image_to_string(rotated, config='--psm 6')
text_psm4 = pytesseract.image_to_string(rotated, config='--psm 4')
text_default = pytesseract.image_to_string(rotated)

print(f"=== PSM 6 OCR Text (Total lines: {len(text_psm6.splitlines())}) ===")
for l in text_psm6.splitlines():
    if l.strip():
        upc_match = re.search(r'\b(\d{10,14})\b', l)
        item_match = re.search(r'\b(\d{5,7})\b', l)
        print(f"  Line: {l.strip()[:80]}")

print("\n--- Counting items per PSM mode ---")
def count_items(txt):
    count = 0
    for l in txt.splitlines():
        # Core-Mark format: item number (5-6 digits), UPC (10-14 digits) or cost
        if re.search(r'\b\d{10,14}\b', l) or re.search(r'\b\d{5,6}\b.*?\d+\.\d{2}', l):
            count += 1
    return count

print(f"Default PSM: {count_items(text_default)} items")
print(f"PSM 4: {count_items(text_psm4)} items")
print(f"PSM 6: {count_items(text_psm6)} items")
