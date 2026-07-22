"""
Enterprise Domain Data Models for Invoice Parsing, Validation, and POS Insertion
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, auto
from typing import List, Optional, Dict, Any


class DocumentType(Enum):
    STANDARD_INVOICE = auto()
    NON_INVOICE_BLOCKED = auto()
    UNKNOWN = auto()


class ReviewState(Enum):
    AUTOMATIC_PASS = auto()
    REVIEW_REQUIRED = auto()
    REVIEWED_APPROVED = auto()
    POSTING_BLOCKED = auto()


class ConversionRule(Enum):
    RULE_12PK_TO_2 = "12PK_TO_2"
    RULE_6PK_TO_4 = "6PK_TO_4"
    RULE_4PK_TO_6 = "4PK_TO_6"
    RULE_SINGLE_24OZ_TO_12 = "SINGLE_24OZ_TO_12"
    RULE_24PK_TO_1 = "24PK_TO_1"
    RULE_18PK_TO_1 = "18PK_TO_1"
    RULE_8PK_TO_3 = "8PK_TO_3"
    DEFAULT_1_TO_1 = "1_TO_1"


@dataclass
class InvoiceFees:
    """Non-inventory fee segregation model (Rules 8 & 11)."""
    tax: Decimal = Decimal('0.00')
    deposit_crv: Decimal = Decimal('0.00')
    freight_delivery: Decimal = Decimal('0.00')
    fuel_charge: Decimal = Decimal('0.00')
    service_fee: Decimal = Decimal('0.00')
    discounts: Decimal = Decimal('0.00')

    @property
    def total_non_inventory_fees(self) -> Decimal:
        return (
            self.tax + self.deposit_crv + self.freight_delivery +
            self.fuel_charge + self.service_fee - self.discounts
        )


# Backward-compatible alias for InvoiceFees
SegregatedFees = InvoiceFees


@dataclass
class InvoiceLineItem:
    """Represents a single parsed line item with case vs single POS unit cost calculation."""
    line_number: int
    raw_item_num: str
    raw_description: str
    raw_upc: Optional[str] = None
    raw_package_text: str = "EA"
    
    case_quantity: Decimal = Decimal('1.00')
    loose_quantity: Decimal = Decimal('0.00')
    unit_cost: Decimal = Decimal('0.00') # Case unit cost from invoice
    total_cost: Decimal = Decimal('0.00')
    
    expected_pos_qty: Optional[Decimal] = None
    approved_actual_good_qty: Optional[Decimal] = None
    
    pos_unit_cost: Optional[Decimal] = None # Calculated Single POS Unit Cost
    conversion_rule_used: str = "DEFAULT_1_TO_1"
    review_state: ReviewState = ReviewState.AUTOMATIC_PASS
    review_reasons: List[str] = field(default_factory=list)

    def calculate_single_pos_unit_cost(self) -> Decimal:
        """Calculates single POS unit cost = Total Line Item Cost / Approved POS Qty."""
        qty = self.approved_actual_good_qty or self.expected_pos_qty or self.case_quantity
        if qty and qty > Decimal('0'):
            calc = (self.total_cost / qty).quantize(Decimal('0.0001'))
            self.pos_unit_cost = calc
            return calc
        self.pos_unit_cost = self.unit_cost
        return self.unit_cost


@dataclass
class InvoiceHeader:
    """Represents the complete parsed invoice header and document state."""
    installation_id: str = "INST-DEFAULT"
    store_id: str = "1001"
    vendor_name: str = "UNKNOWN"
    vendor_id: str = "VEND-DEFAULT"
    invoice_number: str = "INV-0000"
    invoice_date: str = ""
    
    subtotal: Decimal = Decimal('0.00')
    total_amount: Decimal = Decimal('0.00')
    fees: InvoiceFees = field(default_factory=InvoiceFees)
    line_items: List[InvoiceLineItem] = field(default_factory=list)
    
    document_type: DocumentType = DocumentType.STANDARD_INVOICE
    document_valid: bool = True
    blocking_reasons: List[str] = field(default_factory=list)
    
    shadow_mode: bool = True
    posting_enabled: bool = False
