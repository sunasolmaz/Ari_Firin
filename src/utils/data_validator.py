# src/utils/data_validator.py
import re
from datetime import datetime
from typing import Any, List, Tuple

class DataValidator:
    """Veri doğrulama yardımcısı"""
    
    @staticmethod
    def validate_required(value: Any, field_name: str) -> Tuple[bool, str]:
        """Zorunlu alan kontrolü"""
        if value is None or str(value).strip() == '':
            return False, f"{field_name} alanı zorunludur!"
        return True, ""
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """Email doğrulama"""
        if not email:
            return True, ""  # Boş olabilir
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, email):
            return True, ""
        return False, "Geçersiz email formatı!"
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, str]:
        """Telefon doğrulama"""
        if not phone:
            return True, ""  # Boş olabilir
        
        # Sadece rakam, boşluk, -, + kontrolü
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        if cleaned.startswith('+'):
            cleaned = cleaned[1:]
        
        if cleaned.isdigit() and len(cleaned) >= 10:
            return True, ""
        return False, "Geçersiz telefon numarası!"
    
    @staticmethod
    def validate_tax_no(tax_no: str) -> Tuple[bool, str]:
        """Vergi numarası doğrulama"""
        if not tax_no:
            return True, ""  # Boş olabilir
        
        # Sadece rakam kontrolü
        if not tax_no.isdigit():
            return False, "Vergi numarası sadece rakam içermelidir!"
        
        # 10 haneli kontrolü
        if len(tax_no) != 10:
            return False, "Vergi numarası 10 haneli olmalıdır!"
        
        # Türkiye vergi no algoritması (basit)
        try:
            total = 0
            for i in range(9):
                digit = int(tax_no[i])
                total += (digit * (10 - i))
            
            check_digit = (total % 10) if (total % 10) < 10 else 0
            if int(tax_no[9]) != check_digit:
                return False, "Geçersiz vergi numarası!"
            
            return True, ""
        except:
            return False, "Geçersiz vergi numarası!"
    
    @staticmethod
    def validate_iban(iban: str) -> Tuple[bool, str]:
        """IBAN doğrulama"""
        if not iban:
            return True, ""  # Boş olabilir
        
        cleaned = iban.replace(' ', '').upper()
        if not cleaned.startswith('TR') and not cleaned.startswith('tr'):
            return False, "Geçersiz IBAN (TR ile başlamalı)!"
        
        if len(cleaned) != 26:
            return False, "IBAN 26 haneli olmalıdır!"
        
        if not cleaned[2:].isdigit():
            return False, "IBAN rakam içermelidir!"
        
        return True, ""
    
    @staticmethod
    def validate_amount(amount: float, min_value: float = 0, 
                       max_value: float = None) -> Tuple[bool, str]:
        """Tutar doğrulama"""
        if amount < min_value:
            return False, f"Tutar {min_value} TL'den az olamaz!"
        
        if max_value and amount > max_value:
            return False, f"Tutar {max_value} TL'den fazla olamaz!"
        
        return True, ""
    
    @staticmethod
    def validate_date(date_str: str, format: str = '%Y-%m-%d') -> Tuple[bool, str]:
        """Tarih doğrulama"""
        try:
            datetime.strptime(date_str, format)
            return True, ""
        except:
            return False, f"Geçersiz tarih formatı! ({format})"
    
    @staticmethod
    def validate_code(code: str, min_length: int = 1, 
                     max_length: int = 20) -> Tuple[bool, str]:
        """Kod doğrulama"""
        if not code or len(code) < min_length:
            return False, f"Kod {min_length} karakterden az olamaz!"
        
        if len(code) > max_length:
            return False, f"Kod {max_length} karakterden fazla olamaz!"
        
        if not re.match(r'^[A-Z0-9\-_]+$', code.upper()):
            return False, "Kod sadece büyük harf, rakam, - ve _ içerebilir!"
        
        return True, ""
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """Şifre doğrulama"""
        if len(password) < 6:
            return False, "Şifre en az 6 karakter olmalıdır!"
        
        if len(password) > 50:
            return False, "Şifre 50 karakterden uzun olamaz!"
        
        # En az bir rakam
        if not re.search(r'\d', password):
            return False, "Şifre en az bir rakam içermelidir!"
        
        # En az bir büyük harf
        if not re.search(r'[A-Z]', password):
            return False, "Şifre en az bir büyük harf içermelidir!"
        
        # En az bir küçük harf
        if not re.search(r'[a-z]', password):
            return False, "Şifre en az bir küçük harf içermelidir!"
        
        return True, ""
    
    @staticmethod
    def validate_all(data: dict, rules: dict) -> List[str]:
        """Tüm validasyonları uygula"""
        errors = []
        
        for field, field_rules in rules.items():
            value = data.get(field)
            
            for rule in field_rules:
                if rule == 'required':
                    valid, msg = DataValidator.validate_required(value, field)
                    if not valid:
                        errors.append(msg)
                
                elif rule == 'email':
                    valid, msg = DataValidator.validate_email(value)
                    if not valid:
                        errors.append(msg)
                
                elif rule == 'phone':
                    valid, msg = DataValidator.validate_phone(value)
                    if not valid:
                        errors.append(msg)
                
                elif rule == 'tax_no':
                    valid, msg = DataValidator.validate_tax_no(value)
                    if not valid:
                        errors.append(msg)
                
                elif rule == 'iban':
                    valid, msg = DataValidator.validate_iban(value)
                    if not valid:
                        errors.append(msg)
                
                elif rule == 'password':
                    valid, msg = DataValidator.validate_password(value)
                    if not valid:
                        errors.append(msg)
        
        return errors