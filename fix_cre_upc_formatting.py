"""
Fix CRE POS Primary ItemNum formatting:
Convert 13-digit EAN-13 (with 00 prefix) to clean 12-digit UPC-A in Inventory.ItemNum,
handling foreign key constraint fkInventory_SKUS safely.
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
    print(" CONVERTING CRE INVENTORY ITEMNUM TO 12-DIGIT UPC-A FORMAT")
    print("=========================================================")

    cursor.execute("SELECT Store_ID, ItemNum, ItemName, Vendor_Part_Num FROM Inventory WHERE Vendor_Part_Num IS NOT NULL AND Vendor_Part_Num <> ''")
    items = cursor.fetchall()
    
    fixed_count = 0
    skus_inserted = 0

    for store_id, old_num, item_name, vendor_part in items:
        store_id = str(store_id).strip()
        old_num = str(old_num).strip()
        vendor_part = str(vendor_part).strip() if vendor_part else ""

        # Determine target 12-digit primary UPC
        new_primary = old_num
        if len(old_num) == 13 and old_num.startswith('00'):
            new_primary = old_num[1:] # 12-digit (072890003102)
        elif len(old_num) == 11:
            new_primary = '0' + old_num # 12-digit

        # Generate all alternate barcode variants (13-digit, 12-digit, 11-digit, vendor_part)
        all_variants = normalizer.generate_variants(old_num)
        all_variants.add(old_num)
        all_variants.add(new_primary)
        if vendor_part:
            all_variants.add(vendor_part)

        if new_primary != old_num:
            try:
                # 1. Temporarily remove child rows from Inventory_SKUS to satisfy FK constraint
                cursor.execute("DELETE FROM Inventory_SKUS WHERE Store_ID = ? AND ItemNum = ?", (store_id, old_num))
                
                # 2. Update Primary Key in Inventory
                cursor.execute(
                    "UPDATE Inventory SET ItemNum = ?, Helper_ItemNum = ?, Dirty = 1 WHERE Store_ID = ? AND ItemNum = ?",
                    (new_primary, old_num, store_id, old_num)
                )
                fixed_count += cursor.rowcount
            except Exception as ex:
                print(f"Warning updating ItemNum {old_num} -> {new_primary}: {ex}")

        # 3. Re-insert all alternate barcode variants into Inventory_SKUS
        for alt in all_variants:
            if len(alt) >= 6:
                try:
                    cursor.execute(
                        """IF NOT EXISTS (SELECT 1 FROM Inventory_SKUS WHERE Store_ID = ? AND ItemNum = ? AND AltSKU = ?)
                           INSERT INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES (?, ?, ?)""",
                        (store_id, new_primary, alt, store_id, new_primary, alt)
                    )
                    skus_inserted += cursor.rowcount
                except Exception:
                    pass

    conn.commit()
    print(f"Successfully converted {fixed_count} items to 12-digit UPC-A Primary ItemNum format.")
    print(f"Populated Inventory_SKUS with all alternate barcode variants.")

    # Check Heineken 0.0 sample item (0072890003102 -> 072890003102)
    cursor.execute("SELECT Store_ID, ItemNum, ItemName, Price, In_Stock FROM Inventory WHERE ItemNum LIKE '%72890003102%'")
    sample = cursor.fetchone()
    if sample:
        print("\n--- SAMPLE HEINEKEN ITEM RECORD IN INVENTORY ---")
        print(f"Primary ItemNum: '{sample[1]}' | Name: '{sample[2]}' | Price: ${sample[3]:.2f} | Stock: {sample[4]}")

    cursor.execute("SELECT Store_ID, ItemNum, AltSKU FROM Inventory_SKUS WHERE ItemNum LIKE '%72890003102%' OR AltSKU LIKE '%72890003102%'")
    sample_skus = cursor.fetchall()
    print(f"\n--- INVENTORY_SKUS ENTRIES ({len(sample_skus)} entries) ---")
    for s in sample_skus:
        print(f"  Primary ItemNum: '{s[1]}' | AltSKU Barcode: '{s[2]}'")

    conn.close()
    print("\n=========================================================")
    print(" 12-DIGIT UPC CONVERSION & ALTSKU SYNC COMPLETE [OK]")
    print("=========================================================")

except Exception as e:
    print(f"Error converting UPCs: {e}")
