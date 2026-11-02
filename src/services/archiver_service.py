# src/services/archiver_service.py
from datetime import datetime, timedelta
from typing import Dict
from ..core.database import db
from ..core.logger import logger
from ..core.config import config

class ArchiverService:
    """Veri arşivleme servisi"""
    
    def __init__(self):
        self.archive_days = config.get('archive.days_to_archive', 730)
        self.auto_archive = config.get('archive.auto_archive', True)
        self.archive_path = config.get('archive.archive_path', 'archive')
    
    def archive_old_data(self, days: int = None) -> Dict:
        """Eski verileri arşivle"""
        if days is None:
            days = self.archive_days
        
        cutoff_date = datetime.now().date() - timedelta(days=days)
        result = {
            'invoices': 0,
            'customers': 0,
            'journal': 0,
            'items': 0
        }
        
        try:
            # Transaction başlat
            db.begin_transaction()
            
            # 1. Eski faturaları arşivle
            if days >= 730:  # 2 yıldan eski faturalar
                # Arşiv tablosunu oluştur
                db.execute_query("""
                    CREATE TABLE IF NOT EXISTS Invoices_Archive (LIKE Invoices INCLUDING ALL)
                """)
                
                # Faturaları arşivle
                result['invoices'] = db.execute_query("""
                    INSERT INTO Invoices_Archive 
                    SELECT * FROM Invoices 
                    WHERE invoice_date < %s AND status = 'Approved'
                """, (cutoff_date,))
                
                # Ana tablodan sil
                db.execute_query("""
                    DELETE FROM Invoices 
                    WHERE invoice_date < %s AND status = 'Approved'
                """, (cutoff_date,))
            
            # 2. Eski muhasebe kayıtlarını arşivle
            if days >= 365:  # 1 yıldan eski kayıtlar
                db.execute_query("""
                    CREATE TABLE IF NOT EXISTS Journal_Archive (LIKE JournalEntries INCLUDING ALL)
                """)
                
                result['journal'] = db.execute_query("""
                    INSERT INTO Journal_Archive 
                    SELECT * FROM JournalEntries 
                    WHERE entry_date < %s
                """, (cutoff_date,))
                
                db.execute_query("""
                    DELETE FROM JournalEntries 
                    WHERE entry_date < %s
                """, (cutoff_date,))
            
            # 3. Arşivlenen faturaların kalemlerini arşivle
            if result['invoices'] > 0:
                db.execute_query("""
                    CREATE TABLE IF NOT EXISTS InvoiceItems_Archive (LIKE InvoiceItems INCLUDING ALL)
                """)
                
                result['items'] = db.execute_query("""
                    INSERT INTO InvoiceItems_Archive 
                    SELECT ii.* 
                    FROM InvoiceItems ii
                    JOIN Invoices_Archive i ON i.id = ii.invoice_id
                """)
                
                db.execute_query("""
                    DELETE FROM InvoiceItems 
                    WHERE invoice_id IN (SELECT id FROM Invoices_Archive)
                """)
            
            # 4. Veritabanını optimize et
            db.execute_query("VACUUM ANALYZE")
            
            # Transaction onayla
            db.commit()
            
            logger.info(f"✅ Arşivleme tamamlandı: {result}")
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Arşivleme hatası: {e}")
            return result
    
    def get_archive_stats(self) -> Dict:
        """Arşiv istatistiklerini getir"""
        try:
            stats = {}
            
            # Arşiv tablolarını kontrol et
            tables = ['Invoices_Archive', 'Journal_Archive', 'InvoiceItems_Archive']
            for table in tables:
                exists = db.fetch_one("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                """, (table.lower(),))
                
                if exists and exists['exists']:
                    count = db.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
                    stats[table] = count['count'] if count else 0
                else:
                    stats[table] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Arşiv istatistik hatası: {e}")
            return {}
    
    def restore_from_archive(self, table_name: str, record_id: int) -> bool:
        """Arşivden veri geri yükle"""
        try:
            mapping = {
                'invoices': ('Invoices_Archive', 'Invoices'),
                'journal': ('Journal_Archive', 'JournalEntries'),
                'items': ('InvoiceItems_Archive', 'InvoiceItems')
            }
            
            archive_table, main_table = mapping.get(table_name, (None, None))
            if not archive_table:
                return False
            
            # Var mı kontrol et
            exists = db.fetch_one(f"""
                SELECT EXISTS (
                    SELECT 1 FROM {archive_table} WHERE id = %s
                )
            """, (record_id,))
            
            if not exists or not exists['exists']:
                return False
            
            # Veriyi geri yükle
            db.execute_query(f"""
                INSERT INTO {main_table}
                SELECT * FROM {archive_table} WHERE id = %s
            """, (record_id,))
            
            # Arşivden sil
            db.execute_query(f"DELETE FROM {archive_table} WHERE id = %s", (record_id,))
            
            logger.info(f"✅ Veri geri yüklendi: {table_name} - {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"Geri yükleme hatası: {e}")
            return False
    
    def clear_old_archives(self, days: int = 3650) -> bool:
        """10 yıldan eski arşivleri temizle"""
        try:
            cutoff_date = datetime.now().date() - timedelta(days=days)
            
            # Arşiv tablolarını temizle (created_at yok, id'ye göre)
            db.execute_query("""
                DELETE FROM Invoices_Archive 
                WHERE created_at < %s
            """, (cutoff_date,))
            
            db.execute_query("""
                DELETE FROM Journal_Archive 
                WHERE created_at < %s
            """, (cutoff_date,))
            
            logger.info(f"✅ Eski arşivler temizlendi: {days} gün")
            return True
            
        except Exception as e:
            logger.error(f"Arşiv temizleme hatası: {e}")
            return False