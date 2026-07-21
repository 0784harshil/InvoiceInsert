"""
Test matching 13-digit PDF UPCs against 12-digit CRE SQL Server UPCs
"""

import pyodbc
import json

with open('config.json', 'r') as f:
    cfg = json.load(f)

driver = cfg.get('DB_DRIVER', '{SQL Server}')
server = cfg.get('DB Server', 'localhost')
database = cfg.get('DB Name', 'cresql')
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"

pdf_upcs = [
    '0603675263680',
    '0038766361202',
    '0810082770940',
    '0855352008941',
    '0740522110688',
    '0071990000486',
    '0080660956152'
]

try:
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()
    
    print("--- Searching CRE Inventory Table with lstrip('0') normalization ---")
    for upc in pdf_upcs:
        upc_stripped = upc.lstrip('0')
        cursor.execute(
            "SELECT Store_ID, ItemNum, ItemName, Cost, In_Stock FROM Inventory WHERE ItemNum = ? OR ItemNum = ? OR ItemNum LIKE ?",
            (upc, upc_stripped, f"%{upc_stripped}")
        )
        rows = cursor.fetchall()
        print(f"\nPDF UPC: '{upc}' (Stripped: '{upc_stripped}'):")
        if rows:
            for r in rows:
                print(f"   -> DB ItemNum: '{r[1].strip()}' | Desc: '{r[2].strip()}' | Stock: {r[4]}")
        else:
            print("   -> NOT FOUND IN DB")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
