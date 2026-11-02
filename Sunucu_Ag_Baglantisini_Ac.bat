@echo off
chcp 65001 >nul
echo ============================================================
echo   ARI FIRIN - SUNUCU AG VE GUVENLIK DUVARI AYARLAYICI
echo ============================================================
echo.
echo 1. PostgreSQL 5432 Portu Windows Guvenlik Duvarinda Aciliyor...
netsh advfirewall firewall add rule name="PostgreSQL_Port_5432" dir=in action=allow protocol=TCP localport=5432

echo 2. PostgreSQL Servisi Baslatiliyor...
net start postgres

echo.
echo ============================================================
echo ✅ Islem Tamamlandi! Diger bilgisayarlar artik baglanabilir.
echo ============================================================
echo.
pause
