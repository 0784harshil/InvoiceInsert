"""
Test Live Database Insertion & Reconciliation
Verifies that real records are written to the database when shadow_mode=False and posting_enabled=True.
"""

from decimal import Decimal
import os
import sys

from invoice_parser import InvoiceParser
from review_manager import ReviewManager
from db_manager import CertifiedDBManager
from models import ReviewState


def test_live_db_receiving():
    print("======================================================================")
    print("   TESTING LIVE DATABASE INSERTION & READBACK RECONCILIATION")
    print("======================================================================")

    file_path = r"C:\Users\harsh\Downloads\MAIL.pdf"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    parser = InvoiceParser(use_preprocessing=True)
    review_mgr = ReviewManager()
    db_mgr = CertifiedDBManager("config.json")

    # Step 1: Parse
    header = parser.parse_file(file_path)
    header = review_mgr.audit_and_prepare_invoice(header)

    # Step 2: Approve line items
    approved_count = 0
    for item in header.line_items:
        if item.review_state != ReviewState.POSTING_BLOCKED:
            qty = item.expected_pos_qty or item.case_quantity
            review_mgr.approve_line_item(item, qty)
            approved_count += 1

    print(f"Approved {approved_count} line items for live posting.")

    # Step 3: Execute LIVE Database Insertion (shadow_mode=False, posting_enabled=True)
    print("\nExecuting LIVE Database Posting (shadow_mode=False, posting_enabled=True)...")
    res = db_mgr.post_invoice_receiving(header, shadow_mode=False, posting_enabled=True)

    print(f"\nExecution Status: {res['status']}")
    print(f"Items Attempted: {res['items_attempted']}")
    print(f"Items Reconciled: {res['items_reconciled']}")
    print(f"Reconciliation Failed: {res['reconciliation_failed']}")

    print("\nReadback Reconciliation Report Sample:")
    for rep in res['reconciliation_report'][:5]:
        print(f"  - {rep}")

    # Step 4: Verify Database Inventory Table Contents
    print("\nFetching Live Inventory Table Records from Database:")
    records = db_mgr.get_inventory_records()
    print(f"Total Database Inventory Records: {len(records)}")
    for rec in records[:5]:
        print(f"  UPC: {rec['ItemNum']:14s} | Description: {rec['ItemName']:25s} | Stock: {rec['In_Stock']} | Cost: ${rec['Cost']:.2f}")

    assert res['items_reconciled'] > 0, "Live database writes must reconcile items successfully!"
    assert len(records) > 0, "Database inventory table must contain inserted records!"
    print("\n======================================================================")
    print("   LIVE DATABASE INSERTION & RECONCILIATION TEST PASSED [OK]")
    print("======================================================================")


if __name__ == "__main__":
    test_live_db_receiving()
