from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models.db_models import Patient, HealthAssessment, User
from routers.auth import get_current_user

router = APIRouter()


class AssessmentCreate(BaseModel):
    assessment_type: str   # mmas8 | dds17 | iief5 | foot
    answers: List[int]
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────
# SCORING ENGINE
# ─────────────────────────────────────────────────────────

def _score_mmas8(answers: List[int]) -> dict:
    """
    MMAS-8: 8 pertanyaan.
    Q1-Q7: 0=Ya(buruk)/1=Tidak(baik), kecuali Q5 dibalik
    Q8: skala 0-4 (never=4 poin baik → selalu=0)
    Skor total 0-8 (makin tinggi makin patuh)
    """
    if len(answers) != 8:
        raise ValueError("MMAS-8 membutuhkan tepat 8 jawaban")
    score = 0
    # Q1-Q4, Q6-Q7: 0=tidak patuh(Ya), 1=patuh(Tidak)
    for i in [0, 1, 2, 3, 5, 6]:
        score += answers[i]  # 1 jika jawab Tidak (patuh)
    # Q5 dibalik: 1=Ya(patuh), 0=Tidak
    score += answers[4]
    # Q8: 0=selalu lupa(0 poin), 1=sering(0.25), 2=kadang(0.5), 3=jarang(0.75), 4=tidak pernah(1)
    q8_map = {0: 0, 1: 0, 2: 0.5, 3: 0.75, 4: 1}
    score += q8_map.get(answers[7], 0)

    if score >= 8:
        label, level = "Kepatuhan Tinggi", "baik"
    elif score >= 6:
        label, level = "Kepatuhan Sedang", "sedang"
    else:
        label, level = "Kepatuhan Rendah", "buruk"

    return {
        "total_score": round(score, 2),
        "subscores": None,
        "result_label": label,
        "result_level": level,
    }


def _score_dds17(answers: List[int]) -> dict:
    """
    DDS-17: 17 pertanyaan skala 1-6.
    4 subskala:
    - Emotional Burden (EB): item 1,3,8,11,14
    - Physician Distress (PD): item 4,9,15
    - Regimen Distress (RD): item 2,6,10,12,16
    - Interpersonal Distress (ID): item 5,7,13,17
    Total = rata-rata semua item
    Interpretasi: <2=tdk distress, 2-2.9=sedikit, 3-4.9=sedang, >=5=berat
    """
    if len(answers) != 17:
        raise ValueError("DDS-17 membutuhkan tepat 17 jawaban")

    eb_items = [0, 2, 7, 10, 13]
    pd_items = [3, 8, 14]
    rd_items = [1, 5, 9, 11, 15]
    id_items = [4, 6, 12, 16]

    def avg(indices): return round(sum(answers[i] for i in indices) / len(indices), 2)

    total = round(sum(answers) / 17, 2)
    subscores = {
        "emotional_burden":     avg(eb_items),
        "physician_distress":   avg(pd_items),
        "regimen_distress":     avg(rd_items),
        "interpersonal_distress": avg(id_items),
    }

    if total < 2:
        label, level = "Tidak Ada Distress", "baik"
    elif total < 3:
        label, level = "Distress Ringan", "baik"
    elif total < 5:
        label, level = "Distress Sedang", "sedang"
    else:
        label, level = "Distress Berat", "buruk"

    return {
        "total_score": total,
        "subscores": subscores,
        "result_label": label,
        "result_level": level,
    }


def _score_iief5(answers: List[int]) -> dict:
    """
    IIEF-5: 5 pertanyaan skala 1-5. Total skor 5-25.
    >=22=Normal, 17-21=Ringan, 12-16=Ringan-Sedang,
    8-11=Sedang, 5-7=Berat
    """
    if len(answers) != 5:
        raise ValueError("IIEF-5 membutuhkan tepat 5 jawaban")
    total = sum(answers)
    if total >= 22:
        label, level = "Fungsi Ereksi Normal", "baik"
    elif total >= 17:
        label, level = "Disfungsi Ereksi Ringan", "sedang"
    elif total >= 12:
        label, level = "Disfungsi Ereksi Ringan-Sedang", "sedang"
    elif total >= 8:
        label, level = "Disfungsi Ereksi Sedang", "buruk"
    else:
        label, level = "Disfungsi Ereksi Berat", "buruk"

    return {
        "total_score": total,
        "subscores": None,
        "result_label": label,
        "result_level": level,
    }


def _score_foot(answers: List[int]) -> dict:
    """
    Kaki Diabetes: 10 pertanyaan Ya(1)/Tidak(0).
    Skor = jumlah jawaban Ya (risiko).
    0-2=Risiko Rendah, 3-5=Risiko Sedang, 6-10=Risiko Tinggi
    """
    if len(answers) != 10:
        raise ValueError("Kaki Diabetes membutuhkan tepat 10 jawaban")
    total = sum(answers)
    if total <= 2:
        label, level = "Risiko Rendah", "baik"
    elif total <= 5:
        label, level = "Risiko Sedang", "sedang"
    else:
        label, level = "Risiko Tinggi", "buruk"

    return {
        "total_score": total,
        "subscores": None,
        "result_label": label,
        "result_level": level,
    }


SCORERS = {
    "mmas8": _score_mmas8,
    "dds17": _score_dds17,
    "iief5": _score_iief5,
    "foot":  _score_foot,
}


def _to_dict(a: HealthAssessment) -> dict:
    return {
        "id":              a.id,
        "patient_id":      a.patient_id,
        "assessed_at":     a.assessed_at,
        "assessment_type": a.assessment_type,
        "answers":         a.answers,
        "total_score":     float(a.total_score) if a.total_score is not None else None,
        "subscores":       a.subscores,
        "result_label":    a.result_label,
        "result_level":    a.result_level,
        "notes":           a.notes,
    }


# ─────────────────────────────────────────────────────────
# POST /assessment/ — pasien submit kuesioner
# ─────────────────────────────────────────────────────────
@router.post("/", status_code=201)
def submit_assessment(
    data: AssessmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Hanya pasien yang bisa mengisi penilaian")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Profil pasien tidak ditemukan")

    scorer = SCORERS.get(data.assessment_type)
    if not scorer:
        raise HTTPException(400, f"Jenis penilaian tidak valid: {data.assessment_type}")

    try:
        result = scorer(data.answers)
    except ValueError as e:
        raise HTTPException(400, str(e))

    assessment = HealthAssessment(
        patient_id      = patient.id,
        assessment_type = data.assessment_type,
        answers         = data.answers,
        total_score     = result["total_score"],
        subscores       = result["subscores"],
        result_label    = result["result_label"],
        result_level    = result["result_level"],
        notes           = data.notes,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _to_dict(assessment)


# ─────────────────────────────────────────────────────────
# GET /assessment/my — riwayat semua penilaian pasien
# ─────────────────────────────────────────────────────────
@router.get("/my", response_model=List[dict])
def get_my_assessments(
    assessment_type: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")

    q = db.query(HealthAssessment).filter(HealthAssessment.patient_id == patient.id)
    if assessment_type:
        q = q.filter(HealthAssessment.assessment_type == assessment_type)
    records = q.order_by(desc(HealthAssessment.assessed_at)).limit(limit).all()
    return [_to_dict(r) for r in records]


# ─────────────────────────────────────────────────────────
# GET /assessment/my/latest — hasil terbaru per jenis
# ─────────────────────────────────────────────────────────
@router.get("/my/latest")
def get_my_latest_assessments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")

    result = {}
    for atype in ["mmas8", "dds17", "iief5", "foot"]:
        rec = (
            db.query(HealthAssessment)
            .filter(
                HealthAssessment.patient_id == patient.id,
                HealthAssessment.assessment_type == atype,
            )
            .order_by(desc(HealthAssessment.assessed_at))
            .first()
        )
        result[atype] = _to_dict(rec) if rec else None
    return result


# ─────────────────────────────────────────────────────────
# GET /assessment/patient/{id} — dokter lihat penilaian pasien
# ─────────────────────────────────────────────────────────
@router.get("/patient/{patient_id}", response_model=List[dict])
def get_patient_assessments(
    patient_id: int,
    assessment_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["dokter", "admin"]:
        raise HTTPException(403, "Akses ditolak")
    q = db.query(HealthAssessment).filter(HealthAssessment.patient_id == patient_id)
    if assessment_type:
        q = q.filter(HealthAssessment.assessment_type == assessment_type)
    records = q.order_by(desc(HealthAssessment.assessed_at)).all()
    return [_to_dict(r) for r in records]