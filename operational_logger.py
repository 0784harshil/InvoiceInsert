"""
Operational Logger & Transaction Rollback Engine
Enforces full auditability, detailed receiving transaction logs,
and 1-click transaction rollbacks.
"""

from decimal import Decimal
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional


class OperationalLogger:
    """
    Manages operational logs and transaction rollback state persistence.
    """

    def __init__(self, log_file: str = "operational_receiving_logs.json"):
        self.log_file = log_file
        self._ensure_log_file()

    def _ensure_log_file(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w") as f:
                json.dump([], f, indent=2)

    def log_transaction(
        self,
        transaction_id: str,
        invoice_number: str,
        vendor_name: str,
        store_id: str,
        status: str,
        items_detail: List[Dict[str, Any]],
        execution_mode: str = "LIVE"
    ) -> Dict[str, Any]:
        """
        Logs receiving transaction details including initial/final stock, costs, and AltSKUs added.
        """
        record = {
            "transaction_id": transaction_id,
            "timestamp": datetime.now().isoformat(),
            "invoice_number": invoice_number,
            "vendor_name": vendor_name,
            "store_id": store_id,
            "status": status,
            "execution_mode": execution_mode,
            "item_count": len(items_detail),
            "rolled_back": False,
            "rollback_timestamp": None,
            "items_detail": items_detail
        }

        logs = self.get_all_logs()
        # Replace if existing transaction_id
        logs = [l for l in logs if l["transaction_id"] != transaction_id]
        logs.insert(0, record)

        with open(self.log_file, "w") as f:
            json.dump(logs, f, indent=2)

        return record

    def get_all_logs(self) -> List[Dict[str, Any]]:
        """Retrieves all transaction logs ordered by timestamp DESC."""
        try:
            with open(self.log_file, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def get_log_by_id(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Find log record by transaction ID."""
        logs = self.get_all_logs()
        for log in logs:
            if log["transaction_id"] == transaction_id:
                return log
        return None

    def mark_rolled_back(self, transaction_id: str) -> bool:
        """Marks a transaction as rolled back in the log file."""
        logs = self.get_all_logs()
        updated = False
        for log in logs:
            if log["transaction_id"] == transaction_id:
                log["rolled_back"] = True
                log["rollback_timestamp"] = datetime.now().isoformat()
                updated = True
                break

        if updated:
            with open(self.log_file, "w") as f:
                json.dump(logs, f, indent=2)

        return updated
