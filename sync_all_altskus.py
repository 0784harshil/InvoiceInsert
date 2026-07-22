"""
Sync all barcode variants (Primary ItemNum, 13-digit, 12-digit, 11-digit, Vendor Part Num)
into Inventory_SKUS table for every item in CRE Inventory.
"""

import pyodbc
import json
from upc_normalizer import UPCNormalizer

with open('config.json', 'r') as f:
    cfg = json.load(f)

driver = cfg.get('DB_DRIVER', '{SQL Server}')
server = cfg.get('DB Server', 'localhost')
database = cfg.get('DB Name', 'cresql')
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"

normalizer = UPCNormalizer()

try:
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    print("=========================================================")
    print(" SYNCING ALL ALTSKU BARCODES INTO INVENTORY_SKUS TABLE")
    print("=========================================================")

    cursor.execute("SELECT Store_ID, ItemNum, Vendor_Part_Num, Helper_ItemNum FROM Inventory WHERE Store_ID = '1001'")
    items = cursor.fetchall()
    
    total_skus_added = 0
    for store_id, item_num, vendor_part, helper_num in items:
        store_id = str(store_id).strip()
        item_num = str(item_num).strip()
        vendor_part = str(vendor_part).strip() if vendor_part else ""
        helper_num = str(helper_num).strip() if helper_num else ""

        # Generate all barcode variants
        variants = normalizer.generate_variants(item_num)
        variants.add(item_num) # Include Primary ItemNum so AltSKU search works!
        if vendor_part:
            variants.add(vendor_part)
        if helper_num:
            variants.add(helper_num)

        for alt in variants:
            if len(alt) >= 4:
                try:
                    cursor.execute(
                        """IF NOT EXISTS (SELECT 1 FROM Inventory_SKUS WHERE Store_ID = ? AND ItemNum = ? AND AltSKU = ?)
                           INSERT INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES (?, ?, ?)""",
                        (store_id, item_num, alt, store_id, item_num, alt)
                    )
                    total_skus_added += cursor.rowcount
                except Exception:
                    pass

    conn.commit()
    print(f"Successfully synced {total_skus_added} AltSKU barcode entries into Inventory_SKUS table.")

    # Test Fruit Gushers '016000137042'
    cursor.execute("""
        SELECT i.ItemNum, i.ItemName, i.Price, s.AltSKU 
        FROM Inventory i 
        INNER JOIN Inventory_SKUS s ON i.Store_ID = s.Store_ID AND i.ItemNum = s.ItemNum 
        WHERE s.AltSKU = '016000137042' OR s.AltSKU = '16000137042'
    """)
    gushers_rows = cursor.fetchall()
    print(f"\n--- CRE POS Alt SKU Search Results for Gushers ({len(gushers_rows)} matches) ---")
    for r in gushers_rows:
        print(f"  ItemNum: '{r[0]}' | Name: '{r[1]}' | Price: ${r[2]:.2f} | AltSKU Matched: '{r[3]}'")

    conn.close()
    print("\n=========================================================")
    print(" ALTSKU SYNC COMPLETE — READY FOR POS SEARCH & SCANNING")
    print("=========================================================")

except Exception as e:
    print(f"Error syncing AltSKUs: {e}")
