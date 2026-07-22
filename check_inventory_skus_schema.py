"""
Inspect Inventory_SKUS table schema in CRE SQL Server
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
    
    cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Inventory_SKUS'")
    cols = cursor.fetchall()
    print("=== Inventory_SKUS Table Columns ===")
    for c in cols:
        print(f"  Column: {c[0]:25s} | Type: {c[1]}")

    cursor.execute("SELECT TOP 5 * FROM Inventory_SKUS")
    rows = cursor.fetchall()
    print(f"\nSample Rows in Inventory_SKUS ({len(rows)} rows):")
    for r in rows:
        print(f"  {r}")

    conn.close()
except Exception as e:
    print(f"Error checking Inventory_SKUS schema: {e}")
