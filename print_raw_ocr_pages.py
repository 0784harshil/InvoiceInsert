"""
Print exact raw OCR text of Page 2 and Page 3 of MAIL.pdf
"""

from pdf2image import convert_from_path
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

poppler_path = r"C:\poppler\poppler-24.08.0\Library\bin" if os.path.exists(r"C:\poppler\poppler-24.08.0\Library\bin") else None
pdf_path = r"C:\Users\harsh\Downloads\MAIL.pdf"

images = convert_from_path(pdf_path, poppler_path=poppler_path)

print("=== RAW OCR TEXT FOR PAGE 2 ===")
print(pytesseract.image_to_string(images[1]))

print("\n=== RAW OCR TEXT FOR PAGE 3 ===")
print(pytesseract.image_to_string(images[2]))
