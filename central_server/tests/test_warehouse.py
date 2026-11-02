# tests/test_warehouse.py
import pytest
from src.core.database import db
from src.services.warehouse_service import warehouse_service

def test_warehouse_tables_exist():
    """Depo tablolarının varlığını doğrula"""
    products = warehouse_service.get_products()
    assert isinstance(products, list)

def test_add_and_update_product():
    """Yeni depo ürünü ekleme ve güncelleme testi"""
    test_code = f"TEST-P-{db.fetch_one('SELECT COUNT(*) as c FROM WarehouseProducts')['c'] + 1}"
    success, msg, prod_id = warehouse_service.add_product({
        "product_code": test_code,
        "name": "Test Un Çuvalı",
        "category": "Hammadde",
        "unit": "çuval",
        "stock_quantity": 50.0,
        "critical_stock": 10.0,
        "purchase_price": 450.0,
        "notes": "Test amaçlı oluşturuldu"
    })
    assert success is True
    assert prod_id is not None
    assert prod_id > 0

    # Get product
    prod = warehouse_service.get_product(prod_id)
    assert prod is not None
    assert prod['product_code'] == test_code
    assert float(prod['stock_quantity']) == 50.0

    # Update product
    upd_success, upd_msg = warehouse_service.update_product(prod_id, {
        "name": "Test Un Çuvalı 50kg (Revize)",
        "category": "Hammadde",
        "unit": "çuval",
        "critical_stock": 15.0,
        "purchase_price": 480.0,
        "sale_price": 0.0,
        "notes": "Revize edildi"
    })
    assert upd_success is True

    updated_prod = warehouse_service.get_product(prod_id)
    assert updated_prod['name'] == "Test Un Çuvalı 50kg (Revize)"
    assert float(updated_prod['critical_stock']) == 15.0

def test_stock_in_and_out():
    """Stok girişi ve çıkışı testi"""
    test_code = f"TEST-INOUT-{db.fetch_one('SELECT COUNT(*) as c FROM WarehouseProducts')['c'] + 1}"
    success, msg, prod_id = warehouse_service.add_product({
        "product_code": test_code,
        "name": "Test Maya",
        "category": "Hammadde",
        "unit": "kg",
        "stock_quantity": 20.0,
        "critical_stock": 10.0,
        "purchase_price": 60.0
    })
    assert success is True
    
    # 1. Stok Girişi (15 kg ekle -> 35 kg olmalı)
    in_ok, in_msg = warehouse_service.add_stock_in(
        product_id=prod_id,
        quantity=15.0,
        document_no="IRS-99881",
        description="Parti 1 alımı"
    )
    assert in_ok is True
    prod_after_in = warehouse_service.get_product(prod_id)
    assert float(prod_after_in['stock_quantity']) == 35.0

    # 2. Stok Çıkışı (10 kg düş -> 25 kg olmalı)
    out_ok, out_msg = warehouse_service.add_stock_out(
        product_id=prod_id,
        quantity=10.0,
        reason="Fire / Bozulma",
        description="Nemlenme nedeniyle imha"
    )
    assert out_ok is True
    prod_after_out = warehouse_service.get_product(prod_id)
    assert float(prod_after_out['stock_quantity']) == 25.0

    # 3. Yetersiz Stok Çıkışı Reddedilmeli (50 kg düşmeye çalışınca False dönmeli)
    out_fail, fail_msg = warehouse_service.add_stock_out(
        product_id=prod_id,
        quantity=50.0,
        reason="Hatalı Çıkış"
    )
    assert out_fail is False
    assert "Yetersiz stok" in fail_msg

def test_dispatch_to_branch():
    """Merkez depodan şubeye sevkiyat testi"""
    # 1. Şubeyi al (örnek: id 1)
    branches = db.fetch_all("SELECT id, name FROM Branches LIMIT 1")
    assert len(branches) > 0
    branch = branches[0]
    branch_id = branch['id']

    test_code = f"TEST-DISP-{db.fetch_one('SELECT COUNT(*) as c FROM WarehouseProducts')['c'] + 1}"
    success, msg, prod_id = warehouse_service.add_product({
        "product_code": test_code,
        "name": "Test Baklavalık Yağ",
        "category": "Hammadde",
        "unit": "teneke",
        "stock_quantity": 40.0,
        "critical_stock": 5.0,
        "purchase_price": 800.0
    })
    assert success is True

    # Sevkiyat yap (10 teneke şubeye sevk et)
    dispatch_ok, disp_msg = warehouse_service.dispatch_to_branch(
        product_id=prod_id,
        target_branch_id=branch_id,
        quantity=10.0,
        document_no="SEVK-1001",
        description="Haftalık şube ihtiyacı"
    )
    assert dispatch_ok is True

    # Merkez depodaki stok 40 - 10 = 30 olmalı
    prod_after_disp = warehouse_service.get_product(prod_id)
    assert float(prod_after_disp['stock_quantity']) == 30.0

    # Şube Products tablosunda bu ürünün stoğu artmış olmalı
    branch_prod = db.fetch_one("""
        SELECT stock_quantity FROM Products 
        WHERE branch_id = %s AND (product_code = %s OR name = %s)
    """, (branch_id, test_code, "Test Baklavalık Yağ"))
    assert branch_prod is not None
    assert float(branch_prod['stock_quantity']) >= 10.0

    # Sevkiyat geçmişinde kayıt olmalı
    dispatches = warehouse_service.get_branch_dispatches(branch_id=branch_id)
    matching = [d for d in dispatches if d.get('warehouse_product_id') == prod_id]
    assert len(matching) > 0
    assert float(matching[0]['quantity']) == 10.0
    assert matching[0]['branch_name'] == branch['name']

def test_critical_stock_detection():
    """Kritik stok algılama testi"""
    test_code = f"TEST-CRIT-{db.fetch_one('SELECT COUNT(*) as c FROM WarehouseProducts')['c'] + 1}"
    success, msg, prod_id = warehouse_service.add_product({
        "product_code": test_code,
        "name": "Test Kritik Susam",
        "category": "Hammadde",
        "unit": "kg",
        "stock_quantity": 3.0,
        "critical_stock": 10.0,
        "purchase_price": 120.0
    })
    assert success is True

    critical_products = warehouse_service.get_critical_stock_products()
    found = [p for p in critical_products if p['id'] == prod_id]
    assert len(found) == 1
    assert float(found[0]['stock_quantity']) == 3.0
    assert float(found[0]['critical_stock']) == 10.0
