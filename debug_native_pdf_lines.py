"""
Debug pdfplumber native extraction in invoice_parser.py
"""

import pdfplumber
import re

pdf_path = r"C:\Users\harsh\Downloads\MAIL.pdf"

matched_lines = []
unmatched_lines = []

with pdfplumber.open(pdf_path) as pdf:
    for p_num, page in enumerate(pdf.pages, 1):
        text = page.extract_text()
        if not text:
            continue
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line_str = line.strip()
            # Standard pattern
            match1 = re.search(r'^(\d{4,6})\s+(\d+)\s+(.*?)\s+(\d{10,14})\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)$', line_str)
            # Broader pattern: starts with item code, contains UPC (10-14 digits) and at least one decimal price
            match2 = re.search(r'^\d{4,6}\s+.*?\b\d{10,14}\b.*?\d+\.\d{2}', line_str)
            
            if match1:
                matched_lines.append((p_num, line_str))
            elif match2:
                unmatched_lines.append((p_num, line_str))

print(f"Match Pattern 1 (Strict): {len(matched_lines)} items matched.")
print(f"Match Pattern 2 (Broader): {len(unmatched_lines)} additional items found!")

if unmatched_lines:
    print("\n--- SAMPLE UNMATCHED PRODUCT LINES ---")
    for p_num, l in unmatched_lines[:15]:
        print(f"  Page {p_num}: {repr(l)}")
