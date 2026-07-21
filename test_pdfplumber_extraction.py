"""
Test direct native text extraction using pdfplumber on MAIL.pdf
"""

import pdfplumber
import re
from decimal import Decimal

pdf_path = r"C:\Users\harsh\Downloads\MAIL.pdf"

all_items = []
fees = {'tax': Decimal('0'), 'fuel': Decimal('0'), 'discount': Decimal('0')}

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, 1):
        text = page.extract_text()
        if not text:
            continue
            
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_str = line.strip()
            
            # Check for Fee lines (e.g., POS FUEL CHARGE, POS COOK CNTY TAX)
            if 'POS FUEL CHARGE' in line_str.upper():
                amt_match = re.search(r'([\d\.]+)\s*$', line_str)
                if amt_match:
                    fees['fuel'] += Decimal(amt_match.group(1))
                continue
            elif 'POS COOK CNTY TAX' in line_str.upper():
                amt_match = re.search(r'([\d\.]+)\s*$', line_str)
                if amt_match:
                    fees['tax'] += Decimal(amt_match.group(1))
                continue

            # Product Line Item format:
            # ITEM# QTY DESCRIPTION UPC UPRICE DISC DEP PRICE AMOUNT
            # e.g.: "11801 1 ASAHI 0810082770940 35.80 0.00 0.00 35.80 35.80"
            # Package line immediately follows: "SUPER DRY C24 12OZ 12P"
            match = re.search(r'^(\d{4,6})\s+(\d+)\s+(.*?)\s+(\d{10,14})\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)$', line_str)
            if match:
                item_code = match.group(1)
                qty_val = Decimal(match.group(2))
                desc_text = match.group(3)
                upc_str = match.group(4)
                uprice = Decimal(match.group(5))
                disc = Decimal(match.group(6))
                dep = Decimal(match.group(7))
                price = Decimal(match.group(8))
                amount = Decimal(match.group(9))
                
                # Check next line for package detail (e.g. SUPER DRY C24 12OZ 12P)
                pkg_text = "C24"
                if i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    if not re.search(r'^\d{4,6}\s', next_line):
                        pkg_text = next_line
                        desc_text += " " + next_line

                all_items.append({
                    'ItemCode': item_code,
                    'Qty': qty_val,
                    'Description': desc_text[:40],
                    'UPC': upc_str,
                    'PackageText': pkg_text,
                    'UnitPrice': uprice,
                    'Price': price,
                    'Amount': amount
                })

print(f"=========================================================")
print(f"TOTAL PARSED PRODUCT ITEMS IN MAIL.PDF: {len(all_items)}")
print(f"Segregated Fees: Tax=${fees['tax']}, Fuel=${fees['fuel']}")
print(f"=========================================================")

for item in all_items[:15]:
    print(f"  Line {len(all_items)} | Code: {item['ItemCode']:6s} | UPC: {item['UPC']:14s} | Price: ${item['Price']:6.2f} | Qty: {item['Qty']} | Desc: {item['Description']}")
