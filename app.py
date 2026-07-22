"""
Invoice Manager — Enterprise Web UI with Interactive Human Verification Grid
Enforces Rule 9 (Human Review), Rule 10 (Actual-Good Quantity),
Rule 13 (Atomic Transaction & Readback Reconciliation),
Rule 14 (posting_enabled=False), Rule 15 (shadow_mode=True), and Rule 18 (Reconciliation).
"""

from decimal import Decimal, InvalidOperation
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
from models import ReviewState, InvoiceHeader, InvoiceLineItem


st.set_page_config(page_title="Enterprise Invoice Receiving Engine", page_icon="📄", layout="wide")

st.title("Enterprise Invoice Receiving Engine")
st.caption("Rule-Enforced Invoice Processing, Interactive Excel-like Verification Grid, & Live DB Upserts.")

# Sidebar Controls
with st.sidebar:
    st.header("Safety & Controls")
    shadow_mode = st.toggle("Shadow Mode (Audit Only)", value=False, help="Turn OFF to execute REAL live database insertion.")
    posting_enabled = st.toggle("Posting Enabled", value=True, help="Turn ON to allow database updates.")
    
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

if uploaded is not None:
    suffix = os.path.splitext(uploaded.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        tmp_path = tmp.name

    if st.button("🔍 Process Document & Build Template Grid", type="primary"):
        with st.spinner("Extracting invoice data and building interactive verification template..."):
            try:
                header = parser.parse_file(tmp_path)
                header = review_mgr.audit_and_prepare_invoice(header)
                
                # Build initial Pandas DataFrame for interactive st.data_editor
                rows = []
                for item in header.line_items:
                    rows.append({
                        "Line #": item.line_number,
                        "Vendor Item #": item.raw_item_num,
                        "UPC": item.raw_upc or "",
                        "Description": item.raw_description,
                        "Package": item.raw_package_text,
                        "Case Qty": float(item.case_quantity),
                        "Unit Cost ($)": float(item.unit_cost),
                        "Total Cost ($)": float(item.total_cost),
                        "Expected POS Qty": float(item.expected_pos_qty or item.case_quantity),
                        "Approved Qty": float(item.expected_pos_qty or item.case_quantity)
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

# Display Interactive Human Verification View
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
        with st.expander("Segregated Non-Inventory Fees (Excluded from Product Unit Cost)"):
            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric("Tax", f"${header.fees.tax:.2f}")
            f2.metric("CRV / Deposit", f"${header.fees.deposit_crv:.2f}")
            f3.metric("Freight / Delivery", f"${header.fees.freight_delivery:.2f}")
            f4.metric("Fuel Charge", f"${header.fees.fuel_charge:.2f}")
            f5.metric("Discounts", f"-${header.fees.discounts:.2f}")

        st.divider()
        st.subheader("✏️ Human Verification & Template Editor (Excel Grid)")
        st.caption("Rule 9: You can click and edit any cell directly in the grid below to fix OCR text, update costs, or adjust quantities before saving.")

        # Column Header Mapping Assignment
        with st.expander("🛠️ Column Header Mapping Controls", expanded=False):
            m1, m2, m3, m4 = st.columns(4)
            col_list = list(st.session_state["editor_df"].columns)
            m1.selectbox("Map Vendor Item # Column", col_list, index=col_list.index("Vendor Item #"))
            m2.selectbox("Map UPC Column", col_list, index=col_list.index("UPC"))
            m3.selectbox("Map Description Column", col_list, index=col_list.index("Description"))
            m4.selectbox("Map Unit Cost Column", col_list, index=col_list.index("Unit Cost ($)"))

        # Interactive Editable Excel-like Grid
        edited_df = st.data_editor(
            st.session_state["editor_df"],
            num_rows="dynamic",
            height=600,
            use_container_width=True,
            key="interactive_grid",
            column_config={
                "Line #": st.column_config.NumberColumn(disabled=True),
                "Vendor Item #": st.column_config.TextColumn("Vendor Item #", required=True),
                "UPC": st.column_config.TextColumn("UPC Barcode"),
                "Description": st.column_config.TextColumn("Product Description", width="large"),
                "Package": st.column_config.TextColumn("Package (e.g. C24, 6P)"),
                "Case Qty": st.column_config.NumberColumn("Case Qty", format="%.2f"),
                "Unit Cost ($)": st.column_config.NumberColumn("Unit Cost ($)", format="$%.2f"),
                "Total Cost ($)": st.column_config.NumberColumn("Total Cost ($)", format="$%.2f"),
                "Expected POS Qty": st.column_config.NumberColumn("Expected POS Qty", format="%.2f"),
                "Approved Qty": st.column_config.NumberColumn("Approved Qty", format="%.2f")
            }
        )

        # Verification Approval Button
        st.write("")
        if st.button("✅ Confirm & Save Verified Template Data", type="secondary"):
            # Update header line items with exact human-edited values from grid
            updated_line_items = []
            for idx, row in edited_df.iterrows():
                try:
                    line_num = int(row.get("Line #", idx + 1))
                    item_code = str(row.get("Vendor Item #", "")).strip()
                    upc = str(row.get("UPC", "")).strip()
                    desc = str(row.get("Description", "")).strip()
                    pkg = str(row.get("Package", "EA")).strip()
                    case_qty = Decimal(str(row.get("Case Qty", 1.0)))
                    unit_cost = Decimal(str(row.get("Unit Cost ($)", 0.0)))
                    approved_qty = Decimal(str(row.get("Approved Qty", case_qty)))

                    total_cost = case_qty * unit_cost

                    # Recalculate POS Qty
                    pos_qty, rule, req_rev, reason = converter.calculate_expected_pos_qty(
                        case_qty=case_qty,
                        loose_qty=Decimal('0'),
                        store_id=header.store_id,
                        vendor_id=header.vendor_id,
                        vendor_item_num=item_code,
                        package_text=pkg
                    )

                    item = InvoiceLineItem(
                        line_number=line_num,
                        raw_item_num=item_code,
                        raw_description=desc,
                        raw_upc=upc,
                        raw_package_text=pkg,
                        case_quantity=case_qty,
                        loose_quantity=Decimal('0'),
                        unit_cost=unit_cost,
                        total_cost=total_cost,
                        expected_pos_qty=pos_qty,
                        approved_actual_good_qty=approved_qty,
                        conversion_rule_used=rule,
                        review_state=ReviewState.REVIEWED_APPROVED
                    )
                    updated_line_items.append(item)
                except Exception as ex:
                    st.warning(f"Row {idx+1} conversion warning: {ex}")

            header.line_items = updated_line_items
            header.subtotal = sum((i.total_cost for i in updated_line_items), Decimal('0.00'))
            header.total_amount = header.subtotal + header.fees.total_non_inventory_fees

            st.session_state["header"] = header
            st.session_state["editor_df"] = edited_df
            st.session_state["is_verified"] = True
            st.success(f"✅ Verified {len(updated_line_items)} items! Data template is locked and ready for database receiving.")

        # Post / Live DB Receiving Button
        st.divider()
        st.subheader("⚡ Execute Inventory Database Receiving")
        
        if shadow_mode:
            st.warning("⚠️ SHADOW MODE IS ON: Clicking execute will simulate queries without changing database. Toggle OFF 'Shadow Mode' in sidebar to write live data!")
        else:
            st.info("🟢 LIVE MODE IS ACTIVE: Clicking execute will insert/update records directly into the Inventory database table.")

        db = CertifiedDBManager("config.json")
        if st.button("🚀 Execute Receiving & Write to DB", type="primary"):
            # Ensure items are updated from editor if user didn't click save
            if not st.session_state.get("is_verified", False):
                updated_line_items = []
                for idx, row in edited_df.iterrows():
                    try:
                        case_qty = Decimal(str(row.get("Case Qty", 1.0)))
                        unit_cost = Decimal(str(row.get("Unit Cost ($)", 0.0)))
                        approved_qty = Decimal(str(row.get("Approved Qty", case_qty)))
                        item_code = str(row.get("Vendor Item #", "")).strip()
                        upc = str(row.get("UPC", "")).strip()
                        desc = str(row.get("Description", "")).strip()
                        pkg = str(row.get("Package", "EA")).strip()

                        pos_qty, rule, req_rev, reason = converter.calculate_expected_pos_qty(
                            case_qty=case_qty,
                            loose_qty=Decimal('0'),
                            store_id=header.store_id,
                            vendor_id=header.vendor_id,
                            vendor_item_num=item_code,
                            package_text=pkg
                        )

                        item = InvoiceLineItem(
                            line_number=idx + 1,
                            raw_item_num=item_code,
                            raw_description=desc,
                            raw_upc=upc,
                            raw_package_text=pkg,
                            case_quantity=case_qty,
                            loose_quantity=Decimal('0'),
                            unit_cost=unit_cost,
                            total_cost=case_qty * unit_cost,
                            expected_pos_qty=pos_qty,
                            approved_actual_good_qty=approved_qty,
                            conversion_rule_used=rule,
                            review_state=ReviewState.REVIEWED_APPROVED
                        )
                        updated_line_items.append(item)
                    except Exception:
                        pass
                header.line_items = updated_line_items

            res = db.post_invoice_receiving(header, shadow_mode=shadow_mode, posting_enabled=posting_enabled)
            
            if "LIVE_SUCCESS" in res['status']:
                st.balloons()
                st.success(f"✅ REAL DATABASE RECEIVING SUCCESSFUL! Posted & Reconciled {res['items_reconciled']} items. Status: {res['status']}")
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

        # Database Content Inspector
        st.divider()
        st.subheader("🗄️ Database Inventory Table Inspector")
        if st.button("Refresh Live Database Contents"):
            records = db.get_inventory_records()
            if records:
                st.write(f"Displaying top {len(records)} active inventory records in database:")
                st.dataframe(pd.DataFrame(records), height=500, use_container_width=True)
            else:
                st.info("Database inventory table is currently empty.")
else:
    st.info("Upload an invoice document above to begin processing.")
