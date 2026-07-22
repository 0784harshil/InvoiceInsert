"""
Inspect AltSKU and barcode columns in CRE SQL Server Inventory table
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
    
    cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Inventory' AND (COLUMN_NAME LIKE '%SKU%' OR COLUMN_NAME LIKE '%UPC%' OR COLUMN_NAME LIKE '%Barcode%' OR COLUMN_NAME LIKE '%Item%')")
    cols = cursor.fetchall()
    print("=== Barcode / SKU Columns in Inventory Table ===")
    for c in cols:
        print(f"  Column: {c[0]:25s} | Type: {c[1]}")

    conn.close()
except Exception as e:
    print(f"Error checking schema: {e}")
