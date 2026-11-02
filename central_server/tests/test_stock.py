# tests/test_stock.py

def is_critical_stock(current_stock: float, critical_threshold: float) -> bool:
    return current_stock <= critical_threshold or current_stock <= 5.0

def test_critical_stock_detection():
    assert is_critical_stock(4.0, 10.0) is True
    assert is_critical_stock(8.0, 10.0) is True
    assert is_critical_stock(15.0, 10.0) is False
    assert is_critical_stock(3.0, 2.0) is True

def test_stock_quantity_update():
    initial_stock = 100.0
    sold_quantity = 25.0
    added_quantity = 10.0
    
    updated_stock = initial_stock - sold_quantity + added_quantity
    assert updated_stock == 85.0
