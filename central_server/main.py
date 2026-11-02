import os
import shutil
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import database as db

app = FastAPI(title="Suna Central Control Server", version="1.0.0")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Dizinleri hazırla
os.makedirs("data/updates", exist_ok=True)
os.makedirs("data/backups", exist_ok=True)

# Statik dosyalar ve şablonlar
app.mount("/static/updates", StaticFiles(directory="data/updates"), name="updates")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def startup_event():
    db.init_db()

# Basit Admin Oturumu Kontrolü
def is_authenticated(request: Request) -> bool:
    cookie_token = request.cookies.get("admin_session")
    return cookie_token == ADMIN_PASSWORD

# --- 1. MÜŞTERİ UYGULAMALARININ KULLANDIĞI API ENDPOINT'LERİ ---

@app.get("/api/health")
def health_check():
    return {"status": "ok", "time": datetime.now().isoformat()}

@app.get("/api/v1/projects/{project_id}/version")
def check_version(project_id: str):
    """Masaüstü uygulamasının güncellemeleri kontrol ettiği endpoint"""
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Proje bulunamadı")
    
    return {
        "project_id": proj["id"],
        "project_name": proj["name"],
        "latest_version": proj["latest_version"],
        "min_version": proj["min_version"],
        "download_url": proj["download_url"],
        "release_notes": proj["release_notes"],
        "force_update": bool(proj["force_update"]),
        "updated_at": proj["updated_at"]
    }

class LicenseVerifyRequest(BaseModel):
    license_key: str
    machine_id: Optional[str] = None
    client_name: Optional[str] = None

@app.post("/api/v1/projects/{project_id}/license/verify")
def verify_license(project_id: str, payload: LicenseVerifyRequest):
    """Masaüstü uygulamasının lisans doğruladığı endpoint"""
    result = db.verify_client_license(project_id, payload.license_key, payload.machine_id)
    return result

class HeartbeatRequest(BaseModel):
    license_key: str
    version: str

@app.post("/api/v1/projects/{project_id}/heartbeat")
def client_heartbeat(project_id: str, payload: HeartbeatRequest, request: Request):
    """Masaüstü uygulamasının 'Ben çalışıyorum' sinyali gönderdiği endpoint"""
    client_ip = request.client.host if request.client else "unknown"
    db.record_heartbeat(project_id, payload.license_key, payload.version, client_ip)
    return {"status": "received"}

@app.post("/api/v1/projects/{project_id}/backups/upload")
async def upload_backup(
    project_id: str, 
    client_name: str = Form(...), 
    license_key: str = Form(...),
    backup_file: UploadFile = File(...)
):
    """Masaüstü uygulamasının günlük veritabanı yedeğini sunucuya yüklediği endpoint"""
    # Lisans kontrolü
    lic = db.verify_client_license(project_id, license_key, None)
    if not lic.get("valid"):
        raise HTTPException(status_code=403, detail="Geçersiz lisans, yedek yüklenemez.")
    
    proj_dir = os.path.join("data/backups", project_id, client_name)
    os.makedirs(proj_dir, exist_ok=True)
    
    safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{backup_file.filename}"
    file_path = os.path.join(proj_dir, safe_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(backup_file.file, buffer)
        
    filesize = os.path.getsize(file_path)
    db.record_backup(project_id, client_name, safe_filename, filesize)
    
    return {"status": "success", "filename": safe_filename, "size": filesize}


# --- 1.5 UNIVERSAL ADMIN DESKTOP UYGULAMASI İÇİN JSON REST ENDPOINTLERİ ---

@app.get("/api/v1/projects/{project_id}/clients")
def get_project_clients(project_id: str):
    """Universal Admin'in müşterileri ve çevrimiçi durumlarını çektiği endpoint"""
    clients = db.get_all_clients(project_id)
    now = datetime.now()
    for c in clients:
        if c.get("last_seen_at"):
            try:
                last_dt = datetime.fromisoformat(c["last_seen_at"])
                diff = (now - last_dt).total_seconds()
                c["is_online"] = diff < 900  # 15 dk içinde sinyal aldıysa
            except Exception:
                c["is_online"] = False
        else:
            c["is_online"] = False
    return {"clients": clients}

class CreateClientRequest(BaseModel):
    client_name: str
    license_key: str
    expires_at: Optional[str] = None
    machine_id: Optional[str] = None

@app.post("/api/v1/projects/{project_id}/clients")
def create_project_client(project_id: str, payload: CreateClientRequest):
    """Universal Admin'den yeni müşteri/lisans ekleme"""
    db.add_client(project_id, payload.client_name, payload.license_key, payload.expires_at, payload.machine_id)
    return {"status": "success", "message": "Müşteri lisansı oluşturuldu"}

@app.post("/api/v1/clients/{client_id}/toggle")
def api_toggle_client(client_id: int):
    """Universal Admin'den lisans dondurma / açma"""
    db.toggle_client_status(client_id)
    return {"status": "success"}

@app.post("/api/v1/clients/{client_id}/delete")
def api_delete_client(client_id: int):
    """Universal Admin'den lisans silme"""
    db.delete_client(client_id)
    return {"status": "success"}

@app.post("/api/v1/clients/{client_id}/reset-machine")
def api_reset_client_machine(client_id: int):
    """Universal Admin'den makine kilidini sıfırlama (cihaz değişikliğine izin verme)"""
    db.reset_client_machine_id(client_id)
    return {"status": "success", "message": "Makine kilidi sıfırlandı"}

@app.post("/api/v1/projects/{project_id}/updates/publish")
async def api_publish_update(
    project_id: str,
    version: str = Form(...),
    release_notes: str = Form(""),
    force_update: bool = Form(False),
    external_url: Optional[str] = Form(None),
    installer_file: Optional[UploadFile] = File(None)
):
    """Universal Admin'den yeni sürüm ve kurulum dosyası (.exe) yayınlama"""
    download_url = external_url or ""
    if installer_file and installer_file.filename:
        proj_dir = os.path.join("data/updates", project_id)
        os.makedirs(proj_dir, exist_ok=True)
        file_path = os.path.join(proj_dir, installer_file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(installer_file.file, buffer)
        download_url = f"/static/updates/{project_id}/{installer_file.filename}"

    db.update_project_version(
        project_id,
        version.strip(),
        download_url,
        release_notes.strip(),
        force_update
    )
    return {"status": "success", "latest_version": version, "download_url": download_url}

@app.get("/api/v1/projects/{project_id}/backups")
def get_project_backups(project_id: str):
    """Universal Admin'in projeye ait yedekleri listelediği endpoint"""
    backups = [b for b in db.get_recent_backups() if b["project_id"] == project_id]
    return {"backups": backups}

# --- 2. AYDIN'DAN KULLANACAĞINIZ WEB YÖNETİM PANELİ ---

@app.get("/", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if not is_authenticated(request):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})
    
    projects = db.get_all_projects()
    clients = db.get_all_clients()
    backups = db.get_recent_backups()
    
    # Çevrimiçi kontrolü (son 15 dakikada heartbeat atmış mı?)
    now = datetime.now()
    for c in clients:
        if c.get("last_seen_at"):
            try:
                last_dt = datetime.fromisoformat(c["last_seen_at"])
                diff = (now - last_dt).total_seconds()
                c["is_online"] = diff < 900  # 15 dakika
            except Exception:
                c["is_online"] = False
        else:
            c["is_online"] = False

    return templates.TemplateResponse("index.html", {
        "request": request,
        "projects": projects,
        "clients": clients,
        "backups": backups
    })

@app.post("/admin/login")
def admin_login(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="admin_session", value=ADMIN_PASSWORD, httponly=True, max_age=86400*30)
        return response
    return templates.TemplateResponse("login.html", {"request": {}, "error": "Geçersiz şifre!"})

@app.get("/admin/logout")
def admin_logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="admin_session")
    return response

@app.post("/admin/projects/create")
def add_project(request: Request, id: str = Form(...), name: str = Form(...), description: str = Form("")):
    if not is_authenticated(request):
        raise HTTPException(status_code=401)
    db.create_project(id.strip().lower(), name.strip(), description.strip())
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/projects/{project_id}/update-version")
async def update_version(
    request: Request,
    project_id: str,
    version: str = Form(...),
    release_notes: str = Form(""),
    force_update: Optional[str] = Form(None),
    external_url: Optional[str] = Form(None),
    installer_file: Optional[UploadFile] = File(None)
):
    if not is_authenticated(request):
        raise HTTPException(status_code=401)

    download_url = external_url or ""
    
    # Eğer doğrudan .exe yüklendiyse
    if installer_file and installer_file.filename:
        proj_dir = os.path.join("data/updates", project_id)
        os.makedirs(proj_dir, exist_ok=True)
        file_path = os.path.join(proj_dir, installer_file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(installer_file.file, buffer)
        download_url = f"/static/updates/{project_id}/{installer_file.filename}"

    db.update_project_version(
        project_id, 
        version.strip(), 
        download_url, 
        release_notes.strip(), 
        force_update is not None
    )
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/clients/create")
def add_new_client(
    request: Request,
    project_id: str = Form(...),
    client_name: str = Form(...),
    license_key: str = Form(...),
    expires_at: Optional[str] = Form(None)
):
    if not is_authenticated(request):
        raise HTTPException(status_code=401)
    db.add_client(project_id, client_name.strip(), license_key.strip(), expires_at)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/clients/{client_id}/toggle")
def toggle_client(request: Request, client_id: int):
    if not is_authenticated(request):
        raise HTTPException(status_code=401)
    db.toggle_client_status(client_id)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/clients/{client_id}/delete")
def delete_client_endpoint(request: Request, client_id: int):
    if not is_authenticated(request):
        raise HTTPException(status_code=401)
    db.delete_client(client_id)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin/backups/download/{project_id}/{client_name}/{filename}")
def download_backup_file(request: Request, project_id: str, client_name: str, filename: str):
    if not is_authenticated(request):
        raise HTTPException(status_code=401)
    file_path = os.path.join("data/backups", project_id, client_name, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    raise HTTPException(status_code=404, detail="Yedek dosyası bulunamadı")


if __name__ == "__main__":
    import uvicorn
    import socket
    host = "0.0.0.0"
    port = 8000
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"
    print("=" * 55)
    print("  Arı Fırın Merkezi Sunucu Başlatılıyor...")
    print(f"  Yerel  : http://localhost:{port}")
    print(f"  Ağ IP  : http://{local_ip}:{port}")
    print(f"  Hostname: http://{socket.gethostname()}:{port}")
    print("  Durdurmak için: Ctrl+C")
    print("=" * 55)
    uvicorn.run("main:app", host=host, port=port, reload=False)
