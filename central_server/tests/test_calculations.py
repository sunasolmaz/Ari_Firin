# tests/test_calculations.py

def calculate_invoice_totals(subtotal: float, vat_percent: float, discount: float = 0.0):
    vat_amount = subtotal * (vat_percent / 100.0)
    total_before_discount = subtotal + vat_amount
    grand_total = max(0.0, total_before_discount - discount)
    return round(subtotal, 2), round(vat_amount, 2), round(grand_total, 2)

def test_invoice_calculations():
    subtotal, vat, grand_total = calculate_invoice_totals(1000.0, 20.0, 50.0)
    assert subtotal == 1000.0
    assert vat == 200.0
    assert grand_total == 1150.0

def test_remaining_balance_calculation():
    grand_total = 1150.0
    paid_amount = 450.0
    remaining = grand_total - paid_amount
    assert remaining == 700.0
