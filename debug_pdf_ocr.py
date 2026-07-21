"""
Debug OCR parsing on MAIL.pdf to see why Page 2-8 line items were skipped
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
print(f"Total Pages in MAIL.pdf: {len(images)}")

for p_num, img in enumerate(images, 1):
    text = pytesseract.image_to_string(img)
    lines = text.split('\n')
    
    parsed_in_page = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        upc_match = re.search(r'\b(\d{10,14})\b', line)
        numbers = re.findall(r'\$?(\d+\.\d{2,4})', line)
        if upc_match and len(numbers) >= 1:
            parsed_in_page += 1
            
    print(f"Page {p_num}: Found {parsed_in_page} matching product lines.")
    if p_num == 2:
        print("\n--- SAMPLE PAGE 2 RAW OCR LINES ---")
        for l in lines[:25]:
            if l.strip():
                print("  RAW LINE:", repr(l))
