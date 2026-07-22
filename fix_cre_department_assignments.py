"""
Re-classify all inventory items into accurate CRE POS Departments (Candy, BEER, SODA, LIQUOR, Cigs, etc.)
"""

import pyodbc
import json
from department_classifier import DepartmentClassifier

with open('config.json', 'r') as f:
    cfg = json.load(f)

driver = cfg.get('DB_DRIVER', '{SQL Server}')
server = cfg.get('DB Server', 'localhost')
database = cfg.get('DB Name', 'cresql')
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"

classifier = DepartmentClassifier()

try:
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    print("=========================================================")
    print(" RE-CLASSIFYING INVENTORY DEPT_IDS IN CRE DATABASE")
    print("=========================================================")

    cursor.execute("SELECT Store_ID, ItemNum, ItemName, Vendor_Part_Num FROM Inventory WHERE Vendor_Part_Num IS NOT NULL AND Vendor_Part_Num <> ''")
    items = cursor.fetchall()

    reclassified_count = 0
    dept_counts = {}

    for store_id, item_num, item_name, vendor_part in items:
        store_id = str(store_id).strip()
        item_num = str(item_num).strip()
        desc = str(item_name).strip() if item_name else ""

        # Auto-detect proper department
        proper_dept = classifier.classify_department(desc, item_num)
        dept_counts[proper_dept] = dept_counts.get(proper_dept, 0) + 1

        # Update Inventory Dept_ID
        cursor.execute(
            "UPDATE Inventory SET Dept_ID = ?, Dirty = 1 WHERE Store_ID = ? AND ItemNum = ?",
            (proper_dept, store_id, item_num)
        )
        reclassified_count += cursor.rowcount

    conn.commit()
    print(f"Successfully re-classified {reclassified_count} items into accurate CRE Departments.")

    print("\n--- RE-CLASSIFIED DEPARTMENT BREAKDOWN ---")
    for dept, count in dept_counts.items():
        print(f"Department: {dept:15s} -> {count} items")

    # Check Gushers, Haribo, and Heineken
    print("\n--- SAMPLE ITEMS AFTER DEPARTMENT CLASSIFICATION ---")
    cursor.execute("""
        SELECT ItemNum, ItemName, Dept_ID, Price, In_Stock 
        FROM Inventory 
        WHERE ItemNum IN ('016000137042', '042238302556', '072890003102') 
           OR ItemName LIKE '%GUSHERS%' OR ItemName LIKE '%HARIBO%' OR ItemName LIKE '%HEINEKEN%'
    """)
    samples = cursor.fetchall()
    for s in samples:
        print(f"ItemNum: '{s[0]}' | Name: '{s[1]:30s}' | Department: '{s[2]}'")

    conn.close()
    print("\n=========================================================")
    print(" DEPARTMENT CLASSIFICATION FIX COMPLETE [OK]")
    print("=========================================================")

except Exception as e:
    print(f"Error re-classifying departments: {e}")
