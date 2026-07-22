"""
Inspect all tables in cresql database for AltSKU or alternate barcode fields
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
    
    cursor.execute("SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME LIKE '%SKU%' OR COLUMN_NAME LIKE '%Alt%' OR COLUMN_NAME LIKE '%Barcode%' OR COLUMN_NAME LIKE '%Helper%' OR COLUMN_NAME LIKE '%UPC%'")
    cols = cursor.fetchall()
    print("=== AltSKU / Barcode Columns Across All Tables ===")
    for c in cols:
        print(f"  Table: {c[0]:25s} | Column: {c[1]:25s} | Type: {c[2]}")

    conn.close()
except Exception as e:
    print(f"Error checking all tables: {e}")
