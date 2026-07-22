"""
Inspect all distinct Store_ID values in CRE Inventory and Stations tables
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

    cursor.execute("SELECT DISTINCT Store_ID, COUNT(*) FROM Inventory GROUP BY Store_ID")
    stores = cursor.fetchall()
    print("=== Distinct Store_IDs in Inventory Table ===")
    for s in stores:
        print(f"  Store_ID: '{s[0]}' | Items Count: {s[1]}")

    cursor.execute("SELECT DISTINCT Store_ID FROM Stations WHERE Store_ID IS NOT NULL")
    station_stores = cursor.fetchall()
    print("\n=== Distinct Store_IDs in Stations Table ===")
    for s in station_stores:
        print(f"  Station Store_ID: '{s[0]}'")

    cursor.execute("SELECT DISTINCT Store_ID FROM Setup WHERE Store_ID IS NOT NULL")
    setup_stores = cursor.fetchall()
    print("\n=== Distinct Store_IDs in Setup Table ===")
    for s in setup_stores:
        print(f"  Setup Store_ID: '{s[0]}'")

    conn.close()
except Exception as e:
    print(f"Error checking Store_IDs: {e}")
