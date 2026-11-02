# src/utils/performance_monitor.py
import psutil
import time
from datetime import datetime
from typing import Dict, List
from ..core.database import db
from ..core.logger import logger

class PerformanceMonitor:
    """Performans izleyici"""
    
    def __init__(self):
        self.start_time = time.time()
        self.history = []
        self.max_history = 100
    
    def get_current_stats(self) -> Dict:
        """Anlık performans istatistikleri"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # RAM
            memory = psutil.virtual_memory()
            ram_used = memory.used / 1024 / 1024  # MB
            ram_percent = memory.percent
            
            # Disk
            disk = psutil.disk_usage('/')
            disk_used = disk.used / 1024 / 1024 / 1024  # GB
            
            # Veritabanı
            db_size = db.get_database_size()  # MB
            
            # Çalışma süresi
            uptime = time.time() - self.start_time
            
            return {
                'timestamp': datetime.now(),
                'cpu_percent': cpu_percent,
                'ram_used_mb': ram_used,
                'ram_percent': ram_percent,
                'disk_used_gb': disk_used,
                'db_size_mb': db_size,
                'uptime_seconds': uptime,
                'uptime_hours': uptime / 3600
            }
            
        except Exception as e:
            logger.error(f"Performans istatistik hatası: {e}")
            return {}
    
    def add_to_history(self, stats: Dict):
        """Geçmişe ekle"""
        self.history.append(stats)
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def get_history(self, count: int = 10) -> List[Dict]:
        """Geçmiş performans verileri"""
        return self.history[-count:]
    
    def get_detailed_report(self) -> Dict:
        """Detaylı performans raporu"""
        stats = self.get_current_stats()
        
        if not stats:
            return {}
        
        # Ortalama değerler
        if self.history:
            avg_cpu = sum(h.get('cpu_percent', 0) for h in self.history) / len(self.history)
            avg_ram = sum(h.get('ram_percent', 0) for h in self.history) / len(self.history)
        else:
            avg_cpu = stats.get('cpu_percent', 0)
            avg_ram = stats.get('ram_percent', 0)
        
        return {
            'current': stats,
            'average': {
                'cpu_percent': avg_cpu,
                'ram_percent': avg_ram
            },
            'system_info': {
                'cpu_count': psutil.cpu_count(),
                'total_ram_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
                'total_disk_gb': psutil.disk_usage('/').total / 1024 / 1024 / 1024
            }
        }
    
    def check_alerts(self) -> List[str]:
        """Performans uyarıları"""
        alerts = []
        stats = self.get_current_stats()
        
        if not stats:
            return alerts
        
        # CPU uyarısı
        if stats.get('cpu_percent', 0) > 80:
            alerts.append(f"⚠️ CPU kullanımı yüksek: {stats['cpu_percent']:.1f}%")
        
        # RAM uyarısı
        if stats.get('ram_percent', 0) > 85:
            alerts.append(f"⚠️ RAM kullanımı yüksek: {stats['ram_percent']:.1f}%")
        
        # Veritabanı uyarısı
        db_size = stats.get('db_size_mb', 0)
        if db_size > 900:
            alerts.append(f"⚠️ Veritabanı boyutu kritik: {db_size:.1f} MB (Limit: 1 GB)")
        elif db_size > 700:
            alerts.append(f"⚠️ Veritabanı boyutu yüksek: {db_size:.1f} MB")
        
        # Disk uyarısı
        disk_used = stats.get('disk_used_gb', 0)
        total_disk = psutil.disk_usage('/').total / 1024 / 1024 / 1024
        if disk_used / total_disk > 0.9:
            alerts.append(f"⚠️ Disk alanı kritik: %{disk_used/total_disk*100:.1f} doldu")
        
        return alerts
    
    def get_suggestions(self) -> List[str]:
        """Optimizasyon önerileri"""
        suggestions = []
        stats = self.get_current_stats()
        
        if not stats:
            return suggestions
        
        # Veritabanı optimizasyonu
        db_size = stats.get('db_size_mb', 0)
        if db_size > 800:
            suggestions.append("💡 Veritabanını arşivleyin (2 yıldan eski verileri)")
            suggestions.append("💡 VACUUM ANALYZE çalıştırın")
        
        # RAM optimizasyonu
        if stats.get('ram_percent', 0) > 80:
            suggestions.append("💡 Gereksiz modülleri kapatın")
            suggestions.append("💡 Cache boyutunu azaltın")
        
        # Disk optimizasyonu
        disk_used = stats.get('disk_used_gb', 0)
        total_disk = psutil.disk_usage('/').total / 1024 / 1024 / 1024
        if disk_used / total_disk > 0.85:
            suggestions.append("💡 Eski yedek dosyalarını temizleyin")
        
        return suggestions