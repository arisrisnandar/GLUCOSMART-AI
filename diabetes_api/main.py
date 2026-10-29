from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from database import Base, engine
from routers import auth, patients, health, prediction, prescriptions, notifications, admin, doctors, reports, therapy_plans, education, lab, assessment, consultation, diet
from scheduler import start_scheduler
from contextlib import asynccontextmanager

Base.metadata.create_all(bind=engine)
os.makedirs("static/education", exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()          # ← background push notif scheduler
    yield

app = FastAPI(
            title="Diabetes Telefarma API", 
            version="1.0.0", 
            lifespan=lifespan,)


app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(patients.router, prefix="/patients", tags=["Patients"])
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(prediction.router, prefix="/prediction", tags=["Prediction"])
app.include_router(prescriptions.router, prefix="/prescriptions", tags=["Prescriptions"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(doctors.router, prefix="/doctors", tags=["Doctors"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(therapy_plans.router, prefix="/therapy_plans", tags=["TherapyPlans"])
app.include_router(education.router, prefix="/education", tags=["Education"])
app.include_router(lab.router, prefix="/lab", tags=["Lab"])
app.include_router(assessment.router, prefix="/assessment", tags=["Assessment"])
app.include_router(consultation.router,  prefix="/consultation",  tags=["Consultation"])
app.include_router(diet.router,          prefix="/diet",          tags=["Diet"])

@app.get("/")
def root():
    return {"message": "Diabetes Telefarma API is running"}
