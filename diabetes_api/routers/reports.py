from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from io import BytesIO
from datetime import datetime
from database import get_db
from models.db_models import User, Patient, HealthRecord, RiskPrediction, LabRecord
from routers.auth import get_current_user

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

router = APIRouter()

PRIMARY    = colors.HexColor('#1976D2')
DANGER     = colors.HexColor('#D32F2F')
SUCCESS    = colors.HexColor('#388E3C')
WARNING    = colors.HexColor('#F57C00')
LIGHT_BG   = colors.HexColor('#F5F5F5')
LIGHT_BLUE = colors.HexColor('#E3F2FD')
LIGHT_GREEN= colors.HexColor('#E8F5E9')


def _build_styles():
    styles = getSampleStyleSheet()
    custom = {
        'ReportTitle': ParagraphStyle('ReportTitle', fontSize=20, textColor=PRIMARY,
                                      spaceAfter=4, alignment=TA_CENTER, fontName='Helvetica-Bold'),
        'SubTitle':    ParagraphStyle('SubTitle', fontSize=11, textColor=colors.grey,
                                      spaceAfter=2, alignment=TA_CENTER),
        'SectionHead': ParagraphStyle('SectionHead', fontSize=13, textColor=PRIMARY,
                                      spaceBefore=14, spaceAfter=6, fontName='Helvetica-Bold'),
        'BodyText':    ParagraphStyle('BodyText', fontSize=9, spaceAfter=3, leading=14),
        'SmallGrey':   ParagraphStyle('SmallGrey', fontSize=8, textColor=colors.grey),
        'RiskHigh':    ParagraphStyle('RiskHigh', fontSize=11, textColor=DANGER,
                                      fontName='Helvetica-Bold', alignment=TA_CENTER),
        'RiskMed':     ParagraphStyle('RiskMed', fontSize=11, textColor=WARNING,
                                      fontName='Helvetica-Bold', alignment=TA_CENTER),
        'RiskLow':     ParagraphStyle('RiskLow', fontSize=11, textColor=SUCCESS,
                                      fontName='Helvetica-Bold', alignment=TA_CENTER),
    }
    return {**{k: styles[k] for k in styles.byName}, **custom}


def _risk_color(prob: float):
    if prob >= 0.7: return DANGER
    if prob >= 0.4: return WARNING
    return SUCCESS


def _risk_label(prob: float):
    if prob >= 0.7: return 'TINGGI'
    if prob >= 0.4: return 'SEDANG'
    return 'RENDAH'


def _fmt_date(dt) -> str:
    if not dt: return '-'
    try:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        return dt.strftime('%d %b %Y, %H:%M')
    except Exception:
        return str(dt)


def _bool_str(v) -> str:
    if v is None: return '-'
    return 'Ya' if v else 'Tidak'


def _lab_status(value, low=None, high=None):
    """Return (value_str, color, status_label)"""
    if value is None:
        return None, colors.grey, '-'
    v = float(value)
    if high is not None and v > high:
        return v, DANGER, 'Tinggi ↑'
    if low is not None and v < low:
        return v, WARNING, 'Rendah ↓'
    return v, SUCCESS, 'Normal'


def _build_lab_section(story, lab_records: list, s: dict):
    """Tambah section Data Laboratorium ke PDF."""
    story.append(Paragraph('Data Laboratorium', s['SectionHead']))

    if not lab_records:
        story.append(Paragraph('Belum ada data laboratorium.', s['BodyText']))
        return

    latest = lab_records[0]

    # ── Tabel parameter lab ────────────────────────────
    params = [
        # (nama, nilai, low, high, satuan, referensi)
        ('HbA1c',          latest.hba1c,               None, 7.0,   '%',      '< 7.0%'),
        ('LDL Kolesterol',  latest.ldl,                 None, 100.0, 'mg/dL',  '< 100'),
        ('HDL Kolesterol',  latest.hdl,                 40.0, None,  'mg/dL',  '> 40'),
        ('Trigliserida',    latest.triglycerides,        None, 150.0, 'mg/dL',  '< 150'),
        ('Kreatinin',       latest.creatinine,           0.6,  1.2,   'mg/dL',  '0.6 – 1.2'),
        ('Asam Urat',       latest.uric_acid,            None, 7.0,   'mg/dL',  '< 7.0'),
        ('Keton',           latest.ketone,               None, 0.6,   'mmol/L', '< 0.6'),
        ('Lingkar Perut',   latest.waist_circumference,  None, 90.0,  'cm',     '< 90 (L) / < 80 (P)'),
    ]

    # Header
    lab_rows = [[
        Paragraph('<b>Parameter</b>', ParagraphStyle('h', fontSize=8, textColor=colors.white)),
        Paragraph('<b>Hasil</b>',     ParagraphStyle('h', fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph('<b>Satuan</b>',    ParagraphStyle('h', fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph('<b>Referensi</b>', ParagraphStyle('h', fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph('<b>Status</b>',    ParagraphStyle('h', fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
    ]]

    # Filter hanya yang ada nilainya
    has_data = False
    for name, val, low, high, unit, ref in params:
        if val is None:
            continue
        has_data = True
        v, c, label = _lab_status(val, low, high)
        lab_rows.append([
            Paragraph(name, ParagraphStyle('n', fontSize=8)),
            Paragraph(f'{v:.1f}', ParagraphStyle('v', fontSize=8,
                      fontName='Helvetica-Bold', textColor=c, alignment=TA_CENTER)),
            Paragraph(unit, ParagraphStyle('u', fontSize=8, alignment=TA_CENTER)),
            Paragraph(ref,  ParagraphStyle('r', fontSize=7, textColor=colors.grey, alignment=TA_CENTER)),
            Paragraph(label, ParagraphStyle('s', fontSize=8,
                      fontName='Helvetica-Bold', textColor=c, alignment=TA_CENTER)),
        ])

    if not has_data:
        story.append(Paragraph('Data lab tersedia namun semua nilai kosong.', s['BodyText']))
        return

    lab_table = Table(lab_rows, colWidths=[4.5*cm, 2.5*cm, 2*cm, 4.5*cm, 4*cm])
    lab_table.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0), PRIMARY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GREEN]),
        ('GRID',           (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('FONTSIZE',       (0, 0), (-1, -1), 8),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING',        (0, 0), (-1, -1), 6),
    ]))
    story.append(lab_table)

    # Tanggal pemeriksaan lab
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f'Data lab dari: {_fmt_date(latest.record_date)}'
        + (f'  |  Catatan: {latest.notes}' if latest.notes else ''),
        ParagraphStyle('sm', fontSize=7, textColor=colors.grey),
    ))

    # Jika ada riwayat lebih dari 1, tampilkan ringkasan HbA1c trend
    if len(lab_records) > 1:
        story.append(Spacer(1, 8))
        story.append(Paragraph('Tren HbA1c (Riwayat)', ParagraphStyle(
            'sh', fontSize=10, textColor=PRIMARY, fontName='Helvetica-Bold', spaceBefore=4)))

        trend_rows = [['Tanggal', 'HbA1c (%)', 'Status']]
        for lr in lab_records[:6]:
            if lr.hba1c is None:
                continue
            _, c, label = _lab_status(lr.hba1c, high=7.0)
            trend_rows.append([
                _fmt_date(lr.record_date),
                Paragraph(f'{float(lr.hba1c):.1f}%', ParagraphStyle(
                    'tv', fontSize=8, fontName='Helvetica-Bold', textColor=c, alignment=TA_CENTER)),
                Paragraph(label, ParagraphStyle(
                    'ts', fontSize=8, textColor=c, alignment=TA_CENTER)),
            ])

        if len(trend_rows) > 1:
            trend_table = Table(trend_rows, colWidths=[6*cm, 4*cm, 4*cm])
            trend_table.setStyle(TableStyle([
                ('BACKGROUND',     (0, 0), (-1, 0), colors.HexColor('#E3F2FD')),
                ('FONTNAME',       (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',       (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ('GRID',           (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ('PADDING',        (0, 0), (-1, -1), 5),
                ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(trend_table)


def _generate_pdf(patient: Patient, user: User,
                  records: list, predictions: list,
                  lab_records: list = None) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=f"Laporan Kesehatan - {user.name}",
    )
    s = _build_styles()
    story = []

    # ── Header ─────────────────────────────────────────
    story.append(Paragraph('LAPORAN KESEHATAN DIABETES', s['ReportTitle']))
    story.append(Paragraph('DiabetesTelefarma — Sistem Pemantauan Risiko Diabetes', s['SubTitle']))
    story.append(Paragraph(f'Dicetak: {datetime.now().strftime("%d %b %Y, %H:%M")}', s['SmallGrey']))
    story.append(HRFlowable(width='100%', thickness=2, color=PRIMARY, spaceAfter=12))

    # ── Identitas Pasien ───────────────────────────────
    story.append(Paragraph('Identitas Pasien', s['SectionHead']))
    gender_label = 'Perempuan' if patient.gender == 'P' else 'Laki-laki'
    dob = patient.date_of_birth.strftime('%d %b %Y') if patient.date_of_birth else '-'
    info_data = [
        ['Nama Lengkap', ':', user.name,         'Jenis Kelamin', ':', gender_label],
        ['Email',        ':', user.email,        'Tanggal Lahir', ':', dob],
        ['No. HP',       ':', user.phone or '-', 'No. BPJS',      ':', patient.bpjs_number or '-'],
        ['Alamat',       ':', patient.address or '-', '', '', ''],
    ]
    info_table = Table(info_data, colWidths=[3*cm, 0.5*cm, 6*cm, 3*cm, 0.5*cm, 4.5*cm])
    info_table.setStyle(TableStyle([
        ('FONTSIZE',       (0, 0), (-1, -1), 9),
        ('FONTNAME',       (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',       (3, 0), (3, -1), 'Helvetica-Bold'),
        ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [LIGHT_BG, colors.white]),
        ('PADDING',        (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)

    # ── Ringkasan Prediksi Risiko ──────────────────────
    story.append(Paragraph('Ringkasan Prediksi Risiko', s['SectionHead']))
    if predictions:
        latest = predictions[0]
        prob   = float(latest.prob_diabetes or 0)
        rc     = _risk_color(prob)
        summary_data = [[
            Paragraph(f'{prob*100:.1f}%', ParagraphStyle('p', fontSize=28,
                      fontName='Helvetica-Bold', textColor=rc, alignment=TA_CENTER)),
            Paragraph(_risk_label(prob), ParagraphStyle('p', fontSize=16,
                      fontName='Helvetica-Bold', textColor=rc, alignment=TA_CENTER)),
            Paragraph(
                f'<b>Prediksi Terakhir</b><br/>{_fmt_date(latest.predicted_at)}<br/>'
                f'<br/><b>Total Riwayat Prediksi</b><br/>{len(predictions)} prediksi',
                ParagraphStyle('p', fontSize=9, leading=14)
            ),
        ]]
        summary_table = Table(summary_data, colWidths=[4*cm, 5*cm, 8.5*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0),
             colors.HexColor('#FFF8F8') if prob >= 0.5 else colors.HexColor('#F1F8E9')),
            ('BACKGROUND', (2, 0), (2, 0), LIGHT_BG),
            ('BOX',        (0, 0), (-1, -1), 1, colors.lightgrey),
            ('LINEAFTER',  (1, 0), (1, 0), 1, colors.lightgrey),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING',    (0, 0), (-1, -1), 10),
        ]))
        story.append(summary_table)
    else:
        story.append(Paragraph('Belum ada data prediksi.', s['BodyText']))

    # ── Riwayat Prediksi ───────────────────────────────
    if predictions:
        story.append(Spacer(1, 8))
        story.append(Paragraph('Riwayat Prediksi (10 Terakhir)', s['SectionHead']))
        pred_rows = [['Tanggal', 'Prob. Diabetes', 'Prob. Normal', 'Hasil', 'Risiko']]
        for p in predictions[:10]:
            prob_d = float(p.prob_diabetes or 0)
            prob_n = float(p.prob_no_diabetes or 0)
            rc = _risk_color(prob_d)
            pred_rows.append([
                _fmt_date(p.predicted_at),
                f'{prob_d*100:.1f}%',
                f'{prob_n*100:.1f}%',
                p.predicted_label or '-',
                Paragraph(_risk_label(prob_d), ParagraphStyle('r', fontSize=8,
                          fontName='Helvetica-Bold', textColor=rc, alignment=TA_CENTER)),
            ])
        pred_table = Table(pred_rows, colWidths=[4.5*cm, 3*cm, 3*cm, 3*cm, 4*cm])
        pred_table.setStyle(TableStyle([
            ('BACKGROUND',     (0, 0), (-1, 0), PRIMARY),
            ('TEXTCOLOR',      (0, 0), (-1, 0), colors.white),
            ('FONTNAME',       (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',       (0, 0), (-1, -1), 8),
            ('ALIGN',          (1, 0), (-1, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ('GRID',           (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('PADDING',        (0, 0), (-1, -1), 5),
            ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(pred_table)

    # ── Data Laboratorium ← BARU ───────────────────────
    _build_lab_section(story, lab_records or [], s)

    # ── Riwayat Data Kesehatan ─────────────────────────
    story.append(Paragraph('Riwayat Data Kesehatan (10 Terakhir)', s['SectionHead']))
    if not records:
        story.append(Paragraph('Belum ada data kesehatan.', s['BodyText']))
    else:
        for i, r in enumerate(records[:10]):
            rec_date = _fmt_date(r.record_date)
            header = [[Paragraph(f'<b>Pemeriksaan #{i+1}</b> — {rec_date}',
                                 ParagraphStyle('h', fontSize=9, textColor=PRIMARY))]]
            header_table = Table(header, colWidths=[17.5*cm])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
                ('PADDING',    (0, 0), (-1, -1), 6),
            ]))
            detail_data = [
                ['Gula Darah', f'{r.blood_glucose or "-"} mg/dL',
                 'BMI', f'{r.bmi or "-"}',
                 'Tek. Darah', f'{r.systolic_bp or "-"}/{r.diastolic_bp or "-"} mmHg'],
                ['Kolesterol Tinggi', _bool_str(r.high_chol),
                 'Perokok',           _bool_str(r.smoker),
                 'Aktif Fisik',       _bool_str(r.phys_activity)],
                ['Stroke',            _bool_str(r.stroke),
                 'Peny. Jantung',     _bool_str(r.heart_disease_attack),
                 'Kesulitan Jalan',   _bool_str(r.diff_walk)],
                ['Kes. Umum', f'{r.gen_hlth or "-"}/5',
                 'Kes. Mental', f'{r.ment_hlth or "0"} hari',
                 'Kes. Fisik',  f'{r.phys_hlth or "0"} hari'],
            ]
            detail_table = Table(detail_data,
                colWidths=[3.5*cm, 2.5*cm, 3*cm, 2.5*cm, 3*cm, 3*cm])
            detail_table.setStyle(TableStyle([
                ('FONTSIZE',       (0, 0), (-1, -1), 8),
                ('FONTNAME',       (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME',       (2, 0), (2, -1), 'Helvetica-Bold'),
                ('FONTNAME',       (4, 0), (4, -1), 'Helvetica-Bold'),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, LIGHT_BG]),
                ('GRID',           (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ('PADDING',        (0, 0), (-1, -1), 5),
            ]))
            story.append(KeepTogether([header_table, detail_table, Spacer(1, 6)]))

    # ── Footer ─────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'Laporan ini dibuat secara otomatis oleh sistem DiabetesTelefarma. '
        'Hasil prediksi bersifat indikatif dan bukan pengganti diagnosis dokter.',
        ParagraphStyle('footer', fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ── Endpoint: pasien download laporan diri sendiri ────
@router.get("/my")
def download_my_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Profil pasien tidak ditemukan")

    records = (db.query(HealthRecord)
               .filter(HealthRecord.patient_id == patient.id)
               .order_by(desc(HealthRecord.record_date)).limit(10).all())

    predictions = (db.query(RiskPrediction)
                   .filter(RiskPrediction.patient_id == patient.id)
                   .order_by(desc(RiskPrediction.predicted_at)).limit(10).all())

    lab_records = (db.query(LabRecord)
                   .filter(LabRecord.patient_id == patient.id)
                   .order_by(desc(LabRecord.record_date)).limit(6).all())

    pdf = _generate_pdf(patient, current_user, records, predictions, lab_records)
    filename = f"laporan_{current_user.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ── Endpoint: dokter download laporan pasien tertentu ─
@router.get("/patient/{patient_id}")
def download_patient_report(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ["dokter", "admin"]:
        raise HTTPException(403, "Akses ditolak")

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")

    user = db.query(User).filter(User.id == patient.user_id).first()

    records = (db.query(HealthRecord)
               .filter(HealthRecord.patient_id == patient_id)
               .order_by(desc(HealthRecord.record_date)).limit(10).all())

    predictions = (db.query(RiskPrediction)
                   .filter(RiskPrediction.patient_id == patient_id)
                   .order_by(desc(RiskPrediction.predicted_at)).limit(10).all())

    lab_records = (db.query(LabRecord)
                   .filter(LabRecord.patient_id == patient_id)
                   .order_by(desc(LabRecord.record_date)).limit(6).all())

    pdf = _generate_pdf(patient, user, records, predictions, lab_records)
    filename = f"laporan_{user.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )