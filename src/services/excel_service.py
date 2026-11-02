# src/services/excel_service.py
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime
from typing import Dict
from ..core.logger import logger
from ..models.customer import Customer
from ..models.invoice import Invoice

class ExcelService:
    """Excel işlemleri servisi"""
    
    def __init__(self):
        self.style_headers()
    
    def style_headers(self):
        """Excel header stilleri"""
        self.header_font = Font(bold=True, color="FFFFFF")
        self.header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        self.header_alignment = Alignment(horizontal="center", vertical="center")
        self.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
    
    def export_invoices_to_excel(self, branch_id: int, start_date: str, 
                                 end_date: str, file_path: str) -> bool:
        """Faturaları Excel'e aktar"""
        try:
            # Verileri getir
            invoices = Invoice.get_report(branch_id, start_date, end_date)
            
            if not invoices:
                logger.warning("⚠️ Aktarılacak fatura bulunamadı")
                return False
            
            # DataFrame oluştur
            df = pd.DataFrame(invoices)
            
            # Gereksiz sütunları kaldır
            columns_to_keep = [
                'invoice_no', 'invoice_date', 'invoice_type', 'customer_name',
                'total', 'vat_total', 'discount_total', 'grand_total',
                'payment_status', 'status', 'created_by_name'
            ]
            df = df[[col for col in columns_to_keep if col in df.columns]]
            
            # Excel'e yaz
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Faturalar', index=False)
                
                # Style uygula
                worksheet = writer.sheets['Faturalar']
                
                # Header'ları style'la
                for cell in worksheet[1]:
                    cell.font = self.header_font
                    cell.fill = self.header_fill
                    cell.alignment = self.header_alignment
                    cell.border = self.border
                
                # Sütun genişliklerini ayarla
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            logger.info(f"✅ Faturalar Excel'e aktarıldı: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Excel aktarım hatası: {e}")
            return False
    
    def import_customers_from_excel(self, file_path: str, branch_id: int) -> Dict:
        """Excel'den müşteri aktar"""
        result = {'success': 0, 'error': 0, 'errors': []}
        
        try:
            df = pd.read_excel(file_path, sheet_name="Cari")
            required_columns = ['Ünvan']
            
            for col in required_columns:
                if col not in df.columns:
                    raise Exception(f"'{col}' sütunu bulunamadı!")
            
            for index, row in df.iterrows():
                try:
                    customer = Customer({
                        'branch_id': branch_id,
                        'title': str(row.get('Ünvan', '')),
                        'tax_no': str(row.get('Vergi No', '')),
                        'tax_office': str(row.get('Vergi Dairesi', '')),
                        'phone': str(row.get('Telefon', '')),
                        'email': str(row.get('Email', '')),
                        'address': str(row.get('Adres', '')),
                        'balance': float(row.get('Bakiye', 0)),
                        'credit_limit': float(row.get('Kredi Limiti', 0)),
                        'is_supplier': bool(row.get('Tedarikçi', False)),
                        'notes': str(row.get('Notlar', ''))
                    })
                    
                    if customer.save():
                        result['success'] += 1
                    else:
                        result['error'] += 1
                        result['errors'].append(f"Satır {index+2}: Kayıt başarısız")
                        
                except Exception as e:
                    result['error'] += 1
                    result['errors'].append(f"Satır {index+2}: {str(e)}")
            
            logger.info(f"✅ Excel'den müşteri aktarıldı: {result['success']} başarılı")
            
        except Exception as e:
            logger.error(f"❌ Excel okuma hatası: {e}")
            result['error'] += 1
            result['errors'].append(str(e))
        
        return result
    
    def import_invoices_from_excel(self, file_path: str, branch_id: int, 
                                   user_id: int) -> Dict:
        """Excel'den fatura aktar"""
        result = {'success': 0, 'error': 0, 'errors': []}
        
        try:
            df = pd.read_excel(file_path, sheet_name="Faturalar")
            
            for index, row in df.iterrows():
                try:
                    # Müşteri bul veya oluştur
                    customer = Customer.get_by_tax_no(str(row.get('Vergi No', '')), branch_id)
                    if not customer:
                        customer = Customer({
                            'branch_id': branch_id,
                            'title': str(row.get('Müşteri Ünvan', '')),
                            'tax_no': str(row.get('Vergi No', '')),
                            'phone': str(row.get('Telefon', '')),
                            'address': str(row.get('Adres', ''))
                        })
                        customer.save()
                    
                    # Fatura oluştur
                    invoice = Invoice({
                        'branch_id': branch_id,
                        'invoice_date': row.get('Tarih', datetime.now().date()),
                        'invoice_type': row.get('Tip', 'Sales'),
                        'customer_id': customer.id,
                        'grand_total': float(row.get('Genel Toplam', 0)),
                        'status': 'Approved',
                        'notes': str(row.get('Notlar', '')),
                        'created_by': user_id
                    })
                    
                    # Fatura numarası varsa kullan
                    invoice_no = str(row.get('Fatura No', ''))
                    if invoice_no:
                        invoice.invoice_no = invoice_no
                    
                    if invoice.save():
                        result['success'] += 1
                    else:
                        result['error'] += 1
                        result['errors'].append(f"Satır {index+2}: Fatura kayıt başarısız")
                        
                except Exception as e:
                    result['error'] += 1
                    result['errors'].append(f"Satır {index+2}: {str(e)}")
            
            logger.info(f"✅ Excel'den fatura aktarıldı: {result['success']} başarılı")
            
        except Exception as e:
            logger.error(f"❌ Excel okuma hatası: {e}")
            result['error'] += 1
            result['errors'].append(str(e))
        
        return result
    
    def export_template(self, template_type: str, file_path: str) -> bool:
        """Excel şablonu oluştur"""
        try:
            wb = Workbook()
            
            if template_type == 'customers':
                ws = wb.active
                ws.title = "Cari"
                headers = ['Ünvan', 'Vergi No', 'Vergi Dairesi', 'Telefon', 
                          'Email', 'Adres', 'Bakiye', 'Kredi Limiti', 'Tedarikçi', 'Notlar']
                
                for col, header in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=col, value=header)
                    cell.font = self.header_font
                    cell.fill = self.header_fill
                    cell.alignment = self.header_alignment
                    cell.border = self.border
                
            elif template_type == 'invoices':
                ws = wb.active
                ws.title = "Faturalar"
                headers = ['Fatura No', 'Tarih', 'Tip', 'Vergi No', 'Müşteri Ünvan',
                          'Telefon', 'Adres', 'Toplam', 'KDV', 'Genel Toplam', 'Notlar']
                
                for col, header in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=col, value=header)
                    cell.font = self.header_font
                    cell.fill = self.header_fill
                    cell.alignment = self.header_alignment
                    cell.border = self.border
            
            # Sütun genişliklerini ayarla
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            wb.save(file_path)
            logger.info(f"✅ Şablon oluşturuldu: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Şablon oluşturma hatası: {e}")
            return False