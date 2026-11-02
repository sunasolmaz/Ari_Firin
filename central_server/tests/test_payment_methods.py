# tests/test_payment_methods.py
import sys
import os
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.models.invoice import Invoice
from src.services.invoice_service import InvoiceService
from src.services.report_service import ReportService
from datetime import datetime

def test_payment_method_breakdown():
    # 1. Invoice Model test
    data_cash = {
        'id': 101,
        'invoice_no': 'SAT-2026-0001',
        'branch_id': 1,
        'invoice_date': '2026-09-16',
        'invoice_type': 'Sales',
        'customer_id': 1,
        'grand_total': 1500.0,
        'payment_status': 'Paid',
        'payment_method': 'Nakit',
        'status': 'Approved'
    }
    inv_cash = Invoice(data_cash)
    assert inv_cash.payment_method == 'Nakit', f"Beklenen Nakit, gelen {inv_cash.payment_method}"

    data_card = {
        'id': 102,
        'invoice_no': 'SAT-2026-0002',
        'branch_id': 1,
        'invoice_date': '2026-09-16',
        'invoice_type': 'Sales',
        'customer_id': 1,
        'grand_total': 2500.0,
        'payment_status': 'Paid',
        'payment_method': 'Kredi Kartı / POS',
        'status': 'Approved'
    }
    inv_card = Invoice(data_card)
    assert inv_card.payment_method == 'Kredi Kartı / POS', f"Beklenen Kredi Kartı / POS, gelen {inv_card.payment_method}"
    
    print("Payment method model test passed.")

if __name__ == '__main__':
    test_payment_method_breakdown()
