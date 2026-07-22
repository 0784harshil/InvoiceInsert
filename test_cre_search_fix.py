"""
Fix blank ItemName descriptions in CRE Inventory table to enable POS search
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
    print(" FIXING BLANK ITEMNAME DESCRIPTIONS IN CRE INVENTORY")
    print("=========================================================")

    # 1. Update any empty or NULL ItemName with fallback description
    cursor.execute("""
        UPDATE Inventory
        SET ItemName = CASE 
            WHEN Vendor_Part_Num IS NOT NULL AND Vendor_Part_Num <> '' THEN 'ITEM ' + Vendor_Part_Num
            ELSE 'ITEM ' + RIGHT(ItemNum, 6)
        END
        WHERE ItemName IS NULL OR LTRIM(RTRIM(ItemName)) = '' OR ItemName = '0.0'
    """)
    updated_count = cursor.rowcount
    conn.commit()
    print(f"Updated {updated_count} items with non-empty ItemName descriptions.")

    # 2. Specific fix for 0087692015161
    cursor.execute("UPDATE Inventory SET ItemName = 'TRULY LEMONADE C24 12P' WHERE ItemNum = '0087692015161'")
    conn.commit()

    # 3. Check updated values
    cursor.execute("SELECT Store_ID, ItemNum, ItemName, Cost, Price, In_Stock, Inactive, Dirty FROM Inventory WHERE ItemNum = '0087692015161'")
    row = cursor.fetchone()
    print("\n--- UPDATED ITEM RECORD FOR 0087692015161 ---")
    print(f"Store: {row[0]} | ItemNum: '{row[1]}' | ItemName: '{row[2]}' | Price: ${row[4]:.2f} | Stock: {row[5]} | Inactive: {row[6]} | Dirty: {row[7]}")

    conn.close()
    print("\n=========================================================")
    print(" BLANK DESCRIPTIONS FIXED — READY FOR POS SEARCH TEST")
    print("=========================================================")
except Exception as e:
    print(f"Error fixing descriptions: {e}")
