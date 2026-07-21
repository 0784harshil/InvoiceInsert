"""
Package Conversion Engine
Implements exact Decimal math for package conversion formula and rules.

Formula:
Expected POS Quantity =
    Case Quantity * (Case Numerator / Case Denominator)
  + Loose Quantity * (Loose Numerator / Loose Denominator)
"""

from decimal import Decimal, InvalidOperation
from typing import Tuple, Optional, Dict
import re
from models import ConversionRule


class PackageConverter:
    """
    Package Converter enforcing vendor/product/version scoped conversion rules.
    Uses exact Decimal arithmetic.
    """

    def __init__(self):
        # Scoped conversion rules database: (store_id, vendor_id, vendor_item_num, package_text) -> ConversionRule
        self._rule_store: Dict[Tuple[str, str, str, str], ConversionRule] = {}

    def register_rule(self, rule: ConversionRule) -> None:
        """Register a scoped, versioned conversion rule."""
        key = (rule.store_id, rule.vendor_id, rule.vendor_item_num, rule.package_text.upper())
        self._rule_store[key] = rule

    def get_scoped_rule(
        self,
        store_id: str,
        vendor_id: str,
        vendor_item_num: str,
        package_text: str
    ) -> Optional[ConversionRule]:
        """Look up scoped conversion rule."""
        key = (store_id.strip(), vendor_id.strip(), vendor_item_num.strip(), package_text.strip().upper())
        return self._rule_store.get(key)

    def calculate_expected_pos_qty(
        self,
        case_qty: Decimal,
        loose_qty: Decimal,
        store_id: str,
        vendor_id: str,
        vendor_item_num: str,
        package_text: str
    ) -> Tuple[Decimal, Optional[ConversionRule], bool, str]:
        """
        Calculates Expected POS Quantity using exact Decimal math.
        
        Returns:
            Tuple of (expected_pos_qty, rule_used, requires_human_review, reason_message)
        """
        raw_package_text = str(package_text).strip()
        
        # Look for custom scoped rule first
        rule = self.get_scoped_rule(store_id, vendor_id, vendor_item_num, raw_package_text)
        
        # If no scoped rule, detect standard pack patterns
        if not rule:
            case_num, case_den, is_one_zero = self.detect_standard_pack_pattern(raw_package_text)
            rule = ConversionRule(
                store_id=store_id,
                vendor_id=vendor_id,
                vendor_item_num=vendor_item_num,
                package_text=raw_package_text,
                version=1,
                case_numerator=case_num,
                case_denominator=case_den,
                loose_numerator=Decimal('1'),
                loose_denominator=Decimal('1'),
                is_one_slash_zero_notation=is_one_zero
            )

        # Denominator zero check
        if rule.case_denominator == Decimal('0') or rule.loose_denominator == Decimal('0'):
            return Decimal('0'), rule, True, "BLOCKED: Division by zero denominator in package conversion rule."

        # Special "1/0" notation handling: 1 case and 0 loose units
        if rule.is_one_slash_zero_notation:
            calc_case_qty = Decimal('1') if case_qty > Decimal('0') else Decimal('0')
            calc_loose_qty = Decimal('0')
        else:
            calc_case_qty = case_qty
            calc_loose_qty = loose_qty

        # Formula:
        # Expected POS Quantity = Case Qty * (Case Num / Case Denom) + Loose Qty * (Loose Num / Loose Denom)
        try:
            case_part = calc_case_qty * (rule.case_numerator / rule.case_denominator)
            loose_part = calc_loose_qty * (rule.loose_numerator / rule.loose_denominator)
            expected_pos_qty = case_part + loose_part
        except (InvalidOperation, ZeroDivisionError) as e:
            return Decimal('0'), rule, True, f"BLOCKED: Math exception during package conversion: {e}"

        # Check for fractional result (no silent rounding!)
        requires_review = False
        reason = "OK"
        
        if expected_pos_qty % Decimal('1') != Decimal('0'):
            requires_review = True
            reason = f"NEEDS_REVIEW: Fractional POS Quantity calculated ({expected_pos_qty}). Requires human sign-off."

        return expected_pos_qty, rule, requires_review, reason

    def detect_standard_pack_pattern(self, package_text: str) -> Tuple[Decimal, Decimal, bool]:
        """
        Detects standard pack patterns using regex word boundaries.
        Returns: (case_numerator, case_denominator, is_1_0_notation)
        """
        txt = package_text.upper()

        if '1/0' in txt:
            return Decimal('1'), Decimal('1'), True

        # Check 24-pack / 18-pack first
        if re.search(r'\b(24P|24-PACK|24PK)\b', txt):
            return Decimal('1'), Decimal('1'), False
        elif re.search(r'\b(18P|18-PACK|18PK|C18)\b', txt):
            return Decimal('1'), Decimal('1'), False
        elif re.search(r'\b(12P|12-PACK|12PK)\b', txt):
            return Decimal('2'), Decimal('1'), False
        elif re.search(r'\b(8P|8-PACK|8PK)\b', txt):
            return Decimal('3'), Decimal('1'), False
        elif re.search(r'\b(6P|6-PACK|6PK)\b', txt):
            return Decimal('4'), Decimal('1'), False
        elif re.search(r'\b(4P|4-PACK|4PK)\b', txt):
            return Decimal('6'), Decimal('1'), False
        elif '24OZ' in txt and ('C12' in txt or 'B12' in txt or 'C12 24OZ' in txt):
            return Decimal('12'), Decimal('1'), False
        elif 'C24' in txt or 'B24' in txt:
            return Decimal('1'), Decimal('1'), False

        return Decimal('1'), Decimal('1'), False
