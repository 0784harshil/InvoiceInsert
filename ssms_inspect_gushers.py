"""
Inspect exact record for 016000137042 (Fruit Gushers) in cresql.dbo.Inventory and Inventory_SKUS
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

    print("======================================================================")
    print(" INVENTORY TABLE QUERY FOR '016000137042'")
    print("======================================================================")
    cursor.execute("""
        SELECT Store_ID, ItemNum, ItemName, Cost, Price, In_Stock, Inactive, ItemType, Dirty, Dept_ID, Vendor_Part_Num
        FROM Inventory
        WHERE ItemNum = '016000137042' OR ItemNum = '16000137042' OR Vendor_Part_Num = '113720'
    """)
    rows = cursor.fetchall()
    for r in rows:
        print(f"Store_ID: '{r[0]}' | ItemNum: '{r[1]}' | ItemName: '{r[2]}' | Cost: ${r[3]:.2f} | Price: ${r[4]:.2f} | Stock: {r[5]} | Inactive: {r[6]} | ItemType: {r[7]} | Dirty: {r[8]} | Dept: '{r[9]}' | VendorPart: '{r[10]}'")

    print("\n======================================================================")
    print(" INVENTORY_SKUS TABLE QUERY FOR '016000137042'")
    print("======================================================================")
    cursor.execute("""
        SELECT Store_ID, ItemNum, AltSKU
        FROM Inventory_SKUS
        WHERE ItemNum = '016000137042' OR AltSKU = '016000137042' OR AltSKU = '16000137042' OR AltSKU = '113720'
    """)
    skus = cursor.fetchall()
    for s in skus:
        print(f"Store_ID: '{s[0]}' | Primary ItemNum: '{s[1]}' | AltSKU: '{s[2]}'")

    conn.close()
except Exception as e:
    print(f"Error inspecting: {e}")
