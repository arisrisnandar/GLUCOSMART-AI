from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from pydantic import BaseModel
from typing import List, Optional
from database import get_db
from models.db_models import Notification, User
from routers.auth import get_current_user

router = APIRouter()


# ── Pastikan kolom fcm_token ada di tabel users ───────────────────────────────
def _ensure_fcm_column(db: Session):
    try:
        inspector = inspect(db.bind)
        cols = [c["name"] for c in inspector.get_columns("users")]
        if "fcm_token" not in cols:
            db.execute(text("ALTER TABLE users ADD COLUMN fcm_token TEXT"))
            db.commit()
            print("[notifications] kolom fcm_token ditambahkan ke users")
    except Exception as e:
        db.rollback()
        print(f"[notifications] _ensure_fcm_column: {e}")


# ── Schema ────────────────────────────────────────────────────────────────────
class FCMTokenUpdate(BaseModel):
    fcm_token: str


# ────────────────────────────────────────────────────────────────────────────
# POST /notifications/fcm-token — simpan FCM token device
# ────────────────────────────────────────────────────────────────────────────
@router.post("/fcm-token")
def update_fcm_token(
    data: FCMTokenUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_fcm_column(db)
    db.execute(
        text("UPDATE users SET fcm_token = :token WHERE id = :uid"),
        {"token": data.fcm_token, "uid": current_user.id},
    )
    db.commit()
    print(f"[notifications] FCM token saved for user {current_user.id}")
    return {"message": "FCM token berhasil disimpan"}


# ────────────────────────────────────────────────────────────────────────────
# GET /notifications/
# ────────────────────────────────────────────────────────────────────────────
@router.get("/", response_model=List[dict])
def get_my_notifications(
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id
    )
    if unread_only:
        query = query.filter(Notification.is_read == False)
    notifs = query.order_by(Notification.created_at.desc()).limit(50).all()
    return [_to_dict(n) for n in notifs]


# ────────────────────────────────────────────────────────────────────────────
# GET /notifications/unread-count
# ────────────────────────────────────────────────────────────────────────────
@router.get("/unread-count")
def unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).count()
    return {"unread_count": count}


# ────────────────────────────────────────────────────────────────────────────
# PUT /notifications/read-all
# ────────────────────────────────────────────────────────────────────────────
@router.put("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"message": "Semua notifikasi ditandai sudah dibaca"}


# ────────────────────────────────────────────────────────────────────────────
# PUT /notifications/{id}/read
# ────────────────────────────────────────────────────────────────────────────
@router.put("/{notif_id}/read")
def mark_read(
    notif_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == current_user.id,
    ).first()
    if not notif:
        raise HTTPException(404, "Notifikasi tidak ditemukan")
    notif.is_read = True
    db.commit()
    return {"message": "Notifikasi ditandai sudah dibaca"}


def _to_dict(n: Notification) -> dict:
    return {
        "id":         n.id,
        "user_id":    n.user_id,
        "type":       n.type,
        "title":      n.title,
        "body":       n.body,
        "is_read":    n.is_read,
        "created_at": n.created_at,
    }