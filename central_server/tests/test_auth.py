# tests/test_auth.py
import hashlib
from src.models.user import User

def test_pbkdf2_hash_and_verify():
    password = "SecurePassword2026!"
    hashed = User.hash_password(password)
    
    assert hashed.startswith("pbkdf2:sha256:100000$")
    
    user = User({'username': 'testuser', 'password_hash': hashed})
    assert user.authenticate(password) is True
    assert user.authenticate("WrongPassword") is False

def test_legacy_sha256_migration():
    password = "LegacySecret123"
    legacy_sha256 = hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    user = User({'id': None, 'username': 'legacy_user', 'password_hash': legacy_sha256})
    
    assert user.authenticate(password) is True
    assert user.authenticate("WrongPassword") is False
