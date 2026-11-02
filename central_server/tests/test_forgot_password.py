# tests/test_forgot_password.py
"""
Şifremi Unuttum ve E-posta Servisi Testleri
"""

import unittest
from datetime import datetime, timedelta

from src.models.user import User
from src.services.email_service import EmailService


def test_forgot_password_flow():
    """Şifre sıfırlama akışını ve email arama fonksiyonlarını test et"""
    print("[TEST] Testing Password Reset & Email Verification Flow...")
    
    # 1. E-posta ile kullanıcı sorgulama testi
    test_email = "test_reset@arifirin.com"
    existing_user = User.get_by_email(test_email)
    
    if not existing_user:
        user = User({
            'username': 'test_forgot_user',
            'password_hash': User.hash_password('OldPassword123'),
            'full_name': 'Sıfırlama Test Kullanıcısı',
            'email': test_email,
            'role': 'User',
            'is_active': True
        })
        user.save()
        existing_user = User.get_by_email(test_email)
    
    assert existing_user is not None, "Kullanıcı e-posta adresine göre bulunamadı!"
    assert existing_user.email == test_email, "Bulunan kullanıcının e-posta adresi uyuşmuyor!"
    print("  [OK] E-posta ile kullanıcı arama (get_by_email) başarılı")
    
    # 2. EmailService kodu oluşturma ve gönderme simülasyonu
    code = "654321"
    success, msg = EmailService.send_password_reset_code(test_email, existing_user.full_name, code)
    assert success is True, "E-posta servisi doğrulama kodu üretemedi!"
    print(f"  [OK] EmailService mesaji: {msg}")
    
    # 3. reset_password testi
    new_pwd = "NewSecurePassword2026!"
    reset_ok = existing_user.reset_password(new_pwd)
    assert reset_ok is True, "Şifre sıfırlama işlemi başarısız oldu!"
    
    # 4. Yeni şifre ile kimlik doğrulama testi
    reloaded_user = User.get_by_username('test_forgot_user')
    assert reloaded_user.authenticate(new_pwd) is True, "Yeni şifre ile doğrulama başarısız!"
    assert reloaded_user.authenticate('OldPassword123') is False, "Eski şifre halen kabul ediliyor!"
    
    print("  [OK] Sifre sifirlama ve yeni sifreyle dogrulama testi TAMAMLANDI.")
    
    # 5. Temizlik - Test kullanıcısını veritabanından sil
    from src.core.database import db
    db.execute_query("DELETE FROM Users WHERE username = 'test_forgot_user'")
    print("  [OK] Test kullanicisi veritabanindan temizlendi.")

if __name__ == '__main__':
    test_forgot_password_flow()
