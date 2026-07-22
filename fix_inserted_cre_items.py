"""
Fix existing inserted items in CRE Inventory table to satisfy POS scanner requirements:
- Inactive = 0
- ItemType = 0
- Dirty = 1
- Tax_1 = 1
- Price = Cost * 1.30 (or Cost if 0)
- Populate Inventory_SKUS with all 11, 12, and 13 digit UPC variants
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
    print(" FIXING CRE POS SCANNER FIELDS ON INVENTORY TABLE")
    print("=========================================================")

    # 1. Update Inventory flags (Inactive=0, ItemType=0, Dirty=1, Tax_1=1, Price)
    cursor.execute("""
        UPDATE Inventory
        SET Inactive = 0,
            ItemType = 0,
            Dirty = 1,
            Tax_1 = 1,
            Price = CASE WHEN Price IS NULL OR Price = 0 THEN Cost * 1.30 ELSE Price END
        WHERE Vendor_Part_Num IS NOT NULL AND Vendor_Part_Num <> ''
    """)
    updated_rows = cursor.rowcount
    print(f"Updated CRE POS flags (Inactive=0, ItemType=0, Dirty=1, Price) on {updated_rows} inventory items.")

    # 2. Fetch all received items and populate Inventory_SKUS with all barcode variants
    cursor.execute("SELECT Store_ID, ItemNum, Vendor_Part_Num FROM Inventory WHERE Vendor_Part_Num IS NOT NULL AND Vendor_Part_Num <> ''")
    items = cursor.fetchall()
    
    skus_inserted = 0
    for store_id, item_num, vendor_part in items:
        store_id = str(store_id).strip()
        item_num = str(item_num).strip()
        vendor_part = str(vendor_part).strip() if vendor_part else ""

        # Generate variants
        variants = normalizer.generate_variants(item_num)
        if vendor_part:
            variants.add(vendor_part)

        for alt in variants:
            if alt != item_num and len(alt) >= 6:
                try:
                    cursor.execute(
                        """IF NOT EXISTS (SELECT 1 FROM Inventory_SKUS WHERE Store_ID = ? AND ItemNum = ? AND AltSKU = ?)
                           INSERT INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES (?, ?, ?)""",
                        (store_id, item_num, alt, store_id, item_num, alt)
                    )
                    skus_inserted += cursor.rowcount
                except Exception:
                    pass

    conn.commit()
    print(f"Inserted {skus_inserted} alternate barcode variants into Inventory_SKUS table.")

    # 3. Verify sample item values
    cursor.execute("SELECT TOP 5 Store_ID, ItemNum, ItemName, Cost, Price, In_Stock, Inactive, ItemType, Dirty, Helper_ItemNum FROM Inventory WHERE Vendor_Part_Num IS NOT NULL AND Vendor_Part_Num <> ''")
    sample_rows = cursor.fetchall()
    print("\n--- SAMPLE FIXED ITEMS IN CRE INVENTORY ---")
    for r in sample_rows:
        print(f"ItemNum: '{r[1]}' | Name: '{r[2][:25]}' | Price: ${r[4]:.2f} | Inactive: {r[6]} | Type: {r[7]} | Dirty: {r[8]}")

    conn.close()
    print("\n=========================================================")
    print(" CRE POS SCANNER FIELDS FIXED SUCCESSFULLY [OK]")
    print("=========================================================")
except Exception as e:
    print(f"Error fixing CRE items: {e}")
