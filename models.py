"""
Enterprise Receiving Engine - Domain Data Models
Enforces exact Decimal math, raw string preservation, and composite identity keys.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class ReviewState(Enum):
    UNREVIEWED = "UNREVIEWED"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    REVIEWED_APPROVED = "REVIEWED_APPROVED"
    POSTING_BLOCKED = "POSTING_BLOCKED"


@dataclass(frozen=True)
class ProductKey:
    """Product Identity: Store_ID + ItemNum"""
    store_id: str
    item_num: str

    def __post_init__(self):
        # Preserve raw leading zeros
        object.__setattr__(self, 'store_id', str(self.store_id).strip())
        object.__setattr__(self, 'item_num', str(self.item_num).strip())

    @property
    def key_string(self) -> str:
        return f"{self.store_id}::{self.item_num}"


@dataclass(frozen=True)
class MappingKey:
    """Mapping Identity: Installation + Store + Vendor + Vendor Item Number"""
    installation_id: str
    store_id: str
    vendor_id: str
    vendor_item_num: str

    def __post_init__(self):
        object.__setattr__(self, 'installation_id', str(self.installation_id).strip())
        object.__setattr__(self, 'store_id', str(self.store_id).strip())
        object.__setattr__(self, 'vendor_id', str(self.vendor_id).strip())
        object.__setattr__(self, 'vendor_item_num', str(self.vendor_item_num).strip())

    @property
    def key_string(self) -> str:
        return f"{self.installation_id}::{self.store_id}::{self.vendor_id}::{self.vendor_item_num}"


@dataclass(frozen=True)
class ConversionRule:
    """
    Package conversions are vendor/product/version scoped, never global.
    Active templates and mappings are immutable.
    """
    store_id: str
    vendor_id: str
    vendor_item_num: str
    package_text: str
    version: int
    case_numerator: Decimal
    case_denominator: Decimal
    loose_numerator: Decimal = Decimal('0')
    loose_denominator: Decimal = Decimal('1')
    is_one_slash_zero_notation: bool = False

    def __post_init__(self):
        if self.case_denominator == Decimal('0'):
            raise ValueError("Case conversion denominator cannot be zero.")
        if self.loose_denominator == Decimal('0'):
            raise ValueError("Loose conversion denominator cannot be zero.")


@dataclass
class InvoiceLineItem:
    """Line item representation preserving raw values and Decimal math."""
    line_number: int
    raw_item_num: str
    raw_description: str
    raw_upc: Optional[str]
    raw_package_text: str
    
    # Quantities & Costs as Decimal
    case_quantity: Decimal
    loose_quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    
    # Fee Segregation Flags
    is_fee_or_charge: bool = False
    fee_type: Optional[str] = None  # TAX, DEPOSIT, FREIGHT, FUEL, SERVICE, DISCOUNT
    
    # Package Conversion Results
    expected_pos_qty: Optional[Decimal] = None
    conversion_rule_used: Optional[ConversionRule] = None
    
    # State tracking
    review_state: ReviewState = ReviewState.UNREVIEWED
    review_reasons: List[str] = field(default_factory=list)
    approved_actual_good_qty: Optional[Decimal] = None


@dataclass
class SegregatedFees:
    """Tax, deposit, delivery, fuel, service fees, and payments."""
    tax: Decimal = Decimal('0.00')
    deposit_crv: Decimal = Decimal('0.00')
    freight_delivery: Decimal = Decimal('0.00')
    fuel_charge: Decimal = Decimal('0.00')
    service_charge: Decimal = Decimal('0.00')
    discounts: Decimal = Decimal('0.00')
    payments: Decimal = Decimal('0.00')

    @property
    def total_non_inventory_fees(self) -> Decimal:
        return (self.tax + self.deposit_crv + self.freight_delivery + 
                self.fuel_charge + self.service_charge - self.discounts)


@dataclass
class InvoiceHeader:
    """Header level invoice data with strict Decimal subtotals and fees."""
    installation_id: str
    store_id: str
    vendor_name: str
    vendor_id: str
    invoice_number: str
    invoice_date: str
    
    subtotal: Decimal
    total_amount: Decimal
    fees: SegregatedFees = field(default_factory=SegregatedFees)
    
    line_items: List[InvoiceLineItem] = field(default_factory=list)
    
    # Audit & Status
    shadow_mode: bool = True
    posting_enabled: bool = False
    document_valid: bool = True
    blocking_reasons: List[str] = field(default_factory=list)
