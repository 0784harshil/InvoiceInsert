"""
Post & Reconcile all 26 items from unnamed.jpg to CRE SQL Server cresql.dbo.Inventory
"""

from invoice_parser import InvoiceParser
from review_manager import ReviewManager
from db_manager import CertifiedDBManager
from models import ReviewState

img_path = r"C:\Users\harsh\Downloads\unnamed.jpg"

parser = InvoiceParser(use_preprocessing=True)
review_mgr = ReviewManager()
db = CertifiedDBManager("config.json")

print("Processing unnamed.jpg...")
header = parser.parse_file(img_path)
header = review_mgr.audit_and_prepare_invoice(header)

print(f"Total Line Items Extracted: {len(header.line_items)}")

# Approve all items for live posting
for item in header.line_items:
    if item.review_state != ReviewState.POSTING_BLOCKED:
        review_mgr.approve_line_item(item, item.expected_pos_qty or item.case_quantity)

print("\nExecuting Live DB Posting to cresql.dbo.Inventory (shadow_mode=False, posting_enabled=True)...")
results = db.post_invoice_receiving(header, shadow_mode=False, posting_enabled=True)

print(f"\nExecution Status: {results['status']}")
print(f"Items Attempted: {results['items_attempted']}")
print(f"Items Reconciled: {results['items_reconciled']}")
print(f"Reconciliation Failed: {results['reconciliation_failed']}")

print("\nSample Reconciled Items:")
for r in results['reconciliation_report'][:10]:
    print(f"  - {r}")
