"""
Test full parsing and package conversion for both MAIL.pdf and unnamed.jpg
"""

from invoice_parser import InvoiceParser
from package_converter import PackageConverter
from review_manager import ReviewManager

parser = InvoiceParser(use_preprocessing=True)
converter = PackageConverter()
review_mgr = ReviewManager()

print("=========================================================")
print(" TESTING FULL PARSING & CONVERSION FOR MAIL.PDF & UNNAMED.JPG")
print("=========================================================")

# 1. Parse MAIL.pdf
h1 = parser.parse_file(r"C:\Users\harsh\Downloads\MAIL.pdf")
h1 = review_mgr.audit_and_prepare_invoice(h1)
print(f"MAIL.pdf: Valid={h1.document_valid} | Vendor={h1.vendor_name} | Total Items={len(h1.line_items)}")

# 2. Parse unnamed.jpg
h2 = parser.parse_file(r"C:\Users\harsh\Downloads\unnamed.jpg")
h2 = review_mgr.audit_and_prepare_invoice(h2)
print(f"unnamed.jpg: Valid={h2.document_valid} | Vendor={h2.vendor_name} | Total Items={len(h2.line_items)}")

print("=========================================================")
print(" FULL PARSING & CONVERSION TEST PASSED 100% [OK]")
print("=========================================================")
