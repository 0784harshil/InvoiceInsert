"""
Test multi-line OCR text joiner for MAIL.pdf
"""

from pdf2image import convert_from_path
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

poppler_path = r"C:\poppler\poppler-24.08.0\Library\bin" if os.path.exists(r"C:\poppler\poppler-24.08.0\Library\bin") else None
pdf_path = r"C:\Users\harsh\Downloads\MAIL.pdf"

images = convert_from_path(pdf_path, poppler_path=poppler_path)
full_text = ""
for img in images:
    full_text += pytesseract.image_to_string(img) + "\n"

# Preprocess multi-line text: Merge lines that belong to the same item block
lines = full_text.split('\n')
merged_lines = []
current_block = ""

for line in lines:
    line_str = line.strip()
    if not line_str:
        continue
    
    # Check if this line starts a new item (starts with 4-6 digit item number or Fee header)
    starts_new_item = bool(re.match(r'^\d{4,6}\s', line_str)) or bool(re.search(r'TOTAL|SUBTOTAL|TAX|CHARGE|CASES:', line_str, re.IGNORECASE))
    
    if starts_new_item:
        if current_block:
            merged_lines.append(current_block)
        current_block = line_str
    else:
        if current_block:
            current_block += " " + line_str
        else:
            current_block = line_str

if current_block:
    merged_lines.append(current_block)

print(f"Total Merged Blocks: {len(merged_lines)}")
parsed_items = 0
for b in merged_lines:
    upc_match = re.search(r'\b(\d{10,14})\b', b)
    numbers = re.findall(r'\$?(\d+\.\d{2,4})', b)
    if upc_match and len(numbers) >= 1:
        parsed_items += 1
        print(f"  [PARSED] UPC: {upc_match.group(1)} | Text: {b[:70]}...")

print(f"\nTOTAL PARSED PRODUCT ITEMS ACROSS ALL PAGES: {parsed_items}")
