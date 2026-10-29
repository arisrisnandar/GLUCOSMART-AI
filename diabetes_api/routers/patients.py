from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from database import get_db
from models.db_models import Patient, User
from routers.auth import get_current_user

router = APIRouter()


class PatientUpdate(BaseModel):
    # ── Data Utama (tabel users) ──────────────────────
    name:            Optional[str]  = None
    phone:           Optional[str]  = None

    # ── Data Pasien (tabel patients) ─────────────────
    date_of_birth:   Optional[date] = None
    address:         Optional[str]  = None
    bpjs_number:     Optional[str]  = None
    mode_kehamilan:  Optional[bool] = None
    mode_puasa:      Optional[bool] = None

    # ── Biodata Tambahan ──────────────────────────────
    education_level: Optional[str]  = None  # tidak_sekolah|sd|smp|sma|diploma|s1|s2_s3
    occupation:      Optional[str]  = None  # pekerjaan
    income_range:    Optional[str]  = None  # <1jt|1-2jt|2-3jt|3-5jt|5-10jt|>10jt
    workplace:       Optional[str]  = None  # tempat bekerja
    marital_status:  Optional[str]  = None  # belum_menikah|menikah|cerai_hidup|cerai_mati


def _to_out(patient: Patient) -> dict:
    return {
        "id":             patient.id,
        "user_id":        patient.user_id,
        "date_of_birth":  patient.date_of_birth,
        "gender":         patient.gender,
        "address":        patient.address,
        "bpjs_number":    patient.bpjs_number,
        "mode_kehamilan": patient.mode_kehamilan,
        "mode_puasa":     patient.mode_puasa,
        "name":           patient.user.name  if patient.user else None,
        "email":          patient.user.email if patient.user else None,
        "phone":          patient.user.phone if patient.user else None,
        # Biodata tambahan
        "education_level": patient.education_level,
        "occupation":      patient.occupation,
        "income_range":    patient.income_range,
        "workplace":       patient.workplace,
        "marital_status":  patient.marital_status,
    }


@router.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Hanya pasien yang bisa akses endpoint ini")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Profil pasien tidak ditemukan")
    return _to_out(patient)


@router.patch("/me")
def update_my_profile(
    data: PatientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Profil tidak ditemukan")

    data_dict = data.dict(exclude_unset=True)

    # Update tabel User
    if 'name' in data_dict:
        current_user.name = data_dict.pop('name')
    if 'phone' in data_dict:
        current_user.phone = data_dict.pop('phone')

    # Update tabel Patient (termasuk biodata tambahan)
    for field, value in data_dict.items():
        if hasattr(patient, field):
            setattr(patient, field, value)

    try:
        db.commit()
        db.refresh(patient)
        return _to_out(patient)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Database error: {str(e)}")


@router.delete("/me")
def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Hanya pasien yang bisa akses endpoint ini")

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient:
        db.delete(patient)
    db.delete(current_user)

    try:
        db.commit()
        return {"message": "Akun berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Database error: {str(e)}")


@router.put("/{patient_id}/mode")
def update_patient_mode(
    patient_id: int,
    mode_kehamilan: Optional[bool] = None,
    mode_puasa: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient or patient.id != patient_id:
        raise HTTPException(403, "Akses ditolak")

    if mode_kehamilan is not None: patient.mode_kehamilan = mode_kehamilan
    if mode_puasa is not None:     patient.mode_puasa = mode_puasa

    db.commit()
    return {"message": "Mode diperbarui"}


@router.get("/", response_model=List[dict])
def list_patients(
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["dokter", "apoteker", "admin"]:
        raise HTTPException(403, "Akses ditolak")

    query = db.query(Patient).join(User)
    if search:
        query = query.filter(User.name.ilike(f"%{search}%"))
    return [_to_out(p) for p in query.all()]


@router.get("/{patient_id}")
def get_patient(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["dokter", "apoteker", "admin"]:
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")
    return _to_out(patient)