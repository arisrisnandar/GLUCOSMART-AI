from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models.db_models import TherapyPlan, Patient, Doctor, User
from routers.auth import get_current_user

router = APIRouter()


class TherapyPlanCreate(BaseModel):
    patient_id: int
    plan_text: Optional[str] = None
    diet_notes: Optional[str] = None
    exercise_notes: Optional[str] = None


@router.post("/", status_code=201)
def create_or_update_therapy_plan(
    data: TherapyPlanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "dokter":
        raise HTTPException(403, "Hanya dokter yang bisa membuat rencana terapi")

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(404, "Profil dokter tidak ditemukan")

    # Cek apakah sudah ada rencana terapi untuk pasien ini dari dokter ini
    existing = (
        db.query(TherapyPlan)
        .filter(
            TherapyPlan.patient_id == data.patient_id,
            TherapyPlan.doctor_id == doctor.id,
        )
        .first()
    )

    if existing:
        # Update yang sudah ada
        if data.plan_text is not None:
            existing.plan_text = data.plan_text
        if data.diet_notes is not None:
            existing.diet_notes = data.diet_notes
        if data.exercise_notes is not None:
            existing.exercise_notes = data.exercise_notes
        db.commit()
        db.refresh(existing)
        return {"message": "Rencana terapi diperbarui", "id": existing.id}
    else:
        # Buat baru
        plan = TherapyPlan(
            patient_id=data.patient_id,
            doctor_id=doctor.id,
            plan_text=data.plan_text,
            diet_notes=data.diet_notes,
            exercise_notes=data.exercise_notes,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return {"message": "Rencana terapi dibuat", "id": plan.id}


@router.get("/patient/{patient_id}")
def get_therapy_plan(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["dokter", "admin", "pasien"]:
        raise HTTPException(403, "Akses ditolak")

    # Ambil rencana terapi terbaru untuk pasien ini
    plan = (
        db.query(TherapyPlan)
        .filter(TherapyPlan.patient_id == patient_id)
        .order_by(TherapyPlan.updated_at.desc())
        .first()
    )
    if not plan:
        raise HTTPException(404, "Rencana terapi belum ada")

    return {
        "id":             plan.id,
        "patient_id":     plan.patient_id,
        "doctor_id":      plan.doctor_id,
        "plan_text":      plan.plan_text,
        "diet_notes":     plan.diet_notes,
        "exercise_notes": plan.exercise_notes,
        "created_at":     plan.created_at,
        "updated_at":     plan.updated_at,
    }


@router.get("/my")
def get_my_therapy_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pasien ambil rencana terapi miliknya sendiri."""
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Profil pasien tidak ditemukan")

    plan = (
        db.query(TherapyPlan)
        .filter(TherapyPlan.patient_id == patient.id)
        .order_by(TherapyPlan.updated_at.desc())
        .first()
    )
    if not plan:
        raise HTTPException(404, "Rencana terapi belum ada")

    return {
        "id":             plan.id,
        "patient_id":     plan.patient_id,
        "doctor_id":      plan.doctor_id,
        "plan_text":      plan.plan_text,
        "diet_notes":     plan.diet_notes,
        "exercise_notes": plan.exercise_notes,
        "created_at":     plan.created_at,
        "updated_at":     plan.updated_at,
    }