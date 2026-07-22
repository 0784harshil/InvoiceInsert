"""
Check InvoiceParser().parse_file on MAIL.pdf to count line items returned in header
"""

from invoice_parser import InvoiceParser
import os

pdf_path = r"C:\Users\harsh\Downloads\MAIL.pdf"
parser = InvoiceParser()

header = parser.parse_file(pdf_path)

print(f"Header File: {header.invoice_number}")
print(f"Total Line Items in Header: {len(header.line_items)}")

for idx, item in enumerate(header.line_items[:10], 1):
    print(f"  {idx:3d}. Code: {item.raw_item_num:6s} | UPC: {item.raw_upc:14s} | Cost: ${item.unit_cost:6.2f} | Qty: {item.case_quantity} | Desc: {item.raw_description[:30]}")

if len(header.line_items) > 10:
    print(f"  ... and {len(header.line_items) - 10} more items.")
