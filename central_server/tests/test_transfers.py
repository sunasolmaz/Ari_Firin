# tests/test_transfers.py

def validate_transfer(from_acc_id: int, to_acc_id: int, amount: float) -> tuple[bool, str]:
    if from_acc_id == to_acc_id:
        return False, "Kaynak ve hedef hesap aynı olamaz"
    if amount <= 0:
        return False, "Geçerli bir tutar giriniz"
    return True, "Başarılı"

def test_transfer_validation():
    valid, msg = validate_transfer(1, 2, 500.0)
    assert valid is True
    
    valid, msg = validate_transfer(1, 1, 500.0)
    assert valid is False
    assert "aynı olamaz" in msg
    
    valid, msg = validate_transfer(1, 2, -100.0)
    assert valid is False
    assert "Geçerli" in msg
