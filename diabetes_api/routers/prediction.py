from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from database import get_db
from models.db_models import Patient, HealthRecord, RiskPrediction, Notification, User
from routers.auth import get_current_user
from ml.predictor import predict_from_health_record
from firebase_service import send_push

router = APIRouter()


async def _push_risk_notif(
    db: Session, user_id: int, title: str, body: str
):
    """Simpan notif ke DB + kirim FCM push."""
    db.add(Notification(
        user_id=user_id, type="risk_alert",
        title=title, body=body, is_read=False,
    ))
    db.commit()

    row = db.execute(
        text("SELECT fcm_token FROM users WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()
    if row and row[0]:
        await send_push(row[0], title, body, data={"type": "risk_alert"})


@router.post("/run/{health_record_id}")
async def run_prediction(
    health_record_id: int,
    threshold: float = 0.5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.query(HealthRecord).filter(
        HealthRecord.id == health_record_id
    ).first()
    if not record:
        raise HTTPException(404, "Health record tidak ditemukan")

    patient = db.query(Patient).filter(
        Patient.id == record.patient_id
    ).first()
    if current_user.role == "pasien":
        my_patient = db.query(Patient).filter(
            Patient.user_id == current_user.id
        ).first()
        if not my_patient or my_patient.id != record.patient_id:
            raise HTTPException(403, "Akses ditolak")
        patient = my_patient

    mode_puasa     = patient.mode_puasa     if patient else False
    mode_kehamilan = patient.mode_kehamilan if patient else False
    if mode_kehamilan and patient and patient.gender != 'P':
        mode_kehamilan = False

    result = predict_from_health_record(
        record, threshold,
        mode_puasa=mode_puasa,
        mode_kehamilan=mode_kehamilan,
    )

    prediction = RiskPrediction(
        patient_id=record.patient_id,
        health_record_id=record.id,
        prob_diabetes=result["prob_diabetes"],
        prob_no_diabetes=result["prob_no_diabetes"],
        predicted_class=result["predicted_class"],
        predicted_label=result["label"],
        threshold_used=threshold,
    )
    db.add(prediction)
    db.flush()

    # ── Notifikasi berdasarkan risk_level dari predictor ──────────────────
    if patient:
        prob_pct   = result["prob_diabetes"] * 100
        risk_level = result.get("risk_level", "Rendah")

        # Normalisasi: hilangkan suffix "(Risiko GDM)" untuk perbandingan
        risk_base = risk_level.replace(" (Risiko GDM)", "").strip()

        if risk_base == "Tinggi":
            title = "⚠️ Risiko Diabetes Tinggi Terdeteksi"
            body  = f"Risiko diabetes Anda {prob_pct:.1f}%."
            if mode_kehamilan:
                body += " Waspadai risiko GDM. Segera konsultasi dokter kandungan."
            else:
                body += " Segera konsultasi dengan dokter."
            prediction.notif_sent = True
            db.commit()
            await _push_risk_notif(db, patient.user_id, title, body)

        elif risk_base == "Sedang":
            title = "🔶 Risiko Diabetes Sedang"
            body  = f"Risiko diabetes Anda {prob_pct:.1f}%."
            if mode_kehamilan:
                body += " Pantau gula darah Anda secara rutin."
            else:
                body += " Pertahankan gaya hidup sehat dan konsultasi dokter."
            prediction.notif_sent = True
            db.commit()
            await _push_risk_notif(db, patient.user_id, title, body)

        else:
            # Risiko rendah — simpan notif ke DB, tidak perlu push
            db.add(Notification(
                user_id=patient.user_id,
                type="risk_alert",
                title="✅ Risiko Diabetes Rendah",
                body=f"Risiko diabetes Anda {prob_pct:.1f}%. Tetap jaga pola hidup sehat!",
                is_read=False,
            ))
            db.commit()

    db.refresh(prediction)

    return {
        "prediction_id":    prediction.id,
        "label":            result["label"],
        "prob_diabetes":    result["prob_diabetes"],
        "prob_no_diabetes": result["prob_no_diabetes"],
        "predicted_class":  result["predicted_class"],
        "threshold_used":   threshold,
        "is_high_risk":     result["is_high_risk"],
        "risk_level":       result.get("risk_level"),
        "risk_color":       result.get("risk_color"),
        "mode_puasa":       mode_puasa,
        "mode_kehamilan":   mode_kehamilan,
        "detail":           result.get("detail"),
    }


@router.get("/my", response_model=List[dict])
def get_my_predictions(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")
    preds = (
        db.query(RiskPrediction)
        .filter(RiskPrediction.patient_id == patient.id)
        .order_by(RiskPrediction.predicted_at.desc())
        .limit(limit)
        .all()
    )
    return [_pred_to_dict(p) for p in preds]


@router.get("/patient/{patient_id}")
def get_patient_predictions(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["dokter", "admin"]:
        raise HTTPException(403, "Akses ditolak")
    preds = (
        db.query(RiskPrediction)
        .filter(RiskPrediction.patient_id == patient_id)
        .order_by(RiskPrediction.predicted_at.desc())
        .all()
    )
    return [_pred_to_dict(p) for p in preds]


@router.get("/high-risk")
def get_high_risk_patients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["dokter", "admin"]:
        raise HTTPException(403, "Akses ditolak")
    from sqlalchemy import func
    subq = (
        db.query(
            RiskPrediction.patient_id,
            func.max(RiskPrediction.predicted_at).label("latest"),
        )
        .group_by(RiskPrediction.patient_id)
        .subquery()
    )
    preds = (
        db.query(RiskPrediction)
        .join(subq,
              (RiskPrediction.patient_id == subq.c.patient_id) &
              (RiskPrediction.predicted_at == subq.c.latest))
        .filter(RiskPrediction.prob_diabetes >= 0.5)
        .all()
    )
    return [_pred_to_dict(p) for p in preds]


def _pred_to_dict(p: RiskPrediction) -> dict:
    prob = float(p.prob_diabetes) if p.prob_diabetes else 0.0

    # ── FIX: threshold konsisten dengan predictor.py ──────────────────────
    if prob >= 0.60:
        risk_level, risk_color = "Tinggi", "red"
    elif prob >= 0.30:
        risk_level, risk_color = "Sedang", "orange"
    else:
        risk_level, risk_color = "Rendah", "green"

    return {
        "id":               p.id,
        "patient_id":       p.patient_id,
        "health_record_id": p.health_record_id,
        "predicted_at":     p.predicted_at,
        "prob_diabetes":    prob,
        "prob_no_diabetes": float(p.prob_no_diabetes) if p.prob_no_diabetes else None,
        "predicted_class":  p.predicted_class,
        "predicted_label":  p.predicted_label,
        "threshold_used":   float(p.threshold_used) if p.threshold_used else None,
        "notif_sent":       p.notif_sent,
        "risk_level":       risk_level,
        "risk_color":       risk_color,
    }