# tests/test_daily_turnover.py
import pytest
from datetime import datetime, timedelta
from src.core.database import db
from src.services.turnover_service import TurnoverService, turnover_service


@pytest.fixture(scope="module")
def setup_test_data():
    """Testler için veritabanını ve şubeleri hazırla"""
    db.ensure_turnover_tables()
    branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY id ASC")
    if not branches:
        # Şube yoksa test şubesi oluştur
        b_id = db.execute_query("INSERT INTO Branches (name, city) VALUES ('Test Armada', 'Tekirdağ') RETURNING id")
        branches = [{'id': b_id, 'name': 'Test Armada'}]
    return branches


def test_categories_learning(setup_test_data):
    """Akıllı seçenek alanının yeni kategorileri öğrenmesi ve listelemesi"""
    branch_id = setup_test_data[0]['id']
    service = TurnoverService()

    # Başlangıçta kategoriler listelenebilmeli
    incomes = service.get_categories(branch_id, "Income")
    assert isinstance(incomes, list)
    assert len(incomes) > 0

    # Yeni bir gider kategorisi ekle
    unique_expense = f"Özel Fırın Bakımı {datetime.now().strftime('%f')}"
    added = service.add_category(branch_id, "Expense", unique_expense)
    assert added is True

    # Listede artık görünmeli
    expenses = service.get_categories(branch_id, "Expense")
    assert unique_expense in expenses

    # Boş kategori eklenemez
    assert service.add_category(branch_id, "Expense", "   ") is False


def test_add_and_delete_entry(setup_test_data):
    """Gelir ve gider ekleme, silme ve hesaplama testi"""
    branch_id = setup_test_data[0]['id']
    service = TurnoverService()
    test_date = "2026-09-22"

    # 1. Geçersiz tutar reddedilmeli
    success, msg, _ = service.add_entry(branch_id, test_date, "Income", "Tezgâh", -50.0)
    assert success is False

    # 2. Boş kategori reddedilmeli
    success, msg, _ = service.add_entry(branch_id, test_date, "Income", "   ", 100.0)
    assert success is False

    # 3. Geçerli Gelir (Nakit)
    unique_cat = f"Yeni Özel Gelir {datetime.now().strftime('%f')}"
    ok1, _, id1 = service.add_entry(
        branch_id=branch_id,
        entry_date=test_date,
        entry_type="Income",
        category=unique_cat,
        amount=1500.0,
        payment_method="Nakit",
        description="Nakit tezgah geliri"
    )
    assert ok1 is True
    assert id1 is not None

    # Yeni kategori otomatik olarak kategori havuzuna da eklenmiş olmalı!
    cats = service.get_categories(branch_id, "Income")
    assert unique_cat in cats

    # 4. Geçerli Gelir (Kart)
    ok2, _, id2 = service.add_entry(
        branch_id=branch_id,
        entry_date=test_date,
        entry_type="Income",
        category="Kredi Kartı Satış",
        amount=2500.0,
        payment_method="Kredi Kartı / POS",
        description="POS satışı"
    )
    assert ok2 is True

    # 5. Geçerli Gider
    ok3, _, id3 = service.add_entry(
        branch_id=branch_id,
        entry_date=test_date,
        entry_type="Expense",
        category="Un Alımı",
        amount=1000.0,
        payment_method="Nakit",
        description="5 çuval un"
    )
    assert ok3 is True

    # 6. Günlük Özeti Doğrula
    summary = service.get_daily_summary(branch_id, test_date)
    assert summary['total_income'] >= 4000.0
    assert summary['cash_income'] >= 1500.0
    assert summary['card_income'] >= 2500.0
    assert summary['total_expense'] >= 1000.0
    assert summary['net_turnover'] == summary['total_income'] - summary['total_expense']

    # 7. O Güne Kadar Olan Kümülatif Ciroyu Doğrula
    cum = service.get_cumulative_turnover(branch_id, test_date)
    assert cum['cumulative_income'] >= 4000.0
    assert cum['cumulative_net'] == cum['cumulative_income'] - cum['cumulative_expense']

    # 8. Silme işlemi
    del_ok, _ = service.delete_entry(id1)
    assert del_ok is True
    del_ok, _ = service.delete_entry(id2)
    assert del_ok is True
    del_ok, _ = service.delete_entry(id3)
    assert del_ok is True


def test_three_branches_summary(setup_test_data):
    """3 Şube ve konsolide genel toplam ciro testi"""
    service = TurnoverService()
    test_date = datetime.now().date().strftime('%Y-%m-%d')

    three_summary = service.get_three_branches_summary(test_date)
    assert 'branches' in three_summary
    assert 'total_daily_income' in three_summary
    assert 'grand_cumulative_income' in three_summary
    assert isinstance(three_summary['branches'], list)
