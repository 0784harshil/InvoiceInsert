"""
UPC Normalizer Engine
Handles automatic conversion and variant generation for 11-digit, 12-digit, and 13-digit UPCs.
Ensures seamless barcode matching and AltSKU generation for CRE POS scanners.
"""

import re
from typing import List, Set, Dict


class UPCNormalizer:
    """
    UPC Normalizer that generates all valid representation variants (EAN-13, UPC-A, GTIN-11)
    and formats barcodes for CRE POS dual-field storage (ItemNum + AltSKU + Helper_ItemNum).
    """

    @staticmethod
    def clean_upc(upc_str: str) -> str:
        """Strips whitespace, hyphens, and non-numeric characters."""
        if not upc_str:
            return ""
        return re.sub(r'\D', '', str(upc_str).strip())

    @classmethod
    def generate_variants(cls, raw_upc: str) -> Set[str]:
        """
        Generates all valid normalized UPC string variants.
        e.g., '0071990000486' -> {'0071990000486', '071990000486', '71990000486'}
        """
        cleaned = cls.clean_upc(raw_upc)
        if not cleaned:
            return set()

        variants = {cleaned}
        
        # 13-digit EAN-13 with double zero -> 12-digit UPC-A & 11-digit
        if len(cleaned) == 13 and cleaned.startswith('00'):
            variants.add(cleaned[1:])   # 12-digit (071990000486)
            variants.add(cleaned[2:])   # 11-digit (71990000486)
        elif len(cleaned) == 13 and cleaned.startswith('0'):
            variants.add(cleaned[1:])   # 12-digit
        elif len(cleaned) == 12 and cleaned.startswith('0'):
            variants.add(cleaned[1:])   # 11-digit
            variants.add('0' + cleaned) # 13-digit EAN-13
        elif len(cleaned) == 11:
            variants.add('0' + cleaned)  # 12-digit
            variants.add('00' + cleaned) # 13-digit EAN-13

        return {v for v in variants if len(v) >= 6}

    @classmethod
    def determine_primary_and_alts(cls, raw_upc: str, vendor_item_num: str = "") -> Dict[str, str]:
        """
        Determines Primary ItemNum (12-digit UPC-A preferred for CRE POS) and AltSKU list.
        """
        cleaned = cls.clean_upc(raw_upc)
        variants = list(cls.generate_variants(cleaned))

        # Standard CRE POS Primary ItemNum is 12-digit UPC-A (convert 00 prefix 13-digit to 12-digit)
        if len(cleaned) == 13 and cleaned.startswith('00'):
            primary = cleaned[1:]  # 12-digit (072890003102)
        elif len(cleaned) == 11:
            primary = '0' + cleaned # 12-digit (072890003102)
        else:
            primary = cleaned or vendor_item_num or "UNKNOWN"

        alts = [v for v in variants if v != primary]
        if vendor_item_num and vendor_item_num not in alts and vendor_item_num != primary:
            alts.append(vendor_item_num)

        return {
            "primary_item_num": primary,
            "alt_skus": alts,
            "helper_item_num": cleaned if (cleaned != primary) else (alts[0] if alts else primary)
        }
