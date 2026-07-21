"""
Batch test script for invoice processing pipeline.
Tests all PDF files and generates a summary report.
"""

import os
import sys
import glob
from datetime import datetime

# Set console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from invoice_parser import InvoiceParser
from db_manager import DBManager
from validator import InvoiceValidator


def test_single_file(file_path, parser, validator):
    """Test a single file and return results."""
    result = {
        'file': os.path.basename(file_path),
        'status': 'UNKNOWN',
        'items_found': 0,
        'items_valid': 0,
        'confidence': 0.0,
        'issues': [],
        'error': None
    }
    
    try:
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in ['.csv', '.xlsx', '.xls']:
            items = parser.parse_file(file_path)
            confidence = 100.0
        else:
            items, ocr_text, confidence = parser.parse_file(file_path)
        
        result['items_found'] = len(items)
        result['confidence'] = confidence
        
        # Validate each item
        valid_count = 0
        for item in items:
            is_valid, issues = validator.validate_single_item(item)
            if is_valid:
                valid_count += 1
            else:
                result['issues'].extend(issues)
        
        result['items_valid'] = valid_count
        
        if len(items) > 0:
            result['status'] = 'PASS' if valid_count == len(items) else 'PARTIAL'
        else:
            result['status'] = 'NO_ITEMS'
            
    except Exception as e:
        result['status'] = 'ERROR'
        result['error'] = str(e)
    
    return result


def main():
    print("=" * 70)
    print("    INVOICE PROCESSING PIPELINE - BATCH TEST")
    print("=" * 70)
    print(f"    Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Find all test files
    test_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_files = glob.glob(os.path.join(test_dir, "*.pdf"))
    csv_files = glob.glob(os.path.join(test_dir, "*.csv"))
    image_files = glob.glob(os.path.join(test_dir, "*.png")) + glob.glob(os.path.join(test_dir, "*.jpg"))
    
    all_files = pdf_files + csv_files + image_files
    print(f"\nFound {len(all_files)} files to test:")
    print(f"  - PDFs: {len(pdf_files)}")
    print(f"  - CSVs: {len(csv_files)}")
    print(f"  - Images: {len(image_files)}")
    
    # Initialize components
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]
    tesseract_cmd = None
    for p in tesseract_paths:
        if os.path.exists(p):
            tesseract_cmd = p
            break
    
    parser = InvoiceParser(tesseract_cmd=tesseract_cmd, use_preprocessing=True)
    validator = InvoiceValidator()
    
    # Run tests
    results = []
    print("\n" + "-" * 70)
    print("TESTING FILES...")
    print("-" * 70)
    
    for i, file_path in enumerate(all_files, 1):
        filename = os.path.basename(file_path)
        print(f"\n[{i}/{len(all_files)}] Testing: {filename[:50]}...")
        
        result = test_single_file(file_path, parser, validator)
        results.append(result)
        
        # Print result
        status_icon = {
            'PASS': '[OK]',
            'PARTIAL': '[WARN]',
            'NO_ITEMS': '[EMPTY]',
            'ERROR': '[FAIL]'
        }.get(result['status'], '[?]')
        
        print(f"    {status_icon} Items: {result['items_found']} found, {result['items_valid']} valid")
        print(f"    Confidence: {result['confidence']:.1f}%")
        
        if result['error']:
            print(f"    Error: {result['error'][:60]}...")
        if result['issues'] and len(result['issues']) <= 3:
            for issue in result['issues']:
                print(f"    - {issue}")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results if r['status'] == 'PASS')
    partial = sum(1 for r in results if r['status'] == 'PARTIAL')
    empty = sum(1 for r in results if r['status'] == 'NO_ITEMS')
    failed = sum(1 for r in results if r['status'] == 'ERROR')
    
    print(f"\n  Total Files: {len(results)}")
    print(f"  PASS:        {passed}")
    print(f"  PARTIAL:     {partial}")
    print(f"  NO_ITEMS:    {empty}")
    print(f"  ERROR:       {failed}")
    
    total_items = sum(r['items_found'] for r in results)
    total_valid = sum(r['items_valid'] for r in results)
    print(f"\n  Total Items Found: {total_items}")
    print(f"  Total Items Valid: {total_valid}")
    
    if total_items > 0:
        accuracy = (total_valid / total_items) * 100
        print(f"  Accuracy: {accuracy:.1f}%")
    
    # Detailed results table
    print("\n" + "-" * 70)
    print("DETAILED RESULTS")
    print("-" * 70)
    print(f"{'File':<45} {'Status':<10} {'Items':<8} {'Conf':<8}")
    print("-" * 70)
    
    for r in results:
        filename = r['file'][:42] + "..." if len(r['file']) > 45 else r['file']
        print(f"{filename:<45} {r['status']:<10} {r['items_found']}/{r['items_valid']:<5} {r['confidence']:.1f}%")
    
    print("=" * 70)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
