"""
LLM-Powered Semantic Extraction Module
Uses Gemini API to extract structured invoice data from OCR text.
"""

import json
import os
import re


class GeminiExtractor:
    """
    Extracts structured invoice data using Google's Gemini API.
    """
    
    def __init__(self, api_key=None, model_name="gemini-1.5-flash"):
        """
        Initialize the Gemini extractor.
        
        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.
            model_name: Gemini model to use (default: gemini-1.5-flash for speed)
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self.model = None
        
        if not self.api_key:
            print("Warning: No Gemini API key provided. LLM extraction will be disabled.")
    
    def _init_model(self):
        """Lazy initialization of the Gemini model."""
        if self.model is not None:
            return True
            
        if not self.api_key:
            return False
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            return True
        except ImportError:
            print("Error: google-generativeai package not installed.")
            print("Install with: pip install google-generativeai")
            return False
        except Exception as e:
            print(f"Error initializing Gemini model: {e}")
            return False
    
    def extract_invoice_data(self, ocr_text: str) -> dict:
        """
        Extract structured invoice data from OCR text using Gemini.
        
        Args:
            ocr_text: Raw text extracted from invoice via OCR
            
        Returns:
            Dictionary with extracted invoice fields
        """
        if not self._init_model():
            return self._fallback_extraction(ocr_text)
        
        prompt = self._build_extraction_prompt(ocr_text)
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    result_text = json_match.group(0)
            
            parsed = json.loads(result_text)
            return self._normalize_response(parsed)
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse Gemini response as JSON: {e}")
            print(f"Raw response: {result_text[:500]}...")
            return self._fallback_extraction(ocr_text)
        except Exception as e:
            print(f"Gemini API error: {e}")
            return self._fallback_extraction(ocr_text)
    
    def _build_extraction_prompt(self, ocr_text: str) -> str:
        """Build the extraction prompt for Gemini."""
        return f"""You are an expert invoice data extraction system. Analyze the following OCR text from an invoice and extract structured data.

OCR TEXT:
---
{ocr_text}
---

Extract and return ONLY a valid JSON object with this exact structure:
{{
    "vendor_name": "string or null",
    "invoice_number": "string or null", 
    "invoice_date": "string in YYYY-MM-DD format or null",
    "line_items": [
        {{
            "item_code": "vendor's item/product code",
            "description": "product description",
            "case_upc": "10-14 digit UPC for case or null",
            "pack_upc": "10-14 digit UPC for individual unit or null",
            "quantity": number,
            "unit_type": "CA/CS/EA/PK/BOX etc",
            "num_per_case": number or null,
            "unit_price": number,
            "total_price": number
        }}
    ],
    "subtotal": number or null,
    "tax": number or null,
    "total": number or null
}}

IMPORTANT RULES:
1. For UPCs: Extract 10-14 digit barcodes. If you see two UPCs per line, first is usually Case UPC, second is Pack/Unit UPC.
2. For unit_type: Common values are CA (case), CS (case), EA (each), PK (pack), BOX.
3. For num_per_case: This is how many individual units are in a case (e.g., 12-pack = 12).
4. Prices should be numbers without currency symbols.
5. If a field cannot be determined, use null.
6. Return ONLY the JSON, no explanation or markdown.
"""
    
    def _normalize_response(self, parsed: dict) -> dict:
        """Normalize and validate the parsed response."""
        normalized = {
            "vendor_name": parsed.get("vendor_name"),
            "invoice_number": parsed.get("invoice_number"),
            "invoice_date": parsed.get("invoice_date"),
            "line_items": [],
            "subtotal": self._to_float(parsed.get("subtotal")),
            "tax": self._to_float(parsed.get("tax")),
            "total": self._to_float(parsed.get("total"))
        }
        
        for item in parsed.get("line_items", []):
            normalized_item = {
                "item_code": str(item.get("item_code", "")).strip() or None,
                "description": str(item.get("description", "")).strip() or None,
                "case_upc": self._clean_upc(item.get("case_upc")),
                "pack_upc": self._clean_upc(item.get("pack_upc")),
                "quantity": self._to_int(item.get("quantity"), default=1),
                "unit_type": str(item.get("unit_type", "EA")).upper().strip(),
                "num_per_case": self._to_int(item.get("num_per_case")),
                "unit_price": self._to_float(item.get("unit_price")),
                "total_price": self._to_float(item.get("total_price"))
            }
            # Use pack_upc as primary if available, else case_upc
            normalized_item["primary_upc"] = normalized_item["pack_upc"] or normalized_item["case_upc"]
            normalized["line_items"].append(normalized_item)
        
        return normalized
    
    def _clean_upc(self, upc) -> str:
        """Clean and validate UPC codes."""
        if not upc:
            return None
        upc_str = re.sub(r'[^0-9]', '', str(upc))
        if 10 <= len(upc_str) <= 14:
            return upc_str
        return None
    
    def _to_float(self, value, default=None) -> float:
        """Convert value to float safely."""
        if value is None:
            return default
        try:
            # Remove currency symbols and commas
            if isinstance(value, str):
                value = re.sub(r'[$,]', '', value)
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def _to_int(self, value, default=None) -> int:
        """Convert value to int safely."""
        if value is None:
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default
    
    def _fallback_extraction(self, ocr_text: str) -> dict:
        """
        Fallback regex-based extraction when Gemini is unavailable.
        """
        print("Using fallback regex extraction (no LLM)...")
        
        # This is a simplified fallback - the main parsing is in invoice_parser.py
        return {
            "vendor_name": None,
            "invoice_number": None,
            "invoice_date": None,
            "line_items": [],
            "subtotal": None,
            "tax": None,
            "total": None,
            "_fallback": True
        }
    
    def convert_to_inventory_format(self, invoice_data: dict) -> list:
        """
        Convert extracted invoice data to Inventory table format.
        
        Returns:
            List of dicts ready for db_manager.upsert_inventory_item()
        """
        items = []
        for line_item in invoice_data.get("line_items", []):
            if not line_item.get("primary_upc"):
                continue
                
            inventory_item = {
                "ItemNum": line_item["primary_upc"],
                "ItemName": line_item.get("description", "")[:30],  # Max 30 chars
                "Vendor_Part_Num": line_item.get("item_code", "")[:20],  # Max 20 chars
                "Cost": line_item.get("unit_price", 0.0),
                "Quantity_Add": line_item.get("quantity", 1),
                "NumPerCase": line_item.get("num_per_case"),
                "Unit_Type": line_item.get("unit_type", "EA")[:10],  # Max 10 chars
                "Vendor_Name": invoice_data.get("vendor_name", "")[:12] if invoice_data.get("vendor_name") else None
            }
            items.append(inventory_item)
        
        return items


# Quick test
if __name__ == "__main__":
    sample_text = """
    REPUBLIC NATIONAL DISTRIBUTING
    Invoice #: 12345678
    Date: 12/20/2024
    
    102007 GENTLEMAN JACK 24C - CS24 082184035016 1 CA 0 $215.0300 $215.03
    103008 JACK DANIELS 750ML 082184090441 082184090442 2 CA 12 $189.50 $379.00
    
    Subtotal: $594.03
    Tax: $47.52
    Total: $641.55
    """
    
    extractor = GeminiExtractor()
    result = extractor.extract_invoice_data(sample_text)
    print(json.dumps(result, indent=2))
