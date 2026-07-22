"""
Sync both Vendor Item Number and Primary ItemNum into Inventory_SKUS.AltSKU for all items
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
    print(" SYNCING VENDOR ITEM NUMBERS & PRIMARY ITEMNUMS TO ALTSKU")
    print("=========================================================")

    cursor.execute("SELECT Store_ID, ItemNum, Vendor_Part_Num, Helper_ItemNum FROM Inventory WHERE Store_ID = '1001'")
    items = cursor.fetchall()

    vendor_alts_inserted = 0
    itemnum_alts_inserted = 0

    for store_id, item_num, vendor_part, helper_num in items:
        store_id = str(store_id).strip()
        item_num = str(item_num).strip()
        vendor_part = str(vendor_part).strip() if vendor_part else ""
        helper_num = str(helper_num).strip() if helper_num else ""

        # 1. Insert Primary ItemNum into Inventory_SKUS under AltSKU
        if item_num:
            try:
                cursor.execute(
                    """IF NOT EXISTS (SELECT 1 FROM Inventory_SKUS WHERE Store_ID = ? AND ItemNum = ? AND AltSKU = ?)
                       INSERT INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES (?, ?, ?)""",
                    (store_id, item_num, item_num, store_id, item_num, item_num)
                )
                itemnum_alts_inserted += cursor.rowcount
            except Exception:
                pass

        # 2. Insert Vendor Part / Item Number into Inventory_SKUS under AltSKU
        if vendor_part:
            try:
                cursor.execute(
                    """IF NOT EXISTS (SELECT 1 FROM Inventory_SKUS WHERE Store_ID = ? AND ItemNum = ? AND AltSKU = ?)
                       INSERT INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES (?, ?, ?)""",
                    (store_id, item_num, vendor_part, store_id, item_num, vendor_part)
                )
                vendor_alts_inserted += cursor.rowcount
            except Exception:
                pass

        # 3. Insert Helper ItemNum into Inventory_SKUS under AltSKU
        if helper_num:
            try:
                cursor.execute(
                    """IF NOT EXISTS (SELECT 1 FROM Inventory_SKUS WHERE Store_ID = ? AND ItemNum = ? AND AltSKU = ?)
                       INSERT INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES (?, ?, ?)""",
                    (store_id, item_num, helper_num, store_id, item_num, helper_num)
                )
            except Exception:
                pass

    conn.commit()
    print(f"Successfully inserted {itemnum_alts_inserted} Primary ItemNums into Inventory_SKUS.AltSKU.")
    print(f"Successfully inserted {vendor_alts_inserted} Vendor Item Numbers into Inventory_SKUS.AltSKU.")

    # Inspect sample item in Inventory_SKUS (e.g. 016000137042 with Vendor Part 113720)
    cursor.execute("""
        SELECT Store_ID, ItemNum, AltSKU 
        FROM Inventory_SKUS 
        WHERE ItemNum = '016000137042' OR AltSKU = '113720' OR AltSKU = '016000137042'
    """)
    skus = cursor.fetchall()
    print("\n--- SAMPLE INVENTORY_SKUS ENTRIES FOR GUSHERS (ItemNum: 016000137042, VendorPart: 113720) ---")
    for s in skus:
        print(f"Store: {s[0]} | Primary ItemNum: '{s[1]}' | AltSKU Entry: '{s[2]}'")

    conn.close()
    print("\n=========================================================")
    print(" ALTSKU SYNC COMPLETE [OK]")
    print("=========================================================")

except Exception as e:
    print(f"Error syncing Vendor Item Numbers: {e}")
