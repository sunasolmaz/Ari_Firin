# src/services/email_service.py
"""
E-posta Gönderim Servisi - Şifre Sıfırlama ve Bildirimler
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from typing import Tuple

from ..core.config import config
from ..core.logger import logger


class EmailService:
    """E-posta gönderme işlemlerini yöneten servis sınıfı"""
    
    @classmethod
    def get_smtp_config(cls) -> dict:
        """Merkezi veritabanından, yoksa yerel config.json'dan SMTP ayarlarını getirir"""
        cfg = {}
        try:
            from ..core.database import db
            rows = db.fetch_all("SELECT key, value FROM SystemSettings WHERE key LIKE %s", ('smtp_%',))
            if rows:
                for r in rows:
                    key = r['key'].replace('smtp_', '')
                    cfg[key] = r['value']
        except Exception:
            pass
            
        # Eğer veritabanında henüz tanımlı değilse config.json'a bak
        file_cfg = config.get('email', {})
        return {
            'smtp_server': cfg.get('server') or file_cfg.get('smtp_server', 'smtp.gmail.com'),
            'smtp_port': int(cfg.get('port') or file_cfg.get('smtp_port', 587)),
            'sender_email': cfg.get('email') or file_cfg.get('sender_email', ''),
            'sender_password': cfg.get('password') or file_cfg.get('sender_password', ''),
            'use_tls': (cfg.get('use_tls') == 'true') if 'use_tls' in cfg else file_cfg.get('use_tls', True),
            'use_ssl': (cfg.get('use_ssl') == 'true') if 'use_ssl' in cfg else file_cfg.get('use_ssl', False)
        }

    @classmethod
    def save_smtp_config(cls, server: str, port: int, email: str, password: str, use_tls: bool, use_ssl: bool) -> bool:
        """SMTP ayarlarını hem merkezi veritabanına hem de yerel config.json'a kaydeder"""
        try:
            from ..core.database import db
            settings = {
                'smtp_server': server.strip(),
                'smtp_port': str(port),
                'smtp_email': email.strip(),
                'smtp_password': password.strip(),
                'smtp_use_tls': 'true' if use_tls else 'false',
                'smtp_use_ssl': 'true' if use_ssl else 'false'
            }
            for k, v in settings.items():
                db.execute_query("""
                    INSERT INTO SystemSettings (key, value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO UPDATE 
                    SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """, (k, v))
            logger.info("✅ SMTP ayarları merkezi veritabanına kaydedildi.")
        except Exception as e:
            logger.warning(f"⚠️ Veritabanına SMTP ayarı kaydedilemedi: {e}")
            
        # Yerel config.json'a da yaz
        config.set('email.smtp_server', server)
        config.set('email.smtp_port', port)
        config.set('email.sender_email', email)
        config.set('email.sender_password', password)
        config.set('email.use_tls', use_tls)
        config.set('email.use_ssl', use_ssl)
        config.save()
        return True

    @classmethod
    def is_smtp_configured(cls) -> bool:
        """SMTP ayarlarının yapılıp yapılmadığını kontrol eder"""
        cfg = cls.get_smtp_config()
        return bool(cfg.get('smtp_server') and cfg.get('sender_email') and cfg.get('sender_password'))

    @classmethod
    def test_connection(cls, smtp_server: str, smtp_port: int, sender_email: str, 
                        sender_password: str, use_tls: bool = True, use_ssl: bool = False) -> Tuple[bool, str]:
        sender_server = smtp_server.strip()
        sender_email = sender_email.strip()
        # Google Uygulama Şifreleri 4'erli gruplar halinde boşluklu verilir; boşlukları otomatik temizle
        sender_password = sender_password.strip().replace(" ", "")
        
        if not sender_server or not sender_email or not sender_password:
            return False, "Lütfen sunucu, gönderici e-posta ve şifre alanlarının tamamını doldurunuz."

        try:
            smtp_port = int(smtp_port)
            if use_ssl or smtp_port == 465:
                server = smtplib.SMTP_SSL(sender_server, smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(sender_server, smtp_port, timeout=10)
                if use_tls:
                    server.starttls()
                    
            server.login(sender_email, sender_password)
            server.quit()
            return True, "✅ SMTP bağlantısı ve kimlik doğrulama başarılı! E-posta gönderilmeye hazır."
        except smtplib.SMTPAuthenticationError:
            return False, (
                "❌ Kimlik doğrulama başarısız!\n"
                "Gönderici e-posta veya şifre hatalı.\n"
                "⚠️ Not: Gmail kullanıyorsanız normal hesap şifreniz değil, "
                "Google Güvenlik sayfasından üreteceğiniz 16 haneli 'Uygulama Şifresi' girilmelidir."
            )
        except Exception as e:
            return False, f"❌ Bağlantı hatası: {str(e)}"

    @classmethod
    def send_password_reset_code(cls, target_email: str, user_fullname: str, code: str) -> Tuple[bool, str]:
        """
        Şifre sıfırlama doğrulama kodunu e-posta olarak gönderir.
        """
        email_cfg = cls.get_smtp_config()
        smtp_server = email_cfg.get('smtp_server', '').strip()
        smtp_port = int(email_cfg.get('smtp_port', 587))
        sender_email = email_cfg.get('sender_email', '').strip()
        sender_password = email_cfg.get('sender_password', '').strip().replace(" ", "")
        use_tls = email_cfg.get('use_tls', True)
        use_ssl = email_cfg.get('use_ssl', False)
        
        # SMTP bilgileri eksikse kullanıcıyı bilgilendir
        if not smtp_server or not sender_email or not sender_password:
            logger.warning(f"⚠️ E-posta SMTP ayarları eksik. Gönderilemedi: {target_email}")
            return False, (
                "E-posta gönderici (SMTP) ayarları henüz yapılandırılmamış!\n"
                "Gerçek e-posta gidebilmesi için 'E-posta Ayarları'ndan gönderici e-posta ve şifrenizi tanımlayınız."
            )
        
        subject = "🔑 ARI FIRIN - Şifre Sıfırlama Kodu"
        
        # HTML İçeriği (Şık ve modern tasarım)
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0d0d0f; color: #ffffff; padding: 30px;">
            <div style="max-width: 500px; margin: 0 auto; background-color: #1a1a24; border-radius: 12px; padding: 30px; border: 1px solid #3b82f6;">
                <h2 style="color: #38bdf8; text-align: center; margin-bottom: 20px;">☕ ARI FIRIN</h2>
                <h3 style="color: #f1f5f9; text-align: center;">Şifre Sıfırlama Talebi</h3>
                <p style="color: #cbd5e1; font-size: 14px;">Merhaba <strong>{user_fullname}</strong>,</p>
                <p style="color: #cbd5e1; font-size: 14px;">Hesabınız için şifre sıfırlama talebinde bulunuldu. Doğrulama kodunuz aşağıdadır:</p>
                <div style="background-color: #0f172a; border-radius: 8px; padding: 20px; text-align: center; margin: 25px 0;">
                    <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #38bdf8;">{code}</span>
                </div>
                <p style="color: #94a3b8; font-size: 12px; text-align: center;">Bu kod <strong>10 dakika</strong> boyunca geçerlidir.</p>
                <p style="color: #64748b; font-size: 11px; text-align: center; margin-top: 30px;">Bu talebi siz yapmadıysanız lütfen bu e-postayı dikkate almayın.</p>
            </div>
        </body>
        </html>
        """
        
        plain_body = f"Merhaba {user_fullname},\n\nARI FIRIN Şifre sıfırlama doğrulama kodunuz: {code}\n(Kod 10 dakika geçerlidir).\n\nBu talebi siz yapmadıysanız bu mesajı dikkate almayınız."

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = formataddr((str(Header("Arı Fırın Bilgi Sistemi", 'utf-8')), sender_email))
            msg['To'] = target_email
            
            part1 = MIMEText(plain_body, 'plain', 'utf-8')
            part2 = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)
            
            if use_ssl or smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=12)
            else:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=12)
                if use_tls:
                    server.starttls()
                    
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [target_email], msg.as_string())
            server.quit()
            
            logger.info(f"✅ Doğrulama kodu e-postası başarıyla gönderildi: {target_email}")
            return True, f"Doğrulama kodu {target_email} adresinize başarıyla gönderildi."
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP Kimlik Doğrulama Hatası: {e}")
            return False, (
                "E-posta gönderilemedi: SMTP Kimlik Doğrulama Hatası!\n"
                "Gönderici e-posta veya şifresi hatalı.\n"
                "Gmail için 16 haneli Uygulama Şifresi gereklidir."
            )
        except Exception as e:
            logger.error(f"❌ E-posta gönderim hatası: {e}")
            return False, f"E-posta gönderilemedi: {str(e)}"
