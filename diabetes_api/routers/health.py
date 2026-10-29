from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import get_db
from models.db_models import HealthRecord, Patient, User
from routers.auth import get_current_user

router = APIRouter()


class HealthRecordCreate(BaseModel):
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    high_bp: Optional[bool] = None
    blood_glucose: Optional[float] = None
    high_chol: Optional[bool] = None
    chol_check: Optional[bool] = None
    bmi: Optional[float] = None
    smoker: Optional[bool] = None
    stroke: Optional[bool] = None
    heart_disease_attack: Optional[bool] = None
    phys_activity: Optional[bool] = None
    fruits: Optional[bool] = None
    veggies: Optional[bool] = None
    hvy_alcohol_consump: Optional[bool] = None
    any_healthcare: Optional[bool] = None
    no_doc_bc_cost: Optional[bool] = None
    gen_hlth: Optional[int] = None
    ment_hlth: Optional[int] = None
    phys_hlth: Optional[int] = None
    diff_walk: Optional[bool] = None
    sex: Optional[bool] = None
    age: Optional[int] = None
    education: Optional[int] = None
    income: Optional[int] = None

    # ── Field tambahan Model 2: Pima Indians ──────────────────────────────
    pregnancies: Optional[int] = None            # jumlah kehamilan (0 untuk laki-laki)
    skin_thickness: Optional[float] = None       # ketebalan kulit tricep (mm)
    insulin: Optional[float] = None              # kadar insulin 2 jam (µU/mL)
    diabetes_pedigree: Optional[float] = None    # fungsi silsilah diabetes (0.0 – 2.5)


def _get_patient(user: User, db: Session) -> Patient:
    patient = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not patient:
        raise HTTPException(404, "Profil pasien tidak ditemukan")
    return patient


@router.post("/", status_code=201)
def create_health_record(
    data: HealthRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Hanya pasien yang bisa input data")
    patient = _get_patient(current_user, db)

    record = HealthRecord(patient_id=patient.id, **data.dict(exclude_none=True))
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"message": "Data kesehatan berhasil disimpan", "record_id": record.id}


@router.get("/my", response_model=List[dict])
def get_my_health_records(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = _get_patient(current_user, db)
    records = (
        db.query(HealthRecord)
        .filter(HealthRecord.patient_id == patient.id)
        .order_by(HealthRecord.record_date.desc())
        .limit(limit)
        .all()
    )
    return [_record_to_dict(r) for r in records]


@router.get("/patient/{patient_id}", response_model=List[dict])
def get_patient_health_records(
    patient_id: int,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["dokter", "apoteker", "admin"]:
        raise HTTPException(403, "Akses ditolak")
    records = (
        db.query(HealthRecord)
        .filter(HealthRecord.patient_id == patient_id)
        .order_by(HealthRecord.record_date.desc())
        .limit(limit)
        .all()
    )
    return [_record_to_dict(r) for r in records]


@router.get("/{record_id}")
def get_health_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.query(HealthRecord).filter(HealthRecord.id == record_id).first()
    if not record:
        raise HTTPException(404, "Data tidak ditemukan")
    return _record_to_dict(record)


def _record_to_dict(r: HealthRecord) -> dict:
    return {
        "id": r.id,
        "patient_id": r.patient_id,
        "record_date": r.record_date,
        "systolic_bp": r.systolic_bp,
        "diastolic_bp": r.diastolic_bp,
        "high_bp": r.high_bp,
        "blood_glucose": float(r.blood_glucose) if r.blood_glucose else None,
        "high_chol": r.high_chol,
        "chol_check": r.chol_check,
        "bmi": float(r.bmi) if r.bmi else None,
        "smoker": r.smoker,
        "stroke": r.stroke,
        "heart_disease_attack": r.heart_disease_attack,
        "phys_activity": r.phys_activity,
        "fruits": r.fruits,
        "veggies": r.veggies,
        "hvy_alcohol_consump": r.hvy_alcohol_consump,
        "any_healthcare": r.any_healthcare,
        "no_doc_bc_cost": r.no_doc_bc_cost,
        "gen_hlth": r.gen_hlth,
        "ment_hlth": r.ment_hlth,
        "phys_hlth": r.phys_hlth,
        "diff_walk": r.diff_walk,
        "sex": r.sex,
        "age": r.age,
        "education": r.education,
        "income": r.income,
        # Pima Indians fields
        "pregnancies": r.pregnancies,
        "skin_thickness": float(r.skin_thickness) if r.skin_thickness else None,
        "insulin": float(r.insulin) if r.insulin else None,
        "diabetes_pedigree": float(r.diabetes_pedigree) if r.diabetes_pedigree else None,
    }
