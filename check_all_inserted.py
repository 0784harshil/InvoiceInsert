"""
Check all items inserted from MAIL.pdf in CRE SQL Server Inventory table
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
    
    print("--- Searching Inventory Table by Vendor Part Numbers ---")
    vendor_parts = ['64618', '10585', '11801', '57023', '57291', '15650', '42928', '10238', '10159']
    
    query = f"SELECT Store_ID, ItemNum, ItemName, Cost, In_Stock, Vendor_Part_Num FROM Inventory WHERE Vendor_Part_Num IN ({','.join(['?']*len(vendor_parts))})"
    cursor.execute(query, vendor_parts)
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} matching items by Vendor Part Number:")
    for r in rows:
        print(f"  ItemNum (UPC): '{r[1]:14s}' | Desc: '{r[2]:25s}' | Stock: {r[4]} | Vendor Item #: '{r[5]}'")

    print("\n--- Searching Inventory Table for items added today / stock > 0 ---")
    cursor.execute("SELECT Store_ID, ItemNum, ItemName, Cost, In_Stock, Vendor_Part_Num FROM Inventory WHERE ItemName LIKE '%ASAHI%' OR ItemName LIKE '%ALLAGASH%' OR ItemName LIKE '%BELLS%' OR ItemName LIKE '%CORONA%' OR ItemName LIKE '%COORS%'")
    rows_desc = cursor.fetchall()
    print(f"Found {len(rows_desc)} matching items by Description:")
    for r in rows_desc:
        print(f"  ItemNum (UPC): '{r[1]:14s}' | Desc: '{r[2]:25s}' | Stock: {r[4]} | Vendor Item #: '{r[5]}'")

    conn.close()
except Exception as e:
    print(f"Error checking inventory: {e}")
