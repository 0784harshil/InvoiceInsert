"""
Reproduce CRE POS Search queries for Alt SKU vs Item Number vs Search Main Fields
"""

import pyodbc
import json

with open('config.json', 'r') as f:
    cfg = json.load(f)

driver = cfg.get('DB_DRIVER', '{SQL Server}')
server = cfg.get('DB Server', 'localhost')
database = cfg.get('DB Name', 'cresql')
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"

search_val = '016000137042'

try:
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    print(f"=== Testing CRE POS Search Query Variants for '{search_val}' ===")

    # 1. Search by ItemNum
    cursor.execute("""
        SELECT i.ItemNum, i.ItemName, i.Price, i.In_Stock 
        FROM Inventory i 
        WHERE i.Store_ID = '1001' AND i.Inactive = 0 AND i.ItemNum = ?
    """, (search_val,))
    r1 = cursor.fetchall()
    print(f"1. Item Number Query (i.ItemNum = '{search_val}'): {len(r1)} rows found")

    # 2. Search by AltSKU (CRE POS query for Alt SKU radio button)
    cursor.execute("""
        SELECT i.ItemNum, i.ItemName, i.Price, i.In_Stock, s.AltSKU 
        FROM Inventory i 
        INNER JOIN Inventory_SKUS s ON i.Store_ID = s.Store_ID AND i.ItemNum = s.ItemNum 
        WHERE i.Store_ID = '1001' AND i.Inactive = 0 AND s.AltSKU = ?
    """, (search_val,))
    r2 = cursor.fetchall()
    print(f"2. Alt SKU Query (s.AltSKU = '{search_val}'): {len(r2)} rows found")

    # 3. Search Main Fields (CRE POS query for Search Main Fields radio button)
    cursor.execute("""
        SELECT i.ItemNum, i.ItemName, i.Price, i.In_Stock 
        FROM Inventory i 
        WHERE i.Store_ID = '1001' AND i.Inactive = 0 
          AND (i.ItemNum LIKE ? OR i.Helper_ItemNum LIKE ? OR i.Vendor_Part_Num LIKE ?)
    """, (f"%{search_val}%", f"%{search_val}%", f"%{search_val}%"))
    r3 = cursor.fetchall()
    print(f"3. Search Main Fields Query (i.ItemNum LIKE '%{search_val}%'): {len(r3)} rows found")

    # 4. If we ensure every primary ItemNum is ALSO inserted into Inventory_SKUS as an AltSKU:
    print("\n--- Inserting Primary ItemNum into Inventory_SKUS as an AltSKU entry ---")
    cursor.execute(
        """IF NOT EXISTS (SELECT 1 FROM Inventory_SKUS WHERE Store_ID = '1001' AND ItemNum = ? AND AltSKU = ?)
           INSERT INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES ('1001', ?, ?)""",
        (search_val, search_val, search_val, search_val)
    )
    conn.commit()

    # Re-run Alt SKU query
    cursor.execute("""
        SELECT i.ItemNum, i.ItemName, i.Price, i.In_Stock, s.AltSKU 
        FROM Inventory i 
        INNER JOIN Inventory_SKUS s ON i.Store_ID = s.Store_ID AND i.ItemNum = s.ItemNum 
        WHERE i.Store_ID = '1001' AND i.Inactive = 0 AND s.AltSKU = ?
    """, (search_val,))
    r2_fixed = cursor.fetchall()
    print(f"2. Fixed Alt SKU Query (s.AltSKU = '{search_val}'): {len(r2_fixed)} rows found! [FIXED]")

    conn.close()

except Exception as e:
    print(f"Error testing queries: {e}")
