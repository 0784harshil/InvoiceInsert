"""
Certified Database Manager for CRE / POS Integration
Enforces Rules 4, 12, 13, 14, 15, 17, 18:
- CRE POS Register Compatibility: Sets Inactive=0, ItemType=0, Dirty=1, Tax_1=1, Price, and non-empty ItemName.
- Automatic UPC Normalization (EAN-13, UPC-A, GTIN-11) & Dual-Field Storage (ItemNum + AltSKU + Helper_ItemNum).
- Writes alternate barcode variants into Inventory_SKUS table for seamless POS scanning.
- Full Operational Logging & 1-Click Atomic Transaction Rollback.
"""

from decimal import Decimal
import pyodbc
import sqlite3
import json
import os
import traceback
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from models import InvoiceHeader, InvoiceLineItem, ReviewState
from upc_normalizer import UPCNormalizer
from operational_logger import OperationalLogger


class CertifiedDBManager:
    """
    Certified Database Manager guaranteeing transactional safety, shadow mode audit logs,
    CRE POS scanner flags (Inactive=0, ItemType=0, Dirty=1, Price, non-empty ItemName),
    dual-field AltSKU inventory upserts, detailed operational logging, and 1-click rollbacks.
    """

    def __init__(self, config_path: str = 'config.json'):
        self.config = self._load_config(config_path)
        self.conn_str = self._build_connection_string()
        self.sqlite_path = os.path.join(os.path.dirname(os.path.abspath(config_path)), "local_inventory.db")
        self.conn_type: Optional[str] = None  # 'pyodbc' or 'sqlite'
        self.conn: Any = None
        self.sample_store_id: str = self.config.get('default_store_id', '1001')
        self.sample_dept_id: str = self.config.get('default_dept_id', 'BEER')
        
        self.is_certified: bool = self.config.get('receiving_certified', True)
        self.normalizer = UPCNormalizer()
        self.logger = OperationalLogger()
        self._init_sqlite_db()

    def _load_config(self, config_path: str) -> dict:
        if not os.path.exists(config_path):
            return {
                "DB Server": "localhost",
                "DB Name": "cresql",
                "Trusted_Connection": True,
                "receiving_certified": True,
                "default_store_id": "1001",
                "default_dept_id": "BEER"
            }
        with open(config_path, 'r') as f:
            return json.load(f)

    def _build_connection_string(self) -> str:
        driver = self.config.get('DB_DRIVER', '{SQL Server}')
        server = self.config.get('DB Server', 'localhost')
        database = self.config.get('DB Name', 'cresql')
        if self.config.get('Trusted_Connection', True):
            return f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
        else:
            uid = self.config.get('DB_USER', '')
            pwd = self.config.get('DB_PASSWORD', '')
            return f"DRIVER={driver};SERVER={server};DATABASE={database};UID={uid};PWD={pwd};"

    def _init_sqlite_db(self):
        """Initialize local SQLite inventory and AltSKU fallback tables."""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Inventory (
                    Store_ID TEXT DEFAULT '1001',
                    ItemNum TEXT PRIMARY KEY,
                    ItemName TEXT,
                    Cost REAL,
                    Price REAL,
                    In_Stock REAL,
                    Vendor_Part_Num TEXT,
                    Helper_ItemNum TEXT,
                    Inactive INTEGER DEFAULT 0,
                    ItemType INTEGER DEFAULT 0,
                    Dirty INTEGER DEFAULT 1,
                    Tax_1 INTEGER DEFAULT 1,
                    Last_Updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Inventory_SKUS (
                    Store_ID TEXT DEFAULT '1001',
                    ItemNum TEXT,
                    AltSKU TEXT,
                    PRIMARY KEY (Store_ID, ItemNum, AltSKU)
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error initializing SQLite fallback: {e}")

    def connect(self) -> bool:
        """Connects to SQL Server via pyodbc or falls back to SQLite."""
        try:
            self.conn = pyodbc.connect(self.conn_str, autocommit=False)
            self.conn_type = 'pyodbc'
            self._detect_sample_context()
            return True
        except Exception as e:
            print(f"SQL Server PyODBC Connection failed: {e}. Falling back to SQLite.")
            try:
                self.conn = sqlite3.connect(self.sqlite_path, autocommit=False)
                self.conn_type = 'sqlite'
                return True
            except Exception as sqle:
                print(f"Database connection failed: {sqle}")
                self.conn = None
                self.conn_type = None
                return False

    def _detect_sample_context(self):
        """Finds an existing non-null Store_ID and valid Dept_ID from CRE SQL Server."""
        if not self.conn or self.conn_type != 'pyodbc':
            return
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT TOP 1 Store_ID FROM Inventory WHERE Store_ID IS NOT NULL AND Store_ID <> ''")
            row = cursor.fetchone()
            if row and row[0]:
                self.sample_store_id = str(row[0]).strip()

            cursor.execute("SELECT TOP 1 Dept_ID FROM Departments WHERE Dept_ID IS NOT NULL AND Dept_ID <> ''")
            dept_row = cursor.fetchone()
            if dept_row and dept_row[0]:
                self.sample_dept_id = str(dept_row[0]).strip()
        except Exception:
            pass

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            self.conn_type = None

    def post_invoice_receiving(
        self,
        header: InvoiceHeader,
        shadow_mode: bool = True,
        posting_enabled: bool = False
    ) -> Dict[str, Any]:
        """
        Main receiving execution engine enforcing shadow_mode, posting_enabled,
        atomic transactions, CRE POS scanner flags, and readback reconciliation.
        """
        transaction_id = f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{header.invoice_number}"
        results = {
            'transaction_id': transaction_id,
            'status': 'BLOCKED',
            'shadow_mode': shadow_mode,
            'posting_enabled': posting_enabled,
            'items_attempted': 0,
            'items_reconciled': 0,
            'reconciliation_failed': 0,
            'audit_log': [],
            'reconciliation_report': []
        }

        if posting_enabled and not shadow_mode and not self.is_certified:
            results['status'] = 'BLOCKED'
            results['audit_log'].append("SAFETY_BLOCK: Installation receiving behavior is not certified (receiving_certified=False). Live write blocked.")
            return results

        if not posting_enabled:
            results['status'] = 'SHADOW_MODE_ONLY'
            results['audit_log'].append("SHADOW_MODE: posting_enabled=False. Executing in dry-run audit mode.")
            return self._execute_shadow_mode(header, results)

        if shadow_mode:
            results['status'] = 'SHADOW_MODE_ONLY'
            results['audit_log'].append("SHADOW_MODE: shadow_mode=True. SQL statements generated and audited without mutating DB.")
            return self._execute_shadow_mode(header, results)

        return self._execute_live_atomic_receiving(header, results, transaction_id)

    def _execute_shadow_mode(self, header: InvoiceHeader, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generates shadow audit ledger without modifying database tables."""
        store_id = header.store_id or self.sample_store_id
        for item in header.line_items:
            if item.review_state != ReviewState.REVIEWED_APPROVED:
                continue

            raw_upc = str(item.raw_upc or item.raw_item_num)
            mapping = self.normalizer.determine_primary_and_alts(raw_upc, item.raw_item_num)
            qty = item.approved_actual_good_qty or item.expected_pos_qty or Decimal('0')
            cost = item.unit_cost
            price = cost * Decimal('1.30')
            desc = str(item.raw_description).strip() or f"ITEM {item.raw_item_num}"

            shadow_sql = (
                f"-- SHADOW MODE SQL (CRE POS Scanner Enabled - Inactive=0, ItemType=0, Dirty=1):\n"
                f"IF EXISTS (SELECT 1 FROM Inventory WHERE ItemNum = '{mapping['primary_item_num']}')\n"
                f"  UPDATE Inventory SET In_Stock = In_Stock + {qty}, Cost = {cost}, ItemName = '{desc[:30]}', Inactive = 0, ItemType = 0, Dirty = 1, Tax_1 = 1, Helper_ItemNum = '{mapping['helper_item_num']}' WHERE ItemNum = '{mapping['primary_item_num']}'\n"
                f"ELSE\n"
                f"  INSERT INTO Inventory (Store_ID, ItemNum, ItemName, Cost, Price, In_Stock, Helper_ItemNum, Inactive, ItemType, Dirty, Tax_1, Dept_ID) VALUES ('{store_id}', '{mapping['primary_item_num']}', '{desc[:30]}', {cost}, {price}, {qty}, '{mapping['helper_item_num']}', 0, 0, 1, 1, '{self.sample_dept_id}');\n"
            )
            for alt in mapping['alt_skus']:
                shadow_sql += f"INSERT INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES ('{store_id}', '{mapping['primary_item_num']}', '{alt}');\n"

            results['audit_log'].append(shadow_sql)
            results['items_reconciled'] += 1

        results['status'] = 'SHADOW_AUDIT_SUCCESS'
        return results

    def _execute_live_atomic_receiving(
        self,
        header: InvoiceHeader,
        results: Dict[str, Any],
        transaction_id: str
    ) -> Dict[str, Any]:
        """
        Executes live atomic receiving with CRE POS scanner compatibility flags (Inactive=0, ItemType=0, Dirty=1, Tax_1=1, non-empty ItemName).
        """
        if not self.conn:
            if not self.connect():
                results['status'] = 'DB_ERROR'
                results['audit_log'].append("DB_ERROR: Unable to establish database connection for live write.")
                return results

        cursor = self.conn.cursor()
        store_id = self.sample_store_id if (not header.store_id or header.store_id.startswith("STORE-")) else header.store_id
        dept_id = self.sample_dept_id
        items_logged = []

        try:
            for item in header.line_items:
                if item.review_state != ReviewState.REVIEWED_APPROVED:
                    continue

                results['items_attempted'] += 1
                raw_upc = str(item.raw_upc or item.raw_item_num)
                vendor_part = str(item.raw_item_num)[:20]
                add_qty = item.approved_actual_good_qty or item.expected_pos_qty or Decimal('0')
                cost = item.unit_cost
                price = cost * Decimal('1.30')
                desc = str(item.raw_description).strip() or f"ITEM {vendor_part or raw_upc[-6:]}"
                desc = desc[:30]

                # Generate Normalized UPC variants
                upc_variants = list(self.normalizer.generate_variants(raw_upc))
                if vendor_part and vendor_part not in upc_variants:
                    upc_variants.append(vendor_part)

                # Lookup existing item
                query_placeholders = ",".join(["?"] * len(upc_variants)) if upc_variants else "?"
                query_args = upc_variants if upc_variants else [raw_upc]

                cursor.execute(
                    f"""SELECT ItemNum, In_Stock, Cost, Price, ItemName FROM Inventory 
                        WHERE ItemNum IN ({query_placeholders}) 
                           OR Helper_ItemNum IN ({query_placeholders}) 
                           OR Vendor_Part_Num IN ({query_placeholders})
                           OR ItemNum IN (SELECT ItemNum FROM Inventory_SKUS WHERE AltSKU IN ({query_placeholders}))""",
                    query_args * 4
                )
                row = cursor.fetchone()

                if row:
                    action_type = "UPDATE"
                    matched_upc = str(row[0]).strip()
                    initial_stock = Decimal(str(row[1])) if row[1] is not None else Decimal('0')
                    initial_cost = Decimal(str(row[2])) if row[2] is not None else Decimal('0.00')
                    existing_name = str(row[4]).strip() if row[4] else ""

                    target_upc = matched_upc
                    helper_upc = upc_variants[0] if (upc_variants and upc_variants[0] != target_upc) else ""
                    final_name = desc if (not existing_name or existing_name == '0.0') else existing_name

                    cursor.execute(
                        """UPDATE Inventory 
                           SET In_Stock = In_Stock + ?, Cost = ?, Price = CASE WHEN Price IS NULL OR Price = 0 THEN ? ELSE Price END,
                               ItemName = ?, Vendor_Part_Num = ?, Helper_ItemNum = ?, Inactive = 0, ItemType = 0, Dirty = 1, Tax_1 = 1
                           WHERE ItemNum = ?""",
                        (float(add_qty), float(cost), float(price), final_name, vendor_part, helper_upc, target_upc)
                    )
                else:
                    action_type = "INSERT"
                    mapping = self.normalizer.determine_primary_and_alts(raw_upc, vendor_part)
                    target_upc = mapping["primary_item_num"]
                    helper_upc = mapping["helper_item_num"]
                    initial_stock = Decimal('0')
                    initial_cost = Decimal('0.00')

                    if self.conn_type == 'pyodbc':
                        cursor.execute(
                            """INSERT INTO Inventory (
                                Store_ID, ItemNum, ItemName, Cost, Price, In_Stock, Vendor_Part_Num, Helper_ItemNum, Dept_ID,
                                Inactive, ItemType, Dirty, Tax_1, Tax_2, Tax_3, IsKit, IsModifier, Count_This_Item, Print_On_Receipt,
                                Reorder_Level, Reorder_Quantity, Inv_Num_Barcode_Labels, Use_Serial_Numbers, Num_Bonus_Points, IsRental,
                                Use_Bulk_Pricing, Print_Ticket, Print_Voucher, Num_Days_Valid, IsMatrixItem,
                                AutoWeigh, FoodStampable, Exclude_Acct_Limit, Check_ID, Prompt_Price,
                                Prompt_Quantity, Allow_BuyBack, Special_Permission, Prompt_Description,
                                Check_ID2, Transfer_Markup_Enabled, As_Is, Import_Markup, PricePerMeasure,
                                AvailableOnline, DoughnutTax, DisableInventoryUpload, InvoiceLimitQty, ItemCategory, IsRestrictedPerInvoice
                            ) VALUES (
                                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                0, 0, 1, 1, 0, 0, 0, 0, 1, 1,
                                0.0, 0.0, 0, 0, 0, 0,
                                0, 0, 0, 0, 0,
                                0, 0, 0, 0, 0,
                                0, 0, 0, 0,
                                0, 0, 0, 0.0, 0.0,
                                0, 0, 0, 0.0, 0, 0
                            )""",
                            (store_id, target_upc, desc, float(cost), float(price), float(add_qty), vendor_part, helper_upc, dept_id)
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO Inventory (Store_ID, ItemNum, ItemName, Cost, Price, In_Stock, Vendor_Part_Num, Helper_ItemNum, Inactive, ItemType, Dirty, Tax_1) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1, 1)",
                            (store_id, target_upc, desc, float(cost), float(price), float(add_qty), vendor_part, helper_upc)
                        )

                # Upsert Alternate Barcodes into Inventory_SKUS table
                alts_added = []
                for alt_code in upc_variants:
                    if alt_code != target_upc and len(alt_code) >= 6:
                        try:
                            if self.conn_type == 'pyodbc':
                                cursor.execute(
                                    """IF NOT EXISTS (SELECT 1 FROM Inventory_SKUS WHERE Store_ID = ? AND ItemNum = ? AND AltSKU = ?)
                                       INSERT INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES (?, ?, ?)""",
                                    (store_id, target_upc, alt_code, store_id, target_upc, alt_code)
                                )
                            else:
                                cursor.execute(
                                    "INSERT OR IGNORE INTO Inventory_SKUS (Store_ID, ItemNum, AltSKU) VALUES (?, ?, ?)",
                                    (store_id, target_upc, alt_code)
                                )
                            alts_added.append(alt_code)
                        except Exception:
                            pass

                # READBACK RECONCILIATION
                cursor.execute("SELECT In_Stock FROM Inventory WHERE ItemNum = ?", (target_upc,))
                post_row = cursor.fetchone()
                final_stock = Decimal(str(post_row[0])) if post_row and post_row[0] is not None else Decimal('0')
                expected_final_stock = initial_stock + add_qty

                if abs(final_stock - expected_final_stock) < Decimal('0.01'):
                    results['items_reconciled'] += 1
                    msg = f"LIVE_RECONCILED: Item {target_upc} ({desc[:20]}) - Initial Stock: {initial_stock}, Added: {add_qty}, Final Stock: {final_stock} [POS Enabled]"
                    results['reconciliation_report'].append(msg)

                    items_logged.append({
                        "item_num": target_upc,
                        "description": desc,
                        "action_type": action_type,
                        "initial_stock": float(initial_stock),
                        "added_qty": float(add_qty),
                        "final_stock": float(final_stock),
                        "initial_cost": float(initial_cost),
                        "new_cost": float(cost),
                        "alt_skus_added": alts_added
                    })
                else:
                    results['reconciliation_failed'] += 1
                    raise ValueError(f"RECONCILIATION_FAILED: Item {target_upc} readback mismatched! Expected {expected_final_stock}, got {final_stock}.")

            # Commit Transaction
            self.conn.commit()
            results['status'] = f"LIVE_SUCCESS ({self.conn_type.upper()})"
            results['audit_log'].append(f"TRANSACTION_COMMITTED: {results['items_reconciled']} items written & reconciled with POS Scanner Flags.")

            self.logger.log_transaction(
                transaction_id=transaction_id,
                invoice_number=header.invoice_number,
                vendor_name=header.vendor_name,
                store_id=store_id,
                status=results['status'],
                items_detail=items_logged,
                execution_mode="LIVE"
            )

        except Exception as e:
            err_msg = f"{e}\n{traceback.format_exc()}"
            if self.conn:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            results['status'] = 'TRANSACTION_ROLLED_BACK'
            results['audit_log'].append(f"TRANSACTION_FAILED: Rollback triggered due to error: {err_msg}")

        return results

    def rollback_receiving_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Rolls back a receiving transaction by restoring previous inventory stock levels,
        reverting unit costs, and removing added AltSKUs.
        """
        log_record = self.logger.get_log_by_id(transaction_id)
        if not log_record:
            return {"status": "ERROR", "message": f"Transaction ID '{transaction_id}' not found in operational logs."}

        if log_record.get("rolled_back", False):
            return {"status": "ALREADY_ROLLED_BACK", "message": f"Transaction '{transaction_id}' was already rolled back."}

        if not self.conn:
            if not self.connect():
                return {"status": "DB_ERROR", "message": "Unable to connect to database for rollback."}

        cursor = self.conn.cursor()
        reverted_count = 0
        deleted_count = 0

        try:
            for item in log_record.get("items_detail", []):
                item_num = item["item_num"]
                added_qty = item["added_qty"]
                initial_cost = item["initial_cost"]
                action_type = item["action_type"]
                alt_skus = item.get("alt_skus_added", [])

                for alt in alt_skus:
                    cursor.execute("DELETE FROM Inventory_SKUS WHERE ItemNum = ? AND AltSKU = ?", (item_num, alt))

                if action_type == "INSERT":
                    cursor.execute("DELETE FROM Inventory WHERE ItemNum = ?", (item_num,))
                    deleted_count += 1
                else:
                    cursor.execute(
                        "UPDATE Inventory SET In_Stock = In_Stock - ?, Cost = ? WHERE ItemNum = ?",
                        (added_qty, initial_cost, item_num)
                    )
                    reverted_count += 1

            self.conn.commit()
            self.logger.mark_rolled_back(transaction_id)
            return {
                "status": "ROLLBACK_SUCCESS",
                "transaction_id": transaction_id,
                "reverted_items": reverted_count,
                "deleted_items": deleted_count,
                "message": f"Successfully rolled back transaction '{transaction_id}'."
            }

        except Exception as e:
            if self.conn:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            return {"status": "ROLLBACK_FAILED", "message": f"Rollback failed due to error: {e}"}

    def get_inventory_records(self) -> List[Dict[str, Any]]:
        """Retrieve current inventory table contents for audit/verification (returns up to 200 records)."""
        if not self.conn:
            if not self.connect():
                return []
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT TOP 200 Store_ID, ItemNum, ItemName, Cost, Price, In_Stock, Vendor_Part_Num, Helper_ItemNum, Inactive, Dirty FROM Inventory WHERE Vendor_Part_Num IS NOT NULL AND Vendor_Part_Num <> '' ORDER BY In_Stock DESC")
            rows = cursor.fetchall()
            return [
                {
                    "Store_ID": str(r[0]),
                    "ItemNum": str(r[1]),
                    "ItemName": str(r[2]),
                    "Cost": float(r[3]) if r[3] is not None else 0.0,
                    "Price": float(r[4]) if r[4] is not None else 0.0,
                    "In_Stock": float(r[5]) if r[5] is not None else 0.0,
                    "Vendor_Part_Num": str(r[6]) if r[6] is not None else "",
                    "Helper_ItemNum": str(r[7]) if r[7] is not None else "",
                    "Inactive": int(r[8]) if r[8] is not None else 0,
                    "Dirty": bool(r[9]) if r[9] is not None else False
                }
                for r in rows
            ]
        except Exception as e:
            print(f"Error fetching inventory records: {e}")
            return []


# Compatible alias for existing scripts
DBManager = CertifiedDBManager
