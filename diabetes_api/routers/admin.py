from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models.db_models import User, Patient, Doctor, Pharmacist, Medication, EducationContent, RiskPrediction
from routers.auth import get_current_user, hash_password

router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Hanya admin yang bisa akses")
    return current_user


# ── User Management ─────────────────────────────────────────
@router.get("/users", response_model=List[dict])
def list_users(
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return [_user_to_dict(u) for u in query.all()]


@router.put("/users/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User tidak ditemukan")
    user.is_active = not user.is_active
    db.commit()
    return {"message": f"User {'diaktifkan' if user.is_active else 'dinonaktifkan'}", "is_active": user.is_active}


class UserCreate(BaseModel):
    name:     str
    email:    str
    phone:    Optional[str] = None
    password: str
    role:     str


@router.post("/users", status_code=201)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email sudah digunakan")
    user = User(
        name     = data.name,
        email    = data.email,
        phone    = data.phone,
        password = hash_password(data.password),
        role     = data.role,
    )
    db.add(user)
    db.commit()
    return {"message": "User berhasil dibuat", "user_id": user.id}


# ── Approval Dokter & Apoteker ──────────────────────────────
@router.get("/approvals")
def list_pending_approvals(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Daftar dokter & apoteker yang menunggu verifikasi."""
    # Dokter pending
    doctors = (
        db.query(Doctor)
        .join(User)
        .filter(Doctor.approval_status == "pending")
        .all()
    )
    # Apoteker pending
    pharmacists = (
        db.query(Pharmacist)
        .join(User)
        .filter(Pharmacist.approval_status == "pending")
        .all()
    )
    result = []
    for d in doctors:
        result.append({
            "user_id":        d.user_id,
            "name":           d.user.name,
            "email":          d.user.email,
            "phone":          d.user.phone,
            "role":           "dokter",
            "created_at":     d.user.created_at,
            "approval_status": d.approval_status,
            "specialization": d.specialization,
            "nik":            d.nik,
            "str_number":     d.str_number,
            "sip_number":     d.sip_number,
            "document_url":   d.document_url,
        })
    for p in pharmacists:
        result.append({
            "user_id":        p.user_id,
            "name":           p.user.name,
            "email":          p.user.email,
            "phone":          p.user.phone,
            "role":           "apoteker",
            "created_at":     p.user.created_at,
            "approval_status": p.approval_status,
            "nik":            p.nik,
            "stra_number":    p.stra_number,
            "sipa_number":    p.sipa_number,
            "document_url":   p.document_url,
        })
    return result


@router.get("/approvals/count")
def count_pending_approvals(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    doc_count  = db.query(Doctor).filter(Doctor.approval_status == "pending").count()
    apo_count  = db.query(Pharmacist).filter(Pharmacist.approval_status == "pending").count()
    return {"pending_count": doc_count + apo_count}


class ApprovalAction(BaseModel):
    notes: Optional[str] = None


@router.put("/approvals/{user_id}/approve")
def approve_user(
    user_id: int,
    data: ApprovalAction = ApprovalAction(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User tidak ditemukan")

    user.is_active = True

    if user.role == "dokter":
        doc = db.query(Doctor).filter(Doctor.user_id == user_id).first()
        if doc:
            doc.approval_status = "approved"
            doc.approval_notes  = data.notes
    elif user.role == "apoteker":
        apo = db.query(Pharmacist).filter(Pharmacist.user_id == user_id).first()
        if apo:
            apo.approval_status = "approved"
            apo.approval_notes  = data.notes
    else:
        raise HTTPException(400, "Hanya dokter dan apoteker yang perlu approval")

    db.commit()
    return {"message": f"Akun {user.name} telah disetujui"}


@router.put("/approvals/{user_id}/reject")
def reject_user(
    user_id: int,
    data: ApprovalAction = ApprovalAction(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User tidak ditemukan")

    if user.role == "dokter":
        doc = db.query(Doctor).filter(Doctor.user_id == user_id).first()
        if doc:
            doc.approval_status = "rejected"
            doc.approval_notes  = data.notes
    elif user.role == "apoteker":
        apo = db.query(Pharmacist).filter(Pharmacist.user_id == user_id).first()
        if apo:
            apo.approval_status = "rejected"
            apo.approval_notes  = data.notes
    else:
        raise HTTPException(400, "Hanya dokter dan apoteker yang perlu approval")

    db.commit()
    return {"message": f"Akun {user.name} telah ditolak"}


# ── Medication Master ───────────────────────────────────────
class MedicationCreate(BaseModel):
    name:         str
    generic_name: Optional[str] = None
    category:     Optional[str] = None
    description:  Optional[str] = None
    unit:         Optional[str] = None
    stock:        int = 0


@router.get("/medications", response_model=List[dict])
def list_medications(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return [_med_to_dict(m) for m in db.query(Medication).all()]


@router.post("/medications", status_code=201)
def create_medication(data: MedicationCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    med = Medication(**data.dict())
    db.add(med)
    db.commit()
    return {"message": "Obat berhasil ditambahkan", "medication_id": med.id}


@router.put("/medications/{med_id}")
def update_medication(med_id: int, data: MedicationCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    med = db.query(Medication).filter(Medication.id == med_id).first()
    if not med:
        raise HTTPException(404, "Obat tidak ditemukan")
    for k, v in data.dict().items():
        setattr(med, k, v)
    db.commit()
    return {"message": "Obat berhasil diupdate"}


# ── Reports ─────────────────────────────────────────────────
@router.get("/reports/summary")
def get_summary(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    pending = (
        db.query(Doctor).filter(Doctor.approval_status == "pending").count() +
        db.query(Pharmacist).filter(Pharmacist.approval_status == "pending").count()
    )
    return {
        "total_users":           db.query(User).count(),
        "total_patients":        db.query(Patient).count(),
        "total_predictions":     db.query(RiskPrediction).count(),
        "high_risk_predictions": db.query(RiskPrediction).filter(RiskPrediction.prob_diabetes >= 0.5).count(),
        "pending_approvals":     pending,
    }


# ── Education Content ────────────────────────────────────────
class EducationCreate(BaseModel):
    title:       str
    category:    Optional[str] = None
    content:     str
    target_role: str = "all"


@router.get("/education", response_model=List[dict])
def list_education(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return [_edu_to_dict(c) for c in db.query(EducationContent).all()]


@router.post("/education", status_code=201)
def create_education(data: EducationCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    db.add(EducationContent(**data.dict()))
    db.commit()
    return {"message": "Konten edukasi berhasil ditambahkan"}


# ── Helpers ─────────────────────────────────────────────────
def _user_to_dict(u: User) -> dict:
    return {
        "id":         u.id,
        "name":       u.name,
        "email":      u.email,
        "phone":      u.phone,
        "role":       u.role,
        "is_active":  u.is_active,
        "created_at": u.created_at,
    }

def _med_to_dict(m: Medication) -> dict:
    return {"id": m.id, "name": m.name, "generic_name": m.generic_name,
            "category": m.category, "description": m.description,
            "unit": m.unit, "stock": m.stock}

def _edu_to_dict(c: EducationContent) -> dict:
    return {"id": c.id, "title": c.title, "category": c.category,
            "content": c.content, "target_role": c.target_role,
            "is_active": c.is_active, "created_at": c.created_at}