from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models.db_models import Patient, LabRecord, User
from routers.auth import get_current_user

router = APIRouter()


class LabCreate(BaseModel):
    hba1c:               Optional[float] = None   # %
    ldl:                 Optional[float] = None   # mg/dL
    hdl:                 Optional[float] = None   # mg/dL
    triglycerides:       Optional[float] = None   # mg/dL
    creatinine:          Optional[float] = None   # mg/dL
    uric_acid:           Optional[float] = None   # mg/dL
    ketone:              Optional[float] = None   # mmol/L
    waist_circumference: Optional[float] = None   # cm
    notes:               Optional[str]   = None


def _to_dict(r: LabRecord) -> dict:
    return {
        "id":                   r.id,
        "patient_id":           r.patient_id,
        "record_date":          r.record_date,
        "hba1c":                float(r.hba1c)               if r.hba1c               else None,
        "ldl":                  float(r.ldl)                 if r.ldl                 else None,
        "hdl":                  float(r.hdl)                 if r.hdl                 else None,
        "triglycerides":        float(r.triglycerides)       if r.triglycerides       else None,
        "creatinine":           float(r.creatinine)          if r.creatinine          else None,
        "uric_acid":            float(r.uric_acid)           if r.uric_acid           else None,
        "ketone":               float(r.ketone)              if r.ketone              else None,
        "waist_circumference":  float(r.waist_circumference) if r.waist_circumference else None,
        "notes":                r.notes,
        # Status tiap parameter (normal / perhatian / tinggi)
        "status": _calc_status(r),
    }


def _calc_status(r: LabRecord) -> dict:
    """Hitung status tiap parameter berdasarkan referensi klinis."""
    def flag(value, low=None, high=None):
        if value is None:
            return None
        v = float(value)
        if low is not None and v < low:
            return "rendah"
        if high is not None and v > high:
            return "tinggi"
        return "normal"

    return {
        "hba1c":               flag(r.hba1c,               high=7.0),
        "ldl":                 flag(r.ldl,                  high=100.0),
        "hdl":                 flag(r.hdl,                  low=40.0),   # pria; perempuan >50
        "triglycerides":       flag(r.triglycerides,        high=150.0),
        "creatinine":          flag(r.creatinine,           low=0.6, high=1.2),
        "uric_acid":           flag(r.uric_acid,            high=7.0),   # pria; perempuan <6
        "ketone":              flag(r.ketone,               high=0.6),
        "waist_circumference": flag(r.waist_circumference,  high=90.0),  # pria; perempuan <80
    }


# ─────────────────────────────────────────────────────────
# POST /lab/ — pasien input data lab baru
# ─────────────────────────────────────────────────────────
@router.post("/", status_code=201)
def create_lab_record(
    data: LabCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Hanya pasien yang bisa input data lab")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Profil pasien tidak ditemukan")

    record = LabRecord(patient_id=patient.id, **data.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_dict(record)


# ─────────────────────────────────────────────────────────
# GET /lab/my — riwayat data lab pasien (pasien sendiri)
# ─────────────────────────────────────────────────────────
@router.get("/my", response_model=List[dict])
def get_my_lab_records(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Profil pasien tidak ditemukan")

    records = (
        db.query(LabRecord)
        .filter(LabRecord.patient_id == patient.id)
        .order_by(desc(LabRecord.record_date))
        .limit(limit)
        .all()
    )
    return [_to_dict(r) for r in records]


# ─────────────────────────────────────────────────────────
# GET /lab/my/latest — data lab terbaru saja (untuk dashboard)
# ─────────────────────────────────────────────────────────
@router.get("/my/latest")
def get_my_latest_lab(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Profil pasien tidak ditemukan")

    record = (
        db.query(LabRecord)
        .filter(LabRecord.patient_id == patient.id)
        .order_by(desc(LabRecord.record_date))
        .first()
    )
    if not record:
        raise HTTPException(404, "Belum ada data lab")
    return _to_dict(record)


# ─────────────────────────────────────────────────────────
# GET /lab/patient/{patient_id} — dokter/admin lihat lab pasien
# ─────────────────────────────────────────────────────────
@router.get("/patient/{patient_id}", response_model=List[dict])
def get_patient_lab_records(
    patient_id: int,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["dokter", "admin"]:
        raise HTTPException(403, "Akses ditolak")
    records = (
        db.query(LabRecord)
        .filter(LabRecord.patient_id == patient_id)
        .order_by(desc(LabRecord.record_date))
        .limit(limit)
        .all()
    )
    return [_to_dict(r) for r in records]


# ─────────────────────────────────────────────────────────
# DELETE /lab/{record_id} — hapus data lab (pasien sendiri)
# ─────────────────────────────────────────────────────────
@router.delete("/{record_id}")
def delete_lab_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    record = db.query(LabRecord).filter(
        LabRecord.id == record_id,
        LabRecord.patient_id == patient.id,
    ).first()
    if not record:
        raise HTTPException(404, "Data tidak ditemukan")
    db.delete(record)
    db.commit()
    return {"message": "Data lab dihapus"}