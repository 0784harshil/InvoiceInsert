"""
Human Review & Approval Workflow Engine
Enforces Rules 9, 10, 14, 15, 16:
- Machine output always requires human review
- Only reviewed actual-good quantity may eventually increase inventory
- posting_enabled defaults to false
- shadow_mode defaults to true
- Any ambiguity, conflict, fractional quantity, unknown row, or schema drift blocks posting
"""

from decimal import Decimal
from typing import List, Tuple, Dict, Any, Optional
from models import InvoiceHeader, InvoiceLineItem, ReviewState


class ReviewManager:
    """
    Manages the review state machine for invoices and line items.
    """

    def audit_and_prepare_invoice(self, header: InvoiceHeader) -> InvoiceHeader:
        """
        Runs comprehensive rule verification on invoice header and line items.
        Flags issues and assigns ReviewStates.
        """
        header.blocking_reasons.clear()

        # Rule 14 & 15 Enforcements
        header.posting_enabled = False
        header.shadow_mode = True

        # Rule 16: Check for Document Validity
        if not header.document_valid:
            header.blocking_reasons.append("DOCUMENT_BLOCKED: Document failed validation checks (e.g. Non-invoice file).")
            for item in header.line_items:
                item.review_state = ReviewState.POSTING_BLOCKED

        # Validate line items
        unreviewed_count = 0
        blocked_count = 0
        needs_review_count = 0

        for item in header.line_items:
            self._audit_line_item(item)

            if item.review_state == ReviewState.POSTING_BLOCKED:
                blocked_count += 1
            elif item.review_state == ReviewState.NEEDS_HUMAN_REVIEW:
                needs_review_count += 1
            elif item.review_state == ReviewState.UNREVIEWED:
                unreviewed_count += 1

        # Header-level math audit
        self._audit_header_totals(header)

        if unreviewed_count > 0 or needs_review_count > 0:
            header.blocking_reasons.append(
                f"REVIEW_PENDING: {unreviewed_count + needs_review_count} item(s) require human review & approval."
            )

        return header

    def approve_line_item(
        self,
        item: InvoiceLineItem,
        actual_good_qty: Decimal,
        reviewer_id: str = "human_operator"
    ) -> Tuple[bool, str]:
        """
        Explicitly approves actual-good quantity for a line item (Rule 10).
        """
        if item.review_state == ReviewState.POSTING_BLOCKED:
            return False, f"Cannot approve Line {item.line_number}: Item is in POSTING_BLOCKED state."

        if actual_good_qty < Decimal('0'):
            return False, f"Cannot approve Line {item.line_number}: Actual-good quantity cannot be negative."

        item.approved_actual_good_qty = actual_good_qty
        item.review_state = ReviewState.REVIEWED_APPROVED
        item.review_reasons.append(f"APPROVED: {actual_good_qty} units approved by {reviewer_id}.")
        return True, "Item approved successfully."

    def _audit_line_item(self, item: InvoiceLineItem):
        """Audits individual line item against Rule 1, Rule 2, Rule 16."""
        # Rule 1: Never guess missing data
        if not item.raw_upc and not item.raw_item_num:
            item.review_state = ReviewState.NEEDS_HUMAN_REVIEW
            item.review_reasons.append("MISSING_IDENTITY: Item missing both UPC and Vendor Item Number. Requires manual mapping.")

        if item.unit_cost <= Decimal('0.00'):
            item.review_state = ReviewState.NEEDS_HUMAN_REVIEW
            item.review_reasons.append("ZERO_COST: Unit cost is $0.00 or negative. Requires human verification.")

        if item.expected_pos_qty is None:
            item.review_state = ReviewState.POSTING_BLOCKED
            item.review_reasons.append("MISSING_CONVERSION: POS quantity could not be calculated.")

        # Rule 16: Check for fractional quantities
        if item.expected_pos_qty and item.expected_pos_qty % Decimal('1') != Decimal('0'):
            item.review_state = ReviewState.NEEDS_HUMAN_REVIEW
            item.review_reasons.append(f"FRACTIONAL_QTY: Fractional calculated POS quantity ({item.expected_pos_qty}). Requires human sign-off.")

    def _audit_header_totals(self, header: InvoiceHeader):
        """Cross-checks line totals + segregated fees against grand total."""
        calculated_line_sum = sum((i.total_cost for i in header.line_items if not i.is_fee_or_charge), Decimal('0.00'))
        expected_grand_total = calculated_line_sum + header.fees.total_non_inventory_fees

        if header.total_amount != expected_grand_total:
            diff = header.total_amount - expected_grand_total
            if abs(diff) > Decimal('0.05'):
                header.blocking_reasons.append(
                    f"HEADER_MISMATCH: Subtotal sum (${calculated_line_sum}) + Fees (${header.fees.total_non_inventory_fees}) "
                    f"= ${expected_grand_total}, but Invoice Total shows ${header.total_amount} (Diff: ${diff})."
                )
