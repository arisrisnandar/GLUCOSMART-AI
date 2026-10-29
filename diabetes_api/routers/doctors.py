from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from datetime import datetime, timedelta
from database import get_db
from models.db_models import (
    User, Patient, Doctor, HealthRecord,
    RiskPrediction, Prescription, MedicationCompliance
)
from routers.auth import get_current_user

router = APIRouter()


def _require_dokter(current_user: User):
    if current_user.role not in ["dokter", "admin"]:
        raise HTTPException(403, "Akses ditolak")


# ─────────────────────────────────────────────────────────
# GET /doctors/dashboard  — ringkasan statistik untuk dokter
# ─────────────────────────────────────────────────────────
@router.get("/dashboard")
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_dokter(current_user)

    today = datetime.now().date()
    week_ago = datetime.now() - timedelta(days=7)
    month_ago = datetime.now() - timedelta(days=30)

    # Total pasien terdaftar
    total_patients = db.query(Patient).count()

    # Pasien risiko tinggi (prediksi terbaru prob >= 0.5)
    subq = (
        db.query(
            RiskPrediction.patient_id,
            func.max(RiskPrediction.predicted_at).label("latest")
        )
        .group_by(RiskPrediction.patient_id)
        .subquery()
    )
    high_risk_count = (
        db.query(RiskPrediction)
        .join(subq, (RiskPrediction.patient_id == subq.c.patient_id) &
                    (RiskPrediction.predicted_at == subq.c.latest))
        .filter(RiskPrediction.prob_diabetes >= 0.5)
        .count()
    )

    # Prediksi baru minggu ini
    new_predictions_week = (
        db.query(RiskPrediction)
        .filter(RiskPrediction.predicted_at >= week_ago)
        .count()
    )

    # Resep pending (belum diverifikasi)
    pending_prescriptions = (
        db.query(Prescription)
        .filter(Prescription.status == "pending")
        .count()
    )

    # Resep dibuat bulan ini
    prescriptions_month = (
        db.query(Prescription)
        .filter(Prescription.issued_at >= month_ago)
        .count()
    )

    # Distribusi risiko: rendah / sedang / tinggi
    all_latest = (
        db.query(RiskPrediction)
        .join(subq, (RiskPrediction.patient_id == subq.c.patient_id) &
                    (RiskPrediction.predicted_at == subq.c.latest))
        .all()
    )
    risk_distribution = {"rendah": 0, "sedang": 0, "tinggi": 0}
    for p in all_latest:
        prob = float(p.prob_diabetes or 0)
        if prob >= 0.7:
            risk_distribution["tinggi"] += 1
        elif prob >= 0.4:
            risk_distribution["sedang"] += 1
        else:
            risk_distribution["rendah"] += 1

    # 5 pasien risiko tertinggi terbaru
    high_risk_patients = (
        db.query(RiskPrediction, Patient, User)
        .join(subq, (RiskPrediction.patient_id == subq.c.patient_id) &
                    (RiskPrediction.predicted_at == subq.c.latest))
        .join(Patient, Patient.id == RiskPrediction.patient_id)
        .join(User, User.id == Patient.user_id)
        .filter(RiskPrediction.prob_diabetes >= 0.5)
        .order_by(desc(RiskPrediction.prob_diabetes))
        .limit(5)
        .all()
    )

    high_risk_list = [
        {
            "patient_id":    pred.patient_id,
            "name":          user.name,
            "prob_diabetes": float(pred.prob_diabetes or 0),
            "risk_level":    pred.predicted_label,
            "predicted_at":  pred.predicted_at,
        }
        for pred, patient, user in high_risk_patients
    ]

    # Prediksi terbaru (aktivitas terkini)
    recent_predictions = (
        db.query(RiskPrediction, Patient, User)
        .join(Patient, Patient.id == RiskPrediction.patient_id)
        .join(User, User.id == Patient.user_id)
        .order_by(desc(RiskPrediction.predicted_at))
        .limit(5)
        .all()
    )

    recent_list = [
        {
            "patient_id":    pred.patient_id,
            "name":          user.name,
            "prob_diabetes": float(pred.prob_diabetes or 0),
            "predicted_at":  pred.predicted_at,
        }
        for pred, patient, user in recent_predictions
    ]

    return {
        "stats": {
            "total_patients":        total_patients,
            "high_risk_count":       high_risk_count,
            "new_predictions_week":  new_predictions_week,
            "pending_prescriptions": pending_prescriptions,
            "prescriptions_month":   prescriptions_month,
        },
        "risk_distribution": risk_distribution,
        "high_risk_patients": high_risk_list,
        "recent_predictions": recent_list,
    }


# ─────────────────────────────────────────────────────────
# GET /doctors/patients  — daftar pasien dengan info ringkas
# ─────────────────────────────────────────────────────────
@router.get("/patients")
def get_patients_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_dokter(current_user)

    # Subquery latest prediction per patient
    subq = (
        db.query(
            RiskPrediction.patient_id,
            func.max(RiskPrediction.predicted_at).label("latest")
        )
        .group_by(RiskPrediction.patient_id)
        .subquery()
    )

    patients = db.query(Patient, User).join(User, User.id == Patient.user_id).all()

    result = []
    for patient, user in patients:
        latest_pred = (
            db.query(RiskPrediction)
            .join(subq, (RiskPrediction.patient_id == subq.c.patient_id) &
                        (RiskPrediction.predicted_at == subq.c.latest))
            .filter(RiskPrediction.patient_id == patient.id)
            .first()
        )
        result.append({
            "patient_id":    patient.id,
            "name":          user.name,
            "email":         user.email,
            "phone":         user.phone,
            "gender":        patient.gender,
            "date_of_birth": patient.date_of_birth,
            "bpjs_number":   patient.bpjs_number,
            "prob_diabetes": float(latest_pred.prob_diabetes) if latest_pred else None,
            "last_predicted": latest_pred.predicted_at if latest_pred else None,
        })

    return result


# ─────────────────────────────────────────────────────────
# GET /doctors/medications  — daftar obat untuk dropdown resep
# ─────────────────────────────────────────────────────────
@router.get("/medications")
def get_medications_for_prescription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_dokter(current_user)
    from models.db_models import Medication
    meds = db.query(Medication).all()
    return [
        {
            "id":           m.id,
            "name":         m.name,
            "generic_name": m.generic_name,
            "category":     m.category,
            "unit":         m.unit,
            "stock":        m.stock,
        }
        for m in meds
    ]


# ─────────────────────────────────────────────────────────
# GET /doctors/medications  — daftar obat untuk dropdown resep
# ─────────────────────────────────────────────────────────
@router.get("/medications")
def get_medications_for_prescription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_dokter(current_user)
    from models.db_models import Medication
    meds = db.query(Medication).all()
    return [
        {
            "id":           m.id,
            "name":         m.name,
            "generic_name": getattr(m, 'generic_name', None),
            "category":     getattr(m, 'category', None),
            "unit":         getattr(m, 'unit', None),
            "stock":        m.stock,
        }
        for m in meds
    ]