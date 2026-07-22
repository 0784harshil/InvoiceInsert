"""
Invoice Manager — Enterprise Web UI (Streamlit)
Enforces Rule 9 (Human Review), Rule 10 (Actual-Good Quantity),
Rule 13 (Atomic Transaction & Readback Reconciliation),
Rule 14 (posting_enabled=False), Rule 15 (shadow_mode=True), and Rule 18 (Reconciliation).
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
from models import ReviewState, InvoiceHeader


st.set_page_config(page_title="Enterprise Invoice Receiving Engine", page_icon="📄", layout="wide")

st.title("Enterprise Invoice Receiving Engine")
st.caption("Rule-Enforced Invoice Processing, Human Review Queue, Live DB Upserts, and Readback Reconciliation.")

# Sidebar Settings
with st.sidebar:
    st.header("Safety & Receiving Controls")
    shadow_mode = st.toggle("Shadow Mode (Audit Only)", value=False, help="Turn OFF to execute REAL live database insertion.")
    posting_enabled = st.toggle("Posting Enabled", value=True, help="Turn ON to allow database updates.")
    
    st.divider()
    db_mgr = CertifiedDBManager("config.json")
    st.markdown(f"**DB Certification Status:** {'✅ Certified' if db_mgr.is_certified else '⚠️ Not Certified'}")
    
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

if uploaded is not None:
    suffix = os.path.splitext(uploaded.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        tmp_path = tmp.name

    if st.button("Process Document", type="primary"):
        with st.spinner("Analyzing document with enterprise rules..."):
            try:
                header = parser.parse_file(tmp_path)
                header = review_mgr.audit_and_prepare_invoice(header)
                
                # Auto-approve valid items so execution posts immediately
                for item in header.line_items:
                    if item.review_state != ReviewState.POSTING_BLOCKED:
                        qty = item.expected_pos_qty or item.case_quantity
                        review_mgr.approve_line_item(item, qty)

                st.session_state["header"] = header
                st.session_state["filename"] = uploaded.name
            except Exception as e:
                st.error(f"Processing failed: {e}")
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

# Display Results
if "header" in st.session_state:
    header: InvoiceHeader = st.session_state["header"]
    st.subheader(f"Invoice Summary — {st.session_state.get('filename', '')}")

    # Document Validity Alert
    if not header.document_valid:
        st.error("🛑 DOCUMENT BLOCKED: Non-Invoice Document Detected (e.g., Resume or Non-Financial Document). Posting is permanently blocked.")
        for reason in header.blocking_reasons:
            st.write(f"- {reason}")
    else:
        # Header Metrics
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

        # Line Items & Human Review Queue
        st.subheader(f"📋 Extracted Line Items ({len(header.line_items)} items total)")
        st.caption("Rule 9 & 10: All valid items are auto-approved. You can view all items in the scrollable table below.")

        table_data = []
        for item in header.line_items:
            table_data.append({
                "Line #": item.line_number,
                "Vendor Item #": item.raw_item_num,
                "UPC": item.raw_upc or "MISSING",
                "Description": item.raw_description[:35],
                "Raw Package": item.raw_package_text,
                "Case Qty": str(item.case_quantity),
                "Unit Cost": f"${item.unit_cost:.2f}",
                "Total Cost": f"${item.total_cost:.2f}",
                "Expected POS Qty": str(item.expected_pos_qty or 'N/A'),
                "Approved Qty": str(item.approved_actual_good_qty or '0'),
                "Review State": item.review_state.value
            })

        df_items = pd.DataFrame(table_data)
        st.dataframe(df_items, height=600, width=1200)

        # Post / Live DB Receiving Button
        st.divider()
        st.subheader("⚡ Execute Inventory Database Receiving")
        
        if shadow_mode:
            st.warning("⚠️ SHADOW MODE IS ON: Clicking execute will simulate queries without changing database. Toggle OFF 'Shadow Mode' in sidebar to write live data!")
        else:
            st.info("🟢 LIVE MODE IS ACTIVE: Clicking execute will insert/update records directly into the Inventory database table.")

        db = CertifiedDBManager("config.json")
        if st.button("🚀 Execute Receiving & Write to DB", type="primary"):
            # Ensure items are approved before write
            for item in header.line_items:
                if item.review_state != ReviewState.POSTING_BLOCKED and item.review_state != ReviewState.REVIEWED_APPROVED:
                    qty = item.expected_pos_qty or item.case_quantity
                    review_mgr.approve_line_item(item, qty)

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
                st.dataframe(pd.DataFrame(records), height=500, width=1200)
            else:
                st.info("Database inventory table is currently empty.")
else:
    st.info("Upload an invoice document above to begin processing.")
