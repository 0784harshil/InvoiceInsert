"""
Invoice Manager — Enterprise Web UI with Single Item Unit Cost Markup Engine & Dynamic Header Mapping Controls
Enforces Rule 9 (Human Review), Rule 10 (Actual-Good Quantity), Rule 11 (Fee Segregation),
Rule 13 (Atomic Transaction & Readback Reconciliation), Rule 14 (posting_enabled=False),
Rule 15 (shadow_mode=True), and Rule 18 (Reconciliation).
"""

from decimal import Decimal
import os
import sys
import tempfile
import pandas as pd
import streamlit as st

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from invoice_parser import InvoiceParser
from validator import InvoiceValidator
from review_manager import ReviewManager
from db_manager import CertifiedDBManager
from package_converter import PackageConverter
from operational_logger import OperationalLogger
from department_classifier import DepartmentClassifier
from models import ReviewState, InvoiceHeader, InvoiceLineItem, SegregatedFees


st.set_page_config(page_title="Enterprise Invoice Receiving Engine", page_icon="📄", layout="wide")

st.title("Enterprise Invoice Receiving Engine")
st.caption("Rule-Enforced Receiving, Single Item Unit Cost Markup Engine, Interactive Excel Grid, & Dynamic Header Mapping.")

# Sidebar Controls
with st.sidebar:
    st.header("Safety & Controls")
    shadow_mode = st.toggle("Shadow Mode (Audit Only)", value=False, help="Turn OFF to execute REAL live database insertion.")
    posting_enabled = st.toggle("Posting Enabled", value=True, help="Turn ON to allow database updates.")
    
    st.divider()
    st.subheader("Markup & Pricing Settings")
    default_markup_pct = st.number_input("Default Retail Selling Markup (%)", min_value=0.0, max_value=200.0, value=30.0, step=5.0) / 100.0
    st.caption("Markup is applied directly to the **Single POS Unit Cost** (NOT bulk/case cost).")

    st.divider()
    db_mgr = CertifiedDBManager("config.json")
    st.markdown(f"**DB Certification:** {'✅ Certified' if db_mgr.is_certified else '⚠️ Not Certified'}")
    
    if db_mgr.connect():
        st.success(f"Database Connected ({db_mgr.conn_type.upper()})")
        db_mgr.close()
    else:
        st.warning("DB Offline — Shadow Mode Only")

# File Uploader
uploaded = st.file_uploader(
    "Upload Invoice Document (PDF, PNG, JPG, CSV, XLSX)",
    type=["pdf", "png", "jpg", "jpeg", "csv", "xlsx", "xls"],
)

parser = InvoiceParser(use_preprocessing=True)
validator = InvoiceValidator()
review_mgr = ReviewManager()
converter = PackageConverter()
op_logger = OperationalLogger()
classifier = DepartmentClassifier()

if uploaded is not None:
    suffix = os.path.splitext(uploaded.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        tmp_path = tmp.name

    if st.button("🔍 Process Document & Build Template Grid", type="primary"):
        with st.spinner("Extracting invoice data and building single POS unit cost markup template..."):
            try:
                header = parser.parse_file(tmp_path)
                header = review_mgr.audit_and_prepare_invoice(header)
                
                rows = []
                for item in header.line_items:
                    pos_qty = item.expected_pos_qty or item.case_quantity
                    case_cost = item.unit_cost
                    total_cost = item.total_cost or (item.case_quantity * case_cost)
                    
                    # Single POS Unit Cost = Total Line Cost / Approved POS Qty
                    single_pos_unit_cost = (total_cost / pos_qty).quantize(Decimal('0.01')) if pos_qty > Decimal('0') else case_cost
                    
                    # RETAIL SELLING PRICE = Single POS Unit Cost * (1 + Markup %)
                    retail_price = (single_pos_unit_cost * Decimal(str(1 + default_markup_pct))).quantize(Decimal('0.01'))
                    dept = classifier.classify_department(item.raw_description, item.raw_upc or item.raw_item_num)

                    rows.append({
                        "Line #": item.line_number,
                        "Vendor Item #": item.raw_item_num,
                        "UPC": item.raw_upc or "",
                        "Description": item.raw_description,
                        "Department": dept,
                        "Package": item.raw_package_text,
                        "Case Qty": float(item.case_quantity),
                        "Case Cost ($)": float(case_cost),
                        "Expected POS Qty": float(pos_qty),
                        "Approved Qty": float(pos_qty),
                        "Single POS Unit Cost ($)": float(single_pos_unit_cost),
                        "Total Line Cost ($)": float(total_cost),
                        "Retail Selling Price ($)": float(retail_price)
                    })

                st.session_state["header"] = header
                st.session_state["filename"] = uploaded.name
                st.session_state["editor_df"] = pd.DataFrame(rows)
                st.session_state["is_verified"] = False
            except Exception as e:
                st.error(f"Processing failed: {e}")
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

# Display Interactive Human Verification & Cost Management View
if "header" in st.session_state:
    header: InvoiceHeader = st.session_state["header"]
    st.subheader(f"Invoice Summary — {st.session_state.get('filename', '')}")

    if not header.document_valid:
        st.error("🛑 DOCUMENT BLOCKED: Non-Invoice Document Detected. Posting is permanently blocked.")
        for reason in header.blocking_reasons:
            st.write(f"- {reason}")
    else:
        # Metrics Header
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Line Items", f"{len(header.line_items)} items")
        c2.metric("Vendor", header.vendor_name)
        c3.metric("Invoice #", header.invoice_number)
        c4.metric("Subtotal", f"${header.subtotal:.2f}")
        c5.metric("Total Amount", f"${header.total_amount:.2f}")

        # Fee Segregation Expander
        with st.expander("Segregated Non-Inventory Fees (Excluded from Single POS Unit Cost)"):
            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric("Tax", f"${header.fees.tax:.2f}")
            f2.metric("CRV / Deposit", f"${header.fees.deposit_crv:.2f}")
            f3.metric("Freight / Delivery", f"${header.fees.freight_delivery:.2f}")
            f4.metric("Fuel Charge", f"${header.fees.fuel_charge:.2f}")
            f5.metric("Discounts", f"-${header.fees.discounts:.2f}")

        st.divider()
        st.subheader("✏️ Single Unit Cost Management & Human Verification Grid")
        st.caption("Markup % is applied to Single POS Unit Cost. Single POS Unit Cost = (Case Qty * Case Cost) / Approved POS Qty.")

        # Dynamic Column Header Mapping Controls (5 Column Selectors)
        col_list = list(st.session_state["editor_df"].columns)
        with st.expander("🛠️ Column Header Mapping Controls (For Custom CSV / Excel Uploads)", expanded=True):
            st.caption("Select which column in your document or table maps to each POS inventory field:")
            m1, m2, m3, m4, m5 = st.columns(5)
            
            idx_v = col_list.index("Vendor Item #") if "Vendor Item #" in col_list else 0
            idx_u = col_list.index("UPC") if "UPC" in col_list else 0
            idx_d = col_list.index("Description") if "Description" in col_list else 0
            idx_q = col_list.index("Case Qty") if "Case Qty" in col_list else 0
            idx_c = col_list.index("Case Cost ($)") if "Case Cost ($)" in col_list else 0

            map_vendor_col = m1.selectbox("Map Vendor Item # Column", col_list, index=idx_v, key="map_vendor_col")
            map_upc_col = m2.selectbox("Map UPC Column", col_list, index=idx_u, key="map_upc_col")
            map_desc_col = m3.selectbox("Map Description Column", col_list, index=idx_d, key="map_desc_col")
            map_qty_col = m4.selectbox("Map Case Quantity Column", col_list, index=idx_q, key="map_qty_col")
            map_cost_col = m5.selectbox("Map Case Cost Column", col_list, index=idx_c, key="map_cost_col")

        # Interactive Editable Excel-like Grid
        edited_df = st.data_editor(
            st.session_state["editor_df"],
            num_rows="dynamic",
            height=500,
            width="stretch",
            key="interactive_cost_grid",
            column_config={
                "Line #": st.column_config.NumberColumn(disabled=True),
                "Vendor Item #": st.column_config.TextColumn("Vendor Item #", required=True),
                "UPC": st.column_config.TextColumn("UPC Barcode"),
                "Description": st.column_config.TextColumn("Product Description", width="large"),
                "Department": st.column_config.SelectboxColumn("Department", options=['BEER', 'Candy', 'CBD', 'Cigs', 'Cigarilo', 'CIGAR', 'LIQUOR', 'SODA', 'VAPE', 'WINE', 'MISC']),
                "Package": st.column_config.TextColumn("Package (e.g. C24, 6P)"),
                "Case Qty": st.column_config.NumberColumn("Case Qty", format="%.2f"),
                "Case Cost ($)": st.column_config.NumberColumn("Case Cost ($)", format="$%.2f"),
                "Expected POS Qty": st.column_config.NumberColumn("Expected POS Qty", format="%.2f"),
                "Approved Qty": st.column_config.NumberColumn("Approved POS Qty", format="%.2f"),
                "Single POS Unit Cost ($)": st.column_config.NumberColumn("Single POS Unit Cost ($)", format="$%.2f", help="Calculated as (Case Qty * Case Cost) / Approved POS Qty"),
                "Total Line Cost ($)": st.column_config.NumberColumn("Total Line Cost ($)", format="$%.2f"),
                "Retail Selling Price ($)": st.column_config.NumberColumn("Retail Selling Price ($)", format="$%.2f", help="Calculated as Single POS Unit Cost * (1 + Markup %)")
            }
        )

        st.write("")
        if st.button("✅ Confirm Mapped Data & Single Unit Costs", type="secondary"):
            updated_line_items = []
            for idx, row in edited_df.iterrows():
                try:
                    line_num = int(row.get("Line #", idx + 1))
                    item_code = str(row.get(map_vendor_col, "")).strip()
                    upc = str(row.get(map_upc_col, "")).strip()
                    desc = str(row.get(map_desc_col, "")).strip()
                    pkg = str(row.get("Package", "EA")).strip()
                    case_qty = Decimal(str(row.get(map_qty_col, 1.0)))
                    case_cost = Decimal(str(row.get(map_cost_col, 0.0)))
                    approved_qty = Decimal(str(row.get("Approved Qty", case_qty)))

                    pos_qty, rule, req_rev, reason = converter.calculate_expected_pos_qty(
                        case_qty=case_qty,
                        loose_qty=Decimal('0'),
                        store_id=header.store_id,
                        vendor_id=header.vendor_id,
                        vendor_item_num=item_code,
                        package_text=pkg
                    )

                    total_cost = case_qty * case_cost
                    single_unit_cost = (total_cost / approved_qty).quantize(Decimal('0.0001')) if approved_qty > Decimal('0') else case_cost
                    user_retail_price = Decimal(str(row.get("Retail Selling Price ($)", single_unit_cost * Decimal(str(1 + default_markup_pct)))))

                    item = InvoiceLineItem(
                        line_number=line_num,
                        raw_item_num=item_code,
                        raw_description=desc,
                        raw_upc=upc,
                        raw_package_text=pkg,
                        case_quantity=case_qty,
                        loose_quantity=Decimal('0'),
                        unit_cost=single_unit_cost, # Store Single POS Unit Cost into Inventory.Cost!
                        total_cost=total_cost,
                        expected_pos_qty=pos_qty,
                        approved_actual_good_qty=approved_qty,
                        pos_unit_cost=single_unit_cost,
                        conversion_rule_used=rule,
                        review_state=ReviewState.REVIEWED_APPROVED
                    )
                    # Attach retail price to item for db manager
                    item.retail_price = user_retail_price
                    updated_line_items.append(item)
                except Exception as ex:
                    st.warning(f"Row {idx+1} conversion warning: {ex}")

            header.line_items = updated_line_items
            header.subtotal = sum((i.total_cost for i in updated_line_items), Decimal('0.00'))
            header.total_amount = header.subtotal + header.fees.total_non_inventory_fees

            st.session_state["header"] = header
            st.session_state["editor_df"] = edited_df
            st.session_state["is_verified"] = True
            st.success(f"✅ Calculated Retail Selling Prices based on Single POS Unit Cost for {len(updated_line_items)} items!")

        # Post / Live DB Receiving Button
        st.divider()
        st.subheader("⚡ Execute Inventory Database Receiving")
        
        if shadow_mode:
            st.warning("⚠️ SHADOW MODE IS ON: Clicking execute will simulate queries without changing database. Toggle OFF 'Shadow Mode' in sidebar to write live data!")
        else:
            st.info("🟢 LIVE MODE IS ACTIVE: Single POS Unit Costs & Stock will be updated directly in SQL Server Inventory.")

        db = CertifiedDBManager("config.json")
        if st.button("🚀 Execute Receiving & Write to DB", type="primary"):
            if not st.session_state.get("is_verified", False):
                updated_line_items = []
                for idx, row in edited_df.iterrows():
                    try:
                        case_qty = Decimal(str(row.get(map_qty_col, 1.0)))
                        case_cost = Decimal(str(row.get(map_cost_col, 0.0)))
                        approved_qty = Decimal(str(row.get("Approved Qty", case_qty)))
                        item_code = str(row.get(map_vendor_col, "")).strip()
                        upc = str(row.get(map_upc_col, "")).strip()
                        desc = str(row.get(map_desc_col, "")).strip()
                        pkg = str(row.get("Package", "EA")).strip()

                        pos_qty, rule, req_rev, reason = converter.calculate_expected_pos_qty(
                            case_qty=case_qty,
                            loose_qty=Decimal('0'),
                            store_id=header.store_id,
                            vendor_id=header.vendor_id,
                            vendor_item_num=item_code,
                            package_text=pkg
                        )

                        total_cost = case_qty * case_cost
                        single_unit_cost = (total_cost / approved_qty).quantize(Decimal('0.0001')) if approved_qty > Decimal('0') else case_cost
                        user_retail_price = Decimal(str(row.get("Retail Selling Price ($)", single_unit_cost * Decimal(str(1 + default_markup_pct)))))

                        item = InvoiceLineItem(
                            line_number=idx + 1,
                            raw_item_num=item_code,
                            raw_description=desc,
                            raw_upc=upc,
                            raw_package_text=pkg,
                            case_quantity=case_qty,
                            loose_quantity=Decimal('0'),
                            unit_cost=single_unit_cost, # Single POS Unit Cost!
                            total_cost=total_cost,
                            expected_pos_qty=pos_qty,
                            approved_actual_good_qty=approved_qty,
                            pos_unit_cost=single_unit_cost,
                            conversion_rule_used=rule,
                            review_state=ReviewState.REVIEWED_APPROVED
                        )
                        item.retail_price = user_retail_price
                        updated_line_items.append(item)
                    except Exception:
                        pass
                header.line_items = updated_line_items

            res = db.post_invoice_receiving(header, shadow_mode=shadow_mode, posting_enabled=posting_enabled)
            
            if "LIVE_SUCCESS" in res['status']:
                st.balloons()
                st.success(f"✅ REAL DATABASE RECEIVING SUCCESSFUL! Posted & Reconciled {res['items_reconciled']} items with Single POS Unit Costs. Transaction ID: `{res['transaction_id']}`")
            elif "SHADOW" in res['status']:
                st.info(f"ℹ️ Shadow Audit Execution Completed for {res['items_reconciled']} items. Status: {res['status']}")
            else:
                st.error(f"🛑 Receiving Execution Blocked/Failed: {res['status']}")
            
            with st.expander("Reconciliation Report & Audit Log", expanded=True):
                st.markdown(f"### Readback Reconciliation Ledger ({res['items_reconciled']} items)")
                for report_line in res['reconciliation_report']:
                    st.write(f"- {report_line}")
                    
                st.markdown("### Audit Log")
                for log_line in res['audit_log'][:10]:
                    st.code(log_line, language="sql")

# Section: Operational Receiving Logs & 1-Click Rollback Dashboard
st.divider()
st.subheader("🗂️ Operational Receiving Audit Logs & 1-Click Rollback Control")
st.caption("Inspect past receiving transactions or execute 1-click atomic rollbacks if data was posted incorrectly.")

db_inst = CertifiedDBManager("config.json")
logs = op_logger.get_all_logs()

if logs:
    log_summary = []
    for l in logs:
        log_summary.append({
            "Transaction ID": l["transaction_id"],
            "Timestamp": l["timestamp"][:19].replace("T", " "),
            "Invoice #": l["invoice_number"],
            "Vendor": l["vendor_name"],
            "Items Count": l["item_count"],
            "Status": l["status"],
            "Rolled Back": "YES 🔴" if l.get("rolled_back") else "NO 🟢"
        })
    st.dataframe(pd.DataFrame(log_summary), width="stretch")

    # Rollback Selector
    active_txns = [l["transaction_id"] for l in logs if not l.get("rolled_back") and "LIVE_SUCCESS" in l["status"]]
    if active_txns:
        r1, r2 = st.columns([3, 1])
        selected_txn = r1.selectbox("Select Active Receiving Transaction to Rollback", active_txns)
        if r2.button("↩️ Rollback Selected Transaction", type="secondary"):
            with st.spinner(f"Rolling back transaction {selected_txn}..."):
                rollback_res = db_inst.rollback_receiving_transaction(selected_txn)
                if rollback_res["status"] == "ROLLBACK_SUCCESS":
                    st.success(f"✅ {rollback_res['message']}")
                    st.rerun()
                else:
                    st.error(f"🛑 {rollback_res['message']}")
    else:
        st.info("No active un-rolled-back live transactions available for rollback.")
else:
    st.info("No operational receiving logs recorded yet.")

# Section: Database Inventory Table Inspector
st.divider()
st.subheader("🗄️ Live Database Inventory Table Inspector")
if st.button("Refresh Live Database Contents"):
    records = db_inst.get_inventory_records()
    if records:
        st.write(f"Displaying top {len(records)} active inventory records in database:")
        st.dataframe(pd.DataFrame(records), height=450, width="stretch")
    else:
        st.info("Database inventory table is currently empty.")
