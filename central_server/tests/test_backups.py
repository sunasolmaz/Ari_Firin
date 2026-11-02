# tests/test_backups.py
import os
from src.utils.backup_scheduler import BackupScheduler

def test_encrypted_zip_backup_creation(tmp_dir: str):
    scheduler = BackupScheduler()
    scheduler.backup_dir = tmp_dir
    
    # Create dummy sql file
    sql_file = os.path.join(tmp_dir, "manual_test_backup.sql")
    with open(sql_file, "w") as f:
        f.write("CREATE TABLE Test (id INT);")
    
    zip_path = scheduler._encrypt_backup(sql_file)
    
    assert zip_path is not None
    assert zip_path.endswith('.zip')
    assert os.path.exists(zip_path) is True
    assert os.path.exists(sql_file) is False
