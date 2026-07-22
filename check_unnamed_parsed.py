"""
Check line item count returned by InvoiceParser on unnamed.jpg
"""

from invoice_parser import InvoiceParser

img_path = r"C:\Users\harsh\Downloads\unnamed.jpg"
parser = InvoiceParser(use_preprocessing=True)

header = parser.parse_file(img_path)

print(f"Header Document Valid: {header.document_valid}")
print(f"Header Vendor: {header.vendor_name}")
print(f"Total Line Items Extracted: {len(header.line_items)}")

for idx, item in enumerate(header.line_items, 1):
    print(f"  {idx:2d}. ItemCode: {item.raw_item_num:6s} | UPC: {item.raw_upc:14s} | Cost: ${item.unit_cost:6.2f} | Qty: {item.case_quantity} | Desc: {item.raw_description[:35]}")
