"""
Diagnose CRE POS Search Query for '0087692015161'
"""

import pyodbc
import json

with open('config.json', 'r') as f:
    cfg = json.load(f)

driver = cfg.get('DB_DRIVER', '{SQL Server}')
server = cfg.get('DB Server', 'localhost')
database = cfg.get('DB Name', 'cresql')
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"

search_upc = '0087692015161'

try:
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    print(f"=== Inspecting CRE Inventory Record for '{search_upc}' ===")
    cursor.execute("SELECT * FROM Inventory WHERE ItemNum LIKE ? OR ItemNum LIKE ?", (f"%{search_upc.lstrip('0')}%", f"%{search_upc}%"))
    rows = cursor.fetchall()
    
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Inventory'")
    cols = [c[0] for c in cursor.fetchall()]

    for r in rows:
        print(f"\nItem Found: ItemNum='{r[cols.index('ItemNum')]}', Store_ID='{r[cols.index('Store_ID')]}', Dept_ID='{r[cols.index('Dept_ID')]}'")
        for col_name in ['Store_ID', 'ItemNum', 'ItemName', 'Cost', 'Price', 'In_Stock', 'Dept_ID', 'ItemType', 'Inactive', 'Dirty', 'Tax_1', 'Helper_ItemNum', 'ItemCategory', 'IsKit', 'IsModifier', 'Count_This_Item', 'Print_On_Receipt', 'AvailableOnline']:
            if col_name in cols:
                print(f"  {col_name:25s}: {repr(r[cols.index(col_name)])}")

    # Check Inventory_SKUS table
    cursor.execute("SELECT * FROM Inventory_SKUS WHERE ItemNum = ? OR AltSKU = ?", (search_upc, search_upc))
    skus = cursor.fetchall()
    print(f"\n=== Inventory_SKUS Table Entries for '{search_upc}' ({len(skus)} entries) ===")
    for s in skus:
        print(f"  {s}")

    # Compare with a working item in CRE (e.g. Camel or OCB)
    cursor.execute("SELECT TOP 1 * FROM Inventory WHERE ItemNum LIKE '0%' AND Price > 0 AND Store_ID = '1001'")
    working_r = cursor.fetchone()
    print(f"\n=== Working CRE Item ({working_r[cols.index('ItemNum')]}) Key Fields ===")
    for col_name in ['Store_ID', 'ItemNum', 'ItemName', 'Cost', 'Price', 'In_Stock', 'Dept_ID', 'ItemType', 'Inactive', 'Dirty', 'Tax_1', 'Helper_ItemNum', 'ItemCategory', 'IsKit', 'IsModifier', 'Count_This_Item', 'Print_On_Receipt', 'AvailableOnline']:
        if col_name in cols:
            print(f"  {col_name:25s}: {repr(working_r[cols.index(col_name)])}")

    conn.close()
except Exception as e:
    print(f"Error diagnosing search: {e}")
