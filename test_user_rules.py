"""
Verify all 7 package conversion rules specified by the user
"""

from decimal import Decimal
from package_converter import PackageConverter

converter = PackageConverter()

test_cases = [
    ("12-pack (1 case)", "12PK", Decimal('1'), Decimal('2')),
    ("6-pack (1 case)", "6PK", Decimal('1'), Decimal('4')),
    ("4-pack (1 case)", "4PK", Decimal('1'), Decimal('6')),
    ("Single 24oz can case (1 case)", "C12 24OZ", Decimal('1'), Decimal('12')),
    ("24-pack (1 case)", "24PK", Decimal('1'), Decimal('1')),
    ("18-pack (1 case)", "18PK", Decimal('1'), Decimal('1')),
    ("8-pack (1 case)", "8PK", Decimal('1'), Decimal('3')),
]

print("=========================================================")
print(" VERIFYING USER PACKAGE CONVERSION RULES")
print("=========================================================")

all_passed = True
for name, pkg_text, case_qty, expected_pos_qty in test_cases:
    calc_qty, rule, req_rev, reason = converter.calculate_expected_pos_qty(
        case_qty=case_qty,
        loose_qty=Decimal('0'),
        store_id="STORE-1001",
        vendor_id="VEND-TEST",
        vendor_item_num="TEST01",
        package_text=pkg_text
    )
    status = "PASSED" if calc_qty == expected_pos_qty else "FAILED"
    if status == "FAILED":
        all_passed = False
    print(f"Rule: {name:30s} | Text: {pkg_text:10s} | Case Qty: {case_qty} -> POS Qty: {calc_qty} (Expected: {expected_pos_qty}) [{status}]")

print("=========================================================")
if all_passed:
    print(" ALL 7 USER CONVERSION RULES VERIFIED & PASSED 100%!")
else:
    print(" SOME CONVERSION RULES FAILED!")
print("=========================================================")
