from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from database import get_db
from models.db_models import User, Patient, Doctor, Pharmacist
import os

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "diabetes-telefarma-secret-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Schemas ────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name:     str
    email:    EmailStr
    phone:    Optional[str] = None
    password: str
    role:     str
    gender:   Optional[str] = 'L'

    # ── Dokter ──────────────────────────────────────────
    specialization: Optional[str] = None   # spesialisasi dokter
    nik:            Optional[str] = None   # NIK (dokter & apoteker)
    str_number:     Optional[str] = None   # Surat Tanda Registrasi Dokter
    sip_number:     Optional[str] = None   # Surat Izin Praktik Dokter

    # ── Apoteker ────────────────────────────────────────
    stra_number:    Optional[str] = None   # STRA Apoteker
    sipa_number:    Optional[str] = None   # SIPA Apoteker

    # ── Dokumen (base64 atau URL) ────────────────────────
    document_url:   Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type:   str
    role:         str
    user_id:      int
    name:         str

class UserOut(BaseModel):
    id:        int
    name:      str
    email:     str
    phone:     Optional[str]
    role:      str
    is_active: bool

    class Config:
        from_attributes = True


# ── Helpers ────────────────────────────────────────────────
def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    to_encode["sub"] = str(to_encode["sub"])
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub      = payload.get("sub")
        if sub is None: raise credentials_exception
        user_id  = int(sub)
    except (JWTError, ValueError):
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise credentials_exception
    return user


# ── Endpoints ──────────────────────────────────────────────
@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email sudah terdaftar")
    if req.role not in ["pasien", "dokter", "apoteker"]:
        raise HTTPException(400, "Role tidak valid")
    if req.gender not in ["L", "P"]:
        raise HTTPException(400, "Gender tidak valid, gunakan 'L' atau 'P'")

    # Validasi field wajib per role
    if req.role == "dokter":
        missing = []
        if not req.nik:            missing.append("NIK")
        if not req.str_number:     missing.append("Nomor STR")
        if not req.sip_number:     missing.append("Nomor SIP")
        if missing:
            raise HTTPException(400, f"Field wajib untuk dokter: {', '.join(missing)}")

    elif req.role == "apoteker":
        missing = []
        if not req.nik:            missing.append("NIK")
        if not req.stra_number:    missing.append("Nomor STRA")
        if not req.sipa_number:    missing.append("Nomor SIPA")
        if missing:
            raise HTTPException(400, f"Field wajib untuk apoteker: {', '.join(missing)}")

    # Dokter & Apoteker: is_active = False sampai admin approve
    is_active = req.role == "pasien"

    user = User(
        name      = req.name,
        email     = req.email,
        phone     = req.phone,
        password  = hash_password(req.password),
        role      = req.role,
        is_active = is_active,
    )
    db.add(user)
    db.flush()

    if req.role == "pasien":
        db.add(Patient(user_id=user.id, gender=req.gender))

    elif req.role == "dokter":
        db.add(Doctor(
            user_id        = user.id,
            specialization = req.specialization,
            nik            = req.nik,
            str_number     = req.str_number,
            sip_number     = req.sip_number,
            document_url   = req.document_url,
            approval_status= "pending",
        ))

    elif req.role == "apoteker":
        db.add(Pharmacist(
            user_id        = user.id,
            nik            = req.nik,
            stra_number    = req.stra_number,
            sipa_number    = req.sipa_number,
            document_url   = req.document_url,
            approval_status= "pending",
        ))

    db.commit()

    if req.role == "pasien":
        return {"message": "Registrasi berhasil", "user_id": user.id, "needs_approval": False}
    else:
        return {
            "message": "Pendaftaran berhasil. Akun Anda sedang menunggu verifikasi admin.",
            "user_id": user.id,
            "needs_approval": True,
        }


@router.post("/login", response_model=LoginResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.password):
        raise HTTPException(401, "Email atau password salah")
    if not user.is_active:
        # Cek apakah pending approval atau memang dinonaktifkan
        if user.role in ["dokter", "apoteker"]:
            raise HTTPException(403, "Akun Anda sedang menunggu verifikasi admin. Harap tunggu.")
        raise HTTPException(403, "Akun tidak aktif. Hubungi admin.")

    token = create_access_token({"sub": user.id, "role": user.role})
    return LoginResponse(
        access_token = token,
        token_type   = "bearer",
        role         = user.role,
        user_id      = user.id,
        name         = user.name,
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/change-password")
def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(old_password, current_user.password):
        raise HTTPException(400, "Password lama salah")
    current_user.password = hash_password(new_password)
    db.commit()
    return {"message": "Password berhasil diubah"}