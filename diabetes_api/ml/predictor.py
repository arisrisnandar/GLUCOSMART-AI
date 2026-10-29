import joblib
import pandas as pd
import os
import warnings
from sklearn.exceptions import InconsistentVersionWarning
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

# ─────────────────────────────────────────────
# Model 1: Health Indicators (21 fitur gaya hidup)
# ─────────────────────────────────────────────
MODEL1_PATH  = os.getenv("MODEL_PATH",  "ml/gradient_boost_binary_model.pkl")
SCALER1_PATH = os.getenv("SCALER_PATH", "ml/scaler.pkl")

FEATURES_MODEL1 = [
    "HighBP", "HighChol", "CholCheck", "BMI", "Smoker", "Stroke",
    "HeartDiseaseorAttack", "PhysActivity", "Fruits", "Veggies",
    "HvyAlcoholConsump", "AnyHealthcare", "NoDocbcCost", "GenHlth",
    "MentHlth", "PhysHlth", "DiffWalk", "Sex", "Age", "Education", "Income"
]

# ─────────────────────────────────────────────
# Model 2: Pima Indians (8 fitur data lab klinis)
# ─────────────────────────────────────────────
MODEL2_PATH  = os.getenv("MODEL2_PATH",  "ml/gradient_boosting_model.pkl")
SCALER2_PATH = os.getenv("SCALER2_PATH", "ml/scaler_pima.pkl")

FEATURES_MODEL2 = [
    "Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
    "Insulin", "BMI", "DiabetesPedigreeFunction", "Age"
]

WEIGHT_MODEL1 = 0.4
WEIGHT_MODEL2 = 0.6

_m1 = _s1 = _m2 = _s2 = None


def _load_models():
    global _m1, _s1, _m2, _s2
    if _m1 is None:
        _m1 = joblib.load(MODEL1_PATH)
        _s1 = joblib.load(SCALER1_PATH)
    if _m2 is None:
        _m2 = joblib.load(MODEL2_PATH)
        _s2 = joblib.load(SCALER2_PATH)


def _normalize_glucose(
    blood_glucose, mode_puasa: bool, mode_kehamilan: bool
) -> tuple[float, str]:
    """
    Normalisasi nilai gula darah berdasarkan kondisi puasa dan kehamilan.

    Referensi medis:
    ┌─────────────────┬──────────────┬─────────────────────┬──────────────────────┐
    │ Kondisi         │ Normal       │ Prediabetes         │ Diabetes             │
    ├─────────────────┼──────────────┼─────────────────────┼──────────────────────┤
    │ Puasa (umum)    │ 70–100 mg/dL │ 100–125 mg/dL       │ ≥ 126 mg/dL          │
    │ Sewaktu (umum)  │ < 140 mg/dL  │ 140–199 mg/dL       │ ≥ 200 mg/dL          │
    │ Puasa (hamil)   │ < 92 mg/dL   │ 92–125 mg/dL (GDM)  │ ≥ 126 mg/dL          │
    │ Sewaktu (hamil) │ < 130 mg/dL  │ 130–179 mg/dL (GDM) │ ≥ 180 mg/dL          │
    └─────────────────┴──────────────┴─────────────────────┴──────────────────────┘
    """
    if blood_glucose is None:
        return 120.0, "Tidak ada data gula darah, pakai default 120"

    raw = float(blood_glucose)

    if mode_puasa and mode_kehamilan:
        note = f"Gula darah puasa ibu hamil: {raw} mg/dL (normal <92, GDM ≥92)"
        return raw, note

    elif mode_puasa and not mode_kehamilan:
        note = f"Gula darah puasa: {raw} mg/dL (normal 70–100)"
        return raw, note

    elif not mode_puasa and mode_kehamilan:
        converted = raw * 0.70
        converted = max(50.0, min(400.0, converted))
        note = (f"Gula darah sewaktu ibu hamil: {raw} mg/dL "
                f"→ estimasi puasa: {converted:.1f} mg/dL (×0.70)")
        return converted, note

    else:
        # Sewaktu biasa: faktor koreksi 0.75
        converted = raw * 0.75
        converted = max(50.0, min(400.0, converted))
        note = (f"Gula darah sewaktu: {raw} mg/dL "
                f"→ estimasi puasa: {converted:.1f} mg/dL (×0.75)")
        return converted, note


def _get_pregnancy_value(record, mode_kehamilan: bool) -> int:
    recorded = int(record.pregnancies or 0)
    if mode_kehamilan and recorded == 0:
        return 1
    return recorded


def _get_gdm_risk_boost(
    glucose_used: float, mode_kehamilan: bool, mode_puasa: bool
) -> float:
    if not mode_kehamilan:
        return 0.0
    if mode_puasa:
        if glucose_used >= 126:
            return 0.15
        elif glucose_used >= 92:
            return 0.08
        else:
            return 0.0
    else:
        if glucose_used >= 126:
            return 0.15
        elif glucose_used >= 92:
            return 0.08
        else:
            return 0.0


def _predict_model1(record) -> float:
    data = {
        "HighBP":               int(record.high_bp or 0),
        "HighChol":             int(record.high_chol or 0),
        "CholCheck":            int(record.chol_check or 0),
        "BMI":                  float(record.bmi or 25),
        "Smoker":               int(record.smoker or 0),
        "Stroke":               int(record.stroke or 0),
        "HeartDiseaseorAttack": int(record.heart_disease_attack or 0),
        "PhysActivity":         int(record.phys_activity or 0),
        "Fruits":               int(record.fruits or 0),
        "Veggies":              int(record.veggies or 0),
        "HvyAlcoholConsump":    int(record.hvy_alcohol_consump or 0),
        "AnyHealthcare":        int(record.any_healthcare or 1),
        "NoDocbcCost":          int(record.no_doc_bc_cost or 0),
        "GenHlth":              int(record.gen_hlth or 3),
        "MentHlth":             int(record.ment_hlth or 0),
        "PhysHlth":             int(record.phys_hlth or 0),
        "DiffWalk":             int(record.diff_walk or 0),
        "Sex":                  int(record.sex or 0),
        "Age":                  int(record.age or 5),
        "Education":            int(record.education or 4),
        "Income":               int(record.income or 4),
    }
    df = pd.DataFrame([data])[FEATURES_MODEL1]
    scaled = _s1.transform(df)
    return float(_m1.predict_proba(scaled)[0][1])


def _predict_model2(
    record, mode_puasa: bool, mode_kehamilan: bool
) -> tuple[float, float, str]:
    age_category_to_years = {
        1: 20, 2: 25, 3: 30, 4: 35, 5: 40, 6: 45,
        7: 50, 8: 55, 9: 60, 10: 65, 11: 70, 12: 75, 13: 80
    }
    age_val   = record.age or 5
    age_years = (
        age_category_to_years.get(int(age_val), int(age_val))
        if int(age_val) <= 13 else int(age_val)
    )

    glucose_used, glucose_note = _normalize_glucose(
        record.blood_glucose, mode_puasa, mode_kehamilan
    )
    pregnancies = _get_pregnancy_value(record, mode_kehamilan)

    data = {
        "Pregnancies":              pregnancies,
        "Glucose":                  glucose_used,
        "BloodPressure":            float(record.diastolic_bp or 70),
        "SkinThickness":            float(record.skin_thickness or 20),
        "Insulin":                  float(record.insulin or 80),
        "BMI":                      float(record.bmi or 25),
        "DiabetesPedigreeFunction": float(record.diabetes_pedigree or 0.5),
        "Age":                      age_years,
    }
    df     = pd.DataFrame([data])[FEATURES_MODEL2]
    scaled = _s2.transform(df)
    prob   = float(_m2.predict_proba(scaled)[0][1])
    return prob, glucose_used, glucose_note


def predict_from_health_record(
    record,
    threshold: float = 0.5,
    mode_puasa: bool = False,
    mode_kehamilan: bool = False,
) -> dict:
    _load_models()

    prob_m1                          = _predict_model1(record)
    prob_m2_raw, glucose_used, glucose_note = _predict_model2(
        record, mode_puasa, mode_kehamilan
    )

    gdm_boost  = _get_gdm_risk_boost(glucose_used, mode_kehamilan, mode_puasa)
    prob_m2    = min(1.0, prob_m2_raw + gdm_boost)

    prob_combined = round((WEIGHT_MODEL1 * prob_m1) + (WEIGHT_MODEL2 * prob_m2), 4)

    predicted = int(prob_combined >= threshold)
    label     = "Diabetes" if predicted == 1 else "No Diabetes"

    # ── FIX: threshold disesuaikan agar lebih sensitif ────────────────────
    # Tinggi  : prob ≥ 0.60  (diturunkan dari 0.70)
    # Sedang  : prob ≥ 0.30  (diturunkan dari 0.40)
    # Rendah  : prob < 0.30
    if prob_combined >= 0.60:
        risk_level = "Tinggi"
        risk_color = "red"
    elif prob_combined >= 0.30:
        risk_level = "Sedang"
        risk_color = "orange"
    else:
        risk_level = "Rendah"
        risk_color = "green"

    # Label khusus ibu hamil
    if mode_kehamilan and prob_combined >= 0.30:
        risk_level = f"{risk_level} (Risiko GDM)"

    # ── FIX: is_high_risk konsisten dengan risk_level ─────────────────────
    is_high_risk = prob_combined >= 0.60

    # Debug log
    print(f"[predictor] prob_m1={prob_m1:.4f} prob_m2_raw={prob_m2_raw:.4f} "
          f"gdm_boost={gdm_boost:.4f} prob_m2={prob_m2:.4f} "
          f"prob_combined={prob_combined:.4f} risk_level={risk_level}")

    return {
        "label":            label,
        "predicted_class":  predicted,
        "prob_diabetes":    prob_combined,
        "prob_no_diabetes": round(1 - prob_combined, 4),
        "threshold_used":   threshold,
        "is_high_risk":     is_high_risk,
        "risk_level":       risk_level,
        "risk_color":       risk_color,
        "detail": {
            "model1_health_indicators": {
                "name":          "Indikator Gaya Hidup & Kondisi Umum",
                "prob_diabetes": round(prob_m1, 4),
                "weight":        WEIGHT_MODEL1,
            },
            "model2_pima_clinical": {
                "name":          "Data Lab Klinis (Pima Indians)",
                "prob_diabetes": round(prob_m2, 4),
                "prob_raw":      round(prob_m2_raw, 4),
                "gdm_boost":     round(gdm_boost, 4),
                "weight":        WEIGHT_MODEL2,
            },
            "glucose_info": {
                "input_value":    float(record.blood_glucose) if record.blood_glucose else None,
                "value_used":     round(glucose_used, 2),
                "mode_puasa":     mode_puasa,
                "mode_kehamilan": mode_kehamilan,
                "note":           glucose_note,
            },
            "pregnancy_info": {
                "pregnancies_used": _get_pregnancy_value(record, mode_kehamilan),
                "gdm_threshold":    "≥92 mg/dL (puasa)" if mode_kehamilan else "N/A",
            } if mode_kehamilan else None,
        },
    }