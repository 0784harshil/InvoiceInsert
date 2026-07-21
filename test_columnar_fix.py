"""
Test Columnar Parser on MAIL.pdf
"""

from pdf2image import convert_from_path
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

poppler_path = r"C:\poppler\poppler-24.08.0\Library\bin" if os.path.exists(r"C:\poppler\poppler-24.08.0\Library\bin") else None
pdf_path = r"C:\Users\harsh\Downloads\MAIL.pdf"

images = convert_from_path(pdf_path, poppler_path=poppler_path)

all_items = []

for p_num, img in enumerate(images, 1):
    text = pytesseract.image_to_string(img)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # 1. Try row-based parsing first
    row_items = []
    for line in lines:
        upc_match = re.search(r'\b(\d{10,14})\b', line)
        numbers = re.findall(r'\$?(\d+\.\d{2,4})', line)
        parts = line.split()
        if upc_match and len(numbers) >= 1 and len(parts) >= 4:
            row_items.append((parts[0], upc_match.group(1), line))
            
    if len(row_items) >= 4:
        all_items.extend(row_items)
        print(f"Page {p_num}: Found {len(row_items)} items via Row Parsing")
    else:
        # 2. Try Columnar Parsing for pages where OCR split columns
        upcs = re.findall(r'\b\d{10,14}\b', text)
        # Filter out header/phone/date numbers
        upcs = [u for u in upcs if len(u) >= 11 and not u.startswith('773') and not u.startswith('877')]
        
        item_codes = re.findall(r'^\d{4,6}$', text, re.MULTILINE)
        prices = re.findall(r'\b\d{1,4}\.\d{2}\b', text)
        
        # Quantities and descriptions (e.g. "1 ASAHI", "2 BELLS")
        qty_descs = re.findall(r'^(\d+)\s+([A-Z0-9\s\.\-\/]+)', text, re.MULTILINE)
        qty_descs = [qd for qd in qty_descs if not qd[1].startswith('CH GROCER') and not qd[1].startswith('KILBOURN')]

        print(f"Page {p_num} Columnar Extraction: {len(item_codes)} Item Codes, {len(upcs)} UPCs, {len(qty_descs)} Qty/Descs, {len(prices)} Prices")
        
        num_items = min(len(item_codes), len(upcs))
        col_items = []
        for i in range(num_items):
            code = item_codes[i]
            upc = upcs[i]
            qty, desc = qty_descs[i] if i < len(qty_descs) else ("1", "Product")
            price = prices[i] if i < len(prices) else "0.00"
            col_items.append((code, upc, f"{code} {qty} {desc} {upc} {price}"))
            
        all_items.extend(col_items)
        print(f"Page {p_num}: Found {len(col_items)} items via Columnar Parsing")

print(f"\n=========================================")
print(f"TOTAL EXTRACTED ITEMS ACROSS PDF: {len(all_items)}")
print(f"=========================================")
for code, upc, line_str in all_items[:10]:
    print(f"  ItemCode: {code:6s} | UPC: {upc:14s} | Full: {line_str[:50]}...")
