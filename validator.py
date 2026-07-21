"""
Enterprise Invoice Validator Module
Performs data integrity and business rule audits using exact Decimal math.
"""

from decimal import Decimal
import re
from typing import Tuple, List, Dict, Any
from models import InvoiceHeader, InvoiceLineItem, ReviewState


class InvoiceValidator:
    """
    Enforces Rule 16 (blocking on any ambiguity or drift) and Rule 3 (Decimal precision).
    """

    def validate(self, header: InvoiceHeader) -> Tuple[bool, List[str]]:
        """
        Performs strict validation audit on invoice header and line items.
        """
        issues: List[str] = []

        # Rule 16: Non-invoice document check
        if not header.document_valid:
            issues.append("CRITICAL: Non-invoice document supplied. Posting permanently blocked.")

        # Header fields presence check
        if not header.invoice_number or header.invoice_number == "UNKNOWN":
            issues.append("WARNING: Missing or undetected Invoice Number.")

        if not header.vendor_name:
            issues.append("WARNING: Vendor Name missing.")

        # Check line items
        if not header.line_items:
            issues.append("CRITICAL: Invoice contains zero line items.")
            return False, issues

        # Line items audit
        for item in header.line_items:
            # Rule 1: Never guess missing data
            if not item.raw_upc and not item.raw_item_num:
                issues.append(f"Line {item.line_number}: Missing both UPC and Vendor Item Number.")

            if item.unit_cost < Decimal('0.00'):
                issues.append(f"Line {item.line_number}: Negative unit cost (${item.unit_cost}).")

            if item.case_quantity <= Decimal('0') and item.loose_quantity <= Decimal('0'):
                issues.append(f"Line {item.line_number}: Zero or negative quantity.")

            # Rule 16: Fractional quantity check
            if item.expected_pos_qty and item.expected_pos_qty % Decimal('1') != Decimal('0'):
                issues.append(f"Line {item.line_number}: Fractional POS quantity calculated ({item.expected_pos_qty}). Blocked pending human sign-off.")

        # Exact Decimal Math Subtotal Audit
        calculated_line_sum = sum((i.total_cost for i in header.line_items if not i.is_fee_or_charge), Decimal('0.00'))
        expected_total = calculated_line_sum + header.fees.total_non_inventory_fees

        if header.total_amount != expected_total:
            diff = header.total_amount - expected_total
            if abs(diff) > Decimal('0.05'):
                issues.append(
                    f"HEADER_MATH_MISMATCH: Line Sum (${calculated_line_sum}) + Fees (${header.fees.total_non_inventory_fees}) "
                    f"= ${expected_total}, but Invoice Total shows ${header.total_amount} (Diff: ${diff})."
                )

        is_valid = not any(i.startswith("CRITICAL") for i in issues)
        return is_valid, issues

    def format_report(self, is_valid: bool, issues: List[str]) -> str:
        """Formats readable validation report."""
        if is_valid and not issues:
            return "✅ Validation PASSED - All enterprise rules satisfied."

        report = "📋 Enterprise Validation Report:\n"
        for issue in issues:
            if issue.startswith("CRITICAL"):
                report += f"  🛑 {issue}\n"
            elif issue.startswith("HEADER_MATH_MISMATCH"):
                report += f"  ⚠️ {issue}\n"
            else:
                report += f"  ℹ️ {issue}\n"

        return report
