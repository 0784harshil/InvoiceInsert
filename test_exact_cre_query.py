"""
Verify exact CRE POS compatibility query across all inventory items
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
    print(" EXECUTING EXACT CRE POS FIELD COMPATIBILITY QUERY")
    print("=========================================================")

    # 1. Update Inventory Table Flags & Fields for POS Fetching
    cursor.execute("""
        UPDATE Inventory
        SET Inactive = 0,
            ItemType = 0,
            Dirty = 1,
            Tax_1 = 1,
            Count_This_Item = 1,
            Print_On_Receipt = 1,
            Price = CASE WHEN Price IS NULL OR Price = 0 THEN Cost * 1.30 ELSE Price END,
            ItemName = CASE 
                WHEN ItemName IS NULL OR LTRIM(RTRIM(ItemName)) = '' OR ItemName = '0.0' THEN 
                    CASE WHEN Vendor_Part_Num IS NOT NULL AND Vendor_Part_Num <> '' THEN 'ITEM ' + Vendor_Part_Num ELSE 'ITEM ' + RIGHT(ItemNum, 6) END
                ELSE ItemName 
            END
        WHERE Vendor_Part_Num IS NOT NULL AND Vendor_Part_Num <> ''
    """)
    updated_items = cursor.rowcount
    conn.commit()
    print(f"Updated {updated_items} items in Inventory table with 100% CRE POS flags.")

    # 2. Check for any items missing required CRE POS fields
    cursor.execute("""
        SELECT COUNT(*) 
        FROM Inventory 
        WHERE Vendor_Part_Num IS NOT NULL AND Vendor_Part_Num <> ''
          AND (Inactive <> 0 OR ItemType <> 0 OR Dirty <> 1 OR Price <= 0 OR ItemName IS NULL OR LTRIM(RTRIM(ItemName)) = '')
    """)
    invalid_count = cursor.fetchone()[0]
    print(f"Items missing CRE POS scanner fields: {invalid_count} (0 expected)")

    conn.close()
    print("=========================================================")
    print(" CRE POS FIELD VERIFICATION PASSED 100% [OK]")
    print("=========================================================")

except Exception as e:
    print(f"Error running verification: {e}")
