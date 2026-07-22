"""
Diagnose CRE POS Search Failure for Fruit Gushers '016000137042'
"""

import pyodbc
import json

with open('config.json', 'r') as f:
    cfg = json.load(f)

driver = cfg.get('DB_DRIVER', '{SQL Server}')
server = cfg.get('DB Server', 'localhost')
database = cfg.get('DB Name', 'cresql')
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"

target_upc = '016000137042'

try:
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Inventory'")
    cols = [c[0] for c in cursor.fetchall()]

    print(f"=== INSPECTING INVENTORY RECORD FOR '{target_upc}' ===")
    cursor.execute("SELECT * FROM Inventory WHERE ItemNum LIKE ?", (f"%{target_upc[-10:]}%",))
    rows = cursor.fetchall()
    for r in rows:
        print(f"\nItemNum: '{r[cols.index('ItemNum')]}', Store_ID: '{r[cols.index('Store_ID')]}'")
        for col_name in ['Store_ID', 'ItemNum', 'ItemName', 'Cost', 'Price', 'In_Stock', 'Dept_ID', 'ItemType', 'Inactive', 'Dirty', 'Tax_1', 'Helper_ItemNum', 'ItemCategory', 'IsKit', 'IsModifier', 'Count_This_Item', 'Print_On_Receipt', 'AvailableOnline']:
            if col_name in cols:
                print(f"  {col_name:25s}: {repr(r[cols.index(col_name)])}")

    print(f"\n=== INSPECTING INVENTORY_SKUS FOR '{target_upc}' ===")
    cursor.execute("SELECT Store_ID, ItemNum, AltSKU FROM Inventory_SKUS WHERE ItemNum LIKE ? OR AltSKU LIKE ?", (f"%{target_upc[-10:]}%", f"%{target_upc[-10:]}%"))
    skus = cursor.fetchall()
    for s in skus:
        print(f"  Store_ID: '{s[0]}' | ItemNum: '{s[1]}' | AltSKU: '{s[2]}'")

    # Compare with a working item in CRE (e.g. Camel or OCB)
    cursor.execute("SELECT TOP 1 * FROM Inventory WHERE ItemNum LIKE '0%' AND Price > 0 AND Store_ID = '1001'")
    working_r = cursor.fetchone()
    print(f"\n=== WORKING CRE ITEM ({working_r[cols.index('ItemNum')]}) KEY FIELDS ===")
    for col_name in ['Store_ID', 'ItemNum', 'ItemName', 'Cost', 'Price', 'In_Stock', 'Dept_ID', 'ItemType', 'Inactive', 'Dirty', 'Tax_1', 'Helper_ItemNum', 'ItemCategory', 'IsKit', 'IsModifier', 'Count_This_Item', 'Print_On_Receipt', 'AvailableOnline']:
        if col_name in cols:
            print(f"  {col_name:25s}: {repr(working_r[cols.index(col_name)])}")

    conn.close()
except Exception as e:
    print(f"Error diagnosing: {e}")
