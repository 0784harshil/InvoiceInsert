"""
Debug unstructured line item regex on unnamed.jpg lines
"""

import cv2
import pytesseract
import os
import re
from decimal import Decimal

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
parsed_items = []

for idx, line in enumerate(lines, 1):
    line_str = line.strip()
    if not line_str:
        continue

    # Core-Mark / Distro regex: Look for item_num (5-6 digits), UPC (10-14 digits) or price decimal
    upc_match = re.search(r'\b(\d{10,14})\b', line_str)
    item_num_match = re.search(r'\b(\d{5,7})\b', line_str)
    price_matches = re.findall(r'\b(\d+\.\d{2})\b', line_str)

    if (upc_match or item_num_match) and len(price_matches) >= 1:
        item_code = item_num_match.group(1) if item_num_match else "000000"
        upc_code = upc_match.group(1) if upc_match else ""
        price_val = price_matches[-1]
        
        # Clean description
        desc = re.sub(r'^(EA|BX|CS|PK|\d+)\s*\|?\s*', '', line_str)
        desc = re.sub(r'\b\d{5,7}\b|\b\d{10,14}\b|\b\d+\.\d{2}\b', '', desc).replace('|', '').strip()
        
        parsed_items.append({
            'Line': idx,
            'ItemCode': item_code,
            'UPC': upc_code,
            'Price': price_val,
            'Description': desc[:40]
        })

print(f"Total Parsed Items on unnamed.jpg with Enhanced Regex: {len(parsed_items)}")
for it in parsed_items:
    print(f"  Line {it['Line']:2d} | Code: {it['ItemCode']:6s} | UPC: {it['UPC']:14s} | Price: ${it['Price']:6s} | Desc: {it['Description']}")
