import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.environ.get("DB_PATH", "data/central.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs("data/updates", exist_ok=True)
    os.makedirs("data/backups", exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # 1. Projeler Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        latest_version TEXT DEFAULT '1.0.0',
        min_version TEXT DEFAULT '1.0.0',
        download_url TEXT,
        release_notes TEXT,
        force_update INTEGER DEFAULT 0,
        updated_at TEXT
    )
    """)

    # 2. Müşteriler ve Lisanslar Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        client_name TEXT NOT NULL,
        license_key TEXT UNIQUE NOT NULL,
        machine_id TEXT,
        is_active INTEGER DEFAULT 1,
        expires_at TEXT, -- NULL ise süresiz
        features TEXT DEFAULT 'all',
        current_version TEXT,
        last_ip TEXT,
        last_seen_at TEXT,
        created_at TEXT,
        FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
    )
    """)

    # 3. Müşteri Yedekleri Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        client_name TEXT NOT NULL,
        filename TEXT NOT NULL,
        filesize INTEGER DEFAULT 0,
        uploaded_at TEXT
    )
    """)

    # 4. Olay / Erişim Günlüğü Tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT,
        client_name TEXT,
        action TEXT NOT NULL,
        details TEXT,
        created_at TEXT
    )
    """)

    # Varsayılan ilk proje: Arı Fırın
    cursor.execute("SELECT id FROM projects WHERE id = 'ari_firin'")
    if not cursor.fetchone():
        now = datetime.now().isoformat()
        cursor.execute("""
        INSERT INTO projects (id, name, description, latest_version, min_version, release_notes, updated_at)
        VALUES ('ari_firin', 'Arı Fırın', 'Fırın ve Pastane Otomasyon Sistemi', '1.0.0', '1.0.0', 'İlk kararlı sürüm.', ?)
        """, (now,))
        
        # Örnek müşteri lisansı (Tekirdağ Fırın)
        cursor.execute("""
        INSERT INTO clients (project_id, client_name, license_key, is_active, expires_at, created_at)
        VALUES ('ari_firin', 'Tekirdağ Müşterisi', 'ARI-FIRIN-TEKIRDAG-2026', 1, NULL, ?)
        """, (now,))

    conn.commit()
    conn.close()

# --- Proje İşlemleri ---
def get_all_projects() -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY name ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_project(project_id: str, name: str, description: str):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""
    INSERT INTO projects (id, name, description, latest_version, min_version, release_notes, updated_at)
    VALUES (?, ?, ?, '1.0.0', '1.0.0', 'Başlangıç sürümü', ?)
    """, (project_id, name, description, now))
    conn.commit()
    conn.close()

def update_project_version(project_id: str, version: str, download_url: str, release_notes: str, force_update: bool):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""
    UPDATE projects 
    SET latest_version = ?, download_url = ?, release_notes = ?, force_update = ?, updated_at = ?
    WHERE id = ?
    """, (version, download_url, release_notes, 1 if force_update else 0, now, project_id))
    conn.commit()
    conn.close()

# --- Müşteri ve Lisans İşlemleri ---
def get_all_clients(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db()
    if project_id:
        rows = conn.execute("""
        SELECT c.*, p.name as project_name 
        FROM clients c 
        JOIN projects p ON c.project_id = p.id 
        WHERE c.project_id = ? 
        ORDER BY c.created_at DESC
        """, (project_id,)).fetchall()
    else:
        rows = conn.execute("""
        SELECT c.*, p.name as project_name 
        FROM clients c 
        JOIN projects p ON c.project_id = p.id 
        ORDER BY c.created_at DESC
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_client(project_id: str, client_name: str, license_key: str, expires_at: Optional[str], machine_id: Optional[str] = None):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""
    INSERT INTO clients (project_id, client_name, license_key, expires_at, machine_id, is_active, created_at)
    VALUES (?, ?, ?, ?, ?, 1, ?)
    """, (project_id, client_name, license_key, expires_at if expires_at else None, machine_id, now))
    conn.commit()
    conn.close()

def toggle_client_status(client_id: int):
    conn = get_db()
    row = conn.execute("SELECT is_active FROM clients WHERE id = ?", (client_id,)).fetchone()
    if row:
        new_status = 0 if row["is_active"] == 1 else 1
        conn.execute("UPDATE clients SET is_active = ? WHERE id = ?", (new_status, client_id))
        conn.commit()
    conn.close()

def delete_client(client_id: int):
    conn = get_db()
    conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()

def reset_client_machine_id(client_id: int):
    conn = get_db()
    conn.execute("UPDATE clients SET machine_id = NULL WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()

def verify_client_license(project_id: str, license_key: str, machine_id: Optional[str]) -> Dict[str, Any]:
    conn = get_db()
    row = conn.execute("""
    SELECT * FROM clients WHERE project_id = ? AND license_key = ?
    """, (project_id, license_key)).fetchone()
    conn.close()

    if not row:
        return {"valid": False, "message": "Geçersiz lisans anahtarı!"}

    client = dict(row)

    if client["is_active"] != 1:
        return {"valid": False, "message": "Bu lisans yönetici tarafından askıya alınmıştır!"}

    # Bitiş tarihi kontrolü
    if client["expires_at"]:
        try:
            exp_date = datetime.fromisoformat(client["expires_at"])
            if datetime.now() > exp_date:
                return {"valid": False, "message": f"Lisans süreniz {client['expires_at']} tarihinde dolmuştur!"}
        except Exception:
            pass

    # Makine ID eşleştirmesi (eğer ilk kez geliyorsa kaydet, kayıtlıysa doğrula)
    if machine_id:
        if not client["machine_id"]:
            # İlk aktivasyon, makineyi bağla
            conn = get_db()
            conn.execute("UPDATE clients SET machine_id = ? WHERE id = ?", (machine_id, client["id"]))
            conn.commit()
            conn.close()
        elif client["machine_id"] != machine_id:
            return {"valid": False, "message": "Bu lisans başka bir bilgisayara atanmıştır!"}

    return {
        "valid": True,
        "message": "Lisans onaylandı.",
        "client_name": client["client_name"],
        "expires_at": client["expires_at"],
        "features": client.get("features", "all").split(",")
    }

def record_heartbeat(project_id: str, license_key: str, version: str, client_ip: str):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""
    UPDATE clients 
    SET last_seen_at = ?, current_version = ?, last_ip = ?
    WHERE project_id = ? AND license_key = ?
    """, (now, version, client_ip, project_id, license_key))
    conn.commit()
    conn.close()

# --- Yedek İşlemleri ---
def record_backup(project_id: str, client_name: str, filename: str, filesize: int):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""
    INSERT INTO backups (project_id, client_name, filename, filesize, uploaded_at)
    VALUES (?, ?, ?, ?, ?)
    """, (project_id, client_name, filename, filesize, now))
    conn.commit()
    conn.close()

def get_recent_backups(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("""
    SELECT b.*, p.name as project_name 
    FROM backups b 
    JOIN projects p ON b.project_id = p.id 
    ORDER BY b.uploaded_at DESC 
    LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
