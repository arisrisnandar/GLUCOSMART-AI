from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timedelta
from collections import defaultdict
from database import get_db
from models.db_models import (
    Prescription, PrescriptionItem, Medication, MedicationSchedule,
    Patient, Doctor, Pharmacist, User
)
from routers.auth import get_current_user

router = APIRouter()


class PrescriptionItemIn(BaseModel):
    medication_id: int
    dosage: str
    frequency: str
    duration_days: int


class PrescriptionCreate(BaseModel):
    patient_id: int
    notes: Optional[str] = None
    items: List[PrescriptionItemIn]


class PrescriptionVerify(BaseModel):
    status: str


@router.post("/", status_code=201)
def create_prescription(
    data: PrescriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "dokter":
        raise HTTPException(403, "Hanya dokter yang bisa membuat resep")
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(404, "Profil dokter tidak ditemukan")

    prescription = Prescription(
        patient_id=data.patient_id,
        doctor_id=doctor.id,
        notes=data.notes,
    )
    db.add(prescription)
    db.flush()

    for item_data in data.items:
        item = PrescriptionItem(
            prescription_id=prescription.id,
            medication_id=item_data.medication_id,
            dosage=item_data.dosage,
            frequency=item_data.frequency,
            duration_days=item_data.duration_days,
        )
        db.add(item)
        db.flush()
        _generate_schedules(db, data.patient_id, item.id, item_data)

    db.commit()
    return {"message": "Resep berhasil dibuat", "prescription_id": prescription.id}


def _generate_schedules(db: Session, patient_id: int, item_id: int, item: PrescriptionItemIn):
    freq_map  = {"1x sehari": 1, "2x sehari": 2, "3x sehari": 3}
    times_map = {
        1: ["08:00"],
        2: ["08:00", "20:00"],
        3: ["08:00", "13:00", "20:00"],
    }
    freq  = freq_map.get(item.frequency, 1)
    times = times_map.get(freq, ["08:00"])

    from datetime import time as dtime
    for day_offset in range(item.duration_days):
        sched_date = date.today() + timedelta(days=day_offset)
        for t_str in times:
            h, m = map(int, t_str.split(":"))
            sched = MedicationSchedule(
                patient_id=patient_id,
                prescription_item_id=item_id,
                medication_id=item.medication_id,
                scheduled_time=dtime(h, m),
                scheduled_date=sched_date,
            )
            db.add(sched)


@router.get("/my")
def get_my_prescriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "pasien":
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        prescriptions = db.query(Prescription).filter(Prescription.patient_id == patient.id).all()
    elif current_user.role == "dokter":
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        prescriptions = db.query(Prescription).filter(Prescription.doctor_id == doctor.id).all()
    else:
        raise HTTPException(403, "Akses ditolak")
    return [_prescription_to_dict(p) for p in prescriptions]


@router.get("/pending")
def get_pending_prescriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["apoteker", "admin"]:
        raise HTTPException(403, "Akses ditolak")
    prescriptions = db.query(Prescription).filter(Prescription.status == "pending").all()
    return [_prescription_to_dict(p) for p in prescriptions]


@router.put("/{prescription_id}/verify")
def verify_prescription(
    prescription_id: int,
    data: PrescriptionVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "apoteker":
        raise HTTPException(403, "Hanya apoteker yang bisa verifikasi resep")
    pharmacist = db.query(Pharmacist).filter(Pharmacist.user_id == current_user.id).first()
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(404, "Resep tidak ditemukan")
    prescription.status      = data.status
    prescription.pharmacist_id = pharmacist.id
    prescription.verified_at = datetime.now()
    db.commit()
    return {"message": f"Resep diupdate ke status: {data.status}"}


@router.get("/{prescription_id}")
def get_prescription_detail(
    prescription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(404, "Resep tidak ditemukan")
    return _prescription_to_dict(prescription, with_items=True)


def _prescription_to_dict(p: Prescription, with_items=False) -> dict:
    d = {
        "id":            p.id,
        "patient_id":    p.patient_id,
        "doctor_id":     p.doctor_id,
        "issued_at":     p.issued_at,
        "status":        p.status,
        "notes":         p.notes,
        "pharmacist_id": p.pharmacist_id,
        "verified_at":   p.verified_at,
    }
    if with_items:
        d["items"] = [
            {
                "id":              item.id,
                "medication_id":   item.medication_id,
                "medication_name": item.medication.name if item.medication else None,
                "dosage":          item.dosage,
                "frequency":       item.frequency,
                "duration_days":   item.duration_days,
            }
            for item in p.items
        ]
    return d


# ── Medication Schedules ───────────────────────────────
@router.get("/schedules/today")
def get_today_schedules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    schedules = (
        db.query(MedicationSchedule)
        .filter(
            MedicationSchedule.patient_id == patient.id,
            MedicationSchedule.scheduled_date == date.today(),
        )
        .all()
    )
    return [_schedule_to_dict(s) for s in schedules]


@router.put("/schedules/{schedule_id}/take")
def mark_taken(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    schedule = db.query(MedicationSchedule).filter(MedicationSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(404, "Jadwal tidak ditemukan")
    schedule.is_taken  = True
    schedule.taken_at  = datetime.now()
    db.commit()
    return {"message": "Obat ditandai sudah diminum"}


def _schedule_to_dict(s: MedicationSchedule) -> dict:
    return {
        "id":               s.id,
        "patient_id":       s.patient_id,
        "medication_id":    s.medication_id,
        "medication_name":  s.medication.name if s.medication else None,
        "scheduled_time":   str(s.scheduled_time),
        "scheduled_date":   s.scheduled_date,
        "is_taken":         s.is_taken,
        "taken_at":         s.taken_at,
    }


# ─────────────────────────────────────────────────────────
# COMPLIANCE ENDPOINTS
# ─────────────────────────────────────────────────────────
def _calc_compliance(schedules: list) -> dict:
    total = len(schedules)
    taken = sum(1 for s in schedules if s.is_taken)
    pct   = round(taken / total * 100, 1) if total > 0 else 0.0

    daily: dict = defaultdict(lambda: {"total": 0, "taken": 0})
    for s in schedules:
        key = str(s.scheduled_date)
        daily[key]["total"] += 1
        if s.is_taken:
            daily[key]["taken"] += 1

    daily_list = sorted([
        {
            "date":       d,
            "total":      v["total"],
            "taken":      v["taken"],
            "missed":     v["total"] - v["taken"],
            "percentage": round(v["taken"] / v["total"] * 100, 1) if v["total"] > 0 else 0.0,
        }
        for d, v in daily.items()
    ], key=lambda x: x["date"])

    if pct >= 80:
        status, status_color = "Baik", "green"
    elif pct >= 50:
        status, status_color = "Perlu Perhatian", "orange"
    else:
        status, status_color = "Buruk", "red"

    return {
        "total_doses":     total,
        "taken_doses":     taken,
        "missed_doses":    total - taken,
        "percentage":      pct,
        "status":          status,
        "status_color":    status_color,
        "daily_breakdown": daily_list,
    }


@router.get("/compliance/my")
def get_my_compliance(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")

    start = date.today() - timedelta(days=days - 1)
    schedules = (
        db.query(MedicationSchedule)
        .filter(
            MedicationSchedule.patient_id == patient.id,
            MedicationSchedule.scheduled_date >= start,
            MedicationSchedule.scheduled_date <= date.today(),
        )
        .all()
    )
    return _calc_compliance(schedules)


@router.get("/compliance/patient/{patient_id}")
def get_patient_compliance(
    patient_id: int,
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["dokter", "admin"]:
        raise HTTPException(403, "Akses ditolak")

    start = date.today() - timedelta(days=days - 1)
    schedules = (
        db.query(MedicationSchedule)
        .filter(
            MedicationSchedule.patient_id == patient_id,
            MedicationSchedule.scheduled_date >= start,
            MedicationSchedule.scheduled_date <= date.today(),
        )
        .all()
    )
    return _calc_compliance(schedules)