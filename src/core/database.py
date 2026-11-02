# src/core/database.py
"""
PostgreSQL Veritabanı Yönetimi - Multi-Tenant Mimari

Her kullanıcı kendi izole şemasına (tenant_usr_X) sahiptir.
Public şema ortak verileri (Users, SystemSettings) tutar.
"""

import os
import re
import threading
from dotenv import load_dotenv
from psycopg2 import extras

load_dotenv()  # .env dosyasını yükle
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from datetime import datetime, date
from typing import Optional, List, Dict, Tuple, Any

from .config import config
from .logger import logger


class Database:
    """PostgreSQL veritabanı yönetimi (thread-safe)"""

    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pool = None
            cls._instance._local = threading.local()
            cls._instance._active_tenant = None
            cls._instance._ensured_tenant_schemas = set()
            cls._instance._ensured_turnover_schemas = set()
            cls._instance._ensured_payment_plan_schemas = set()
            cls._instance._ensured_stock_count_schemas = set()
            cls._instance._ensured_bakery_supply_schemas = set()
            cls._instance._ensured_production_schemas = set()
            cls._instance._initialize_pool()
        return cls._instance

    # ══════════════════════════════════════════════════════════════
    # TENANT (Kullanıcıya Özel Şema) YÖNETİMİ & GÜVENLİK
    # ══════════════════════════════════════════════════════════════

    TENANT_SCHEMA_PATTERN = re.compile(r'^[a-zA-Z0-9_]{1,63}$')

    @classmethod
    def validate_tenant_schema(cls, schema_name: Optional[str]) -> Optional[str]:
        """PostgreSQL şema adı güvenlik doğrulaması (SQL / DDL Injection önleme)"""
        if not schema_name or schema_name == 'public':
            return 'public'
        if not isinstance(schema_name, str):
            raise ValueError(f"Geçersiz şema adı: {type(schema_name)}")
        schema_clean = schema_name.strip()
        if not cls.TENANT_SCHEMA_PATTERN.match(schema_clean):
            raise ValueError(f"Güvenlik İhlali: Şema adı yalnızca alfanümerik karakterler ve alt çizgi içerebilir: '{schema_name}'")
        return schema_clean

    def set_tenant(self, tenant_schema: Optional[str]):
        """Aktif kullanıcı veritabanı alanını (tenant şemasını) ayarlar"""
        tenant_schema = self.validate_tenant_schema(tenant_schema)
        self._active_tenant = tenant_schema
        self._local.active_tenant = tenant_schema
        # Eğer aktif bir transaction bağlantısı varsa ona da hemen uygula
        txn_conn = getattr(self._local, 'txn_conn', None)
        if txn_conn is not None:
            with txn_conn.cursor() as cur:
                if tenant_schema and tenant_schema != 'public':
                    cur.execute(f'SET search_path TO "{tenant_schema}", public;')
                else:
                    cur.execute('SET search_path TO public;')
        if tenant_schema and tenant_schema != 'public':
            logger.info(f"🏢 Aktif kullanıcı alanı (Tenant): {tenant_schema}")
        else:
            logger.info("🏢 Aktif kullanıcı alanı sıfırlandı: public")

    def clear_tenant(self):
        """Aktif kullanıcı veritabanı alanını (tenant şemasını) tamamen temizler"""
        self._active_tenant = None
        self._local.active_tenant = None
        txn_conn = getattr(self._local, 'txn_conn', None)
        if txn_conn is not None:
            try:
                with txn_conn.cursor() as cur:
                    cur.execute('SET search_path TO public;')
            except Exception:
                pass
        logger.info("🏢 Aktif kullanıcı alanı tamamen sıfırlandı: public")

    def get_tenant(self) -> Optional[str]:
        """Geçerli aktif tenant şema adını döndürür"""
        tenant = getattr(self._local, 'active_tenant', None)
        if tenant is not None:
            return tenant
        return self._active_tenant

    @staticmethod
    def get_tenant_schema_for_user(user_id: int) -> str:
        """Kullanıcı ID'sine özel benzersiz PostgreSQL şema adını üretir"""
        return f"tenant_usr_{user_id}"

    # ══════════════════════════════════════════════════════════════
    # BAĞLANTI HAVUZU
    # ══════════════════════════════════════════════════════════════

    def _initialize_pool(self):
        """Bağlantı havuzunu başlat (thread-safe)"""
        try:
            db_config = config.get('database')
            pool_size = config.get('performance.connection_pool', 5)

            sslmode = db_config.get('sslmode', os.environ.get('DB_SSLMODE', 'prefer'))
            conn_kwargs = {
                'minconn': 1,
    		'maxconn': pool_size,
    		'host': os.getenv('DB_HOST', db_config.get('host', 'localhost')),
    		'port': int(os.getenv('DB_PORT', db_config.get('port', 5432))),
    		'database': os.getenv('DB_NAME', db_config.get('database', 'accounting_db')),
    		'user': os.getenv('DB_USER', db_config.get('user', 'postgres')),
    		'password': os.getenv('DB_PASSWORD', db_config.get('password', '')),
            }
            if sslmode:
                conn_kwargs['sslmode'] = sslmode

            # ThreadedConnectionPool: Çoklu thread'de güvenli
            self._pool = ThreadedConnectionPool(**conn_kwargs)
            logger.info(f"✅ Veritabanı bağlantı havuzu başlatıldı (maxconn={pool_size})")
        except Exception as e:
            logger.error(f"❌ Veritabanı bağlantı hatası: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Bağlantı al (Context manager - Aktif transaction varsa o bağlantıyı döndürür)"""
        txn_conn = getattr(self._local, 'txn_conn', None)
        if txn_conn is not None:
            yield txn_conn
            return

        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            # Bağlantıyı havuza temiz ve search_path'i sıfırlanmış şekilde iade et
            try:
                if not conn.closed:
                    conn.rollback()
                    with conn.cursor() as cur:
                        cur.execute('RESET search_path;')
            except Exception:
                pass
            self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self, commit=False):
        """
        Cursor al (Context manager).
        Aktif tenant varsa search_path ayarlar.
        Transaction içindeyse tekrar ayarlamaz (gereksiz yük önlenir).
        """
        is_in_txn = getattr(self._local, 'txn_conn', None) is not None
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            try:
                # Sadece transaction DIŞINDA search_path ayarla
                if not is_in_txn:
                    active_tenant = self.get_tenant()
                    if active_tenant and active_tenant != 'public':
                        cursor.execute(f'SET search_path TO "{active_tenant}", public;')
                    else:
                        cursor.execute('SET search_path TO public;')

                yield cursor
                if commit and not is_in_txn:
                    conn.commit()
            except Exception as e:
                if not is_in_txn:
                    conn.rollback()
                logger.error(f"❌ Transaction hatası: {e}")
                raise
            finally:
                cursor.close()

    # ══════════════════════════════════════════════════════════════
    # SORGU İŞLEMLERİ
    # ══════════════════════════════════════════════════════════════

    def execute_query(self, query: str, params: tuple = None) -> Any:
        """Sorgu çalıştır (INSERT, UPDATE, DELETE). RETURNING sorgularında dönen ID/değeri döndürür."""
        with self.get_cursor(commit=True) as cursor:
            cursor.execute(query, tuple(params) if params else ())
            if cursor.description:
                row = cursor.fetchone()
                if row:
                    if 'id' in row:
                        return row['id']
                    return next(iter(row.values()))
            return cursor.rowcount

    def fetch_all(self, query: str, params: tuple = None) -> List[Dict]:
        """Tüm kayıtları getir"""
        with self.get_cursor() as cursor:
            cursor.execute(query, tuple(params) if params else ())
            return cursor.fetchall()

    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Tek kayıt getir"""
        with self.get_cursor() as cursor:
            cursor.execute(query, tuple(params) if params else ())
            return cursor.fetchone()

    def fetch_paginated(self, query: str, page: int = 1,
                       page_size: int = None, params: tuple = None) -> Tuple[List[Dict], int]:
        """Sayfalı veri getir"""
        if page_size is None:
            page_size = config.get('performance.page_size', 50)

        offset = max(0, (page - 1) * page_size)
        count_query = f"SELECT COUNT(*) as total FROM ({query}) AS subquery"
        query_params = tuple(params) if params else ()

        with self.get_cursor() as cursor:
            cursor.execute(count_query, query_params)
            count_res = cursor.fetchone()
            total = count_res['total'] if count_res else 0

            paginated_query = f"{query} LIMIT %s OFFSET %s"
            cursor.execute(paginated_query, query_params + (page_size, offset))
            data = cursor.fetchall()

            return data, total

    # ══════════════════════════════════════════════════════════════
    # TRANSACTION YÖNETİMİ (Nested destekli)
    # ══════════════════════════════════════════════════════════════

    def begin_transaction(self):
        """Transaction başlat (Thread-local bağlantı tutar ve nested transaction destekler)"""
        depth = getattr(self._local, 'txn_depth', 0)
        if depth == 0 or getattr(self._local, 'txn_conn', None) is None:
            conn = self._pool.getconn()
            conn.autocommit = False
            self._local.txn_conn = conn
            self._local.txn_depth = 1
            active_tenant = self.get_tenant()
            with conn.cursor() as cur:
                if active_tenant and active_tenant != 'public':
                    cur.execute(f'SET search_path TO "{active_tenant}", public;')
                else:
                    cur.execute('SET search_path TO public;')
        else:
            self._local.txn_depth = depth + 1

    def commit(self):
        """Transaction onayla (en dış blok tamamlandığında havuza iade eder)"""
        depth = getattr(self._local, 'txn_depth', 0)
        if depth > 1:
            self._local.txn_depth = depth - 1
            return

        conn = getattr(self._local, 'txn_conn', None)
        if conn is not None:
            try:
                conn.commit()
            finally:
                self._pool.putconn(conn)
                self._local.txn_conn = None
                self._local.txn_depth = 0

    def rollback(self):
        """Transaction geri al (tüm nesting seviyelerini iptal eder ve havuza iade eder)"""
        conn = getattr(self._local, 'txn_conn', None)
        if conn is not None:
            try:
                conn.rollback()
            finally:
                self._pool.putconn(conn)
                self._local.txn_conn = None
                self._local.txn_depth = 0

    @contextmanager
    def transaction(self):
        """Transaction context manager (hata durumunda loglar)"""
        self.begin_transaction()
        try:
            yield
            self.commit()
        except Exception as e:
            self.rollback()
            logger.error(f"❌ Transaction geri alındı: {e}")
            raise

    # ══════════════════════════════════════════════════════════════
    # VERİTABANI DURUMU
    # ══════════════════════════════════════════════════════════════

    def is_initialized(self) -> bool:
        """Veritabanı temel tablolarının hazır olup olmadığını kontrol eder"""
        try:
            row = self.fetch_one(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'users'"
            )
            return bool(row)
        except Exception:
            return False

    def is_tenant_initialized(self, schema_name: str) -> bool:
        """Belirtilen kullanıcı şemasının tablolarının hazır olup olmadığını kontrol eder"""
        try:
            row = self.fetch_one(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = %s AND table_name = 'branches'",
                (schema_name,)
            )
            return bool(row)
        except Exception:
            return False

    def get_database_size(self) -> float:
        """Veritabanı boyutunu MB cinsinden al (hata durumunda 0.0 döner)"""
        try:
            result = self.fetch_one("""
                SELECT pg_database_size(%s) / 1024 / 1024 as size_mb
            """, (config.get('database.database'),))
            return float(result['size_mb']) if result and result.get('size_mb') else 0.0
        except Exception as e:
            logger.warning(f"⚠️ Veritabanı boyutu alınamadı: {e}")
            return 0.0

    # ══════════════════════════════════════════════════════════════
    # TENANT ŞEMA OLUŞTURMA (Kullanıcıya Özel İzole Alan)
    # ══════════════════════════════════════════════════════════════

    # Her kullanıcı şemasında MUTLAKA bulunması gereken tablolar.
    # Biri eksik olursa sorgular sessizce ortak "public" şemasına düşer ve
    # kullanıcılar arasında veri sızıntısına yol açabilir.
    REQUIRED_TENANT_TABLES = (
        'advanceoffsets', 'auditlog', 'bakerypricelist', 'bakeryproductions',
        'bakerysupplies', 'bakerysupplyitems', 'bankaccounts', 'banktransactions',
        'branches', 'branchshipmentitems', 'branchshipments', 'companyexpenses',
        'customers', 'dailyturnovercategories', 'dailyturnovers', 'employeeledger',
        'employees', 'externalsaleitems', 'externalsales', 'invoiceitems',
        'invoices', 'journalentries', 'paymentplans', 'products',
        'stockcountitems', 'stockcountsessions', 'stockcounttemplateitems',
        'stockmovements', 'warehouseproducts', 'warehousestockmovements',
    )

    def get_missing_tenant_tables(self, schema_name: str) -> List[str]:
        """Kullanıcı şemasında eksik olan zorunlu tabloları döndürür."""
        rows = self.fetch_all(
            "SELECT LOWER(table_name) AS t FROM information_schema.tables "
            "WHERE table_schema = %s",
            (schema_name,)
        )
        existing = {r['t'] for r in rows}
        return [t for t in self.REQUIRED_TENANT_TABLES if t not in existing]

    def ensure_tenant_schema(self, schema_name: str,
                             default_branch_name: str = "Merkez Şube",
                             city: str = None) -> bool:
        schema_name = self.validate_tenant_schema(schema_name)
        """
        Kullanıcıya özel izole PostgreSQL şemasını (Tenant) ve tablolarını oluşturur.
        Her kullanıcı yalnızca kendi şemasındaki verileri okur ve yazar.

        Args:
            schema_name: Oluşturulacak şema adı (ör: tenant_usr_1)
            default_branch_name: İlk şube adı
            city: İlk şube şehri. Verilmezse public.Branches'ten aynı isimli
                  şubenin şehri kullanılır, yoksa "Tekirdağ" varsayılır.
        """
        if not hasattr(self, '_ensured_tenant_schemas'):
            self._ensured_tenant_schemas = set()

        if schema_name in self._ensured_tenant_schemas:
            return True

        # Hızlı doğrulama: Eğer 30 zorunlu tenant tablosu zaten şemada eksiksiz mevcutsa,
        # 30+ adet ağır DDL sorgusunu (CREATE TABLE, INDEX, TRIGGER) tekrar çalıştırmadan doğrudan geç.
        missing_tables = self.get_missing_tenant_tables(schema_name)
        if not missing_tables:
            self._ensured_tenant_schemas.add(schema_name)
            if hasattr(self, '_ensured_turnover_schemas'):
                self._ensured_turnover_schemas.add(schema_name)
            if hasattr(self, '_ensured_payment_plan_schemas'):
                self._ensured_payment_plan_schemas.add(schema_name)
            if hasattr(self, '_ensured_stock_count_schemas'):
                self._ensured_stock_count_schemas.add(schema_name)
            if hasattr(self, '_ensured_bakery_supply_schemas'):
                self._ensured_bakery_supply_schemas.add(schema_name)
                self._ensured_production_schemas.add(schema_name)
            logger.info(f"⚡ Tenant şeması doğrulandı ({schema_name}) - 30 zorunlu tablo eksiksiz mevcut.")
            return True

        try:
            # Şehir verilmemişse public'ten almaya çalış
            if not city and default_branch_name:
                try:
                    public_branch = self.fetch_one(
                        "SELECT city FROM Branches WHERE name = %s LIMIT 1",
                        (default_branch_name,)
                    )
                    if public_branch and public_branch.get('city'):
                        city = public_branch['city']
                        logger.info(f"🏙️ Public'ten şehir alındı: {city}")
                except Exception:
                    pass

            if not city:
                city = "Tekirdağ"

            # 1. Şemayı oluştur
            with self.get_cursor(commit=True) as cursor:
                cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}";')

            # 2. Şema tablolarını oluştur
            tables = [
                # Şubeler
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".Branches (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    city VARCHAR(100),
                    phone VARCHAR(20) NULL,
                    address TEXT,
                    tax_no VARCHAR(20) NULL,
                    branch_type VARCHAR(50) DEFAULT 'retail',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Cari Hesaplar
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".Customers (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE CASCADE,
                    customer_code VARCHAR(20) UNIQUE,
                    title VARCHAR(200) NOT NULL,
                    tax_no VARCHAR(20),
                    tax_office VARCHAR(100),
                    phone VARCHAR(20),
                    email VARCHAR(100),
                    address TEXT,
                    balance DECIMAL(15,2) DEFAULT 0,
                    credit_limit DECIMAL(15,2) DEFAULT 0,
                    is_supplier BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Ürünler / Stok
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".Products (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE CASCADE,
                    product_code VARCHAR(20) UNIQUE,
                    barcode VARCHAR(50),
                    name VARCHAR(200) NOT NULL,
                    category VARCHAR(100),
                    unit VARCHAR(20),
                    purchase_price DECIMAL(15,2) DEFAULT 0,
                    sale_price DECIMAL(15,2) DEFAULT 0,
                    stock_quantity DECIMAL(15,3) DEFAULT 0,
                    critical_stock DECIMAL(15,3) DEFAULT 0,
                    vat_rate DECIMAL(5,2) DEFAULT 18,
                    is_active BOOLEAN DEFAULT TRUE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Faturalar
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".Invoices (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE CASCADE,
                    invoice_no VARCHAR(50) UNIQUE NOT NULL,
                    invoice_date DATE NOT NULL,
                    invoice_type VARCHAR(20) CHECK (invoice_type IN ('Sales', 'Purchase', 'Return')),
                    customer_id INTEGER REFERENCES "{schema_name}".Customers(id),
                    total DECIMAL(15,2) DEFAULT 0,
                    vat_total DECIMAL(15,2) DEFAULT 0,
                    discount_total DECIMAL(15,2) DEFAULT 0,
                    grand_total DECIMAL(15,2) DEFAULT 0,
                    paid_amount DECIMAL(15,2) DEFAULT 0,
                    remaining_amount DECIMAL(15,2) DEFAULT 0,
                    currency VARCHAR(3) DEFAULT 'TRY',
                    exchange_rate DECIMAL(10,4) DEFAULT 1,
                    status VARCHAR(20) DEFAULT 'Draft',
                    payment_status VARCHAR(20) DEFAULT 'Unpaid',
                    payment_method VARCHAR(50) DEFAULT 'Nakit',
                    notes TEXT,
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Fatura Kalemleri
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".InvoiceItems (
                    id SERIAL PRIMARY KEY,
                    invoice_id INTEGER REFERENCES "{schema_name}".Invoices(id) ON DELETE CASCADE,
                    product_id INTEGER REFERENCES "{schema_name}".Products(id),
                    product_name VARCHAR(200) NOT NULL,
                    quantity DECIMAL(15,3) DEFAULT 1,
                    unit VARCHAR(20),
                    unit_price DECIMAL(15,2) DEFAULT 0,
                    discount_rate DECIMAL(5,2) DEFAULT 0,
                    discount_amount DECIMAL(15,2) DEFAULT 0,
                    vat_rate DECIMAL(5,2) DEFAULT 18,
                    vat_amount DECIMAL(15,2) DEFAULT 0,
                    line_total DECIMAL(15,2) DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Yevmiye Defteri
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".JournalEntries (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE CASCADE,
                    entry_date DATE NOT NULL,
                    account_code VARCHAR(20) NOT NULL,
                    account_name VARCHAR(200) NOT NULL,
                    explanation TEXT,
                    debit DECIMAL(15,2) DEFAULT 0,
                    credit DECIMAL(15,2) DEFAULT 0,
                    invoice_id INTEGER REFERENCES "{schema_name}".Invoices(id) ON DELETE CASCADE,
                    reference_no VARCHAR(50),
                    currency VARCHAR(3) DEFAULT 'TRY',
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Banka Hesapları
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".BankAccounts (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE CASCADE,
                    account_name VARCHAR(200) NOT NULL,
                    bank_name VARCHAR(200),
                    branch_name VARCHAR(100),
                    account_no VARCHAR(50),
                    iban VARCHAR(34),
                    balance DECIMAL(15,2) DEFAULT 0,
                    currency VARCHAR(3) DEFAULT 'TRY',
                    is_active BOOLEAN DEFAULT TRUE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Banka Hareketleri
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".BankTransactions (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE CASCADE,
                    bank_account_id INTEGER REFERENCES "{schema_name}".BankAccounts(id),
                    transaction_date DATE NOT NULL,
                    transaction_type VARCHAR(20) CHECK (transaction_type IN ('Deposit', 'Withdrawal', 'Transfer')),
                    amount DECIMAL(15,2) DEFAULT 0,
                    description TEXT,
                    reference_no VARCHAR(50),
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Audit Log
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".AuditLog (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES public.Users(id),
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id),
                    action VARCHAR(100) NOT NULL,
                    table_name VARCHAR(50),
                    record_id INTEGER,
                    old_data TEXT,
                    new_data TEXT,
                    ip_address VARCHAR(50),
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Günlük Ciro ve Kasa
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".DailyTurnovers (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE CASCADE,
                    entry_date DATE NOT NULL,
                    entry_type VARCHAR(20) NOT NULL,
                    category VARCHAR(150) NOT NULL,
                    amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                    payment_method VARCHAR(50) DEFAULT 'Nakit',
                    description TEXT,
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Günlük Kategori Havuzu
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".DailyTurnoverCategories (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE CASCADE,
                    category_type VARCHAR(20) NOT NULL,
                    name VARCHAR(150) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(branch_id, category_type, name)
                );
                """,
                # Depo Ürünleri
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".WarehouseProducts (
                    id SERIAL PRIMARY KEY,
                    product_code VARCHAR(50) UNIQUE,
                    barcode VARCHAR(50),
                    name VARCHAR(200) NOT NULL,
                    category VARCHAR(100),
                    unit VARCHAR(30) DEFAULT 'Adet',
                    purchase_price DECIMAL(15,2) DEFAULT 0,
                    sale_price DECIMAL(15,2) DEFAULT 0,
                    stock_quantity DECIMAL(15,3) DEFAULT 0,
                    critical_stock DECIMAL(15,3) DEFAULT 10,
                    is_active BOOLEAN DEFAULT TRUE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Depo Sevk Hareketleri
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".WarehouseStockMovements (
                    id SERIAL PRIMARY KEY,
                    warehouse_product_id INTEGER REFERENCES "{schema_name}".WarehouseProducts(id) ON DELETE CASCADE,
                    movement_type VARCHAR(20) NOT NULL,
                    quantity DECIMAL(15,3) NOT NULL,
                    unit VARCHAR(30),
                    previous_stock DECIMAL(15,3) DEFAULT 0,
                    new_stock DECIMAL(15,3) DEFAULT 0,
                    target_branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE SET NULL,
                    movement_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    document_no VARCHAR(100),
                    supplier_name VARCHAR(255),
                    description TEXT,
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ═══════════════════════════════════════════════════════
                # PERSONEL (ÇALIŞANLAR) TABLOSU
                # ═══════════════════════════════════════════════════════
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".Employees (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE SET NULL,
                    employee_code VARCHAR(30) UNIQUE,
                    full_name VARCHAR(200) NOT NULL,
                    national_id VARCHAR(11),
                    phone VARCHAR(20),
                    email VARCHAR(150),
                    address TEXT,
                    position VARCHAR(100),
                    department VARCHAR(100),
                    hire_date DATE,
                    birth_date DATE,
                    iban VARCHAR(34),
                    monthly_salary DECIMAL(15,2) DEFAULT 0,
                    salary_day INTEGER DEFAULT 1,
                    notes TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ═══════════════════════════════════════════════════════
                # ÖDEME PLANLARI (Personel Maaşı / Kira / Taksit / Diğer)
                # ═══════════════════════════════════════════════════════
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".PaymentPlans (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE SET NULL,
                    plan_type VARCHAR(30) NOT NULL,
                    title VARCHAR(250) NOT NULL,
                    payee_type VARCHAR(30),
                    payee_id INTEGER,
                    payee_name VARCHAR(200),
                    total_amount DECIMAL(15,2) DEFAULT 0,
                    installment_count INTEGER DEFAULT 1,
                    installment_no INTEGER DEFAULT 1,
                    gross_amount DECIMAL(15,2) DEFAULT 0,
                    advance_deduction DECIMAL(15,2) DEFAULT 0,
                    amount DECIMAL(15,2) NOT NULL,
                    due_date DATE NOT NULL,
                    payment_method VARCHAR(50) DEFAULT 'Havale / EFT',
                    account_id INTEGER,
                    status VARCHAR(20) DEFAULT 'bekliyor',
                    paid_date DATE,
                    paid_amount DECIMAL(15,2) DEFAULT 0,
                    reminder_days INTEGER DEFAULT 3,
                    notes TEXT,
                    reference_type VARCHAR(30),
                    reference_id INTEGER,
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ═══════════════════════════════════════════════════════
                # PERSONEL CARİ HAREKETLERİ (Avans / Maaş / Mahsup)
                # ═══════════════════════════════════════════════════════
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".EmployeeLedger (
                    id SERIAL PRIMARY KEY,
                    employee_id INTEGER REFERENCES "{schema_name}".Employees(id) ON DELETE CASCADE,
                    entry_type VARCHAR(30) NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    description TEXT,
                    payment_plan_id INTEGER,
                    account_id INTEGER,
                    remaining_amount DECIMAL(15,2) DEFAULT 0,
                    is_closed INTEGER DEFAULT 0,
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ═══════════════════════════════════════════════════════
                # AVANS MAHSUP EŞLEŞMELERİ
                # ═══════════════════════════════════════════════════════
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".AdvanceOffsets (
                    id SERIAL PRIMARY KEY,
                    advance_ledger_id INTEGER REFERENCES "{schema_name}".EmployeeLedger(id) ON DELETE CASCADE,
                    salary_plan_id INTEGER REFERENCES "{schema_name}".PaymentPlans(id) ON DELETE CASCADE,
                    offset_amount DECIMAL(15,2) NOT NULL,
                    offset_date DATE DEFAULT CURRENT_DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ═══════════════════════════════════════════════════════
                # FIRIN ÜRETİM & İMALAT TABLOLARI
                # ═══════════════════════════════════════════════════════
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".BakeryProductions (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE SET NULL,
                    production_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    product_name VARCHAR(200) NOT NULL,
                    category VARCHAR(50) DEFAULT 'Ekmek',
                    unit VARCHAR(30) DEFAULT 'Adet',
                    quantity DECIMAL(15,2) NOT NULL,
                    unit_cost DECIMAL(15,2) DEFAULT 0,
                    sale_price DECIMAL(15,2) DEFAULT 0,
                    shipped_quantity DECIMAL(15,2) DEFAULT 0,
                    external_sold_quantity DECIMAL(15,2) DEFAULT 0,
                    remaining_quantity DECIMAL(15,2) DEFAULT 0,
                    notes TEXT,
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".BranchShipments (
                    id SERIAL PRIMARY KEY,
                    shipment_no VARCHAR(50) UNIQUE,
                    source_branch_id INTEGER REFERENCES "{schema_name}".Branches(id),
                    target_branch_id INTEGER REFERENCES "{schema_name}".Branches(id),
                    shipment_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    product_name VARCHAR(200) NOT NULL,
                    quantity DECIMAL(15,2) NOT NULL,
                    unit VARCHAR(30) DEFAULT 'Adet',
                    unit_price DECIMAL(15,2) DEFAULT 0,
                    total_amount DECIMAL(15,2) DEFAULT 0,
                    status VARCHAR(30) DEFAULT 'Teslim Edildi',
                    driver_notes TEXT,
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".ExternalSales (
                    id SERIAL PRIMARY KEY,
                    sale_no VARCHAR(50) UNIQUE,
                    sale_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    customer_id INTEGER REFERENCES "{schema_name}".Customers(id) ON DELETE SET NULL,
                    customer_name VARCHAR(200) NOT NULL,
                    product_name VARCHAR(200) NOT NULL,
                    quantity DECIMAL(15,2) NOT NULL,
                    unit VARCHAR(30) DEFAULT 'Adet',
                    unit_price DECIMAL(15,2) DEFAULT 0,
                    total_amount DECIMAL(15,2) DEFAULT 0,
                    payment_method VARCHAR(50) DEFAULT 'Nakit',
                    payment_status VARCHAR(30) DEFAULT 'Paid',
                    notes TEXT,
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".BranchShipmentItems (
                    id SERIAL PRIMARY KEY,
                    shipment_id INTEGER REFERENCES "{schema_name}".BranchShipments(id) ON DELETE CASCADE,
                    product_name VARCHAR(200) NOT NULL,
                    category VARCHAR(50) DEFAULT 'Unlu Mamül',
                    quantity DECIMAL(15,2) NOT NULL,
                    unit VARCHAR(30) DEFAULT 'Adet',
                    unit_price DECIMAL(15,2) DEFAULT 0,
                    total_amount DECIMAL(15,2) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".ExternalSaleItems (
                    id SERIAL PRIMARY KEY,
                    sale_id INTEGER REFERENCES "{schema_name}".ExternalSales(id) ON DELETE CASCADE,
                    product_name VARCHAR(200) NOT NULL,
                    category VARCHAR(50) DEFAULT 'Unlu Mamül',
                    quantity DECIMAL(15,2) NOT NULL,
                    unit VARCHAR(30) DEFAULT 'Adet',
                    unit_price DECIMAL(15,2) DEFAULT 0,
                    total_amount DECIMAL(15,2) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ═══════════════════════════════════════════════════════
                # FIRIN İMALATHANE ÖZEL FİYAT LİSTESİ
                # ═══════════════════════════════════════════════════════
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".BakeryPriceList (
                    id SERIAL PRIMARY KEY,
                    product_name VARCHAR(150) NOT NULL,
                    category VARCHAR(50) DEFAULT 'Genel',
                    unit VARCHAR(30) DEFAULT 'Adet',
                    branch_price NUMERIC(15, 2) DEFAULT 0.00,
                    customer_price NUMERIC(15, 2) DEFAULT 0.00,
                    notes TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ═══════════════════════════════════════════════════════
                # İMALATHANE TEDARİK & MANAV/ŞARKÜTERİ ALIŞLARI
                # ═══════════════════════════════════════════════════════
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".BakerySupplies (
                    id SERIAL PRIMARY KEY,
                    invoice_id INT,
                    invoice_no VARCHAR(50),
                    supply_date DATE DEFAULT CURRENT_DATE,
                    supplier_name VARCHAR(150),
                    item_name VARCHAR(150),
                    category VARCHAR(150) DEFAULT 'Hammadde',
                    quantity NUMERIC(15, 3) DEFAULT 0.0,
                    unit VARCHAR(30) DEFAULT 'kg',
                    unit_price NUMERIC(15, 2) DEFAULT 0.00,
                    total_price NUMERIC(15, 2) DEFAULT 0.00,
                    received_by VARCHAR(100),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".BakerySupplyItems (
                    id SERIAL PRIMARY KEY,
                    supply_id INT REFERENCES "{schema_name}".BakerySupplies(id) ON DELETE CASCADE,
                    item_name VARCHAR(150) NOT NULL,
                    category VARCHAR(50) DEFAULT 'Hammadde',
                    quantity NUMERIC(15, 3) NOT NULL DEFAULT 1.0,
                    unit VARCHAR(30) DEFAULT 'kg',
                    unit_price NUMERIC(15, 2) DEFAULT 0.00,
                    total_price NUMERIC(15, 2) DEFAULT 0.00,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ═══════════════════════════════════════════════════════
                # GENEL ŞİRKET & ORTAK GİDERLERİ
                # ═══════════════════════════════════════════════════════
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".CompanyExpenses (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE SET NULL,
                    expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    person_name VARCHAR(200) NOT NULL,
                    amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                    category VARCHAR(100) DEFAULT 'Ortak Özel Harcama',
                    location_destination VARCHAR(255),
                    payment_method VARCHAR(50) DEFAULT 'Nakit',
                    document_no VARCHAR(100),
                    description TEXT,
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ═══════════════════════════════════════════════════════
                # AY SONU STOK SAYIM MODÜLÜ TABLOLARI
                # ═══════════════════════════════════════════════════════
                # 1. Sayım Dönemleri
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".StockCountSessions (
                    id SERIAL PRIMARY KEY,
                    branch_id INTEGER REFERENCES "{schema_name}".Branches(id) ON DELETE CASCADE,
                    period_name VARCHAR(50) NOT NULL,
                    status VARCHAR(20) DEFAULT 'Draft',
                    notes TEXT,
                    created_by INTEGER REFERENCES public.Users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # 2. Sayım Kalemleri
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".StockCountItems (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES "{schema_name}".StockCountSessions(id) ON DELETE CASCADE,
                    category VARCHAR(100),
                    product_name VARCHAR(150) NOT NULL,
                    unit VARCHAR(50) DEFAULT 'Adet',
                    opening_stock DECIMAL(15,2) DEFAULT 0,
                    incoming_stock DECIMAL(15,2) DEFAULT 0,
                    physical_count DECIMAL(15,2) DEFAULT 0,
                    sold_out DECIMAL(15,2) DEFAULT 0,
                    transfer_out_qty DECIMAL(15,2) DEFAULT 0,
                    waste_qty DECIMAL(15,2) DEFAULT 0,
                    waste_value DECIMAL(15,2) DEFAULT 0,
                    unit_cost DECIMAL(15,2) DEFAULT 0,
                    remaining_value DECIMAL(15,2) DEFAULT 0,
                    sold_value DECIMAL(15,2) DEFAULT 0,
                    display_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # 3. Gelen-Giden Hareket Logu
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".StockMovements (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES "{schema_name}".StockCountSessions(id) ON DELETE CASCADE,
                    date DATE NOT NULL DEFAULT CURRENT_DATE,
                    category VARCHAR(100),
                    product_name VARCHAR(150) NOT NULL,
                    movement_type VARCHAR(50) NOT NULL,
                    quantity DECIMAL(15,2) DEFAULT 0,
                    unit VARCHAR(50) DEFAULT 'Adet',
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # 4. Varsayılan Sayım Şablon Ürünleri
                f"""
                CREATE TABLE IF NOT EXISTS "{schema_name}".StockCountTemplateItems (
                    id SERIAL PRIMARY KEY,
                    category VARCHAR(100) NOT NULL,
                    product_name VARCHAR(150) NOT NULL,
                    unit VARCHAR(50) DEFAULT 'Adet',
                    display_order INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(category, product_name)
                );
                """
            ]

            with self.get_cursor(commit=True) as cursor:
                for q in tables:
                    cursor.execute(q)
                # Bakery view alias'ları
                cursor.execute(f'CREATE OR REPLACE VIEW "{schema_name}".bakery_supplies AS SELECT * FROM "{schema_name}".BakerySupplies;')
                cursor.execute(f'CREATE OR REPLACE VIEW "{schema_name}".bakery_supply_items AS SELECT * FROM "{schema_name}".BakerySupplyItems;')
                cursor.execute(f'CREATE OR REPLACE VIEW "{schema_name}".bakery_price_list AS SELECT * FROM "{schema_name}".BakeryPriceList;')

            # 3. İndeksleri oluştur
            prefix = schema_name.replace('-', '_').replace('.', '_')
            indexes = [
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_cust_branch ON "{schema_name}".Customers(branch_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_cust_tax ON "{schema_name}".Customers(tax_no);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_cust_code ON "{schema_name}".Customers(customer_code);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_inv_branch ON "{schema_name}".Invoices(branch_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_inv_date ON "{schema_name}".Invoices(invoice_date);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_inv_cust ON "{schema_name}".Invoices(customer_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_inv_status ON "{schema_name}".Invoices(status);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_inv_item ON "{schema_name}".InvoiceItems(invoice_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_journal_branch ON "{schema_name}".JournalEntries(branch_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_prod_branch ON "{schema_name}".Products(branch_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_prod_code ON "{schema_name}".Products(product_code);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_bank_branch ON "{schema_name}".BankAccounts(branch_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_dt_branch_date ON "{schema_name}".DailyTurnovers(branch_id, entry_date);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_dt_type ON "{schema_name}".DailyTurnovers(entry_type);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_wh_prod_code ON "{schema_name}".WarehouseProducts(product_code);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_wh_mov_prod ON "{schema_name}".WarehouseStockMovements(warehouse_product_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_wh_mov_branch ON "{schema_name}".WarehouseStockMovements(target_branch_id);',
                # YENİ: Personel & Ödeme Planı index'leri
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_emp_branch ON "{schema_name}".Employees(branch_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_emp_active ON "{schema_name}".Employees(is_active);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_plan_due ON "{schema_name}".PaymentPlans(due_date);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_plan_status ON "{schema_name}".PaymentPlans(status);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_plan_type ON "{schema_name}".PaymentPlans(plan_type);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_plan_payee ON "{schema_name}".PaymentPlans(payee_type, payee_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_ledger_emp ON "{schema_name}".EmployeeLedger(employee_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_ledger_type ON "{schema_name}".EmployeeLedger(entry_type);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_ledger_open ON "{schema_name}".EmployeeLedger(is_closed);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_offset_advance ON "{schema_name}".AdvanceOffsets(advance_ledger_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_offset_salary ON "{schema_name}".AdvanceOffsets(salary_plan_id);',
                # İmalat & Sevkiyat index'leri
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_prod_date ON "{schema_name}".BakeryProductions(production_date);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_ship_date ON "{schema_name}".BranchShipments(shipment_date);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_ext_date ON "{schema_name}".ExternalSales(sale_date);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_bsi_shipment ON "{schema_name}".BranchShipmentItems(shipment_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_esi_sale ON "{schema_name}".ExternalSaleItems(sale_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_bsi_sup ON "{schema_name}".BakerySupplyItems(supply_id);',
                # Stok Sayımı index'leri
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_sc_sess_branch ON "{schema_name}".StockCountSessions(branch_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_sc_item_sess ON "{schema_name}".StockCountItems(session_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_sc_mov_sess ON "{schema_name}".StockMovements(session_id);',
                f'CREATE INDEX IF NOT EXISTS idx_{prefix}_sc_mov_date ON "{schema_name}".StockMovements(date);'
            ]
            with self.get_cursor(commit=True) as cursor:
                for idx in indexes:
                    cursor.execute(idx)

            # 4. Trigger'ları oluştur
            triggers = [
                f"""
                DROP TRIGGER IF EXISTS update_invoice_totals_trigger ON "{schema_name}".InvoiceItems;
                CREATE TRIGGER update_invoice_totals_trigger
                AFTER INSERT OR UPDATE OR DELETE ON "{schema_name}".InvoiceItems
                FOR EACH ROW
                EXECUTE FUNCTION public.update_invoice_totals();
                """,
                f"""
                DROP TRIGGER IF EXISTS generate_customer_code_trigger ON "{schema_name}".Customers;
                CREATE TRIGGER generate_customer_code_trigger
                BEFORE INSERT ON "{schema_name}".Customers
                FOR EACH ROW
                EXECUTE FUNCTION public.generate_customer_code();
                """,
                f"""
                DROP TRIGGER IF EXISTS generate_invoice_number_trigger ON "{schema_name}".Invoices;
                CREATE TRIGGER generate_invoice_number_trigger
                BEFORE INSERT ON "{schema_name}".Invoices
                FOR EACH ROW
                WHEN (NEW.invoice_no IS NULL OR NEW.invoice_no = '')
                EXECUTE FUNCTION public.generate_invoice_number();
                """
            ]
            with self.get_cursor(commit=True) as cursor:
                for trg in triggers:
                    cursor.execute(trg)

            # 5. Varsayılan Başlangıç Verileri (Şube, Kategoriler, Ürünler, Hesap Planı)
            with self.get_cursor(commit=True) as cursor:
                # Şube kontrolü
                cursor.execute(f'SELECT id FROM "{schema_name}".Branches LIMIT 1;')
                first_branch = cursor.fetchone()
                if not first_branch:
                    cursor.execute(f"""
                        INSERT INTO "{schema_name}".Branches (name, city, address)
                        VALUES (%s, %s, 'Merkez')
                        RETURNING id;
                    """, (default_branch_name, city))
                    first_branch = cursor.fetchone()

                branch_id = first_branch['id'] if first_branch else 1

                # Varsayılan tüm şubeleri bu tenant alanında da garanti et
                tenant_target_branches = [
                    ('Armada', 'Tekirdağ', 'Çorlu', 'retail'),
                    ('Çobançeşme', 'Tekirdağ', 'Çorlu', 'retail'),
                    ('Rumeli', 'Tekirdağ', 'Çorlu', 'retail'),
                    ('Orion Şube', 'Tekirdağ', 'Çorlu', 'retail'),
                    ('İmalathane', 'Tekirdağ', 'Çorlu Üretim & Fırın İmalat Merkezi', 'bakery'),
                ]
                for tb_name, tb_city, tb_addr, tb_type in tenant_target_branches:
                    cursor.execute(f'SELECT id FROM "{schema_name}".Branches WHERE LOWER(name) = LOWER(%s) LIMIT 1;', (tb_name,))
                    if not cursor.fetchone():
                        cursor.execute(f"""
                            INSERT INTO "{schema_name}".Branches (name, city, address, branch_type, is_active)
                            VALUES (%s, %s, %s, %s, TRUE);
                        """, (tb_name, tb_city, tb_addr, tb_type))

                # İmalathane her zaman fırın (bakery) tipinde olmalı; aksi halde
                # Fırın İmalathanesi / üretim bölümleri kullanıcıya görünmez.
                cursor.execute(f"""
                    UPDATE "{schema_name}".Branches
                    SET branch_type = 'bakery'
                    WHERE (name = 'İmalathane' OR LOWER(name) = LOWER('İmalathane'))
                      AND COALESCE(branch_type, '') <> 'bakery';
                """)

                # Hesap Planı
                cursor.execute(f'SELECT id FROM "{schema_name}".JournalEntries LIMIT 1;')
                if not cursor.fetchone():
                    accounts = [
                        ('100', 'KASA'), ('102', 'BANKALAR'), ('120', 'ALICILAR'),
                        ('150', 'İLK MADDE VE MALZEME'), ('250', 'BANKALAR KREDİLERİ'),
                        ('320', 'SATICILAR'), ('391', 'HESAPLANAN KDV'),
                        ('600', 'YURTİÇİ SATIŞLAR'), ('620', 'SATIŞLARIN MALİYETİ'),
                        ('770', 'GENEL YÖNETİM GİDERLERİ')
                    ]
                    for code, name in accounts:
                        cursor.execute(f"""
                            INSERT INTO "{schema_name}".JournalEntries 
                            (branch_id, entry_date, account_code, account_name, explanation, debit, credit)
                            VALUES (%s, CURRENT_DATE, %s, %s, %s, 0, 0)
                        """, (branch_id, code, name, f"Hesap Planı - {name}"))

                # Günlük Ciro Kategorileri
                cursor.execute(f'SELECT id FROM "{schema_name}".DailyTurnoverCategories LIMIT 1;')
                if not cursor.fetchone():
                    default_incomes = [
                        "Tezgâh Satışı", "Paket Servis", "Toptan Ekmek Satışı",
                        "Pastane & Tatlı", "Kafeterya & İçecek", "Özel Sipariş"
                    ]
                    default_expenses = [
                        "Un & Hammadde Alımı", "Maya, Tuz & Katkı", "Elektrik / Su / Doğalgaz",
                        "Personel Yevmiye / Maaş", "Yakıt & Ulaşım", "Kira & Aidat",
                        "Ambalaj & Poşet", "Genel Temizlik & Bakım"
                    ]
                    for inc in default_incomes:
                        cursor.execute(f"""
                            INSERT INTO "{schema_name}".DailyTurnoverCategories (branch_id, category_type, name)
                            VALUES (%s, 'Income', %s)
                            ON CONFLICT (branch_id, category_type, name) DO NOTHING;
                        """, (branch_id, inc))
                    for exp in default_expenses:
                        cursor.execute(f"""
                            INSERT INTO "{schema_name}".DailyTurnoverCategories (branch_id, category_type, name)
                            VALUES (%s, 'Expense', %s)
                            ON CONFLICT (branch_id, category_type, name) DO NOTHING;
                        """, (branch_id, exp))

                # Depo Ürünleri
                cursor.execute(f'SELECT id FROM "{schema_name}".WarehouseProducts LIMIT 1;')
                if not cursor.fetchone():
                    default_products = [
                        ("DEP-001", "Un (Tip 550 Ekmeklik)", "Hammadde", "Çuval (50 Kg)", 650.00, 750.00, 120.0, 20.0, "Birinci kalite ekmeklik un"),
                        ("DEP-002", "Un (Börek & Baklavalık)", "Hammadde", "Çuval (50 Kg)", 780.00, 900.00, 45.0, 10.0, "Özel baklavalık un"),
                        ("DEP-003", "Yaş Ekmek Mayası", "Hammadde", "Koli (24 Adet)", 320.00, 380.00, 35.0, 8.0, "Taze pres maya"),
                        ("DEP-004", "İyotlu Sofra Tuzu", "Hammadde", "Çuval (25 Kg)", 120.00, 150.00, 50.0, 10.0, "İnce sofra ve hamur tuzu"),
                        ("DEP-005", "Toz Şeker", "Hammadde", "Çuval (50 Kg)", 1100.00, 1300.00, 25.0, 5.0, "Kristal toz şeker"),
                        ("DEP-006", "Susam (Kavrulmuş)", "Hammadde", "Çuval (25 Kg)", 1850.00, 2200.00, 18.0, 5.0, "Simitlik kavrulmuş susam"),
                        ("DEP-007", "Bitkisel Margarin / Yağ", "Hammadde", "Koli (10 Kg)", 480.00, 560.00, 30.0, 6.0, "Börek ve poğaça yağı"),
                        ("DEP-008", "Ayçiçek Yağı", "Hammadde", "Teneke (18 Lt)", 720.00, 850.00, 40.0, 8.0, "Birinci sınıf yemeklik yağ"),
                        ("DEP-009", "Kraft Ekmek Poşeti", "Ambalaj", "Koli (1000 Adet)", 250.00, 300.00, 60.0, 15.0, "Logolu kraft ekmek kesesi"),
                        ("DEP-010", "Pastane Taşıma Kutusu", "Ambalaj", "Koli (500 Adet)", 420.00, 500.00, 25.0, 10.0, "Gıda temasına uygun kutu"),
                    ]
                    for p in default_products:
                        cursor.execute(f"""
                            INSERT INTO "{schema_name}".WarehouseProducts (
                                product_code, name, category, unit,
                                purchase_price, sale_price, stock_quantity, critical_stock, notes
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (product_code) DO NOTHING;
                        """, p)



            missing = self.get_missing_tenant_tables(schema_name)
            if missing:
                raise RuntimeError(
                    f"Kullanıcı veritabanı alanı eksik kuruldu ({schema_name}). "
                    f"Eksik tablolar: {', '.join(missing)}. Veri güvenliği için giriş engellendi."
                )

            self._ensured_tenant_schemas.add(schema_name)
            if hasattr(self, '_ensured_turnover_schemas'):
                self._ensured_turnover_schemas.add(schema_name)
            if hasattr(self, '_ensured_payment_plan_schemas'):
                self._ensured_payment_plan_schemas.add(schema_name)
            if hasattr(self, '_ensured_stock_count_schemas'):
                self._ensured_stock_count_schemas.add(schema_name)
            if hasattr(self, '_ensured_bakery_supply_schemas'):
                self._ensured_bakery_supply_schemas.add(schema_name)
                self._ensured_production_schemas.add(schema_name)

            logger.info(f"✅ Kullanıcıya özel izole veritabanı alanı hazır: {schema_name} (şehir: {city})")
            return True
        except Exception as e:
            logger.error(f"❌ ensure_tenant_schema hatası ({schema_name}): {e}")
            raise

    def ensure_stock_count_tables(self, schema_name: Optional[str] = None):
        """Ay Sonu Stok Sayım Modülü tablolarını mevcut/verilen şemada oluşturur"""
        target_schema = schema_name or self.get_tenant()
        if not target_schema or target_schema == 'public':
            return True
        if not hasattr(self, '_ensured_stock_count_schemas'):
            self._ensured_stock_count_schemas = set()
        if target_schema in self._ensured_stock_count_schemas:
            return True
        try:
            with self.get_cursor(commit=True) as cursor:
                # 1. Sessions
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS "{target_schema}".StockCountSessions (
                        id SERIAL PRIMARY KEY,
                        branch_id INTEGER REFERENCES "{target_schema}".Branches(id) ON DELETE CASCADE,
                        period_name VARCHAR(50) NOT NULL,
                        status VARCHAR(20) DEFAULT 'Draft',
                        notes TEXT,
                        created_by INTEGER REFERENCES public.Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # 2. Items
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS "{target_schema}".StockCountItems (
                        id SERIAL PRIMARY KEY,
                        session_id INTEGER REFERENCES "{target_schema}".StockCountSessions(id) ON DELETE CASCADE,
                        category VARCHAR(100),
                        product_name VARCHAR(150) NOT NULL,
                        unit VARCHAR(50) DEFAULT 'Adet',
                        opening_stock DECIMAL(15,2) DEFAULT 0,
                        transfer_out_qty DECIMAL(15,2) DEFAULT 0,
                        waste_qty DECIMAL(15,2) DEFAULT 0,
                        waste_value DECIMAL(15,2) DEFAULT 0,
                        incoming_stock DECIMAL(15,2) DEFAULT 0,
                        physical_count DECIMAL(15,2) DEFAULT 0,
                        sold_out DECIMAL(15,2) DEFAULT 0,
                        unit_cost DECIMAL(15,2) DEFAULT 0,
                        remaining_value DECIMAL(15,2) DEFAULT 0,
                        sold_value DECIMAL(15,2) DEFAULT 0,
                        display_order INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Eksik olabilecek yeni sütunları güvenli şekilde ekle
                cursor.execute(f"""
                    ALTER TABLE "{target_schema}".StockCountItems 
                    ADD COLUMN IF NOT EXISTS transfer_out_qty DECIMAL(15,2) DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS waste_qty DECIMAL(15,2) DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS waste_value DECIMAL(15,2) DEFAULT 0;
                """)
                # 3. Movements
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS "{target_schema}".StockMovements (
                        id SERIAL PRIMARY KEY,
                        session_id INTEGER REFERENCES "{target_schema}".StockCountSessions(id) ON DELETE CASCADE,
                        date DATE NOT NULL DEFAULT CURRENT_DATE,
                        category VARCHAR(100),
                        product_name VARCHAR(150) NOT NULL,
                        movement_type VARCHAR(50) NOT NULL,
                        quantity DECIMAL(15,2) DEFAULT 0,
                        unit VARCHAR(50) DEFAULT 'Adet',
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # 4. Template Items
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS "{target_schema}".StockCountTemplateItems (
                        id SERIAL PRIMARY KEY,
                        category VARCHAR(100) NOT NULL,
                        product_name VARCHAR(150) NOT NULL,
                        unit VARCHAR(50) DEFAULT 'Adet',
                        display_order INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(category, product_name)
                    );
                """)
                # Indexes
                prefix = target_schema.replace('-', '_').replace('.', '_')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{prefix}_sc_sess_branch ON "{target_schema}".StockCountSessions(branch_id);')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{prefix}_sc_item_sess ON "{target_schema}".StockCountItems(session_id);')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{prefix}_sc_mov_sess ON "{target_schema}".StockMovements(session_id);')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{prefix}_sc_mov_date ON "{target_schema}".StockMovements(date);')


            self._ensured_stock_count_schemas.add(target_schema)
            logger.info(f"✅ Stok Sayım tabloları hazır: {target_schema}")
            return True
        except Exception as e:
            logger.error(f"❌ ensure_stock_count_tables hatası: {e}")
            return False

    # ══════════════════════════════════════════════════════════════
    # VERİTABANI BAŞLATMA (public şema)
    # ══════════════════════════════════════════════════════════════

    def initialize_database(self, force: bool = False):
        """Veritabanı tablolarını oluştur"""
        try:
            if not force and self.is_initialized():
                return True

            self._create_tables()
            self._create_indexes()
            self._create_triggers()
            self._insert_default_data()

            logger.info("✅ Veritabanı başarıyla oluşturuldu!")
            return True
        except Exception as e:
            logger.error(f"❌ Veritabanı oluşturma hatası: {e}")
            raise

    def _create_tables(self):
        """Tabloları oluştur"""
        tables = [
            # Şubeler
            """
            CREATE TABLE IF NOT EXISTS Branches (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                city VARCHAR(100),
                phone VARCHAR(20) NULL,
                address TEXT,
                tax_no VARCHAR(20) NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Kullanıcılar
            """
            CREATE TABLE IF NOT EXISTS Users (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(100),
                email VARCHAR(100),
                phone VARCHAR(20),
                role VARCHAR(50) DEFAULT 'Admin',
                is_active BOOLEAN DEFAULT TRUE,
                is_online BOOLEAN DEFAULT FALSE,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Cari Hesaplar
            """
            CREATE TABLE IF NOT EXISTS Customers (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                customer_code VARCHAR(20) UNIQUE,
                title VARCHAR(200) NOT NULL,
                tax_no VARCHAR(20),
                tax_office VARCHAR(100),
                phone VARCHAR(20),
                email VARCHAR(100),
                address TEXT,
                balance DECIMAL(15,2) DEFAULT 0,
                credit_limit DECIMAL(15,2) DEFAULT 0,
                is_supplier BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Ürünler/Stok
            """
            CREATE TABLE IF NOT EXISTS Products (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                product_code VARCHAR(20) UNIQUE,
                barcode VARCHAR(50),
                name VARCHAR(200) NOT NULL,
                category VARCHAR(100),
                unit VARCHAR(20),
                purchase_price DECIMAL(15,2) DEFAULT 0,
                sale_price DECIMAL(15,2) DEFAULT 0,
                stock_quantity DECIMAL(15,3) DEFAULT 0,
                critical_stock DECIMAL(15,3) DEFAULT 0,
                vat_rate DECIMAL(5,2) DEFAULT 18,
                is_active BOOLEAN DEFAULT TRUE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Faturalar
            """
            CREATE TABLE IF NOT EXISTS Invoices (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                invoice_no VARCHAR(50) UNIQUE NOT NULL,
                invoice_date DATE NOT NULL,
                invoice_type VARCHAR(20) CHECK (invoice_type IN ('Sales', 'Purchase', 'Return')),
                customer_id INTEGER REFERENCES Customers(id),
                total DECIMAL(15,2) DEFAULT 0,
                vat_total DECIMAL(15,2) DEFAULT 0,
                discount_total DECIMAL(15,2) DEFAULT 0,
                grand_total DECIMAL(15,2) DEFAULT 0,
                paid_amount DECIMAL(15,2) DEFAULT 0,
                remaining_amount DECIMAL(15,2) DEFAULT 0,
                currency VARCHAR(3) DEFAULT 'TRY',
                exchange_rate DECIMAL(10,4) DEFAULT 1,
                status VARCHAR(20) DEFAULT 'Draft',
                payment_status VARCHAR(20) DEFAULT 'Unpaid',
                payment_method VARCHAR(50) DEFAULT 'Nakit',
                notes TEXT,
                created_by INTEGER REFERENCES Users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Fatura Kalemleri
            """
            CREATE TABLE IF NOT EXISTS InvoiceItems (
                id SERIAL PRIMARY KEY,
                invoice_id INTEGER REFERENCES Invoices(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES Products(id),
                product_name VARCHAR(200) NOT NULL,
                quantity DECIMAL(15,3) DEFAULT 1,
                unit VARCHAR(20),
                unit_price DECIMAL(15,2) DEFAULT 0,
                discount_rate DECIMAL(5,2) DEFAULT 0,
                discount_amount DECIMAL(15,2) DEFAULT 0,
                vat_rate DECIMAL(5,2) DEFAULT 18,
                vat_amount DECIMAL(15,2) DEFAULT 0,
                line_total DECIMAL(15,2) DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Muhasebe Kayıtları
            """
            CREATE TABLE IF NOT EXISTS JournalEntries (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                entry_date DATE NOT NULL,
                account_code VARCHAR(20) NOT NULL,
                account_name VARCHAR(200) NOT NULL,
                explanation TEXT,
                debit DECIMAL(15,2) DEFAULT 0,
                credit DECIMAL(15,2) DEFAULT 0,
                invoice_id INTEGER REFERENCES Invoices(id) ON DELETE CASCADE,
                reference_no VARCHAR(50),
                currency VARCHAR(3) DEFAULT 'TRY',
                created_by INTEGER REFERENCES Users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Banka Hesapları
            """
            CREATE TABLE IF NOT EXISTS BankAccounts (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                account_name VARCHAR(200) NOT NULL,
                bank_name VARCHAR(200),
                branch_name VARCHAR(100),
                account_no VARCHAR(50),
                iban VARCHAR(34),
                balance DECIMAL(15,2) DEFAULT 0,
                currency VARCHAR(3) DEFAULT 'TRY',
                is_active BOOLEAN DEFAULT TRUE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Banka İşlemleri
            """
            CREATE TABLE IF NOT EXISTS BankTransactions (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                bank_account_id INTEGER REFERENCES BankAccounts(id),
                transaction_date DATE NOT NULL,
                transaction_type VARCHAR(20) CHECK (transaction_type IN ('Deposit', 'Withdrawal', 'Transfer')),
                amount DECIMAL(15,2) DEFAULT 0,
                description TEXT,
                reference_no VARCHAR(50),
                created_by INTEGER REFERENCES Users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Audit Log
            """
            CREATE TABLE IF NOT EXISTS AuditLog (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES Users(id),
                branch_id INTEGER REFERENCES Branches(id),
                action VARCHAR(100) NOT NULL,
                table_name VARCHAR(50),
                record_id INTEGER,
                old_data TEXT,
                new_data TEXT,
                ip_address VARCHAR(50),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Sistem Ayarları
            """
            CREATE TABLE IF NOT EXISTS SystemSettings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Günlük Ciro & Kasa Hareketleri
            """
            CREATE TABLE IF NOT EXISTS DailyTurnovers (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                entry_date DATE NOT NULL,
                entry_type VARCHAR(20) NOT NULL,
                category VARCHAR(150) NOT NULL,
                amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                payment_method VARCHAR(50) DEFAULT 'Nakit',
                description TEXT,
                created_by INTEGER REFERENCES Users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Akıllı Kayar Seçenek / Kategori Havuzu
            """
            CREATE TABLE IF NOT EXISTS DailyTurnoverCategories (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                category_type VARCHAR(20) NOT NULL,
                name VARCHAR(150) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(branch_id, category_type, name)
            )
            """,
            # Merkez Depo Ürünleri
            """
            CREATE TABLE IF NOT EXISTS WarehouseProducts (
                id SERIAL PRIMARY KEY,
                product_code VARCHAR(50) UNIQUE,
                barcode VARCHAR(50),
                name VARCHAR(200) NOT NULL,
                category VARCHAR(100),
                unit VARCHAR(30) DEFAULT 'Adet',
                purchase_price DECIMAL(15,2) DEFAULT 0,
                sale_price DECIMAL(15,2) DEFAULT 0,
                stock_quantity DECIMAL(15,3) DEFAULT 0,
                critical_stock DECIMAL(15,3) DEFAULT 10,
                is_active BOOLEAN DEFAULT TRUE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Depo Stok Hareketleri ve Şubelere Sevkiyat
            """
            CREATE TABLE IF NOT EXISTS WarehouseStockMovements (
                id SERIAL PRIMARY KEY,
                warehouse_product_id INTEGER REFERENCES WarehouseProducts(id) ON DELETE CASCADE,
                movement_type VARCHAR(20) NOT NULL,
                quantity DECIMAL(15,3) NOT NULL,
                unit VARCHAR(30),
                previous_stock DECIMAL(15,3) DEFAULT 0,
                new_stock DECIMAL(15,3) DEFAULT 0,
                target_branch_id INTEGER REFERENCES Branches(id) ON DELETE SET NULL,
                movement_date DATE NOT NULL DEFAULT CURRENT_DATE,
                document_no VARCHAR(100),
                supplier_name VARCHAR(255),
                description TEXT,
                created_by INTEGER REFERENCES Users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Genel Şirket & Ortak Giderleri
            """
            CREATE TABLE IF NOT EXISTS CompanyExpenses (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES Branches(id) ON DELETE SET NULL,
                expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
                person_name VARCHAR(200) NOT NULL,
                amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                category VARCHAR(100) DEFAULT 'Ortak Özel Harcama',
                location_destination VARCHAR(255),
                payment_method VARCHAR(50) DEFAULT 'Nakit',
                document_no VARCHAR(100),
                description TEXT,
                created_by INTEGER REFERENCES Users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]

        with self.get_cursor(commit=True) as cursor:
            for table in tables:
                cursor.execute(table)
            try:
                cursor.execute("ALTER TABLE Invoices ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'Nakit';")
                cursor.execute("ALTER TABLE Users ADD COLUMN IF NOT EXISTS is_online BOOLEAN DEFAULT FALSE;")
            except Exception as e:
                logger.warning(f"Kolon güncelleme uyarısı: {e}")

        logger.info("✅ Tablolar oluşturuldu")

    def _create_indexes(self):
        """Performans için index'ler oluştur"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_customers_branch ON Customers(branch_id)",
            "CREATE INDEX IF NOT EXISTS idx_customers_tax ON Customers(tax_no)",
            "CREATE INDEX IF NOT EXISTS idx_customers_code ON Customers(customer_code)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_branch ON Invoices(branch_id)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_date ON Invoices(invoice_date)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_customer ON Invoices(customer_id)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_status ON Invoices(status)",
            "CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON InvoiceItems(invoice_id)",
            "CREATE INDEX IF NOT EXISTS idx_journal_branch ON JournalEntries(branch_id)",
            "CREATE INDEX IF NOT EXISTS idx_journal_date ON JournalEntries(entry_date)",
            "CREATE INDEX IF NOT EXISTS idx_journal_account ON JournalEntries(account_code)",
            "CREATE INDEX IF NOT EXISTS idx_products_branch ON Products(branch_id)",
            "CREATE INDEX IF NOT EXISTS idx_products_code ON Products(product_code)",
            "CREATE INDEX IF NOT EXISTS idx_bank_accounts_branch ON BankAccounts(branch_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_user ON AuditLog(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_date ON AuditLog(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_daily_turnovers_branch_date ON DailyTurnovers(branch_id, entry_date)",
            "CREATE INDEX IF NOT EXISTS idx_daily_turnovers_type ON DailyTurnovers(entry_type)",
            "CREATE INDEX IF NOT EXISTS idx_turnover_categories_lookup ON DailyTurnoverCategories(branch_id, category_type)",
            "CREATE INDEX IF NOT EXISTS idx_warehouse_products_code ON WarehouseProducts(product_code)",
            "CREATE INDEX IF NOT EXISTS idx_warehouse_products_cat ON WarehouseProducts(category)",
            "CREATE INDEX IF NOT EXISTS idx_warehouse_movements_prod ON WarehouseStockMovements(warehouse_product_id)",
            "CREATE INDEX IF NOT EXISTS idx_warehouse_movements_type ON WarehouseStockMovements(movement_type)",
            "CREATE INDEX IF NOT EXISTS idx_warehouse_movements_branch ON WarehouseStockMovements(target_branch_id)",
            "CREATE INDEX IF NOT EXISTS idx_warehouse_movements_date ON WarehouseStockMovements(movement_date)"
        ]

        with self.get_cursor(commit=True) as cursor:
            for index in indexes:
                cursor.execute(index)

        logger.info("✅ Index'ler oluşturuldu")

    def ensure_warehouse_tables(self):
        """Merkez Depo ve Sevkiyat tablolarının varlığını garantiye alır ve varsayılan hammadde/ürünleri ekler"""
        tenant = self.get_tenant()
        if not tenant or tenant == 'public':
            return
        try:
            with self.get_cursor(commit=True) as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS WarehouseProducts (
                        id SERIAL PRIMARY KEY,
                        product_code VARCHAR(50) UNIQUE,
                        barcode VARCHAR(50),
                        name VARCHAR(200) NOT NULL,
                        category VARCHAR(100),
                        unit VARCHAR(30) DEFAULT 'Adet',
                        purchase_price DECIMAL(15,2) DEFAULT 0,
                        sale_price DECIMAL(15,2) DEFAULT 0,
                        stock_quantity DECIMAL(15,3) DEFAULT 0,
                        critical_stock DECIMAL(15,3) DEFAULT 10,
                        is_active BOOLEAN DEFAULT TRUE,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS WarehouseStockMovements (
                        id SERIAL PRIMARY KEY,
                        warehouse_product_id INTEGER REFERENCES WarehouseProducts(id) ON DELETE CASCADE,
                        movement_type VARCHAR(20) NOT NULL,
                        quantity DECIMAL(15,3) NOT NULL,
                        unit VARCHAR(30),
                        target_branch_id INTEGER REFERENCES Branches(id) ON DELETE SET NULL,
                        movement_date DATE NOT NULL DEFAULT CURRENT_DATE,
                        document_no VARCHAR(100),
                        description TEXT,
                        created_by INTEGER REFERENCES Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_warehouse_products_code ON WarehouseProducts(product_code);
                    CREATE INDEX IF NOT EXISTS idx_warehouse_products_cat ON WarehouseProducts(category);
                    CREATE INDEX IF NOT EXISTS idx_warehouse_movements_prod ON WarehouseStockMovements(warehouse_product_id);
                    CREATE INDEX IF NOT EXISTS idx_warehouse_movements_type ON WarehouseStockMovements(movement_type);
                    CREATE INDEX IF NOT EXISTS idx_warehouse_movements_branch ON WarehouseStockMovements(target_branch_id);
                    CREATE INDEX IF NOT EXISTS idx_warehouse_movements_date ON WarehouseStockMovements(movement_date);
                """)

            count_res = self.fetch_one("SELECT COUNT(*) as count FROM WarehouseProducts")
            if count_res and count_res['count'] == 0:
                default_products = [
                    ("DEP-001", "Un (Tip 550 Ekmeklik)", "Hammadde", "Çuval (50 Kg)", 650.00, 750.00, 120.0, 20.0, "Birinci kalite ekmeklik un"),
                    ("DEP-002", "Un (Börek & Baklavalık)", "Hammadde", "Çuval (50 Kg)", 780.00, 900.00, 45.0, 10.0, "Özel baklavalık un"),
                    ("DEP-003", "Yaş Ekmek Mayası", "Hammadde", "Koli (24 Adet)", 320.00, 380.00, 35.0, 8.0, "Taze pres maya"),
                    ("DEP-004", "İyotlu Sofra Tuzu", "Hammadde", "Çuval (25 Kg)", 120.00, 150.00, 50.0, 10.0, "İnce sofra ve hamur tuzu"),
                    ("DEP-005", "Toz Şeker", "Hammadde", "Çuval (50 Kg)", 1100.00, 1300.00, 25.0, 5.0, "Kristal toz şeker"),
                    ("DEP-006", "Susam (Kavrulmuş)", "Hammadde", "Çuval (25 Kg)", 1850.00, 2200.00, 18.0, 5.0, "Simitlik kavrulmuş susam"),
                    ("DEP-007", "Bitkisel Margarin / Yağ", "Hammadde", "Koli (10 Kg)", 480.00, 560.00, 30.0, 6.0, "Börek ve poğaça yağı"),
                    ("DEP-008", "Ayçiçek Yağı", "Hammadde", "Teneke (18 Lt)", 720.00, 850.00, 40.0, 8.0, "Birinci sınıf yemeklik yağ"),
                    ("DEP-009", "Kraft Ekmek Poşeti", "Ambalaj", "Koli (1000 Adet)", 250.00, 300.00, 60.0, 15.0, "Logolu kraft ekmek kesesi"),
                    ("DEP-010", "Pastane Taşıma Kutusu", "Ambalaj", "Koli (500 Adet)", 420.00, 500.00, 25.0, 10.0, "Gıda temasına uygun kutu"),
                ]
                with self.get_cursor(commit=True) as cursor:
                    for p in default_products:
                        cursor.execute("""
                            INSERT INTO WarehouseProducts (
                                product_code, name, category, unit,
                                purchase_price, sale_price, stock_quantity, critical_stock, notes
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (product_code) DO NOTHING
                        """, p)
                logger.info("✅ Varsayılan depo ürünleri eklendi")
        except Exception as e:
            logger.error(f"ensure_warehouse_tables hatası: {e}")

    def ensure_turnover_tables(self):
        """Günlük Ciro ve Akıllı Kategori tablolarının varlığını garantiye alır ve varsayılan seçenekleri ekler"""
        tenant = self.get_tenant()
        if not tenant or tenant == 'public':
            return
        if not hasattr(self, '_ensured_turnover_schemas'):
            self._ensured_turnover_schemas = set()
        if tenant in self._ensured_turnover_schemas:
            return
        try:
            with self.get_cursor(commit=True) as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS DailyTurnovers (
                        id SERIAL PRIMARY KEY,
                        branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                        entry_date DATE NOT NULL,
                        entry_type VARCHAR(20) NOT NULL,
                        category VARCHAR(150) NOT NULL,
                        amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                        payment_method VARCHAR(50) DEFAULT 'Nakit',
                        description TEXT,
                        created_by INTEGER REFERENCES Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS DailyTurnoverCategories (
                        id SERIAL PRIMARY KEY,
                        branch_id INTEGER REFERENCES Branches(id) ON DELETE CASCADE,
                        category_type VARCHAR(20) NOT NULL,
                        name VARCHAR(150) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(branch_id, category_type, name)
                    );
                    CREATE INDEX IF NOT EXISTS idx_daily_turnovers_branch_date ON DailyTurnovers(branch_id, entry_date);
                    CREATE INDEX IF NOT EXISTS idx_daily_turnovers_type ON DailyTurnovers(entry_type);
                    CREATE INDEX IF NOT EXISTS idx_turnover_categories_lookup ON DailyTurnoverCategories(branch_id, category_type);
                """)

            default_incomes = [
                "Tezgâh Satışı", "Paket Servis", "Toptan Ekmek Satışı",
                "Pastane & Tatlı", "Kafeterya & İçecek", "Özel Sipariş"
            ]
            default_expenses = [
                "Un & Hammadde Alımı", "Maya, Tuz & Katkı", "Elektrik / Su / Doğalgaz",
                "Personel Yevmiye / Maaş", "Yakıt & Ulaşım", "Kira & Aidat",
                "Ambalaj & Poşet", "Genel Temizlik & Bakım"
            ]

            branches = self.fetch_all("SELECT id FROM Branches WHERE is_active = TRUE")
            with self.get_cursor(commit=True) as cursor:
                for b in branches:
                    bid = b['id']
                    for inc in default_incomes:
                        cursor.execute("""
                            INSERT INTO DailyTurnoverCategories (branch_id, category_type, name)
                            VALUES (%s, 'Income', %s)
                            ON CONFLICT (branch_id, category_type, name) DO NOTHING;
                        """, (bid, inc))
                    for exp in default_expenses:
                        cursor.execute("""
                            INSERT INTO DailyTurnoverCategories (branch_id, category_type, name)
                            VALUES (%s, 'Expense', %s)
                            ON CONFLICT (branch_id, category_type, name) DO NOTHING;
                        """, (bid, exp))
            self._ensured_turnover_schemas.add(tenant)
        except Exception as e:
            logger.error(f"ensure_turnover_tables hatası: {e}")

    def ensure_payment_plan_tables(self):
        """
        Personel, Ödeme Planı, Cari Hareket ve Avans Mahsup tablolarının
        varlığını garantiye alır. (Tenant şeması aktifken çağrılmalıdır.)
        """
        tenant = self.get_tenant()
        if not tenant or tenant == 'public':
            return
        if not hasattr(self, '_ensured_payment_plan_schemas'):
            self._ensured_payment_plan_schemas = set()
        if tenant in self._ensured_payment_plan_schemas:
            return
        try:
            with self.get_cursor(commit=True) as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS Employees (
                        id SERIAL PRIMARY KEY,
                        branch_id INTEGER REFERENCES Branches(id) ON DELETE SET NULL,
                        employee_code VARCHAR(30) UNIQUE,
                        full_name VARCHAR(200) NOT NULL,
                        national_id VARCHAR(11),
                        phone VARCHAR(20),
                        email VARCHAR(150),
                        address TEXT,
                        position VARCHAR(100),
                        department VARCHAR(100),
                        hire_date DATE,
                        birth_date DATE,
                        iban VARCHAR(34),
                        monthly_salary DECIMAL(15,2) DEFAULT 0,
                        salary_day INTEGER DEFAULT 1,
                        notes TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS PaymentPlans (
                        id SERIAL PRIMARY KEY,
                        branch_id INTEGER REFERENCES Branches(id) ON DELETE SET NULL,
                        plan_type VARCHAR(30) NOT NULL,
                        title VARCHAR(250) NOT NULL,
                        payee_type VARCHAR(30),
                        payee_id INTEGER,
                        payee_name VARCHAR(200),
                        total_amount DECIMAL(15,2) DEFAULT 0,
                        installment_count INTEGER DEFAULT 1,
                        installment_no INTEGER DEFAULT 1,
                        gross_amount DECIMAL(15,2) DEFAULT 0,
                        advance_deduction DECIMAL(15,2) DEFAULT 0,
                        amount DECIMAL(15,2) NOT NULL,
                        due_date DATE NOT NULL,
                        payment_method VARCHAR(50) DEFAULT 'Havale / EFT',
                        account_id INTEGER,
                        status VARCHAR(20) DEFAULT 'bekliyor',
                        paid_date DATE,
                        paid_amount DECIMAL(15,2) DEFAULT 0,
                        reminder_days INTEGER DEFAULT 3,
                        notes TEXT,
                        reference_type VARCHAR(30),
                        reference_id INTEGER,
                        created_by INTEGER REFERENCES public.Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS EmployeeLedger (
                        id SERIAL PRIMARY KEY,
                        employee_id INTEGER REFERENCES Employees(id) ON DELETE CASCADE,
                        entry_type VARCHAR(30) NOT NULL,
                        amount DECIMAL(15,2) NOT NULL,
                        entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
                        description TEXT,
                        payment_plan_id INTEGER,
                        account_id INTEGER,
                        remaining_amount DECIMAL(15,2) DEFAULT 0,
                        is_closed INTEGER DEFAULT 0,
                        created_by INTEGER REFERENCES public.Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS AdvanceOffsets (
                        id SERIAL PRIMARY KEY,
                        advance_ledger_id INTEGER REFERENCES EmployeeLedger(id) ON DELETE CASCADE,
                        salary_plan_id INTEGER REFERENCES PaymentPlans(id) ON DELETE CASCADE,
                        offset_amount DECIMAL(15,2) NOT NULL,
                        offset_date DATE DEFAULT CURRENT_DATE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_emp_branch ON Employees(branch_id);
                    CREATE INDEX IF NOT EXISTS idx_emp_active ON Employees(is_active);
                    CREATE INDEX IF NOT EXISTS idx_plan_due ON PaymentPlans(due_date);
                    CREATE INDEX IF NOT EXISTS idx_plan_status ON PaymentPlans(status);
                    CREATE INDEX IF NOT EXISTS idx_plan_type ON PaymentPlans(plan_type);
                    CREATE INDEX IF NOT EXISTS idx_plan_payee ON PaymentPlans(payee_type, payee_id);
                    CREATE INDEX IF NOT EXISTS idx_ledger_emp ON EmployeeLedger(employee_id);
                    CREATE INDEX IF NOT EXISTS idx_ledger_type ON EmployeeLedger(entry_type);
                    CREATE INDEX IF NOT EXISTS idx_ledger_open ON EmployeeLedger(is_closed);
                    CREATE INDEX IF NOT EXISTS idx_offset_advance ON AdvanceOffsets(advance_ledger_id);
                    CREATE INDEX IF NOT EXISTS idx_offset_salary ON AdvanceOffsets(salary_plan_id);
                """)
            self._ensured_payment_plan_schemas.add(tenant)
            logger.info("✅ Ödeme planı ve personel tabloları hazır")
        except Exception as e:
            logger.error(f"ensure_payment_plan_tables hatası: {e}")

    def ensure_bakery_supply_tables(self):
        """
        İmalathane Tedarik (BakerySupplies) ve Kalemler (BakerySupplyItems)
        tablolarının varlığını ve kolon esnekliklerini garantiye alır.
        Eski tek-kalemli kayıtları otomatik olarak BakerySupplyItems tablosuna taşır.
        """
        tenant = self.get_tenant()
        if not tenant or tenant == 'public':
            return
        if not hasattr(self, '_ensured_bakery_supply_schemas'):
            self._ensured_bakery_supply_schemas = set()
        if tenant in self._ensured_bakery_supply_schemas:
            return
        try:
            with self.get_cursor(commit=True) as cursor:
                # 1. Ana ve alt tablolar
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS BakerySupplies (
                        id SERIAL PRIMARY KEY,
                        invoice_id INT,
                        invoice_no VARCHAR(50),
                        supply_date DATE DEFAULT CURRENT_DATE,
                        supplier_name VARCHAR(150),
                        item_name VARCHAR(150),
                        category VARCHAR(150) DEFAULT 'Hammadde',
                        quantity NUMERIC(15, 3) DEFAULT 0.0,
                        unit VARCHAR(30) DEFAULT 'kg',
                        unit_price NUMERIC(15, 2) DEFAULT 0.00,
                        total_price NUMERIC(15, 2) DEFAULT 0.00,
                        received_by VARCHAR(100),
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS BakerySupplyItems (
                        id SERIAL PRIMARY KEY,
                        supply_id INT REFERENCES BakerySupplies(id) ON DELETE CASCADE,
                        item_name VARCHAR(150) NOT NULL,
                        category VARCHAR(50) DEFAULT 'Hammadde',
                        quantity NUMERIC(15, 3) NOT NULL DEFAULT 1.0,
                        unit VARCHAR(30) DEFAULT 'kg',
                        unit_price NUMERIC(15, 2) DEFAULT 0.00,
                        total_price NUMERIC(15, 2) DEFAULT 0.00,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_bsi_supply_id ON BakerySupplyItems(supply_id);
                """)
                # 2. Kolon NOT NULL kısıtını esnet
                try:
                    cursor.execute("ALTER TABLE BakerySupplies ALTER COLUMN item_name DROP NOT NULL;")
                    cursor.execute("ALTER TABLE BakerySupplies ALTER COLUMN quantity DROP NOT NULL;")
                except Exception:
                    pass

                # 3. View alias'ları
                try:
                    cursor.execute("CREATE OR REPLACE VIEW bakery_supplies AS SELECT * FROM BakerySupplies;")
                    cursor.execute("CREATE OR REPLACE VIEW bakery_supply_items AS SELECT * FROM BakerySupplyItems;")
                except Exception:
                    pass

                # 4. Eski kayıtların migrasyonu
                cursor.execute("""
                    INSERT INTO BakerySupplyItems (supply_id, item_name, category, quantity, unit, unit_price, total_price)
                    SELECT id, COALESCE(item_name, 'Malzeme'), COALESCE(category, 'Hammadde'), COALESCE(quantity, 1.0), COALESCE(unit, 'kg'), COALESCE(unit_price, 0.0), COALESCE(total_price, 0.0)
                    FROM BakerySupplies
                    WHERE id NOT IN (SELECT DISTINCT supply_id FROM BakerySupplyItems WHERE supply_id IS NOT NULL)
                      AND (item_name IS NOT NULL AND item_name != '');
                """)
            logger.info("✅ İmalathane tedarik tabloları ve kalemleri hazır")
        except Exception as e:
            logger.error(f"ensure_bakery_supply_tables hatası: {e}")

    def ensure_production_tables(self, schema_name: Optional[str] = None):
        """
        İmalathane, Üretim, Şube Sevkiyat Kalemleri ve Dış Satış Kalemleri
        tablolarının varlığını garantiye alır. (Tenant şeması aktifken veya verilen şemada çalışır.)
        """
        target_schema = schema_name or self.get_tenant()
        if not target_schema or target_schema == 'public':
            return
        if not hasattr(self, '_ensured_production_schemas'):
            self._ensured_production_schemas = set()
        if target_schema in self._ensured_production_schemas:
            return
        try:
            with self.get_cursor(commit=True) as cursor:
                # 1. Ana üretim & sevkiyat tabloları (varsa atlar)
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS "{target_schema}".BakeryProductions (
                        id SERIAL PRIMARY KEY,
                        branch_id INTEGER REFERENCES "{target_schema}".Branches(id) ON DELETE SET NULL,
                        production_date DATE NOT NULL DEFAULT CURRENT_DATE,
                        product_name VARCHAR(200) NOT NULL,
                        category VARCHAR(50) DEFAULT 'Ekmek',
                        unit VARCHAR(30) DEFAULT 'Adet',
                        quantity DECIMAL(15,2) NOT NULL,
                        unit_cost DECIMAL(15,2) DEFAULT 0,
                        sale_price DECIMAL(15,2) DEFAULT 0,
                        shipped_quantity DECIMAL(15,2) DEFAULT 0,
                        external_sold_quantity DECIMAL(15,2) DEFAULT 0,
                        remaining_quantity DECIMAL(15,2) DEFAULT 0,
                        notes TEXT,
                        created_by INTEGER REFERENCES public.Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS "{target_schema}".BranchShipments (
                        id SERIAL PRIMARY KEY,
                        shipment_no VARCHAR(50) UNIQUE,
                        source_branch_id INTEGER REFERENCES "{target_schema}".Branches(id),
                        target_branch_id INTEGER REFERENCES "{target_schema}".Branches(id),
                        shipment_date DATE NOT NULL DEFAULT CURRENT_DATE,
                        product_name VARCHAR(200) NOT NULL,
                        quantity DECIMAL(15,2) NOT NULL,
                        unit VARCHAR(30) DEFAULT 'Adet',
                        unit_price DECIMAL(15,2) DEFAULT 0,
                        total_amount DECIMAL(15,2) DEFAULT 0,
                        status VARCHAR(30) DEFAULT 'Teslim Edildi',
                        driver_notes TEXT,
                        created_by INTEGER REFERENCES public.Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS "{target_schema}".ExternalSales (
                        id SERIAL PRIMARY KEY,
                        sale_no VARCHAR(50) UNIQUE,
                        sale_date DATE NOT NULL DEFAULT CURRENT_DATE,
                        customer_id INTEGER REFERENCES "{target_schema}".Customers(id) ON DELETE SET NULL,
                        customer_name VARCHAR(200) NOT NULL,
                        product_name VARCHAR(200) NOT NULL,
                        quantity DECIMAL(15,2) NOT NULL,
                        unit VARCHAR(30) DEFAULT 'Adet',
                        unit_price DECIMAL(15,2) DEFAULT 0,
                        total_amount DECIMAL(15,2) DEFAULT 0,
                        payment_method VARCHAR(50) DEFAULT 'Nakit',
                        payment_status VARCHAR(30) DEFAULT 'Paid',
                        notes TEXT,
                        created_by INTEGER REFERENCES public.Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS "{target_schema}".BranchShipmentItems (
                        id SERIAL PRIMARY KEY,
                        shipment_id INTEGER REFERENCES "{target_schema}".BranchShipments(id) ON DELETE CASCADE,
                        product_name VARCHAR(200) NOT NULL,
                        category VARCHAR(50) DEFAULT 'Unlu Mamül',
                        quantity DECIMAL(15,2) NOT NULL,
                        unit VARCHAR(30) DEFAULT 'Adet',
                        unit_price DECIMAL(15,2) DEFAULT 0,
                        total_amount DECIMAL(15,2) DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS "{target_schema}".ExternalSaleItems (
                        id SERIAL PRIMARY KEY,
                        sale_id INTEGER REFERENCES "{target_schema}".ExternalSales(id) ON DELETE CASCADE,
                        product_name VARCHAR(200) NOT NULL,
                        category VARCHAR(50) DEFAULT 'Unlu Mamül',
                        quantity DECIMAL(15,2) NOT NULL,
                        unit VARCHAR(30) DEFAULT 'Adet',
                        unit_price DECIMAL(15,2) DEFAULT 0,
                        total_amount DECIMAL(15,2) DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # 2. İndeksler
                prefix = target_schema.replace('-', '_').replace('.', '_')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{prefix}_prod_date ON "{target_schema}".BakeryProductions(production_date);')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{prefix}_ship_date ON "{target_schema}".BranchShipments(shipment_date);')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{prefix}_ext_date ON "{target_schema}".ExternalSales(sale_date);')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{prefix}_bsi_shipment ON "{target_schema}".BranchShipmentItems(shipment_id);')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{prefix}_esi_sale ON "{target_schema}".ExternalSaleItems(sale_id);')

            # 3. İmalathane şubesini garanti et
            try:
                row = self.fetch_one("SELECT id FROM Branches WHERE LOWER(name) LIKE %s", ('%imalat%',))
                if not row:
                    self.execute_query("""
                        INSERT INTO Branches (name, city, address, branch_type, is_active)
                        VALUES ('İmalathane', 'Tekirdağ', 'Çorlu Üretim & Fırın İmalat Merkezi', 'bakery', TRUE)
                    """)
            except Exception:
                pass

            self._ensured_production_schemas.add(target_schema)
            logger.info(f"✅ İmalathane ve sevkiyat tabloları hazır: {target_schema}")
        except Exception as e:
            logger.error(f"ensure_production_tables hatası: {e}")


    def _create_triggers(self):
        """Trigger'ları oluştur"""
        triggers = [
            # Fatura toplamlarını otomatik hesapla
            """
            CREATE OR REPLACE FUNCTION update_invoice_totals()
            RETURNS TRIGGER AS $$
            DECLARE
                target_invoice_id INTEGER;
            BEGIN
                IF (TG_OP = 'DELETE') THEN
                    target_invoice_id := OLD.invoice_id;
                ELSE
                    target_invoice_id := NEW.invoice_id;
                END IF;

                IF target_invoice_id IS NOT NULL THEN
                    UPDATE Invoices 
                    SET 
                        total = (SELECT COALESCE(SUM(line_total), 0) FROM InvoiceItems WHERE invoice_id = target_invoice_id),
                        vat_total = (SELECT COALESCE(SUM(vat_amount), 0) FROM InvoiceItems WHERE invoice_id = target_invoice_id),
                        grand_total = (SELECT COALESCE(SUM(line_total), 0) + COALESCE(SUM(vat_amount), 0) FROM InvoiceItems WHERE invoice_id = target_invoice_id) - COALESCE(discount_total, 0)
                    WHERE id = target_invoice_id;
                END IF;

                IF (TG_OP = 'DELETE') THEN
                    RETURN OLD;
                ELSE
                    RETURN NEW;
                END IF;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS update_invoice_totals_trigger ON InvoiceItems;
            CREATE TRIGGER update_invoice_totals_trigger
            AFTER INSERT OR UPDATE OR DELETE ON InvoiceItems
            FOR EACH ROW
            EXECUTE FUNCTION update_invoice_totals();
            """,
            # Otomatik cari kodu oluştur
            """
            CREATE OR REPLACE FUNCTION generate_customer_code()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.customer_code IS NULL OR NEW.customer_code = '' THEN
                    NEW.customer_code := 'C' || LPAD(NEW.id::text, 6, '0');
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS generate_customer_code_trigger ON Customers;
            CREATE TRIGGER generate_customer_code_trigger
            BEFORE INSERT ON Customers
            FOR EACH ROW
            EXECUTE FUNCTION generate_customer_code();
            """,
            # Otomatik fatura no oluştur
            """
            CREATE OR REPLACE FUNCTION generate_invoice_number()
            RETURNS TRIGGER AS $$
            DECLARE
                branch_name_val VARCHAR(200);
                branch_prefix VARCHAR(10);
                year_prefix VARCHAR(4);
                next_number INTEGER;
            BEGIN
                SELECT name INTO branch_name_val FROM Branches WHERE id = NEW.branch_id;
                IF branch_name_val IS NOT NULL AND LENGTH(branch_name_val) >= 3 THEN
                    branch_prefix := UPPER(SUBSTRING(branch_name_val, 1, 3));
                ELSE
                    branch_prefix := 'FTR';
                END IF;

                year_prefix := TO_CHAR(COALESCE(NEW.invoice_date, CURRENT_DATE), 'YYYY');

                SELECT COALESCE(MAX(CAST(SUBSTRING(invoice_no FROM '([0-9]+)$') AS INTEGER)), 0) + 1
                INTO next_number
                FROM Invoices 
                WHERE branch_id = NEW.branch_id 
                AND invoice_no LIKE branch_prefix || '-' || year_prefix || '-%';

                NEW.invoice_no := branch_prefix || '-' || year_prefix || '-' || LPAD(next_number::text, 6, '0');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS generate_invoice_number_trigger ON Invoices;
            CREATE TRIGGER generate_invoice_number_trigger
            BEFORE INSERT ON Invoices
            FOR EACH ROW
            WHEN (NEW.invoice_no IS NULL OR NEW.invoice_no = '')
            EXECUTE FUNCTION generate_invoice_number();
            """
        ]

        with self.get_cursor(commit=True) as cursor:
            for trigger in triggers:
                cursor.execute(trigger)

        logger.info("✅ Trigger'lar oluşturuldu")

    def _insert_default_data(self):
        """Varsayılan verileri ekle (her şubeye hesap planı dahil)"""
        try:
            # ═══════════ 1. ŞUBELER ═══════════
            existing_branch = self.fetch_one("SELECT COUNT(*) as count FROM Branches")
            if existing_branch and existing_branch['count'] == 0:
                self.execute_query("""
                    INSERT INTO Branches (name, city, address)
                    VALUES 
                        ('Armada', 'Tekirdağ', 'Çorlu'),
                        ('Çobançeşme', 'Tekirdağ', 'Çorlu'),
                        ('Rumeli', 'Tekirdağ', 'Çorlu'),
                        ('Orion Şube', 'Tekirdağ', 'Çorlu')
                """)
                logger.info("✅ Varsayılan şubeler eklendi")
            else:
                # Şubeler var ama eksik olabilir → garantile
                logger.info(f"ℹ️ Mevcut {existing_branch['count']} şube bulundu, varsayılan ekleme atlandı")
                self._ensure_default_branches()

            # Multi-Tenant Mimarisi: Hesap planı ve iş verileri her kullanıcının kendi tenant şemasında oluşturulur.
            logger.info("✅ Tüm varsayılan veriler başarıyla yüklendi")

        except Exception as e:
            logger.error(f"❌ Varsayılan veri ekleme hatası: {e}")
            raise

    def _ensure_default_branches(self):
        """Varsayılan şube ve birimleri garanti altına al (eksik olanları ekler)"""
        target_branches = [
            {'name': 'Armada', 'city': 'Tekirdağ', 'address': 'Çorlu', 'branch_type': 'retail'},
            {'name': 'Çobançeşme', 'city': 'Tekirdağ', 'address': 'Çorlu', 'branch_type': 'retail'},
            {'name': 'Rumeli', 'city': 'Tekirdağ', 'address': 'Çorlu', 'branch_type': 'retail'},
            {'name': 'Orion Şube', 'city': 'Tekirdağ', 'address': 'Çorlu', 'branch_type': 'retail'},
            {'name': 'İmalathane', 'city': 'Tekirdağ', 'address': 'Çorlu', 'branch_type': 'bakery'},
            {'name': 'Merkez Depo', 'city': 'Tekirdağ', 'address': 'Çorlu', 'branch_type': 'warehouse'},
        ]
        try:
            for b in target_branches:
                existing = self.fetch_one(
                    "SELECT id FROM Branches WHERE LOWER(name) = LOWER(%s) LIMIT 1",
                    (b['name'],)
                )
                if not existing:
                    self.execute_query("""
                        INSERT INTO Branches (name, city, address, branch_type, is_active)
                        VALUES (%s, %s, %s, %s, TRUE)
                    """, (b['name'], b['city'], b['address'], b['branch_type']))
                    logger.info(f"➕ Eksik şube/birim eklendi: {b['name']}")
        except Exception as e:
            logger.warning(f"Varsayılan şube kontrolü uyarısı: {e}")

    # ══════════════════════════════════════════════════════════════
    # YEDEKLEME / GERİ YÜKLEME (shell=False ile güvenli)
    # ══════════════════════════════════════════════════════════════

    def backup_database(self, backup_path: str = None) -> str:
        """Veritabanını yedekle (güvenli subprocess çağrısı)"""
        import subprocess

        if backup_path is None:
            backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"

        db_config = config.get('database')
        env = os.environ.copy()
        env['PGPASSWORD'] = os.getenv('DB_PASSWORD', db_config.get('password', ''))

        # Veri gizliliği: Giriş yapmış kullanıcı yalnızca KENDİ şemasını yedekler.
        # (Önceden tüm veritabanı, yani diğer kullanıcıların verileri de yedeğe giriyordu.)
        active_tenant = self.get_tenant()
        tenant_args = ['-n', active_tenant] if active_tenant and active_tenant != 'public' else []

        try:
            with open(backup_path, 'w', encoding='utf-8') as f:
                subprocess.run(
                    [
                        'pg_dump',
                        '-U', str(db_config['user']),
                        '-h', str(db_config['host']),
                        '-p', str(db_config['port']),
                        '-d', str(db_config['database']),
                    ] + tenant_args,
                    stdout=f,
                    env=env,
                    check=True,
                    shell=False  # ← GÜVENLİK
                )
            logger.info(f"✅ Yedekleme başarılı: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"❌ Yedekleme hatası: {e}")
            raise

    def restore_database(self, backup_path: str):
        """Veritabanını geri yükle (güvenli subprocess çağrısı)"""
        import subprocess

        db_config = config.get('database')
        env = os.environ.copy()
        env['PGPASSWORD'] = os.getenv('DB_PASSWORD', db_config.get('password', ''))

        # Veri gizliliği: Giriş yapmış bir kullanıcı, başka kullanıcıların
        # şemalarını içeren (veya tüm veritabanını kapsayan) bir yedeği geri yükleyemez.
        active_tenant = self.get_tenant()
        if active_tenant and active_tenant != 'public':
            import re as _re
            with open(backup_path, 'r', encoding='utf-8', errors='ignore') as chk:
                content = chk.read()
            schemas_in_file = set(_re.findall(r'\b(tenant_usr_\d+)\b', content))
            if schemas_in_file - {active_tenant} or 'public.users' in content.lower():
                raise PermissionError(
                    "Bu yedek dosyası başka kullanıcıların verilerini içeriyor; "
                    "geri yükleme güvenlik nedeniyle engellendi."
                )

        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                subprocess.run(
                    [
                        'psql',
                        '-U', str(db_config['user']),
                        '-h', str(db_config['host']),
                        '-p', str(db_config['port']),
                        '-d', str(db_config['database']),
                    ],
                    stdin=f,
                    env=env,
                    check=True,
                    shell=False  # ← GÜVENLİK
                )
            logger.info(f"✅ Geri yükleme başarılı: {backup_path}")
        except Exception as e:
            logger.error(f"❌ Geri yükleme hatası: {e}")
            raise


# Global database instance
db = Database()