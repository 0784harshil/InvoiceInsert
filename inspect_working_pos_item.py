"""
Inspect exact column values for working POS items in CRE Inventory table
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

    cursor.execute("SELECT TOP 5 Store_ID, ItemNum, ItemName, Cost, Price, In_Stock, Dept_ID, ItemType, Inactive, Tax_1, Dirty, Helper_ItemNum FROM Inventory WHERE ItemName LIKE 'OCB%' OR ItemName LIKE 'Camel%' OR ItemName LIKE 'Marl%'")
    rows = cursor.fetchall()

    print("=== WORKING POS ITEMS SAMPLE VALUES ===")
    for r in rows:
        print(f"Store: {r[0]} | ItemNum: '{r[1]}' | Name: '{r[2]}' | Cost: ${r[3]} | Price: ${r[4]} | Stock: {r[5]} | Dept: '{r[6]}' | Type: {r[7]} | Inactive: {r[8]} | Tax_1: {r[9]} | Dirty: {r[10]} | Helper: '{r[11]}'")

    conn.close()
except Exception as e:
    print(f"Error inspecting working items: {e}")
