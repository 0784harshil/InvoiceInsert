"""
Diagnose CRE SQL Server valid Dept_ID from Departments table
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
    cursor.execute("SELECT TOP 5 Dept_ID, Description FROM Departments")
    rows = cursor.fetchall()
    print("Valid Dept_IDs in Departments table:")
    for r in rows:
        print(f"  - Dept_ID: '{r[0]}' | Description: '{r[1]}'")
    conn.close()
except Exception as e:
    print(f"Error fetching Departments: {e}")
