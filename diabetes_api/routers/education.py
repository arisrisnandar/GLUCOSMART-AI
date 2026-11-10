from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from typing import Optional, Dict, List
from database import get_db
from models.db_models import EducationContent, User, Notification
from routers.auth import get_current_user
from firebase_service import send_push_multi
import os
import uuid
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import re
from pathlib import Path
from contextlib import suppress
from collections import defaultdict

router = APIRouter()

# ── Konfigurasi Direktori & Keamanan ──────────────────────────────────────────
BASE_UPLOAD_DIR = Path("static/education").resolve()
ALLOWED_SUBFOLDERS = {"posters", "pdfs"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".mp4", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Pastikan direktori dasar ada
BASE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = os.getenv("BASE_URL", "").rstrip("/")

# ── News cache & config ───────────────────────────────────────────────────────
_news_cache: dict = {"data": [], "fetched_at": None}
_news_lock = asyncio.Lock()
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")

_GNEWS_QUERIES = [
    "diabetes", "gula darah", "insulin", "diet diabetes", "kesehatan diabetes",
]

_AUTO_CATEGORY_KEYWORDS = {
    "Tentang Diabetes": ["diabetes", "diabetik", "diabetis", "kadar gula", "gula darah", "hiperglikemia", "hipoglikemia", "insulin", "pankreas"],
    "Pengobatan": ["obat", "metformin", "insulin", "terapi", "pengobatan", "medikasi", "farmasi", "dosis"],
    "Gaya Hidup": ["diet", "olahraga", "aktivitas fisik", "makan sehat", "nutrisi", "berat badan", "gaya hidup", "pola makan", "tidur"],
    "Kondisi Darurat": ["darurat", "koma", "kejang", "ketoasidosis", "hipoglikemia berat", "tidak sadar", "gawat"],
    "Perawatan Kaki": ["kaki", "luka", "amputasi", "neuropati", "perifer"],
    "Kondisi Khusus": ["hamil", "kehamilan", "anak", "lansia", "remaja", "gestasional", "komplikasi"],
}


def _is_safe_url(url: Optional[str]) -> bool:
    """Validasi agar URL hanya menggunakan skema http atau https yang aman."""
    if not url:
        return True
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


# ── Ensure kolom ──────────────────────────────────────────────────────────────
def _ensure_columns(db: Session):
    try:
        inspector = inspect(db.bind)
        existing = [c["name"] for c in inspector.get_columns("education_content")]
        if "content_type" not in existing:
            db.execute(text("ALTER TABLE education_content ADD COLUMN content_type VARCHAR(20) DEFAULT 'article'"))
        if "media_url" not in existing:
            db.execute(text("ALTER TABLE education_content ADD COLUMN media_url TEXT"))
        if "thumbnail_url" not in existing:
            db.execute(text("ALTER TABLE education_content ADD COLUMN thumbnail_url TEXT"))
        db.commit()
    except Exception as e:
        db.rollback()
        # Logging internal saja tanpa membocorkan detail sensitif ke response HTTP
        print(f"[education] _ensure_columns error: {e}")


# ── Save upload (Perbaikan Ketat Path Traversal & Filesystem Oracle) ──────────
def _save_upload(file: UploadFile, subfolder: str, base_url: str) -> str:
    # 1. Validasi subfolder menggunakan WHITELIST
    if subfolder not in ALLOWED_SUBFOLDERS:
        raise HTTPException(status_code=400, detail="Gagal memproses file yang diunggah")

    # 2. Sanitasi nama file menggunakan Regex Whitelist
    raw_filename = file.filename or ""
    safe_filename = os.path.basename(raw_filename)
    
    # Hanya izinkan huruf, angka, titik, dan garis bawah pada nama file asli
    if not re.match(r"^[\w\-\.]+$", safe_filename):
        raise HTTPException(status_code=400, detail="Gagal memproses file yang diunggah")

    # 3. Validasi Ekstensi
    raw_ext = os.path.splitext(safe_filename)[1].lower()
    if raw_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Format atau ekstensi file tidak diizinkan")

    # 4. Buat nama file baru yang SEPENUHNYA aman (Hanya UUID + ekstensi yang divalidasi)
    safe_filename_generated = f"{uuid.uuid4().hex}{raw_ext}"
    
    # 5. Konstruksi Path menggunakan string literal yang sudah tervalidasi
    base_path = str(BASE_UPLOAD_DIR)
    folder_path = os.path.join(base_path, subfolder)
    dest_path = os.path.join(folder_path, safe_filename_generated)

    # 6. Validasi Path Traversal terakhir (memastikan dest_path ada di dalam base_path)
    real_dest = os.path.realpath(dest_path)
    real_base = os.path.realpath(base_path)
    
    if not real_dest.startswith(real_base + os.sep):
        raise HTTPException(status_code=400, detail="Gagal memproses file yang diunggah")

    # 7. Buat direktori jika belum ada
    try:
        os.makedirs(folder_path, exist_ok=True)
    except Exception:
        raise HTTPException(status_code=500, detail="Gagal memproses file yang diunggah")

    # 8. Simpan file dengan batasan ukuran (Mencegah DoS)
    total_size = 0
    try:
        with open(real_dest, "wb") as f:
            while True:
                chunk = file.file.read(1024 * 64)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(status_code=400, detail="Gagal memproses file yang diunggah")
                f.write(chunk)
    except HTTPException:
        # ── PERBAIKAN SONARQUBE: Hindari Filesystem Oracle ──
        with suppress(Exception):
            if os.path.isfile(real_dest):
                os.unlink(real_dest)
        raise
    except Exception:
        with suppress(Exception):
            if os.path.isfile(real_dest):
                os.unlink(real_dest)
        # Seragamkan semua pesan error internal
        raise HTTPException(status_code=500, detail="Gagal memproses file yang diunggah")

    return f"{base_url}/static/education/{subfolder}/{safe_filename_generated}"


# ── Notify async ──────────────────────────────────────────────────────────────
async def _notify(db: Session, title: str, body: str, target_role: str):
    q = db.query(User).filter(User.is_active == True)
    if target_role == "pasien":
        q = q.filter(User.role == "pasien")
    elif target_role == "dokter":
        q = q.filter(User.role == "dokter")
    else:
        q = q.filter(User.role.in_(["pasien", "dokter", "apoteker"]))
    users = q.all()
    for u in users:
        db.add(Notification(user_id=u.id, type="education", title=title, body=body, is_read=False))
    db.commit()
    tokens = [getattr(u, "fcm_token", None) for u in users if getattr(u, "fcm_token", None)]
    if tokens:
        await send_push_multi(tokens, title, body)


# ── Serializer konten manual ──────────────────────────────────────────────────
def _to_dict(a: EducationContent) -> dict:
    return {
        "id": a.id, "title": a.title, "category": a.category,
        "content_type": getattr(a, "content_type", "article") or "article",
        "content": a.content or "", "target_role": a.target_role,
        "is_active": a.is_active,
        "media_url": getattr(a, "media_url", None),
        "thumbnail_url": getattr(a, "thumbnail_url", None),
        "created_at": a.created_at, "is_external": False,
    }


def _guess_category(text: str) -> str:
    text_lower = text.lower()
    for cat, keywords in _AUTO_CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return cat
    return "Tentang Diabetes"


async def _fetch_gnews(query: str, lang: str = "id", max_results: int = 5) -> list:
    if not GNEWS_API_KEY:
        print("[education/news] GNEWS_API_KEY tidak diset, skip fetch")
        return []
    url = "https://gnews.io/api/v4/search"
    params = {"q": query, "lang": lang, "country": "id", "max": max_results, "apikey": GNEWS_API_KEY, "in": "title,description", "sortby": "publishedAt"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json().get("articles", [])
            else:
                print(f"[education/news] GNews HTTP {resp.status_code}")
    except Exception as e:
        print(f"[education/news] GNews fetch error: {type(e).__name__}")
    return []


def _normalize_gnews(articles: list) -> list:
    result = []
    seen_urls = set()
    for a in articles:
        url = a.get("url", "")
        if not url or url in seen_urls or not _is_safe_url(url):
            continue
        seen_urls.add(url)

        title = a.get("title", "").strip()
        description = a.get("description", "").strip()
        image = a.get("image", None)
        if image and not _is_safe_url(image):
            image = None

        published_raw = a.get("publishedAt", "")
        source_name = a.get("source", {}).get("name", "")

        try:
            dt = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
            published_formatted = dt.strftime("%d %b %Y")
        except Exception:
            published_formatted = ""

        category = _guess_category(f"{title} {description}")

        result.append({
            "id": f"news_{abs(hash(url)) % 10**9}", "title": title, "category": category,
            "content_type": "news", "content": description, "media_url": url,
            "thumbnail_url": image, "source": source_name,
            "published_at": published_formatted, "is_external": True,
        })
    return result


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/seed/init", status_code=201)
def seed_education(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(403, "Hanya admin")
    existing = db.query(EducationContent).count()
    if existing > 0:
        return {"message": f"Sudah ada {existing} konten, skip seed"}
    _ensure_columns(db)
    obj = EducationContent(title="Apa Itu Diabetes Melitus?", category="Tentang Diabetes", content="Diabetes melitus adalah penyakit kronis...", target_role="all", is_active=True)
    object.__setattr__(obj, "content_type", "article")
    object.__setattr__(obj, "media_url", None)
    object.__setattr__(obj, "thumbnail_url", None)
    db.add(obj)
    db.commit()
    return {"message": "Seed berhasil"}


@router.get("/categories")
def get_categories(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(EducationContent.category).filter(EducationContent.is_active == True, EducationContent.target_role.in_(["all", current_user.role])).distinct().all())
    return [r[0] for r in rows if r[0]]


@router.get("/news/feed")
async def get_news_feed(refresh: bool = False, current_user: User = Depends(get_current_user)):
    global _news_cache
    now = datetime.now(timezone.utc)
    async with _news_lock:
        cache_valid = (not refresh and _news_cache["fetched_at"] is not None and (now - _news_cache["fetched_at"]) < timedelta(hours=3) and _news_cache["data"])
        if cache_valid:
            return _news_cache["data"]

    tasks = [_fetch_gnews(q, max_results=4) for q in _GNEWS_QUERIES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles = []
    for res in results:
        if isinstance(res, list):
            all_articles.extend(_normalize_gnews(res))

    seen_titles: set = set()
    deduped = []
    for art in all_articles:
        key = art["title"][:40].lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            deduped.append(art)

    async with _news_lock:
        _news_cache["data"] = deduped[:30]
        _news_cache["fetched_at"] = now

    return _news_cache["data"]


@router.get("/news/sources")
def get_news_sources(current_user: User = Depends(get_current_user)):
    return {
        "sources": [{"name": "GNews API", "description": "Agregator berita berbahasa Indonesia tentang diabetes & kesehatan", "url": "https://gnews.io", "keywords": _GNEWS_QUERIES}],
        "cache_duration_hours": 3,
        "last_fetched": str(_news_cache.get("fetched_at")) if _news_cache.get("fetched_at") else None,
        "total_cached": len(_news_cache.get("data", [])),
    }


@router.get("/")
def list_education(
    category: Optional[str] = Query(None, max_length=100),
    content_type: Optional[str] = Query(None, max_length=20),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_columns(db)
    q = db.query(EducationContent).filter(EducationContent.is_active == True)
    if category:
        q = q.filter(EducationContent.category == category)
    if content_type:
        q = q.filter(EducationContent.content_type == content_type)
    q = q.filter(EducationContent.target_role.in_(["all", current_user.role]))
    rows = q.order_by(EducationContent.created_at.desc()).offset(offset).limit(limit).all()
    return [_to_dict(a) for a in rows]


@router.post("/", status_code=201)
async def create_education(
    title: str = Form(..., max_length=200),
    category: str = Form(..., max_length=100),
    content_type: str = Form(..., max_length=20),
    content: str = Form("", max_length=10000),
    target_role: str = Form("all", max_length=50),
    media_url: Optional[str] = Form(None, max_length=500),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("admin", "dokter"):
        raise HTTPException(403, "Hanya admin atau dokter")
    if media_url and not _is_safe_url(media_url):
        raise HTTPException(400, "URL media tidak valid (harus http/https)")
        
    _ensure_columns(db)
    base_url = BASE_URL or "https://gawk-mourner-dance.ngrok-free.dev"
    saved_url = None
    if content_type == "video":
        saved_url = media_url
    elif content_type in ("poster", "pdf") and file and file.filename:
        subfolder = "posters" if content_type == "poster" else "pdfs"
        saved_url = _save_upload(file, subfolder, base_url)
        
    obj = EducationContent(title=title, category=category, content=content, target_role=target_role, is_active=True)
    object.__setattr__(obj, "content_type", content_type)
    object.__setattr__(obj, "media_url", saved_url)
    object.__setattr__(obj, "thumbnail_url", None)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    
    label = {"article": "Artikel", "poster": "Poster", "video": "Video", "pdf": "Dokumen PDF"}.get(content_type, "Konten")
    await _notify(db, title=f"📚 {label} Baru: {title}", body=f'Dokter mengunggah {label.lower()} baru: "{title}"', target_role=target_role)
    return _to_dict(obj)


@router.put("/{article_id}", status_code=200)
async def update_education(
    article_id: int,
    title: str = Form(..., max_length=200),
    category: str = Form(..., max_length=100),
    content_type: str = Form(..., max_length=20),
    content: str = Form("", max_length=10000),
    target_role: str = Form("all", max_length=50),
    media_url: Optional[str] = Form(None, max_length=500),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("admin", "dokter"):
        raise HTTPException(403, "Tidak memiliki akses")
    if media_url and not _is_safe_url(media_url):
        raise HTTPException(400, "URL media tidak valid (harus http/https)")
        
    _ensure_columns(db)
    obj = db.query(EducationContent).filter(EducationContent.id == article_id).first()
    if not obj:
        raise HTTPException(404, "Konten tidak ditemukan")

    base_url = BASE_URL or "https://gawk-mourner-dance.ngrok-free.dev"
    new_media_url = getattr(obj, "media_url", None)
    if content_type == "video":
        new_media_url = media_url
    elif content_type in ("poster", "pdf") and file and file.filename:
        subfolder = "posters" if content_type == "poster" else "pdfs"
        new_media_url = _save_upload(file, subfolder, base_url)

    obj.title = title
    obj.category = category
    obj.content = content
    obj.target_role = target_role
    object.__setattr__(obj, "content_type", content_type)
    object.__setattr__(obj, "media_url", new_media_url)
    db.commit()
    db.refresh(obj)
    
    return _to_dict(obj)
