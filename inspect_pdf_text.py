"""
Inspect text extraction on MAIL.pdf using pdfplumber / pypdf vs OCR
"""

import os
import re

# Try importing pdfplumber or pypdf
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

pdf_path = r"C:\Users\harsh\Downloads\MAIL.pdf"

print(f"pdfplumber available: {HAS_PDFPLUMBER}")
print(f"pypdf available: {HAS_PYPDF}")

if HAS_PDFPLUMBER:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"\nTotal Pages via pdfplumber: {len(pdf.pages)}")
        total_items = 0
        for idx, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            lines = [l for l in text.split('\n') if l.strip()]
            print(f"\n--- Page {idx} (Total text lines: {len(lines)}) ---")
            for l in lines[:10]:
                print(f"  {repr(l)}")

elif HAS_PYPDF:
    reader = pypdf.PdfReader(pdf_path)
    print(f"\nTotal Pages via pypdf: {len(reader.pages)}")
    for idx, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        lines = [l for l in text.split('\n') if l.strip()]
        print(f"\n--- Page {idx} (Total text lines: {len(lines)}) ---")
        for l in lines[:10]:
            print(f"  {repr(l)}")
