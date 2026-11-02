# tests/run_all_tests.py
import sys
import unittest
import os
import tempfile

test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, test_dir)

import test_auth
import test_calculations
import test_stock
import test_transfers
import test_backups
import test_forgot_password
import test_payment_methods
from test_accounting_edge_cases import TestAccountingEdgeCases
from test_security_audit import TestSecurityAudit
from test_ota_update_integration import TestOtaUpdateIntegration
from test_cloud_backup_license_sync import TestCloudBackupLicenseSync
from test_production_packaging import TestProductionPackaging
from test_setup_wizard import TestSetupWizardAndInstaller
from test_installer_and_distribution import TestInstallerAndDistribution

class TestAppSecurityAndLogic(unittest.TestCase):
    def test_auth_pbkdf2(self):
        test_auth.test_pbkdf2_hash_and_verify()

    def test_auth_legacy(self):
        test_auth.test_legacy_sha256_migration()

    def test_forgot_password(self):
        test_forgot_password.test_forgot_password_flow()

    def test_payment_method_breakdown(self):
        test_payment_methods.test_payment_method_breakdown()

    def test_calculations_invoice(self):
        test_calculations.test_invoice_calculations()

    def test_calculations_balance(self):
        test_calculations.test_remaining_balance_calculation()

    def test_stock_detection(self):
        test_stock.test_critical_stock_detection()

    def test_stock_update(self):
        test_stock.test_stock_quantity_update()

    def test_transfers(self):
        test_transfers.test_transfer_validation()

    def test_encrypted_backups(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_backups.test_encrypted_zip_backup_creation(tmp_dir)

if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestAppSecurityAndLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestAccountingEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityAudit))
    suite.addTests(loader.loadTestsFromTestCase(TestOtaUpdateIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestCloudBackupLicenseSync))
    suite.addTests(loader.loadTestsFromTestCase(TestProductionPackaging))
    suite.addTests(loader.loadTestsFromTestCase(TestSetupWizardAndInstaller))
    suite.addTests(loader.loadTestsFromTestCase(TestInstallerAndDistribution))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

