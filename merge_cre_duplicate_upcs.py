"""
Merge 13-digit duplicate items into 12-digit primary UPC items in CRE Inventory table
"""

import pyodbc
import json

with open('config.json', 'r') as f:
    cfg = json.load(f)

driver = cfg.get('DB_DRIVER', '{SQL Server}')
server = cfg.get('DB Server', 'localhost')
database = cfg.get('DB Name', 'cresql')
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"

try:
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    print("=========================================================")
    print(" MERGING 13-DIGIT DUPLICATES INTO 12-DIGIT PRIMARY UPCS")
    print("=========================================================")

    # Find items starting with 00 (13-digit)
    cursor.execute("SELECT Store_ID, ItemNum, In_Stock, Cost, Price, ItemName FROM Inventory WHERE ItemNum LIKE '00%' AND LEN(ItemNum) = 13")
    dup_rows = cursor.fetchall()
    
    merged_count = 0
    for store_id, old_13, stock_13, cost_13, price_13, name_13 in dup_rows:
        store_id = str(store_id).strip()
        old_13 = str(old_13).strip()
        target_12 = old_13[1:] # 12-digit (087692852315)
        stock_13 = float(stock_13) if stock_13 else 0.0

        # Check if 12-digit target exists
        cursor.execute("SELECT ItemNum, In_Stock, Cost, Price, ItemName FROM Inventory WHERE Store_ID = ? AND ItemNum = ?", (store_id, target_12))
        target_row = cursor.fetchone()

        if target_row:
            # 1. Transfer stock to 12-digit target
            cursor.execute(
                "UPDATE Inventory SET In_Stock = In_Stock + ?, Dirty = 1 WHERE Store_ID = ? AND ItemNum = ?",
                (stock_13, store_id, target_12)
            )
            # 2. Delete child Inventory_SKUS for 13-digit item
            cursor.execute("DELETE FROM Inventory_SKUS WHERE Store_ID = ? AND ItemNum = ?", (store_id, old_13))
            # 3. Delete 13-digit inventory record
            cursor.execute("DELETE FROM Inventory WHERE Store_ID = ? AND ItemNum = ?", (store_id, old_13))
            merged_count += 1

            # 4. Insert 13-digit version into Inventory_SKUS under target_12
            cursor.execute(
                """IF NOT EXISTS (SELECT 1 FROM Inventory_SKUS WHERE Store_ID = ? AND ItemNum = ? AND AltSKU = ?)
                   INSERT INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES (?, ?, ?)""",
                (store_id, target_12, old_13, store_id, target_12, old_13)
            )

    conn.commit()
    print(f"Successfully merged {merged_count} 13-digit duplicate items into clean 12-digit primary records.")

    # Inspect Truly Lemonade 0087692852315 -> 087692852315
    cursor.execute("SELECT Store_ID, ItemNum, ItemName, Price, In_Stock FROM Inventory WHERE ItemNum LIKE '%87692852315%'")
    rows = cursor.fetchall()
    print("\n--- INVENTORY RECORD FOR 87692852315 ---")
    for r in rows:
        print(f"  Primary ItemNum: '{r[1]}' | Name: '{r[2]}' | Price: ${r[3]:.2f} | Stock: {r[4]}")

    cursor.execute("SELECT Store_ID, ItemNum, AltSKU FROM Inventory_SKUS WHERE ItemNum LIKE '%87692852315%' OR AltSKU LIKE '%87692852315%'")
    skus = cursor.fetchall()
    print(f"\n--- INVENTORY_SKUS ENTRIES ({len(skus)} entries) ---")
    for s in skus:
        print(f"  Primary ItemNum: '{s[1]}' | AltSKU Barcode: '{s[2]}'")

    conn.close()
    print("\n=========================================================")
    print(" DUPLICATE MERGE COMPLETE [OK]")
    print("=========================================================")

except Exception as e:
    print(f"Error merging duplicates: {e}")
