"""
Diagnose CRE SQL Server Inventory table schema and test single insert/update
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
    print("Connected to SQL Server!")
    
    # Get column names and data types of Inventory table
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'Inventory'
    """)
    cols = cursor.fetchall()
    print("\nInventory Table Columns:")
    for c in cols:
        print(f"  - {c[0]:25s} | Type: {c[1]:15s} | Nullable: {c[2]:5s} | MaxLen: {c[3]}")
        
    conn.close()
except Exception as e:
    print(f"Diagnostic Error: {e}")
