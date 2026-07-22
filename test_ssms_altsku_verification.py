"""
Execute receiving for both MAIL.pdf and unnamed.jpg to populate Inventory and Inventory_SKUS in CRE SQL Server
"""

from invoice_parser import InvoiceParser
from review_manager import ReviewManager
from db_manager import CertifiedDBManager
from models import ReviewState

parser = InvoiceParser(use_preprocessing=True)
review_mgr = ReviewManager()
db = CertifiedDBManager("config.json")

print("=========================================================")
print(" POSTING ALL ITEMS WITH ALTSKUS TO CRE SQL SERVER")
print("=========================================================")

# 1. Post MAIL.pdf (101 items)
h1 = parser.parse_file(r"C:\Users\harsh\Downloads\MAIL.pdf")
h1 = review_mgr.audit_and_prepare_invoice(h1)
for item in h1.line_items:
    if item.review_state != ReviewState.POSTING_BLOCKED:
        review_mgr.approve_line_item(item, item.expected_pos_qty or item.case_quantity)

res1 = db.post_invoice_receiving(h1, shadow_mode=False, posting_enabled=True)
print(f"MAIL.pdf Status: {res1['status']} | Reconciled: {res1['items_reconciled']} items")

# 2. Post unnamed.jpg (26 items)
h2 = parser.parse_file(r"C:\Users\harsh\Downloads\unnamed.jpg")
h2 = review_mgr.audit_and_prepare_invoice(h2)
for item in h2.line_items:
    if item.review_state != ReviewState.POSTING_BLOCKED:
        review_mgr.approve_line_item(item, item.expected_pos_qty or item.case_quantity)

res2 = db.post_invoice_receiving(h2, shadow_mode=False, posting_enabled=True)
print(f"unnamed.jpg Status: {res2['status']} | Reconciled: {res2['items_reconciled']} items")

print("=========================================================")
print(" DATA POPULATION COMPLETE — READY FOR SSMS TESTING")
print("=========================================================")
