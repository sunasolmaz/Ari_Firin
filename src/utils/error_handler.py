# src/utils/error_handler.py
import sys
import traceback
from datetime import datetime
from PyQt5.QtWidgets import QMessageBox
from ..core.logger import logger

class ErrorHandler:
    """Global hata yöneticisi"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.error_log = []
        self.max_errors = 100
    
    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """Exception yakala ve işle"""
        # Log'la
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.error(f"Kritik Hata:\n{error_msg}")
        
        # Hatayı kaydet
        self.error_log.append({
            'timestamp': datetime.now(),
            'type': exc_type.__name__,
            'message': str(exc_value),
            'traceback': error_msg
        })
        
        if len(self.error_log) > self.max_errors:
            self.error_log.pop(0)
        
        # Kullanıcıya göster
        self.show_error_dialog(exc_type, exc_value, error_msg)
        
        # Hata raporu gönder
        self.send_error_report(exc_type, exc_value, error_msg)
    
    def show_error_dialog(self, exc_type, exc_value, traceback_str):
        """Hata dialog'u göster"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Kritik Hata")
        msg.setText(f"<b>Bir hata oluştu:</b>\n\n{exc_type.__name__}: {exc_value}")
        
        # Detay butonu
        detail_btn = msg.addButton("Detayları Göster", QMessageBox.ActionRole)
        msg.addButton("Kapat", QMessageBox.RejectRole)
        
        msg.exec_()
        
        if msg.clickedButton() == detail_btn:
            # Detay penceresi
            detail_dialog = QMessageBox()
            detail_dialog.setWindowTitle("Hata Detayları")
            detail_dialog.setText(traceback_str[:5000])  # Çok uzun olmaması için
            detail_dialog.exec_()
    
    def send_error_report(self, exc_type, exc_value, traceback_str):
        """Hata raporu gönder"""
        try:
            import requests
            from ..core.config import config
            
            report_url = config.get('error_report.url')
            if not report_url:
                return
            
            data = {
                'application': config.get('application.name'),
                'version': config.get('application.version'),
                'error_type': exc_type.__name__,
                'error_message': str(exc_value),
                'traceback': traceback_str,
                'timestamp': datetime.now().isoformat(),
                'user': 'system'
            }
            
            requests.post(report_url, json=data, timeout=5)
            
        except:
            pass  # Rapor gönderilemezse sessizce geç
    
    def show_warning(self, title: str, message: str):
        """Uyarı mesajı göster"""
        logger.warning(f"{title}: {message}")
        QMessageBox.warning(None, title, message)
    
    def show_info(self, title: str, message: str):
        """Bilgi mesajı göster"""
        logger.info(f"{title}: {message}")
        QMessageBox.information(None, title, message)
    
    def show_error(self, title: str, message: str):
        """Hata mesajı göster"""
        logger.error(f"{title}: {message}")
        QMessageBox.critical(None, title, message)
    
    def get_last_errors(self, count: int = 10) -> list:
        """Son hataları getir"""
        return self.error_log[-count:]

# Global error handler
error_handler = ErrorHandler()

# Exception handler'ı bağla
def excepthook(exc_type, exc_value, exc_traceback):
    error_handler.handle_exception(exc_type, exc_value, exc_traceback)

sys.excepthook = excepthook