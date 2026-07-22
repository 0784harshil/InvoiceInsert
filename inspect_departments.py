"""
Inspect valid departments in cresql.dbo.Departments and Department assignments in Inventory
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
    print(" 1. VALID DEPARTMENTS IN cresql.dbo.Departments TABLE")
    print("=========================================================")
    cursor.execute("SELECT Dept_ID, Description FROM Departments ORDER BY Dept_ID")
    depts = cursor.fetchall()
    for d in depts:
        print(f"Dept_ID: '{d[0]:15s}' | Description: '{d[1]}'")

    print("\n=========================================================")
    print(" 2. CURRENT DEPT_ID DISTRIBUTION IN Inventory TABLE")
    print("=========================================================")
    cursor.execute("SELECT Dept_ID, COUNT(*) FROM Inventory GROUP BY Dept_ID ORDER BY COUNT(*) DESC")
    inv_depts = cursor.fetchall()
    for idp in inv_depts:
        print(f"Dept_ID: '{idp[0]}' | Items Count: {idp[1]}")

    conn.close()

except Exception as e:
    print(f"Error inspecting departments: {e}")
