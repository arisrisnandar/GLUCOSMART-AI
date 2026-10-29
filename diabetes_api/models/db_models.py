from sqlalchemy import Column, BigInteger, String, Enum, Boolean, DateTime, Date, Time, Text, SmallInteger, Integer, DECIMAL, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20))
    password = Column(String(255), nullable=False)
    role = Column(Enum("admin", "pasien", "dokter", "apoteker"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    patient = relationship("Patient", back_populates="user", uselist=False)
    doctor = relationship("Doctor", back_populates="user", uselist=False)
    pharmacist = relationship("Pharmacist", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user")


class Patient(Base):
    __tablename__ = "patients"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    date_of_birth = Column(Date)
    gender = Column(Enum("L", "P"))
    address = Column(Text)
    bpjs_number = Column(String(50))
    mode_kehamilan = Column(Boolean, default=False)
    mode_puasa = Column(Boolean, default=False)

    # ── Biodata Tambahan ──────────────────────────────
    education_level = Column(String(20))   # tidak_sekolah|sd|smp|sma|diploma|s1|s2_s3
    occupation      = Column(String(100))  # pekerjaan
    income_range    = Column(String(20))   # <1jt|1-2jt|2-3jt|3-5jt|5-10jt|>10jt
    workplace       = Column(String(150))  # tempat bekerja
    marital_status  = Column(String(20))   # belum_menikah|menikah|cerai_hidup|cerai_mati

    user = relationship("User", back_populates="patient")
    health_records = relationship("HealthRecord", back_populates="patient")
    risk_predictions = relationship("RiskPrediction", back_populates="patient")
    medication_schedules = relationship("MedicationSchedule", back_populates="patient")
    medication_compliance = relationship("MedicationCompliance", back_populates="patient")
    prescriptions = relationship("Prescription", back_populates="patient")
    therapy_plans = relationship("TherapyPlan", back_populates="patient")
    lab_records = relationship("LabRecord", back_populates="patient")
    health_assessments = relationship("HealthAssessment", back_populates="patient")
    consultation_sessions = relationship("ConsultationSession", back_populates="patient")  # ← BARU
    diet_entries = relationship("DietEntry", back_populates="patient")


class Doctor(Base):
    __tablename__ = "doctors"
    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id         = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    specialization  = Column(String(100))
    license_number  = Column(String(100))   # legacy

    # ── Data Legalitas ────────────────────────────────
    nik             = Column(String(20))    # Nomor Induk Kependudukan
    str_number      = Column(String(100))   # Surat Tanda Registrasi Dokter
    sip_number      = Column(String(100))   # Surat Izin Praktik
    document_url    = Column(Text)          # foto/scan dokumen legalitas

    # ── Approval Admin ────────────────────────────────
    approval_status = Column(String(20), default="pending")  # pending|approved|rejected
    approval_notes  = Column(Text)

    user = relationship("User", back_populates="doctor")
    prescriptions = relationship("Prescription", back_populates="doctor")
    therapy_plans = relationship("TherapyPlan", back_populates="doctor")


class Pharmacist(Base):
    __tablename__ = "pharmacists"
    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id         = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    license_number  = Column(String(100))   # legacy
    pharmacy_name   = Column(String(150))

    # ── Data Legalitas ────────────────────────────────
    nik             = Column(String(20))    # Nomor Induk Kependudukan
    stra_number     = Column(String(100))   # Surat Tanda Registrasi Apoteker
    sipa_number     = Column(String(100))   # Surat Izin Praktik Apoteker
    document_url    = Column(Text)          # foto/scan dokumen legalitas

    # ── Approval Admin ────────────────────────────────
    approval_status = Column(String(20), default="pending")  # pending|approved|rejected
    approval_notes  = Column(Text)

    user = relationship("User", back_populates="pharmacist")
    consultation_sessions = relationship("ConsultationSession", back_populates="pharmacist")


class HealthRecord(Base):
    __tablename__ = "health_records"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id = Column(BigInteger, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    record_date = Column(DateTime, server_default=func.now())
    systolic_bp = Column(SmallInteger)
    diastolic_bp = Column(SmallInteger)
    high_bp = Column(Boolean)
    blood_glucose = Column(DECIMAL(6, 2))
    high_chol = Column(Boolean)
    chol_check = Column(Boolean)
    bmi = Column(DECIMAL(5, 2))
    smoker = Column(Boolean)
    stroke = Column(Boolean)
    heart_disease_attack = Column(Boolean)
    phys_activity = Column(Boolean)
    fruits = Column(Boolean)
    veggies = Column(Boolean)
    hvy_alcohol_consump = Column(Boolean)
    any_healthcare = Column(Boolean)
    no_doc_bc_cost = Column(Boolean)
    gen_hlth = Column(SmallInteger)
    ment_hlth = Column(SmallInteger)
    phys_hlth = Column(SmallInteger)
    diff_walk = Column(Boolean)
    sex = Column(Boolean)
    age = Column(SmallInteger)
    education = Column(SmallInteger)
    income = Column(SmallInteger)
    pregnancies = Column(SmallInteger, default=0)
    skin_thickness = Column(DECIMAL(5, 2))
    insulin = Column(DECIMAL(7, 2))
    diabetes_pedigree = Column(DECIMAL(6, 4))

    patient = relationship("Patient", back_populates="health_records")
    risk_predictions = relationship("RiskPrediction", back_populates="health_record")


class LabRecord(Base):
    __tablename__ = "lab_records"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id = Column(BigInteger, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    record_date = Column(DateTime, server_default=func.now())
    hba1c = Column(DECIMAL(4, 2))
    ldl = Column(DECIMAL(6, 2))
    hdl = Column(DECIMAL(6, 2))
    triglycerides = Column(DECIMAL(6, 2))
    creatinine = Column(DECIMAL(5, 2))
    uric_acid = Column(DECIMAL(5, 2))
    ketone = Column(DECIMAL(5, 2))
    waist_circumference = Column(DECIMAL(5, 2))
    notes = Column(Text)
    patient = relationship("Patient", back_populates="lab_records")


class HealthAssessment(Base):
    __tablename__ = "health_assessments"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id = Column(BigInteger, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    assessed_at = Column(DateTime, server_default=func.now())
    assessment_type = Column(String(20), nullable=False)
    answers = Column(JSON, nullable=False)
    total_score = Column(DECIMAL(6, 2))
    subscores = Column(JSON)
    result_label = Column(String(100))
    result_level = Column(String(20))
    notes = Column(Text)
    patient = relationship("Patient", back_populates="health_assessments")


# ── KONSULTASI CHAT ────────────────────────────────────────
class ConsultationSession(Base):
    """Sesi konsultasi antara pasien dan apoteker."""
    __tablename__ = "consultation_sessions"
    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id     = Column(BigInteger, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    pharmacist_id  = Column(BigInteger, ForeignKey("pharmacists.id"), nullable=True)  # null = belum diambil
    subject        = Column(String(200), nullable=False)   # topik/judul konsultasi
    status         = Column(Enum("open", "active", "closed"), default="open")
    created_at     = Column(DateTime, server_default=func.now())
    updated_at     = Column(DateTime, server_default=func.now(), onupdate=func.now())
    closed_at      = Column(DateTime, nullable=True)

    patient    = relationship("Patient", back_populates="consultation_sessions")
    pharmacist = relationship("Pharmacist", back_populates="consultation_sessions")
    messages   = relationship("ConsultationMessage", back_populates="session",
                              order_by="ConsultationMessage.sent_at")


class ConsultationMessage(Base):
    """Pesan dalam sesi konsultasi."""
    __tablename__ = "consultation_messages"
    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("consultation_sessions.id", ondelete="CASCADE"), nullable=False)
    sender_id  = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    sender_role= Column(String(20), nullable=False)  # pasien | apoteker
    message    = Column(Text, nullable=False)
    sent_at    = Column(DateTime, server_default=func.now())
    is_read    = Column(Boolean, default=False)
    is_edited  = Column(Boolean, default=False)

    session = relationship("ConsultationSession", back_populates="messages")
    sender  = relationship("User")


# ── DIET & KALORI ─────────────────────────────────────────
class DietEntry(Base):
    """Catatan makanan harian pasien."""
    __tablename__ = "diet_entries"
    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id  = Column(BigInteger, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    entry_date  = Column(Date, nullable=False)          # tanggal makan
    meal_type   = Column(String(20), nullable=False)    # sarapan|makan_siang|makan_malam|snack
    food_name   = Column(String(200), nullable=False)   # nama makanan
    portion     = Column('portion', String(100), quote=True)                   # porsi (mis: "1 piring", "200g")
    calories    = Column(Integer, default=0)            # estimasi kalori (kkal)
    carbs_g     = Column(DECIMAL(6, 1))                 # karbohidrat (gram)
    protein_g   = Column(DECIMAL(6, 1))                 # protein (gram)
    fat_g       = Column(DECIMAL(6, 1))                 # lemak (gram)
    gi_category = Column(String(20))                    # rendah|sedang|tinggi (indeks glikemik)
    notes       = Column(Text)
    created_at  = Column(DateTime, server_default=func.now())

    patient = relationship("Patient", back_populates="diet_entries")


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id = Column(BigInteger, ForeignKey("patients.id"), nullable=False)
    health_record_id = Column(BigInteger, ForeignKey("health_records.id"))
    predicted_at = Column(DateTime, server_default=func.now())
    prob_diabetes = Column(DECIMAL(5, 4))
    prob_no_diabetes = Column(DECIMAL(5, 4))
    predicted_class = Column(Boolean)
    predicted_label = Column(String(50))
    threshold_used = Column(DECIMAL(3, 2))
    notif_sent = Column(Boolean, default=False)

    patient = relationship("Patient", back_populates="risk_predictions")
    health_record = relationship("HealthRecord", back_populates="risk_predictions")


class Medication(Base):
    __tablename__ = "medications"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    generic_name = Column(String(150))
    category = Column(String(100))
    description = Column(Text)
    unit = Column(String(30))
    stock = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class MedicationSchedule(Base):
    __tablename__ = "medication_schedules"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id = Column(BigInteger, ForeignKey("patients.id"), nullable=False)
    prescription_item_id = Column(BigInteger, ForeignKey("prescription_items.id"))
    medication_id = Column(BigInteger, ForeignKey("medications.id"), nullable=False)
    scheduled_time = Column(Time, nullable=False)
    scheduled_date = Column(Date, nullable=False)
    is_taken = Column(Boolean, default=False)
    taken_at = Column(DateTime)

    patient = relationship("Patient", back_populates="medication_schedules")
    medication = relationship("Medication")


class MedicationCompliance(Base):
    __tablename__ = "medication_compliance"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id = Column(BigInteger, ForeignKey("patients.id"), nullable=False)
    check_date = Column(Date, nullable=False)
    total_doses = Column(Integer, default=0)
    taken_doses = Column(Integer, default=0)

    patient = relationship("Patient", back_populates="medication_compliance")


class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id = Column(BigInteger, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(BigInteger, ForeignKey("doctors.id"), nullable=False)
    issued_at = Column(DateTime, server_default=func.now())
    status = Column(Enum("pending", "verified", "dispensed"), default="pending")
    notes = Column(Text)
    pharmacist_id = Column(BigInteger, ForeignKey("pharmacists.id"))
    verified_at = Column(DateTime)

    patient = relationship("Patient", back_populates="prescriptions")
    doctor = relationship("Doctor", back_populates="prescriptions")
    items = relationship("PrescriptionItem", back_populates="prescription")


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    prescription_id = Column(BigInteger, ForeignKey("prescriptions.id"), nullable=False)
    medication_id = Column(BigInteger, ForeignKey("medications.id"), nullable=False)
    dosage = Column(String(100))
    frequency = Column(String(100))
    duration_days = Column(Integer)

    prescription = relationship("Prescription", back_populates="items")
    medication = relationship("Medication")


class TherapyPlan(Base):
    __tablename__ = "therapy_plans"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id = Column(BigInteger, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(BigInteger, ForeignKey("doctors.id"), nullable=False)
    plan_text = Column(Text)
    diet_notes = Column(Text)
    exercise_notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    patient = relationship("Patient", back_populates="therapy_plans")
    doctor = relationship("Doctor", back_populates="therapy_plans")


class EducationContent(Base):
    __tablename__ = "education_content"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    category = Column(String(100))
    content = Column(Text)
    content_type = Column(String(20), default="article")  # ← TAMBAH
    media_url   = Column(Text)                             # ← TAMBAH
    thumbnail_url = Column(Text)                           # ← TAMBAH
    target_role = Column(Enum("all", "pasien", "dokter", "apoteker"), default="all")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    type = Column(Enum("reminder", "risk_alert", "education", "system"), nullable=False)
    title = Column(String(200))
    body = Column(Text)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="notifications")