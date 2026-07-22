"""
Compare existing working POS items in CRE Inventory table vs newly inserted items
to find missing flags required for POS scanner/search lookup.
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

    # Get column names
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Inventory'")
    col_names = [c[0] for c in cursor.fetchall()]

    # Fetch a working existing item (e.g., Camel or Marlboro)
    cursor.execute("SELECT TOP 1 * FROM Inventory WHERE ItemNum LIKE '0%' AND Cost = 0.0 AND Store_ID IS NOT NULL")
    existing_row = cursor.fetchone()

    # Fetch one of our inserted items (e.g., Allagash or Asahi or Coors Light)
    cursor.execute("SELECT TOP 1 * FROM Inventory WHERE Vendor_Part_Num = '64618' OR Vendor_Part_Num = '10585' OR Vendor_Part_Num = '11801'")
    inserted_row = cursor.fetchone()

    print("======================================================================")
    print(" COMPARING WORKING POS ITEM VS INSERTED ITEM COLUMNS")
    print("======================================================================")

    if existing_row and inserted_row:
        diff_count = 0
        for i, col in enumerate(col_names):
            val_exist = existing_row[i]
            val_insert = inserted_row[i]
            if val_exist != val_insert:
                print(f"Column: {col:30s} | Working POS: {repr(val_exist):20s} | Inserted Item: {repr(val_insert)}")
                diff_count += 1
        print(f"\nTotal Differing Columns: {diff_count}")
    else:
        print("Could not fetch rows for comparison.")

    conn.close()
except Exception as e:
    print(f"Error comparing rows: {e}")
