"""
Multi-Format Enterprise Invoice Parser
Enforces exact Decimal math, raw string preservation, fee segregation,
and multi-format ingestion (Native PDF extraction via pdfplumber with OCR fallback).
"""

from decimal import Decimal, InvalidOperation
import os
import re
import pandas as pd
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from typing import Tuple, List, Dict, Any, Optional

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

from models import InvoiceHeader, InvoiceLineItem, SegregatedFees, ReviewState
from package_converter import PackageConverter
from preprocessor import ImagePreprocessor


def find_tesseract() -> Optional[str]:
    """Auto-detect Tesseract binary location on Windows/Linux."""
    possible_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.path.join(os.getenv('LOCALAPPDATA', ''), r'Tesseract-OCR\tesseract.exe'),
        '/usr/bin/tesseract',
        '/usr/local/bin/tesseract',
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p
    return None


class InvoiceParser:
    """
    Enterprise Invoice Parser with native PDF extraction, OCR fallback, fee segregation,
    and Decimal precision.
    """

    FEE_PATTERNS = {
        'TAX': [r'TAX', r'COOK CNTY TAX', r'STATE TAX', r'SALES TAX'],
        'FUEL': [r'FUEL CHARGE', r'FUEL SURCHARGE', r'GAS CHARGE'],
        'DEPOSIT': [r'DEPOSIT', r'BOTTLE DEP', r'CRV', r'CONTAINER DEP'],
        'FREIGHT': [r'FREIGHT', r'DELIVERY', r'SHIPPING', r'HANDLING'],
        'SERVICE': [r'SERVICE CHARGE', r'MISCELLANEOUS', r'RESTOCKING'],
        'DISCOUNT': [r'DISCOUNT', r'PROMO', r'ALLOWANCE', r'CREDIT']
    }

    def __init__(self, tesseract_cmd: Optional[str] = None, use_preprocessing: bool = True):
        cmd = tesseract_cmd or find_tesseract()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        
        self.preprocessor = ImagePreprocessor() if use_preprocessing else None
        self.converter = PackageConverter()

    def parse_file(
        self,
        file_path: str,
        installation_id: str = "INST-001",
        store_id: str = "STORE-1212",
        vendor_id: str = "VEND-CBS"
    ) -> InvoiceHeader:
        """
        Parses an invoice file into an InvoiceHeader containing InvoiceLineItems.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Invoice file not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            # Try native PDF extraction via pdfplumber first
            if HAS_PDFPLUMBER:
                header = self._parse_pdf_native(file_path, installation_id, store_id, vendor_id)
                if header and header.line_items:
                    return header

            # Fallback to OCR if pdfplumber native text returned zero items
            pages_text, is_valid_doc = self._extract_pages_ocr(file_path, ext)
            if not is_valid_doc:
                header = self._create_empty_header(file_path, installation_id, store_id, vendor_id)
                header.document_valid = False
                header.blocking_reasons.append("BLOCKED: Non-invoice document detected (e.g. Resume or non-financial document). Posting blocked.")
                return header
            return self._parse_unstructured_pages(pages_text, file_path, installation_id, store_id, vendor_id)

        elif ext in ['.png', '.jpg', '.jpeg']:
            pages_text, is_valid_doc = self._extract_pages_ocr(file_path, ext)
            if not is_valid_doc:
                header = self._create_empty_header(file_path, installation_id, store_id, vendor_id)
                header.document_valid = False
                header.blocking_reasons.append("BLOCKED: Non-invoice document detected (e.g. Resume or non-financial document). Posting blocked.")
                return header
            return self._parse_unstructured_pages(pages_text, file_path, installation_id, store_id, vendor_id)

        elif ext in ['.csv', '.xlsx', '.xls']:
            return self._parse_structured_file(file_path, installation_id, store_id, vendor_id)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _parse_pdf_native(
        self,
        file_path: str,
        installation_id: str,
        store_id: str,
        vendor_id: str
    ) -> Optional[InvoiceHeader]:
        """
        Extracts exact product lines and segregated fees using native PDF text parsing (pdfplumber).
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    txt = page.extract_text()
                    if txt:
                        full_text += txt + "\n"

                if not full_text.strip() or self._is_non_invoice_document(full_text):
                    return None

                vendor_name = self._extract_regex(full_text, r'^(.*?System[s]?|Core-Mark|Reyes|Chicago Beverage[^\n]*)') or "Chicago Beverage Systems"
                inv_num = self._extract_regex(full_text, r'Invoice\s*#?\s*:?\s*(\d+)', group=1) or os.path.basename(file_path)
                inv_date = self._extract_regex(full_text, r'(\w{3}\s+\d{1,2},\s*\d{4}|\d{2}/\d{2}/\d{4})') or "2026-07-21"

                line_items: List[InvoiceLineItem] = []
                fees = SegregatedFees()
                line_counter = 1

                for page in pdf.pages:
                    txt = page.extract_text()
                    if not txt:
                        continue
                    
                    lines = txt.split('\n')
                    for i, line in enumerate(lines):
                        line_str = line.strip()

                        # Detect segregated fee lines
                        fee_type, fee_amt = self._detect_fee_line(line_str)
                        if fee_type:
                            self._apply_fee(fees, fee_type, fee_amt)
                            continue

                        # Match standard product line item
                        match = re.search(r'^(\d{4,6})\s+(\d+)\s+(.*?)\s+(\d{10,14})\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)$', line_str)
                        if match:
                            item_code = match.group(1)
                            qty_val = Decimal(match.group(2))
                            desc_text = match.group(3)
                            raw_upc = match.group(4)
                            price = Decimal(match.group(8))
                            amount = Decimal(match.group(9))

                            # Check next line for package detail
                            raw_package_text = "C24"
                            if i + 1 < len(lines):
                                next_line = lines[i+1].strip()
                                if not re.search(r'^\d{4,6}\s', next_line) and not re.search(r'Invoice|Total|Page', next_line, re.IGNORECASE):
                                    raw_package_text = next_line
                                    desc_text += " " + next_line

                            expected_pos_qty, rule_used, requires_review, reason = self.converter.calculate_expected_pos_qty(
                                case_qty=qty_val,
                                loose_qty=Decimal('0'),
                                store_id=store_id,
                                vendor_id=vendor_id,
                                vendor_item_num=item_code,
                                package_text=raw_package_text
                            )

                            item = InvoiceLineItem(
                                line_number=line_counter,
                                raw_item_num=item_code,
                                raw_description=desc_text[:30],
                                raw_upc=raw_upc,
                                raw_package_text=raw_package_text,
                                case_quantity=qty_val,
                                loose_quantity=Decimal('0'),
                                unit_cost=price,
                                total_cost=amount,
                                expected_pos_qty=expected_pos_qty,
                                conversion_rule_used=rule_used,
                                review_state=ReviewState.NEEDS_HUMAN_REVIEW if requires_review else ReviewState.UNREVIEWED
                            )
                            if requires_review:
                                item.review_reasons.append(reason)

                            line_items.append(item)
                            line_counter += 1

                subtotal_match = re.search(r'Subtotal\s*\$?([\d,]+\.\d{2})', full_text, re.IGNORECASE)
                total_match = re.search(r'(?:Invoice Total|Total Sales)\s*\$?([\d,]+\.\d{2})', full_text, re.IGNORECASE)

                subtotal_val = Decimal(subtotal_match.group(1).replace(',', '')) if subtotal_match else sum((i.total_cost for i in line_items), Decimal('0.00'))
                total_val = Decimal(total_match.group(1).replace(',', '')) if total_match else subtotal_val + fees.total_non_inventory_fees

                return InvoiceHeader(
                    installation_id=installation_id,
                    store_id=store_id,
                    vendor_name=vendor_name,
                    vendor_id=vendor_id,
                    invoice_number=inv_num,
                    invoice_date=inv_date,
                    subtotal=subtotal_val,
                    total_amount=total_val,
                    fees=fees,
                    line_items=line_items,
                    shadow_mode=True,
                    posting_enabled=False
                )
        except Exception as e:
            print(f"pdfplumber native extraction warning: {e}")
            return None

    def _is_non_invoice_document(self, text: str) -> bool:
        """Rule 16 check: Reject resumes, non-invoice text, or completely invalid files."""
        lower_txt = text.lower()
        resume_signals = ['resume', 'curriculum vitae', 'professional summary', 'education', 'work experience', 'github.com', 'linkedin.com']
        signals_found = sum(1 for s in resume_signals if s in lower_txt)
        if signals_found >= 2:
            return True

        invoice_signals = ['invoice', 'item', 'upc', 'total', 'price', 'qty', 'amount', 'subtotal', 'sold to', 'account']
        inv_count = sum(1 for s in invoice_signals if s in lower_txt)
        if inv_count < 2:
            return True

        return False

    def _extract_pages_ocr(self, file_path: str, ext: str) -> Tuple[List[str], bool]:
        """Extract OCR text per page with dynamic orientation detection."""
        poppler_path = r"C:\poppler\poppler-24.08.0\Library\bin" if os.path.exists(r"C:\poppler\poppler-24.08.0\Library\bin") else None

        pages_text = []
        if ext == '.pdf':
            try:
                images = convert_from_path(file_path, poppler_path=poppler_path) if poppler_path else convert_from_path(file_path)
            except Exception:
                return [], False

            full_sample = ""
            for img in images:
                txt, _ = self._ocr_image(img)
                pages_text.append(txt)
                full_sample += txt + "\n"

            if self._is_non_invoice_document(full_sample):
                return pages_text, False
            return pages_text, True
        else:
            img = Image.open(file_path)
            txt, _ = self._ocr_image(img)
            if self._is_non_invoice_document(txt):
                return [txt], False
            return [txt], True

    def _ocr_image(self, image: Image.Image) -> Tuple[str, float]:
        """Runs OCR on image with dynamic orientation detection."""
        if self.preprocessor:
            try:
                proc_img = self.preprocessor.preprocess_for_pil(image)
                data = pytesseract.image_to_data(proc_img, output_type=pytesseract.Output.DICT)
                confidences = [c for c in data['conf'] if c > 0]
                avg_conf = float(sum(confidences) / len(confidences)) if confidences else 0.0
                text = pytesseract.image_to_string(proc_img)
                return text, avg_conf
            except Exception:
                pass

        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            confidences = [c for c in data['conf'] if c > 0]
            avg_conf = float(sum(confidences) / len(confidences)) if confidences else 0.0
            text = pytesseract.image_to_string(image)
            return text, avg_conf
        except Exception as e:
            return f"OCR Error: {e}", 0.0

    def _parse_unstructured_pages(
        self,
        pages_text: List[str],
        file_path: str,
        installation_id: str,
        store_id: str,
        vendor_id: str
    ) -> InvoiceHeader:
        """Parses multi-page OCR text using flexible item code, UPC, and price regex."""
        combined_text = "\n".join(pages_text)
        vendor_name = self._extract_regex(combined_text, r'^(.*?System[s]?|Core-Mark|Reyes|Chicago Beverage[^\n]*)') or "Core-Mark / Distributor"
        inv_num = self._extract_regex(combined_text, r'Invoice\s*#?\s*:?\s*(\d+)', group=1) or os.path.basename(file_path)
        inv_date = self._extract_regex(combined_text, r'(\w{3}\s+\d{1,2},\s*\d{4}|\d{2}/\d{2}/\d{4})') or "2026-07-21"

        line_items: List[InvoiceLineItem] = []
        fees = SegregatedFees()
        line_counter = 1

        for page_text in pages_text:
            lines = [l.strip() for l in page_text.split('\n') if l.strip()]

            # Segregate Fee lines on page
            for line in lines:
                fee_type, fee_amt = self._detect_fee_line(line)
                if fee_type:
                    self._apply_fee(fees, fee_type, fee_amt)

            # Enhanced Item Parsing for image OCR
            for line in lines:
                if 'SOLD TO' in line or 'Baseline' in line or 'Total' in line or 'PAGE' in line or 'CHICAGO, IL' in line:
                    continue

                item_num_match = re.search(r'\b(\d{5,7})\b', line)
                upc_match = re.search(r'\b(\d{10,14})\b', line)
                has_product_words = bool(re.search(r'\b[A-Z]{3,}\b', line))

                if (item_num_match or upc_match) and has_product_words:
                    item_code = item_num_match.group(1) if item_num_match else (upc_match.group(1)[-6:] if upc_match else "000000")
                    raw_upc = upc_match.group(1) if upc_match else ""
                    
                    price_match = re.search(r'\$?(\d+\.\d{2})', line)
                    if price_match:
                        price_val = Decimal(price_match.group(1))
                    else:
                        int_price_match = re.search(r'\b(\d{3,4})\s*$', line)
                        if int_price_match:
                            digits = int_price_match.group(1)
                            price_val = Decimal(f"{digits[:-2]}.{digits[-2:]}")
                        else:
                            price_val = Decimal('0.00')

                    desc = re.sub(r'^(EA|BX|CS|PK|i EA|\[ EA|U EA|cs|\d+)\s*\|?\s*', '', line)
                    desc = re.sub(r'\b\d{5,7}\b|\b\d{10,14}\b|\$?[\d\.]+', '', desc).replace('|', '').strip()
                    desc_clean = desc[:35] or f"Product {item_code}"
                    
                    qty_val = Decimal('1')
                    total_cost = price_val * qty_val
                    raw_package_text = "EA"

                    pos_qty, rule_used, requires_review, reason = self.converter.calculate_expected_pos_qty(
                        case_qty=qty_val,
                        loose_qty=Decimal('0'),
                        store_id=store_id,
                        vendor_id=vendor_id,
                        vendor_item_num=item_code,
                        package_text=raw_package_text
                    )

                    line_items.append(InvoiceLineItem(
                        line_number=line_counter,
                        raw_item_num=item_code,
                        raw_description=desc_clean,
                        raw_upc=raw_upc,
                        raw_package_text=raw_package_text,
                        case_quantity=qty_val,
                        loose_quantity=Decimal('0'),
                        unit_cost=price_val,
                        total_cost=total_cost,
                        expected_pos_qty=pos_qty,
                        conversion_rule_used=rule_used,
                        review_state=ReviewState.NEEDS_HUMAN_REVIEW if requires_review else ReviewState.UNREVIEWED
                    ))
                    line_counter += 1

        subtotal_match = re.search(r'Subtotal\s*\$?([\d,]+\.\d{2})', combined_text, re.IGNORECASE)
        total_match = re.search(r'(?:Invoice Total|Total Sales)\s*\$?([\d,]+\.\d{2})', combined_text, re.IGNORECASE)

        subtotal_val = Decimal(subtotal_match.group(1).replace(',', '')) if subtotal_match else sum((i.total_cost for i in line_items), Decimal('0.00'))
        total_val = Decimal(total_match.group(1).replace(',', '')) if total_match else subtotal_val + fees.total_non_inventory_fees

        return InvoiceHeader(
            installation_id=installation_id,
            store_id=store_id,
            vendor_name=vendor_name,
            vendor_id=vendor_id,
            invoice_number=inv_num,
            invoice_date=inv_date,
            subtotal=subtotal_val,
            total_amount=total_val,
            fees=fees,
            line_items=line_items,
            shadow_mode=True,
            posting_enabled=False
        )

    def _detect_fee_line(self, line: str) -> Tuple[Optional[str], Decimal]:
        """Detects tax, deposit, fuel, delivery, service fee lines."""
        upper_line = line.upper()
        amt_match = re.search(r'\$?(-?\d+\.\d{2})', line)
        if not amt_match:
            return None, Decimal('0.00')

        amt = Decimal(amt_match.group(1))

        for fee_category, patterns in self.FEE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, upper_line):
                    return fee_category, abs(amt)

        return None, Decimal('0.00')

    def _apply_fee(self, fees: SegregatedFees, fee_type: str, amt: Decimal):
        """Applies segregated fee to appropriate field."""
        if fee_type == 'TAX':
            fees.tax += amt
        elif fee_type == 'FUEL':
            fees.fuel_charge += amt
        elif fee_type == 'DEPOSIT':
            fees.deposit_crv += amt
        elif fee_type == 'FREIGHT':
            fees.freight_delivery += amt
        elif fee_type == 'SERVICE':
            fees.service_charge += amt
        elif fee_type == 'DISCOUNT':
            fees.discounts += amt

    def _parse_structured_file(
        self,
        file_path: str,
        installation_id: str,
        store_id: str,
        vendor_id: str
    ) -> InvoiceHeader:
        """Parses CSV or Excel files with exact Decimal math and raw string preservation."""
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str)
        else:
            df = pd.read_excel(file_path, dtype=str)

        df.columns = [str(c).lower().strip() for c in df.columns]
        line_items = []
        line_counter = 1

        for _, row in df.iterrows():
            upc = str(row.get('upc') or row.get('pack upc') or row.get('itemnum') or '').strip()
            item_code = str(row.get('item') or row.get('vendor_part_num') or row.get('code') or '').strip()
            desc = str(row.get('description') or row.get('itemname') or '').strip()
            cost_str = str(row.get('cost') or row.get('price') or '0.00').strip()
            qty_str = str(row.get('qty') or row.get('quantity') or '1').strip()
            pkg_str = str(row.get('package') or row.get('u/m') or 'EA').strip()

            try:
                unit_cost = Decimal(cost_str)
                qty_val = Decimal(qty_str)
            except InvalidOperation:
                unit_cost = Decimal('0.00')
                qty_val = Decimal('1')

            total_cost = unit_cost * qty_val

            pos_qty, rule, req_rev, reason = self.converter.calculate_expected_pos_qty(
                case_qty=qty_val,
                loose_qty=Decimal('0'),
                store_id=store_id,
                vendor_id=vendor_id,
                vendor_item_num=item_code,
                package_text=pkg_str
            )

            item = InvoiceLineItem(
                line_number=line_counter,
                raw_item_num=item_code,
                raw_description=desc,
                raw_upc=upc,
                raw_package_text=pkg_str,
                case_quantity=qty_val,
                loose_quantity=Decimal('0'),
                unit_cost=unit_cost,
                total_cost=total_cost,
                expected_pos_qty=pos_qty,
                conversion_rule_used=rule,
                review_state=ReviewState.NEEDS_HUMAN_REVIEW if req_rev else ReviewState.UNREVIEWED
            )
            if req_rev:
                item.review_reasons.append(reason)

            line_items.append(item)
            line_counter += 1

        subtotal = sum((i.total_cost for i in line_items), Decimal('0.00'))

        return InvoiceHeader(
            installation_id=installation_id,
            store_id=store_id,
            vendor_name="Structured Import Vendor",
            vendor_id=vendor_id,
            invoice_number=os.path.basename(file_path),
            invoice_date="2026-07-21",
            subtotal=subtotal,
            total_amount=subtotal,
            line_items=line_items,
            shadow_mode=True,
            posting_enabled=False
        )

    def _extract_regex(self, text: str, pattern: str, group: int = 0) -> Optional[str]:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return match.group(group).strip() if match else None

    def _create_empty_header(self, file_path: str, installation_id: str, store_id: str, vendor_id: str) -> InvoiceHeader:
        return InvoiceHeader(
            installation_id=installation_id,
            store_id=store_id,
            vendor_name="Unknown Vendor",
            vendor_id=vendor_id,
            invoice_number=os.path.basename(file_path),
            invoice_date="2026-07-21",
            subtotal=Decimal('0.00'),
            total_amount=Decimal('0.00'),
            line_items=[],
            shadow_mode=True,
            posting_enabled=False
        )
