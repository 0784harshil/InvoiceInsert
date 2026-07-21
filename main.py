"""
Enterprise Invoice Receiving Engine - CLI Entrypoint
Runs complete receiving pipeline with strict rule validation,
fee segregation, Decimal arithmetic, and shadow mode audit logging.
"""

import os
import sys
from decimal import Decimal

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from invoice_parser import InvoiceParser
from validator import InvoiceValidator
from review_manager import ReviewManager
from db_manager import CertifiedDBManager
from models import ReviewState, InvoiceHeader


def process_invoice_cli(file_path: str, shadow_mode: bool = True, posting_enabled: bool = False):
    print("=" * 70)
    print(f"ENTERPRISE RECEIVING ENGINE — PROCESSING: {os.path.basename(file_path)}")
    print("=" * 70)

    parser = InvoiceParser(use_preprocessing=True)
    validator = InvoiceValidator()
    review_mgr = ReviewManager()
    db_mgr = CertifiedDBManager("config.json")

    # Step 1: Parse
    print("\n[Step 1] Ingesting & Parsing Document...")
    header: InvoiceHeader = parser.parse_file(file_path)

    # Step 2: Audit & Validate
    print("\n[Step 2] Auditing Enterprise Rules & Fee Segregation...")
    header = review_mgr.audit_and_prepare_invoice(header)
    is_valid, issues = validator.validate(header)

    print(f"   Document Valid: {header.document_valid}")
    print(f"   Line Items Extracted: {len(header.line_items)}")
    print(f"   Subtotal: ${header.subtotal:.2f}")
    print(f"   Segregated Fees (Tax, Fuel, Deposits): ${header.fees.total_non_inventory_fees:.2f}")
    print(f"   Grand Total: ${header.total_amount:.2f}")

    if issues:
        print("\n   Audit Findings:")
        for issue in issues:
            print(f"      - {issue}")

    # Step 3: Print Line Items Preview
    print("\n[Step 3] Line Items Review Queue:")
    for item in header.line_items[:10]:
        print(
            f"   Line {item.line_number:2d} | UPC: {item.raw_upc or 'MISSING':14s} | "
            f"Item: {item.raw_description[:25]:25s} | Cost: ${item.unit_cost:6.2f} | "
            f"Expected POS Qty: {item.expected_pos_qty} | State: {item.review_state.value}"
        )
    if len(header.line_items) > 10:
        print(f"   ... and {len(header.line_items) - 10} more line items")

    # Step 4: Shadow Mode / Live Receiving Execution
    print("\n[Step 4] Executing Database Receiving Engine...")
    results = db_mgr.post_invoice_receiving(header, shadow_mode=shadow_mode, posting_enabled=posting_enabled)

    print(f"\n   Execution Status: {results['status']}")
    print(f"   Shadow Mode: {results['shadow_mode']}")
    print(f"   Posting Enabled: {results['posting_enabled']}")

    if results['audit_log']:
        print("\n   Audit Log / SQL Ledger Preview:")
        for log in results['audit_log'][:5]:
            print(f"      {log}")

    print("\n" + "=" * 70)
    print("RECEIVING SUMMARY COMPLETE")
    print("=" * 70)
    return results


def main():
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = input("\nEnter invoice file path: ").strip('"').strip()

    shadow_mode = '--live' not in sys.argv
    posting_enabled = '--post' in sys.argv

    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return 1

    process_invoice_cli(file_path, shadow_mode=shadow_mode, posting_enabled=posting_enabled)
    return 0


if __name__ == "__main__":
    sys.exit(main())
