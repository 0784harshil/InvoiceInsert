"""
Inspect raw OCR lines 30 to 48 of unnamed.jpg
"""

import cv2
import pytesseract
import os

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
txt = pytesseract.image_to_string(img)

lines = txt.splitlines()

print("--- RAW LINES 30 to 48 ---")
for idx, l in enumerate(lines[28:48], 29):
    print(f"Line {idx:2d}: {repr(l)}")
