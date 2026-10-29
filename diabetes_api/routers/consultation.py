from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import get_db
from models.db_models import (
    Patient, Pharmacist, User, Notification,
    ConsultationSession, ConsultationMessage
)
from routers.auth import get_current_user
from firebase_service import send_push

router = APIRouter()


class SessionCreate(BaseModel):
    subject: str


class MessageCreate(BaseModel):
    message: str


class MessageUpdate(BaseModel):
    message: str


# ── Helper ────────────────────────────────────────────────────────────────────
def _get_token(db: Session, user_id: int) -> Optional[str]:
    row = db.execute(
        text("SELECT fcm_token FROM users WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()
    return row[0] if row and row[0] else None


async def _notify_push(
    db: Session, user_id: int,
    notif_type: str, title: str, body: str,
    data: dict = None,
):
    db.add(Notification(
        user_id=user_id, type=notif_type,
        title=title, body=body, is_read=False,
    ))
    db.commit()
    token = _get_token(db, user_id)
    if token:
        await send_push(token, title, body, data=data or {})


def _msg_to_dict(m: ConsultationMessage) -> dict:
    return {
        "id":          m.id,
        "session_id":  m.session_id,
        "sender_id":   m.sender_id,
        "sender_role": m.sender_role,
        "sender_name": m.sender.name if m.sender else "-",
        "message":     m.message,
        "sent_at":     m.sent_at,
        "is_read":     m.is_read,
        "is_edited":   m.is_edited if hasattr(m, "is_edited") else False,
    }


def _session_to_dict(s: ConsultationSession, with_messages=False) -> dict:
    last_msg = s.messages[-1] if s.messages else None
    d = {
        "id":              s.id,
        "patient_id":      s.patient_id,
        "patient_name":    s.patient.user.name if s.patient and s.patient.user else "-",
        "pharmacist_id":   s.pharmacist_id,
        "pharmacist_name": s.pharmacist.user.name if s.pharmacist and s.pharmacist.user else "Belum diambil",
        "subject":         s.subject,
        "status":          s.status,
        "created_at":      s.created_at,
        "updated_at":      s.updated_at,
        "closed_at":       s.closed_at,
        "message_count":   len(s.messages),
        "last_message":    _msg_to_dict(last_msg) if last_msg else None,
        "unread_count":    sum(1 for m in s.messages if not m.is_read),
    }
    if with_messages:
        d["messages"] = [_msg_to_dict(m) for m in s.messages]
    return d


# ── PASIEN ────────────────────────────────────────────────────────────────────
@router.post("/sessions/", status_code=201)
async def create_session(
    data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Hanya pasien yang bisa membuat sesi konsultasi")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Profil pasien tidak ditemukan")

    session = ConsultationSession(
        patient_id=patient.id,
        subject=data.subject.strip(),
        status="open",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # ── Notif ke semua apoteker aktif ─────────────────────────────────────
    apotekers = (
        db.query(User)
        .filter(User.role == "apoteker", User.is_active == True)
        .all()
    )
    for ap in apotekers:
        await _notify_push(
            db, ap.id, "system",
            title="💬 Konsultasi Baru",
            body=f"Pasien {current_user.name} membuka konsultasi: \"{data.subject}\"",
            data={"type": "consultation", "session_id": str(session.id)},
        )

    return _session_to_dict(session)


@router.get("/sessions/my", response_model=List[dict])
def get_my_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")
    sessions = (
        db.query(ConsultationSession)
        .filter(ConsultationSession.patient_id == patient.id)
        .order_by(desc(ConsultationSession.updated_at))
        .all()
    )
    return [_session_to_dict(s) for s in sessions]


# ── APOTEKER ──────────────────────────────────────────────────────────────────
@router.get("/sessions/", response_model=List[dict])
def get_all_sessions(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["apoteker", "admin"]:
        raise HTTPException(403, "Akses ditolak")
    q = db.query(ConsultationSession)
    if status:
        q = q.filter(ConsultationSession.status == status)
    sessions = q.order_by(desc(ConsultationSession.updated_at)).all()
    return [_session_to_dict(s) for s in sessions]


@router.put("/sessions/{session_id}/take")
async def take_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "apoteker":
        raise HTTPException(403, "Hanya apoteker yang bisa mengambil sesi")
    pharmacist = db.query(Pharmacist).filter(
        Pharmacist.user_id == current_user.id
    ).first()
    if not pharmacist:
        raise HTTPException(404, "Profil apoteker tidak ditemukan")
    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if session.status != "open":
        raise HTTPException(400, "Sesi sudah diambil atau ditutup")

    session.pharmacist_id = pharmacist.id
    session.status = "active"
    db.commit()
    db.refresh(session)

    # ── Notif ke pasien: apoteker bergabung ───────────────────────────────
    patient = db.query(Patient).filter(
        Patient.id == session.patient_id
    ).first()
    if patient:
        await _notify_push(
            db, patient.user_id, "system",
            title="✅ Apoteker Bergabung",
            body=f"Apoteker {current_user.name} siap melayani konsultasi Anda.",
            data={"type": "consultation", "session_id": str(session_id)},
        )

    return _session_to_dict(session)


# ── SHARED ────────────────────────────────────────────────────────────────────
@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if current_user.role == "pasien":
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient or session.patient_id != patient.id:
            raise HTTPException(403, "Akses ditolak")
    elif current_user.role == "apoteker":
        pass
    else:
        raise HTTPException(403, "Akses ditolak")
    for msg in session.messages:
        if msg.sender_role != current_user.role and not msg.is_read:
            msg.is_read = True
    db.commit()
    return _session_to_dict(session, with_messages=True)


@router.get("/sessions/{session_id}/messages")
def get_messages(
    session_id: int,
    after_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if current_user.role == "pasien":
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient or session.patient_id != patient.id:
            raise HTTPException(403, "Akses ditolak")
    q = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == session_id
    )
    if after_id:
        q = q.filter(ConsultationMessage.id > after_id)
    messages = q.order_by(ConsultationMessage.sent_at).all()
    for msg in messages:
        if msg.sender_role != current_user.role and not msg.is_read:
            msg.is_read = True
    db.commit()
    return [_msg_to_dict(m) for m in messages]


@router.post("/sessions/{session_id}/messages", status_code=201)
async def send_message(
    session_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if session.status == "closed":
        raise HTTPException(400, "Sesi sudah ditutup")

    if current_user.role == "pasien":
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient or session.patient_id != patient.id:
            raise HTTPException(403, "Akses ditolak")
    elif current_user.role == "apoteker":
        if session.status == "open":
            pharmacist = db.query(Pharmacist).filter(
                Pharmacist.user_id == current_user.id
            ).first()
            if pharmacist:
                session.pharmacist_id = pharmacist.id
                session.status = "active"
    else:
        raise HTTPException(403, "Akses ditolak")

    msg = ConsultationMessage(
        session_id=session_id,
        sender_id=current_user.id,
        sender_role=current_user.role,
        message=data.message.strip(),
    )
    db.add(msg)
    session.updated_at = datetime.now()
    db.commit()
    db.refresh(msg)

    # ── Notif pesan baru ke penerima ──────────────────────────────────────
    preview = data.message[:50] + "..." if len(data.message) > 50 else data.message

    if current_user.role == "pasien":
        # Kirim ke apoteker yang menangani
        if session.pharmacist_id:
            pharm = db.query(Pharmacist).filter(
                Pharmacist.id == session.pharmacist_id
            ).first()
            if pharm:
                await _notify_push(
                    db, pharm.user_id, "system",
                    title=f"💬 Pesan dari {current_user.name}",
                    body=preview,
                    data={"type": "consultation", "session_id": str(session_id)},
                )
    elif current_user.role == "apoteker":
        # Kirim ke pasien
        patient = db.query(Patient).filter(
            Patient.id == session.patient_id
        ).first()
        if patient:
            await _notify_push(
                db, patient.user_id, "system",
                title=f"💬 Pesan dari Apoteker",
                body=preview,
                data={"type": "consultation", "session_id": str(session_id)},
            )

    return _msg_to_dict(msg)


@router.put("/sessions/{session_id}/close")
def close_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if current_user.role == "pasien":
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient or session.patient_id != patient.id:
            raise HTTPException(403, "Akses ditolak")
    elif current_user.role not in ["apoteker", "admin"]:
        raise HTTPException(403, "Akses ditolak")
    session.status    = "closed"
    session.closed_at = datetime.now()
    db.commit()
    return {"message": "Sesi konsultasi ditutup"}


@router.put("/sessions/{session_id}/messages/{message_id}")
def edit_message(
    session_id: int, message_id: int,
    data: MessageUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = db.query(ConsultationMessage).filter(
        ConsultationMessage.id == message_id,
        ConsultationMessage.session_id == session_id,
        ConsultationMessage.sender_id == current_user.id,
    ).first()
    if not msg:
        raise HTTPException(404, "Pesan tidak ditemukan atau bukan milik Anda")
    msg.message = data.message.strip()
    if hasattr(msg, "is_edited"):
        msg.is_edited = True
    db.commit()
    db.refresh(msg)
    return _msg_to_dict(msg)


@router.delete("/sessions/{session_id}/messages/{message_id}")
def delete_message(
    session_id: int, message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = db.query(ConsultationMessage).filter(
        ConsultationMessage.id == message_id,
        ConsultationMessage.session_id == session_id,
        ConsultationMessage.sender_id == current_user.id,
    ).first()
    if not msg:
        raise HTTPException(404, "Pesan tidak ditemukan atau bukan milik Anda")
    db.delete(msg)
    db.commit()
    return {"message": "Pesan dihapus"}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if current_user.role == "pasien":
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient or session.patient_id != patient.id:
            raise HTTPException(403, "Akses ditolak")
    elif current_user.role not in ["apoteker", "admin"]:
        raise HTTPException(403, "Akses ditolak")
    db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == session_id
    ).delete(synchronize_session=False)
    db.delete(session)
    db.commit()
    return {"message": "Sesi konsultasi dihapus"}


@router.put("/sessions/{session_id}/reopen")
def reopen_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "apoteker":
        raise HTTPException(403, "Hanya apoteker yang bisa membuka sesi")
    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(404, "Sesi tidak ditemukan")
    if session.status != "closed":
        raise HTTPException(400, "Sesi belum ditutup")
    session.status    = "active"
    session.closed_at = None
    db.commit()
    return {"message": "Sesi dibuka kembali"}