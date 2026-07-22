"""
Test complete 26-item parser for unnamed.jpg
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
    if not line_str or 'SOLD TO' in line_str or 'Baseline' in line_str or 'Total' in line_str or 'PAGE' in line_str:
        continue

    # Look for 5-6 digit item code or 10-14 digit UPC
    item_num_match = re.search(r'\b(\d{5,7})\b', line_str)
    upc_match = re.search(r'\b(\d{10,14})\b', line_str)
    has_product_words = bool(re.search(r'\b[A-Z]{3,}\b', line_str))

    if (item_num_match or upc_match) and has_product_words:
        item_code = item_num_match.group(1) if item_num_match else "000000"
        upc_code = upc_match.group(1) if upc_match else ""
        
        # Price extraction: decimal price, or 3-4 digit integer at end (e.g. 471 -> 4.71)
        price_match = re.search(r'\$?(\d+\.\d{2})', line_str)
        if price_match:
            price_val = price_match.group(1)
        else:
            int_price_match = re.search(r'\b(\d{3,4})\s*$', line_str)
            if int_price_match:
                digits = int_price_match.group(1)
                price_val = f"{digits[:-2]}.{digits[-2:]}"
            else:
                price_val = "0.00"

        # Clean description
        desc = re.sub(r'^(EA|BX|CS|PK|i EA|\[ EA|U EA|cs|\d+)\s*\|?\s*', '', line_str)
        desc = re.sub(r'\b\d{5,7}\b|\b\d{10,14}\b|\$?[\d\.]+', '', desc).replace('|', '').strip()

        parsed_items.append({
            'Line': idx,
            'ItemCode': item_code,
            'UPC': upc_code,
            'Price': price_val,
            'Description': desc[:35]
        })

print(f"=========================================================")
print(f"TOTAL PARSED ITEMS ON UNNAMED.JPG: {len(parsed_items)}")
print(f"=========================================================")
for item in parsed_items:
    print(f"  Line {item['Line']:2d} | Code: {item['ItemCode']:6s} | UPC: {item['UPC']:14s} | Price: ${item['Price']:6s} | Desc: {item['Description']}")
