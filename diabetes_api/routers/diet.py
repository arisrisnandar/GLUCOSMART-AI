from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func as sqlfunc
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, timedelta
from database import get_db
from models.db_models import Patient, DietEntry, User
from routers.auth import get_current_user

router = APIRouter()


class DietEntryCreate(BaseModel):
    entry_date:  Optional[date]  = None   # default: hari ini
    meal_type:   str                       # sarapan|makan_siang|makan_malam|snack
    food_name:   str
    portion:     Optional[str]   = None
    calories:    int             = 0
    carbs_g:     Optional[float] = None
    protein_g:   Optional[float] = None
    fat_g:       Optional[float] = None
    gi_category: Optional[str]  = None    # rendah|sedang|tinggi
    notes:       Optional[str]  = None


MEAL_ORDER = {"sarapan": 1, "makan_siang": 2, "makan_malam": 3, "snack": 4}

# Referensi makanan Indonesia (nama, kalori per porsi, karbohidrat, protein, lemak, gi)
FOOD_DATABASE = [
    # Makanan pokok
    {"name": "Nasi Putih",         "portion": "1 centong (100g)", "calories": 175, "carbs_g": 38.9, "protein_g": 3.5,  "fat_g": 0.4,  "gi_category": "tinggi"},
    {"name": "Nasi Merah",         "portion": "1 centong (100g)", "calories": 162, "carbs_g": 34.0, "protein_g": 3.5,  "fat_g": 1.2,  "gi_category": "sedang"},
    {"name": "Nasi Uduk", "portion": "1 piring (200g)", "calories": 260, "carbs_g": 45.0, "protein_g": 5.0, "fat_g": 6.0, "gi_category": "tinggi"},
    {"name": "Nasi Kuning", "portion": "1 piring (200g)", "calories": 270, "carbs_g": 46.0, "protein_g": 5.0, "fat_g": 7.0, "gi_category": "tinggi"},
    {"name": "Nasi Putih (1 piring)","portion": "1 piring (200g)","calories": 350, "carbs_g": 77.8, "protein_g": 7.0,  "fat_g": 0.8,  "gi_category": "tinggi"},
    {"name": "Roti Tawar Putih",   "portion": "2 lembar (60g)",  "calories": 160, "carbs_g": 30.0, "protein_g": 5.0,  "fat_g": 2.0,  "gi_category": "tinggi"},
    {"name": "Roti Gandum",        "portion": "2 lembar (60g)",  "calories": 140, "carbs_g": 26.0, "protein_g": 6.0,  "fat_g": 2.0,  "gi_category": "sedang"},
    {"name": "Mie Goreng",         "portion": "1 porsi (200g)",  "calories": 330, "carbs_g": 42.0, "protein_g": 8.0,  "fat_g": 14.0, "gi_category": "tinggi"},
    {"name": "Mie Ayam", "portion": "1 porsi", "calories": 300, "carbs_g": 45.0, "protein_g": 10.0, "fat_g": 10.0, "gi_category": "tinggi"},
    {"name": "Mie Rebus", "portion": "1 porsi", "calories": 280, "carbs_g": 42.0, "protein_g": 8.0, "fat_g": 9.0, "gi_category": "tinggi"},
    {"name": "Indomie Goreng", "portion": "1 bungkus", "calories": 350, "carbs_g": 50.0, "protein_g": 8.0, "fat_g": 14.0, "gi_category": "tinggi"},
    {"name": "Kwetiau Goreng", "portion": "1 porsi", "calories": 320, "carbs_g": 45.0, "protein_g": 9.0, "fat_g": 12.0, "gi_category": "tinggi"},
    {"name": "Kentang Rebus",      "portion": "1 buah (150g)",   "calories": 130, "carbs_g": 30.0, "protein_g": 3.0,  "fat_g": 0.1,  "gi_category": "sedang"},
    {"name": "Ubi Jalar Rebus",    "portion": "1 buah (150g)",   "calories": 145, "carbs_g": 33.0, "protein_g": 2.5,  "fat_g": 0.1,  "gi_category": "rendah"},
    {"name": "Lontong", "portion": "1 buah (150g)", "calories": 130, "carbs_g": 28.0, "protein_g": 3.0, "fat_g": 0.5, "gi_category": "sedang"},
    {"name": "Ketupat", "portion": "1 buah (150g)", "calories": 160, "carbs_g": 35.0, "protein_g": 4.0, "fat_g": 0.5, "gi_category": "sedang"},
    {"name": "Bubur Ayam", "portion": "1 mangkuk", "calories": 165, "carbs_g": 25.0, "protein_g": 8.0, "fat_g": 5.0, "gi_category": "sedang"},
    {"name": "Bubur Kacang Hijau", "portion": "1 mangkuk", "calories": 180, "carbs_g": 30.0, "protein_g": 6.0, "fat_g": 3.0, "gi_category": "sedang"},
    {"name": "Bubur Sumsum", "portion": "1 mangkuk", "calories": 200, "carbs_g": 35.0, "protein_g": 2.0, "fat_g": 5.0, "gi_category": "tinggi"},
    {"name": "Bubur Ketan Hitam", "portion": "1 mangkuk", "calories": 210, "carbs_g": 40.0, "protein_g": 4.0, "fat_g": 3.0, "gi_category": "tinggi"},
    {"name": "Nasi Liwet", "portion": "1 piring (200g)", "calories": 310, "carbs_g": 48.0, "protein_g": 6.0, "fat_g": 9.0, "gi_category": "tinggi"},
    {"name": "Nasi Kebuli", "portion": "1 piring (200g)", "calories": 360, "carbs_g": 52.0, "protein_g": 10.0, "fat_g": 12.0, "gi_category": "tinggi"},
    {"name": "Papeda", "portion": "1 porsi (200g)", "calories": 140, "carbs_g": 35.0, "protein_g": 0.2, "fat_g": 0.1, "gi_category": "tinggi"},
    {"name": "Jagung Rebus", "portion": "1 buah sedang (100g)", "calories": 96, "carbs_g": 21.0, "protein_g": 3.4, "fat_g": 1.5, "gi_category": "sedang"},
    {"name": "Singkong Rebus", "portion": "100g", "calories": 160, "carbs_g": 38.0, "protein_g": 1.4, "fat_g": 0.3, "gi_category": "sedang"},
    {"name": "Nasi Goreng", "portion": "1 piring (200g)", "calories": 340, "carbs_g": 50.0, "protein_g": 8.0, "fat_g": 12.0, "gi_category": "tinggi"},
    {"name": "Nasi Padang", "portion": "1 piring", "calories": 600, "carbs_g": 80.0, "protein_g": 25.0, "fat_g": 22.0, "gi_category": "tinggi"},
    {"name": "Nasi Bakar", "portion": "1 bungkus", "calories": 320, "carbs_g": 55.0, "protein_g": 8.0, "fat_g": 7.0, "gi_category": "tinggi"},
    {"name": "Nasi Timbel", "portion": "1 bungkus", "calories": 380, "carbs_g": 65.0, "protein_g": 8.0, "fat_g": 8.0, "gi_category": "tinggi"},
    {"name": "Nasi Campur Bali", "portion": "1 piring", "calories": 520, "carbs_g": 72.0, "protein_g": 20.0, "fat_g": 18.0, "gi_category": "tinggi"},
    {"name": "Ketoprak", "portion": "1 porsi", "calories": 310, "carbs_g": 42.0, "protein_g": 10.0, "fat_g": 12.0, "gi_category": "sedang"},
    {"name": "Lontong Sayur", "portion": "1 porsi", "calories": 280, "carbs_g": 38.0, "protein_g": 8.0, "fat_g": 10.0, "gi_category": "sedang"},
    {"name": "Bihun Goreng", "portion": "1 porsi (150g)", "calories": 260, "carbs_g": 40.0, "protein_g": 6.0, "fat_g": 9.0, "gi_category": "tinggi"},
    {"name": "Bihun Kuah", "portion": "1 mangkuk", "calories": 210, "carbs_g": 35.0, "protein_g": 5.0, "fat_g": 6.0, "gi_category": "tinggi"},
    {"name": "Soun Goreng", "portion": "1 porsi (100g)", "calories": 180, "carbs_g": 38.0, "protein_g": 2.0, "fat_g": 3.0, "gi_category": "tinggi"},
    {"name": "Macaroni Schotel", "portion": "1 potong", "calories": 280, "carbs_g": 30.0, "protein_g": 10.0, "fat_g": 14.0, "gi_category": "sedang"},
    {"name": "Roti Bakar", "portion": "2 lembar", "calories": 200, "carbs_g": 32.0, "protein_g": 5.0, "fat_g": 7.0, "gi_category": "tinggi"},
    {"name": "Roti Canai", "portion": "1 lembar", "calories": 300, "carbs_g": 42.0, "protein_g": 6.0, "fat_g": 12.0, "gi_category": "tinggi"},
    {"name": "Oatmeal", "portion": "1 mangkuk (40g kering)", "calories": 150, "carbs_g": 27.0, "protein_g": 5.0, "fat_g": 3.0, "gi_category": "rendah"},
    {"name": "Granola", "portion": "1/2 cup (50g)", "calories": 220, "carbs_g": 32.0, "protein_g": 5.0, "fat_g": 8.0, "gi_category": "sedang"},

    # Lauk protein
    {"name": "Ayam Goreng",        "portion": "1 potong (80g)",  "calories": 246, "carbs_g": 5.0,  "protein_g": 21.0, "fat_g": 16.0, "gi_category": "rendah"},
    {"name": "Ayam Bakar",         "portion": "1 potong (80g)",  "calories": 180, "carbs_g": 2.0,  "protein_g": 25.0, "fat_g": 8.0,  "gi_category": "rendah"},
    {"name": "Ikan Goreng",        "portion": "1 ekor (100g)",   "calories": 196, "carbs_g": 4.0,  "protein_g": 22.0, "fat_g": 11.0, "gi_category": "rendah"},
    {"name": "Ikan Bakar",         "portion": "1 ekor (100g)",   "calories": 150, "carbs_g": 0.0,  "protein_g": 25.0, "fat_g": 5.0,  "gi_category": "rendah"},
    {"name": "Telur Goreng",       "portion": "1 butir (55g)",   "calories": 108, "carbs_g": 0.5,  "protein_g": 7.5,  "fat_g": 8.5,  "gi_category": "rendah"},
    {"name": "Telur Rebus",        "portion": "1 butir (55g)",   "calories": 78,  "carbs_g": 0.6,  "protein_g": 6.3,  "fat_g": 5.3,  "gi_category": "rendah"},
    {"name": "Tempe Goreng",       "portion": "2 potong (50g)",  "calories": 100, "carbs_g": 6.5,  "protein_g": 9.0,  "fat_g": 5.0,  "gi_category": "rendah"},
    {"name": "Tahu Goreng",        "portion": "2 potong (100g)", "calories": 117, "carbs_g": 4.0,  "protein_g": 8.0,  "fat_g": 8.0,  "gi_category": "rendah"},
    {"name": "Daging Sapi",        "portion": "1 porsi (80g)",   "calories": 170, "carbs_g": 0.0,  "protein_g": 22.0, "fat_g": 9.0,  "gi_category": "rendah"},
    {"name": "Rendang", "portion": "100g", "calories": 350, "carbs_g": 5.0, "protein_g": 20.0, "fat_g": 28.0, "gi_category": "rendah"},
    {"name": "Opor Ayam", "portion": "1 porsi", "calories": 280, "carbs_g": 6.0, "protein_g": 18.0, "fat_g": 22.0, "gi_category": "rendah"},
    {"name": "Gulai Ayam", "portion": "1 porsi", "calories": 320, "carbs_g": 8.0, "protein_g": 20.0, "fat_g": 25.0, "gi_category": "rendah"},
    {"name": "Sate Ayam", "portion": "10 tusuk", "calories": 250, "carbs_g": 10.0, "protein_g": 20.0, "fat_g": 15.0, "gi_category": "rendah"},
    {"name": "Sate Kambing", "portion": "10 tusuk", "calories": 300, "carbs_g": 8.0, "protein_g": 22.0, "fat_g": 20.0, "gi_category": "rendah"},
    {"name": "Empal Gentong", "portion": "1 mangkuk", "calories": 250, "carbs_g": 8.0, "protein_g": 18.0, "fat_g": 16.0, "gi_category": "rendah"},
    {"name": "Sop Buntut", "portion": "1 porsi", "calories": 420, "carbs_g": 10.0, "protein_g": 25.0, "fat_g": 32.0, "gi_category": "rendah"},
    {"name": "Cumi Goreng Tepung", "portion": "100g", "calories": 285, "carbs_g": 18.0, "protein_g": 15.0, "fat_g": 18.0, "gi_category": "sedang"},
    {"name": "Udang Balado", "portion": "100g", "calories": 145, "carbs_g": 4.0, "protein_g": 20.0, "fat_g": 6.0, "gi_category": "rendah"},
    {"name": "Pepes Ikan", "portion": "1 bungkus", "calories": 120, "carbs_g": 2.0, "protein_g": 18.0, "fat_g": 5.0, "gi_category": "rendah"},
    {"name": "Telur Asin", "portion": "1 butir", "calories": 137, "carbs_g": 1.1, "protein_g": 9.5, "fat_g": 10.2, "gi_category": "rendah"},
    {"name": "Ati Ampela Goreng", "portion": "1 pasang", "calories": 140, "carbs_g": 1.0, "protein_g": 16.0, "fat_g": 8.0, "gi_category": "rendah"},
    {"name": "Ayam Geprek", "portion": "1 potong + nasi", "calories": 520, "carbs_g": 60.0, "protein_g": 28.0, "fat_g": 18.0, "gi_category": "tinggi"},
    {"name": "Ayam Pop", "portion": "1 potong (80g)", "calories": 165, "carbs_g": 1.0, "protein_g": 24.0, "fat_g": 7.0, "gi_category": "rendah"},
    {"name": "Bebek Goreng", "portion": "1 potong (100g)", "calories": 330, "carbs_g": 3.0, "protein_g": 22.0, "fat_g": 26.0, "gi_category": "rendah"},
    {"name": "Bebek Betutu", "portion": "1 porsi (100g)", "calories": 290, "carbs_g": 5.0, "protein_g": 20.0, "fat_g": 22.0, "gi_category": "rendah"},
    {"name": "Ikan Pindang", "portion": "1 ekor (100g)", "calories": 110, "carbs_g": 0.0, "protein_g": 20.0, "fat_g": 3.5, "gi_category": "rendah"},
    {"name": "Ikan Asin Goreng", "portion": "1 potong (30g)", "calories": 95, "carbs_g": 0.0, "protein_g": 14.0, "fat_g": 4.5, "gi_category": "rendah"},
    {"name": "Ikan Tongkol Balado", "portion": "100g", "calories": 160, "carbs_g": 5.0, "protein_g": 22.0, "fat_g": 7.0, "gi_category": "rendah"},
    {"name": "Ikan Gurame Goreng", "portion": "1 ekor sedang", "calories": 280, "carbs_g": 6.0, "protein_g": 30.0, "fat_g": 15.0, "gi_category": "rendah"},
    {"name": "Kepiting Saus Tiram", "portion": "1 porsi", "calories": 220, "carbs_g": 10.0, "protein_g": 18.0, "fat_g": 12.0, "gi_category": "rendah"},
    {"name": "Cah Udang Brokoli", "portion": "1 porsi", "calories": 175, "carbs_g": 8.0, "protein_g": 18.0, "fat_g": 8.0, "gi_category": "rendah"},
    {"name": "Semur Daging", "portion": "1 porsi (100g)", "calories": 230, "carbs_g": 10.0, "protein_g": 20.0, "fat_g": 12.0, "gi_category": "sedang"},
    {"name": "Dendeng Balado", "portion": "50g", "calories": 175, "carbs_g": 4.0, "protein_g": 18.0, "fat_g": 10.0, "gi_category": "rendah"},
    {"name": "Tengkleng Kambing", "portion": "1 mangkuk", "calories": 310, "carbs_g": 6.0, "protein_g": 22.0, "fat_g": 23.0, "gi_category": "rendah"},
    {"name": "Tongseng Kambing", "portion": "1 mangkuk", "calories": 290, "carbs_g": 8.0, "protein_g": 20.0, "fat_g": 20.0, "gi_category": "rendah"},
    {"name": "Telur Balado", "portion": "1 butir", "calories": 120, "carbs_g": 3.0, "protein_g": 7.0, "fat_g": 9.0, "gi_category": "rendah"},
    {"name": "Tempe Bacem", "portion": "2 potong (60g)", "calories": 130, "carbs_g": 12.0, "protein_g": 9.0, "fat_g": 5.0, "gi_category": "sedang"},
    {"name": "Tahu Bacem", "portion": "2 potong (100g)", "calories": 105, "carbs_g": 8.0, "protein_g": 7.0, "fat_g": 5.0, "gi_category": "sedang"},
    {"name": "Tempe Mendoan", "portion": "2 lembar", "calories": 160, "carbs_g": 14.0, "protein_g": 8.0, "fat_g": 8.0, "gi_category": "sedang"},
    {"name": "Oncom Goreng", "portion": "100g", "calories": 115, "carbs_g": 10.0, "protein_g": 10.0, "fat_g": 4.0, "gi_category": "rendah"},
    {"name": "Nugget Ayam", "portion": "5 potong (100g)", "calories": 250, "carbs_g": 14.0, "protein_g": 14.0, "fat_g": 15.0, "gi_category": "sedang"},
    {"name": "Sosis Sapi Goreng", "portion": "2 buah (80g)", "calories": 240, "carbs_g": 8.0, "protein_g": 10.0, "fat_g": 19.0, "gi_category": "sedang"},

    # Sayuran
    {"name": "Sayur Bayam",        "portion": "1 mangkok (100g)","calories": 22,  "carbs_g": 3.5,  "protein_g": 2.3,  "fat_g": 0.3,  "gi_category": "rendah"},
    {"name": "Tumis Kangkung",     "portion": "1 porsi (100g)",  "calories": 45,  "carbs_g": 5.0,  "protein_g": 2.5,  "fat_g": 2.0,  "gi_category": "rendah"},
    {"name": "Sayur Sop",          "portion": "1 mangkok (200g)","calories": 80,  "carbs_g": 12.0, "protein_g": 4.0,  "fat_g": 2.0,  "gi_category": "rendah"},
    {"name": "Sayur Asem", "portion": "1 mangkuk", "calories": 80, "carbs_g": 12.0, "protein_g": 3.0, "fat_g": 2.0, "gi_category": "rendah"},
    {"name": "Sayur Lodeh", "portion": "1 mangkuk", "calories": 150, "carbs_g": 10.0, "protein_g": 4.0, "fat_g": 10.0, "gi_category": "rendah"},
    {"name": "Capcay", "portion": "1 porsi", "calories": 120, "carbs_g": 15.0, "protein_g": 5.0, "fat_g": 5.0, "gi_category": "rendah"},
    {"name": "Gado-Gado", "portion": "1 porsi", "calories": 310, "carbs_g": 28.0, "protein_g": 12.0, "fat_g": 18.0, "gi_category": "sedang"},
    {"name": "Pecel Sayur", "portion": "1 porsi", "calories": 220, "carbs_g": 22.0, "protein_g": 8.0, "fat_g": 12.0, "gi_category": "rendah"},
    {"name": "Urap Sayur", "portion": "1 porsi", "calories": 150, "carbs_g": 15.0, "protein_g": 5.0, "fat_g": 9.0, "gi_category": "rendah"},
    {"name": "Tumis Buncis", "portion": "100g", "calories": 65, "carbs_g": 7.0, "protein_g": 2.0, "fat_g": 4.0, "gi_category": "rendah"},
    {"name": "Perkedel Kentang", "portion": "1 buah", "calories": 125, "carbs_g": 14.0, "protein_g": 2.5, "fat_g": 7.0, "gi_category": "sedang"},
    {"name": "Tumis Tauge", "portion": "100g", "calories": 45, "carbs_g": 5.0, "protein_g": 2.5, "fat_g": 2.0, "gi_category": "rendah"},
    {"name": "Tumis Jamur Tiram", "portion": "100g", "calories": 60, "carbs_g": 6.0, "protein_g": 3.0, "fat_g": 3.0, "gi_category": "rendah"},
    {"name": "Tumis Terong", "portion": "100g", "calories": 70, "carbs_g": 7.0, "protein_g": 1.5, "fat_g": 4.0, "gi_category": "rendah"},
    {"name": "Sayur Kare", "portion": "1 mangkuk", "calories": 180, "carbs_g": 14.0, "protein_g": 5.0, "fat_g": 12.0, "gi_category": "rendah"},
    {"name": "Plecing Kangkung", "portion": "1 porsi", "calories": 80, "carbs_g": 8.0, "protein_g": 2.5, "fat_g": 4.5, "gi_category": "rendah"},
    {"name": "Lalapan + Sambal", "portion": "1 porsi", "calories": 55, "carbs_g": 6.0, "protein_g": 2.0, "fat_g": 2.5, "gi_category": "rendah"},
    {"name": "Karedok", "portion": "1 porsi", "calories": 190, "carbs_g": 18.0, "protein_g": 6.0, "fat_g": 11.0, "gi_category": "rendah"},
    {"name": "Rujak Cingur", "portion": "1 porsi", "calories": 320, "carbs_g": 35.0, "protein_g": 12.0, "fat_g": 15.0, "gi_category": "sedang"},
    {"name": "Asinan Betawi", "portion": "1 porsi", "calories": 180, "carbs_g": 28.0, "protein_g": 4.0, "fat_g": 6.0, "gi_category": "sedang"},

    # Makanan Berkuah
    {"name": "Bakso", "portion": "1 mangkuk", "calories": 200, "carbs_g": 20.0, "protein_g": 10.0, "fat_g": 8.0, "gi_category": "sedang"},
    {"name": "Soto Ayam", "portion": "1 mangkuk", "calories": 180, "carbs_g": 15.0, "protein_g": 12.0, "fat_g": 8.0, "gi_category": "rendah"},
    {"name": "Soto Betawi", "portion": "1 mangkuk", "calories": 300, "carbs_g": 12.0, "protein_g": 15.0, "fat_g": 20.0, "gi_category": "rendah"},
    {"name": "Pempek Kapal Selam", "portion": "1 buah besar", "calories": 340, "carbs_g": 40.0, "protein_g": 15.0, "fat_g": 12.0, "gi_category": "sedang"},
    {"name": "Tekwan", "portion": "1 mangkuk", "calories": 250, "carbs_g": 35.0, "protein_g": 12.0, "fat_g": 6.0, "gi_category": "sedang"},
    {"name": "Seblak Komplit", "portion": "1 porsi", "calories": 450, "carbs_g": 55.0, "protein_g": 12.0, "fat_g": 22.0, "gi_category": "tinggi"},
    {"name": "Rawon", "portion": "1 mangkuk", "calories": 220, "carbs_g": 8.0, "protein_g": 18.0, "fat_g": 14.0, "gi_category": "rendah"},
    {"name": "Soto Madura", "portion": "1 mangkuk", "calories": 210, "carbs_g": 18.0, "protein_g": 14.0, "fat_g": 9.0, "gi_category": "rendah"},
    {"name": "Soto Kudus", "portion": "1 mangkuk", "calories": 190, "carbs_g": 16.0, "protein_g": 12.0, "fat_g": 8.0, "gi_category": "rendah"},
    {"name": "Coto Makassar", "portion": "1 mangkuk", "calories": 280, "carbs_g": 10.0, "protein_g": 20.0, "fat_g": 18.0, "gi_category": "rendah"},
    {"name": "Sup Kimlo", "portion": "1 mangkuk", "calories": 150, "carbs_g": 14.0, "protein_g": 10.0, "fat_g": 6.0, "gi_category": "rendah"},
    {"name": "Laksa", "portion": "1 mangkuk", "calories": 350, "carbs_g": 42.0, "protein_g": 14.0, "fat_g": 14.0, "gi_category": "tinggi"},
    {"name": "Mie Celor", "portion": "1 mangkuk", "calories": 380, "carbs_g": 50.0, "protein_g": 14.0, "fat_g": 14.0, "gi_category": "tinggi"},
    {"name": "Pindang Patin", "portion": "1 mangkuk", "calories": 180, "carbs_g": 5.0, "protein_g": 20.0, "fat_g": 9.0, "gi_category": "rendah"},
    {"name": "Garang Asem Ayam", "portion": "1 mangkuk", "calories": 200, "carbs_g": 6.0, "protein_g": 18.0, "fat_g": 12.0, "gi_category": "rendah"},
    {"name": "Sayur Bening Bayam", "portion": "1 mangkuk", "calories": 45, "carbs_g": 5.0, "protein_g": 2.5, "fat_g": 0.5, "gi_category": "rendah"},
    {"name": "Soto Banjar", "portion": "1 mangkuk", "calories": 240, "carbs_g": 22.0, "protein_g": 14.0, "fat_g": 10.0, "gi_category": "sedang"},

    #Jajanan
    {"name": "Martabak Manis", "portion": "1 potong", "calories": 400, "carbs_g": 50.0, "protein_g": 6.0, "fat_g": 18.0, "gi_category": "tinggi"},
    {"name": "Martabak Telur", "portion": "1 potong", "calories": 350, "carbs_g": 30.0, "protein_g": 12.0, "fat_g": 20.0, "gi_category": "tinggi"},
    {"name": "Pisang Goreng", "portion": "2 buah", "calories": 200, "carbs_g": 30.0, "protein_g": 2.0, "fat_g": 8.0, "gi_category": "tinggi"},
    {"name": "Singkong Goreng", "portion": "100g", "calories": 220, "carbs_g": 35.0, "protein_g": 1.5, "fat_g": 8.0, "gi_category": "tinggi"},
    {"name": "Bakwan Sayur", "portion": "1 buah", "calories": 140, "carbs_g": 15.0, "protein_g": 2.0, "fat_g": 8.5, "gi_category": "tinggi"},
    {"name": "Cireng", "portion": "3 buah", "calories": 210, "carbs_g": 32.0, "protein_g": 1.0, "fat_g": 9.0, "gi_category": "tinggi"},
    {"name": "Cilok Bumbu Kacang", "portion": "5 butir", "calories": 180, "carbs_g": 25.0, "protein_g": 3.0, "fat_g": 8.0, "gi_category": "tinggi"},
    {"name": "Lumpia Semarang", "portion": "1 buah", "calories": 125, "carbs_g": 18.0, "protein_g": 6.0, "fat_g": 4.5, "gi_category": "sedang"},
    {"name": "Kue Putu Ayu", "portion": "2 buah", "calories": 130, "carbs_g": 22.0, "protein_g": 2.0, "fat_g": 4.0, "gi_category": "tinggi"},
    {"name": "Siomay Bandung", "portion": "1 porsi (5 pcs)", "calories": 280, "carbs_g": 30.0, "protein_g": 14.0, "fat_g": 11.0, "gi_category": "sedang"},
    {"name": "Batagor", "portion": "1 porsi (5 pcs)", "calories": 320, "carbs_g": 28.0, "protein_g": 14.0, "fat_g": 17.0, "gi_category": "sedang"},
    {"name": "Tahu Sumedang", "portion": "5 buah (100g)", "calories": 180, "carbs_g": 10.0, "protein_g": 11.0, "fat_g": 11.0, "gi_category": "rendah"},
    {"name": "Kerak Telor", "portion": "1 porsi", "calories": 310, "carbs_g": 35.0, "protein_g": 10.0, "fat_g": 15.0, "gi_category": "tinggi"},
    {"name": "Klepon", "portion": "5 buah", "calories": 180, "carbs_g": 35.0, "protein_g": 2.0, "fat_g": 4.0, "gi_category": "tinggi"},
    {"name": "Onde-Onde", "portion": "3 buah", "calories": 220, "carbs_g": 32.0, "protein_g": 4.0, "fat_g": 9.0, "gi_category": "tinggi"},
    {"name": "Dadar Gulung", "portion": "2 buah", "calories": 160, "carbs_g": 25.0, "protein_g": 3.0, "fat_g": 5.0, "gi_category": "tinggi"},
    {"name": "Risoles Mayo", "portion": "1 buah", "calories": 170, "carbs_g": 18.0, "protein_g": 5.0, "fat_g": 9.0, "gi_category": "sedang"},
    {"name": "Pastel Isi", "portion": "1 buah", "calories": 185, "carbs_g": 20.0, "protein_g": 5.0, "fat_g": 10.0, "gi_category": "sedang"},
    {"name": "Lemper", "portion": "1 buah", "calories": 140, "carbs_g": 22.0, "protein_g": 5.0, "fat_g": 4.0, "gi_category": "tinggi"},
    {"name": "Getuk", "portion": "1 potong (80g)", "calories": 150, "carbs_g": 30.0, "protein_g": 1.5, "fat_g": 3.0, "gi_category": "tinggi"},
    {"name": "Wajik", "portion": "1 potong (60g)", "calories": 160, "carbs_g": 34.0, "protein_g": 1.5, "fat_g": 2.5, "gi_category": "tinggi"},
    {"name": "Cenil", "portion": "100g", "calories": 145, "carbs_g": 32.0, "protein_g": 1.0, "fat_g": 2.0, "gi_category": "tinggi"},
    {"name": "Talam Ubi", "portion": "1 potong", "calories": 130, "carbs_g": 26.0, "protein_g": 2.0, "fat_g": 3.0, "gi_category": "sedang"},
    {"name": "Pukis", "portion": "2 buah", "calories": 175, "carbs_g": 28.0, "protein_g": 4.0, "fat_g": 5.0, "gi_category": "tinggi"},
    {"name": "Surabi", "portion": "1 buah", "calories": 160, "carbs_g": 28.0, "protein_g": 3.5, "fat_g": 4.5, "gi_category": "tinggi"},
    {"name": "Donat Kentang", "portion": "1 buah", "calories": 240, "carbs_g": 32.0, "protein_g": 4.0, "fat_g": 11.0, "gi_category": "tinggi"},
    {"name": "Kroket Kentang", "portion": "2 buah", "calories": 200, "carbs_g": 22.0, "protein_g": 5.0, "fat_g": 11.0, "gi_category": "sedang"},
    {"name": "Tahu Gejrot", "portion": "1 porsi", "calories": 140, "carbs_g": 12.0, "protein_g": 7.0, "fat_g": 7.0, "gi_category": "rendah"},
    {"name": "Mie Lidi Pedas", "portion": "1 bungkus (50g)", "calories": 250, "carbs_g": 30.0, "protein_g": 4.0, "fat_g": 13.0, "gi_category": "tinggi"},

    # Buah
    {"name": "Pisang",             "portion": "1 buah (100g)",   "calories": 89,  "carbs_g": 23.0, "protein_g": 1.1,  "fat_g": 0.3,  "gi_category": "sedang"},
    {"name": "Apel",               "portion": "1 buah (150g)",   "calories": 78,  "carbs_g": 21.0, "protein_g": 0.4,  "fat_g": 0.2,  "gi_category": "rendah"},
    {"name": "Pepaya",             "portion": "1 potong (200g)", "calories": 80,  "carbs_g": 20.0, "protein_g": 0.9,  "fat_g": 0.1,  "gi_category": "rendah"},
    {"name": "Semangka",           "portion": "1 potong (200g)", "calories": 62,  "carbs_g": 15.6, "protein_g": 1.2,  "fat_g": 0.2,  "gi_category": "tinggi"},
    {"name": "Jeruk",              "portion": "1 buah (130g)",   "calories": 47,  "carbs_g": 12.0, "protein_g": 0.9,  "fat_g": 0.1,  "gi_category": "rendah"},
    {"name": "Alpukat", "portion": "1/2 buah (100g)", "calories": 160, "carbs_g": 8.5, "protein_g": 2.0, "fat_g": 14.7, "gi_category": "rendah"},
    {"name": "Mangga", "portion": "1 buah (200g)", "calories": 120, "carbs_g": 30.0, "protein_g": 1.6, "fat_g": 0.8, "gi_category": "sedang"},
    {"name": "Durian", "portion": "3 biji (100g)", "calories": 147, "carbs_g": 27.0, "protein_g": 1.5, "fat_g": 5.3, "gi_category": "tinggi"},
    {"name": "Naga Merah", "portion": "1 buah sedang (250g)", "calories": 125, "carbs_g": 23.0, "protein_g": 3.0, "fat_g": 1.0, "gi_category": "rendah"},
    {"name": "Melon", "portion": "1 potong (150g)", "calories": 54, "carbs_g": 13.0, "protein_g": 0.8, "fat_g": 0.3, "gi_category": "sedang"},
    {"name": "Nanas", "portion": "1 potong (100g)", "calories": 50, "carbs_g": 13.0, "protein_g": 0.5, "fat_g": 0.1, "gi_category": "sedang"},
    {"name": "Salak", "portion": "2 buah (100g)", "calories": 82, "carbs_g": 20.0, "protein_g": 0.8, "fat_g": 0.4, "gi_category": "rendah"},
    {"name": "Sawo", "portion": "1 buah (100g)", "calories": 83, "carbs_g": 20.0, "protein_g": 0.4, "fat_g": 1.1, "gi_category": "sedang"},
    {"name": "Manggis", "portion": "3 buah (100g)", "calories": 73, "carbs_g": 18.0, "protein_g": 0.4, "fat_g": 0.6, "gi_category": "rendah"},
    {"name": "Rambutan", "portion": "5 buah (100g)", "calories": 82, "carbs_g": 21.0, "protein_g": 0.9, "fat_g": 0.2, "gi_category": "sedang"},
    {"name": "Jambu Biji", "portion": "1 buah (100g)", "calories": 68, "carbs_g": 14.0, "protein_g": 2.5, "fat_g": 1.0, "gi_category": "rendah"},
    {"name": "Jambu Air", "portion": "2 buah (100g)", "calories": 46, "carbs_g": 12.0, "protein_g": 0.6, "fat_g": 0.3, "gi_category": "rendah"},
    {"name": "Sirsak", "portion": "100g", "calories": 66, "carbs_g": 17.0, "protein_g": 1.0, "fat_g": 0.3, "gi_category": "rendah"},
    {"name": "Kurma", "portion": "3 butir (25g)", "calories": 70, "carbs_g": 18.0, "protein_g": 0.5, "fat_g": 0.1, "gi_category": "sedang"},
    {"name": "Anggur", "portion": "10 butir (100g)", "calories": 67, "carbs_g": 18.0, "protein_g": 0.7, "fat_g": 0.2, "gi_category": "sedang"},
    {"name": "Kelengkeng", "portion": "10 butir (100g)", "calories": 60, "carbs_g": 15.0, "protein_g": 1.3, "fat_g": 0.1, "gi_category": "sedang"},
    {"name": "Pir", "portion": "1 buah (170g)", "calories": 96, "carbs_g": 25.0, "protein_g": 0.6, "fat_g": 0.2, "gi_category": "rendah"},
    {"name": "Strawberry", "portion": "5 buah (100g)", "calories": 32, "carbs_g": 7.7, "protein_g": 0.7, "fat_g": 0.3, "gi_category": "rendah"},
    {"name": "Nangka", "portion": "3 biji (100g)", "calories": 95, "carbs_g": 23.0, "protein_g": 1.7, "fat_g": 0.6, "gi_category": "sedang"},
    {"name": "Srikaya", "portion": "1 buah (100g)", "calories": 101, "carbs_g": 25.0, "protein_g": 2.0, "fat_g": 0.6, "gi_category": "tinggi"},
    {"name": "Kedondong", "portion": "1 buah (100g)", "calories": 41, "carbs_g": 10.0, "protein_g": 1.0, "fat_g": 0.1, "gi_category": "rendah"},
    
    # Minuman
    {"name": "Susu Sapi (rendah lemak)", "portion": "1 gelas (200ml)", "calories": 102, "carbs_g": 12.0, "protein_g": 7.0, "fat_g": 2.5, "gi_category": "rendah"},
    {"name": "Teh Manis",          "portion": "1 gelas (200ml)", "calories": 60,  "carbs_g": 15.0, "protein_g": 0.0,  "fat_g": 0.0,  "gi_category": "tinggi"},
    {"name": "Teh Tawar",          "portion": "1 gelas (200ml)", "calories": 2,   "carbs_g": 0.5,  "protein_g": 0.0,  "fat_g": 0.0,  "gi_category": "rendah"},
    {"name": "Kopi Hitam",         "portion": "1 gelas (200ml)", "calories": 5,   "carbs_g": 1.0,  "protein_g": 0.3,  "fat_g": 0.0,  "gi_category": "rendah"},
    {"name": "Es Jeruk", "portion": "1 gelas", "calories": 110, "carbs_g": 25.0, "protein_g": 1.0, "fat_g": 0.0, "gi_category": "sedang"},
    {"name": "Jus Alpukat", "portion": "1 gelas", "calories": 250, "carbs_g": 20.0, "protein_g": 3.0, "fat_g": 18.0, "gi_category": "rendah"},
    {"name": "Jus Mangga", "portion": "1 gelas", "calories": 180, "carbs_g": 40.0, "protein_g": 1.0, "fat_g": 0.5, "gi_category": "sedang"},
    {"name": "Es Doger", "portion": "1 gelas", "calories": 320, "carbs_g": 45.0, "protein_g": 4.0, "fat_g": 14.0, "gi_category": "tinggi"},
    {"name": "Es Campur", "portion": "1 mangkuk", "calories": 280, "carbs_g": 50.0, "protein_g": 3.0, "fat_g": 8.0, "gi_category": "tinggi"},
    {"name": "Boba Milk Tea", "portion": "1 gelas (medium)", "calories": 450, "carbs_g": 65.0, "protein_g": 4.0, "fat_g": 20.0, "gi_category": "tinggi"},
    {"name": "Kopi Susu Gula Aren", "portion": "1 gelas", "calories": 220, "carbs_g": 30.0, "protein_g": 3.5, "fat_g": 9.5, "gi_category": "tinggi"},
    {"name": "STMJ", "portion": "1 gelas", "calories": 250, "carbs_g": 28.0, "protein_g": 10.0, "fat_g": 11.0, "gi_category": "sedang"},
    {"name": "Air Kelapa Muda", "portion": "1 gelas (250ml)", "calories": 45, "carbs_g": 9.0, "protein_g": 0.5, "fat_g": 0.1, "gi_category": "rendah"},
    {"name": "Susu Kedelai", "portion": "1 gelas (250ml)", "calories": 100, "carbs_g": 8.0, "protein_g": 7.0, "fat_g": 4.0, "gi_category": "rendah"},
    {"name": "Susu Full Cream", "portion": "1 gelas (200ml)", "calories": 130, "carbs_g": 10.0, "protein_g": 7.0, "fat_g": 8.0, "gi_category": "rendah"},
    {"name": "Yogurt Buah", "portion": "1 cup (150g)", "calories": 140, "carbs_g": 22.0, "protein_g": 6.0, "fat_g": 3.0, "gi_category": "sedang"},
    {"name": "Jus Jambu Merah", "portion": "1 gelas", "calories": 95, "carbs_g": 22.0, "protein_g": 1.0, "fat_g": 0.3, "gi_category": "rendah"},
    {"name": "Jus Tomat", "portion": "1 gelas (250ml)", "calories": 45, "carbs_g": 10.0, "protein_g": 2.0, "fat_g": 0.2, "gi_category": "rendah"},
    {"name": "Jus Wortel", "portion": "1 gelas (250ml)", "calories": 95, "carbs_g": 22.0, "protein_g": 2.2, "fat_g": 0.4, "gi_category": "sedang"},
    {"name": "Wedang Jahe", "portion": "1 gelas", "calories": 60, "carbs_g": 14.0, "protein_g": 0.2, "fat_g": 0.1, "gi_category": "sedang"},
    {"name": "Wedang Uwuh", "portion": "1 gelas", "calories": 50, "carbs_g": 12.0, "protein_g": 0.1, "fat_g": 0.1, "gi_category": "sedang"},
    {"name": "Bajigur", "portion": "1 gelas", "calories": 150, "carbs_g": 25.0, "protein_g": 1.5, "fat_g": 5.0, "gi_category": "tinggi"},
    {"name": "Bandrek", "portion": "1 gelas", "calories": 110, "carbs_g": 20.0, "protein_g": 1.0, "fat_g": 3.0, "gi_category": "sedang"},
    {"name": "Es Teh Manis", "portion": "1 gelas", "calories": 70, "carbs_g": 18.0, "protein_g": 0.0, "fat_g": 0.0, "gi_category": "tinggi"},
    {"name": "Es Cendol", "portion": "1 gelas", "calories": 250, "carbs_g": 42.0, "protein_g": 2.0, "fat_g": 8.0, "gi_category": "tinggi"},
    {"name": "Es Dawet", "portion": "1 gelas", "calories": 230, "carbs_g": 40.0, "protein_g": 2.0, "fat_g": 7.0, "gi_category": "tinggi"},
    {"name": "Kopi Instan Sachet", "portion": "1 sachet", "calories": 75, "carbs_g": 13.0, "protein_g": 1.0, "fat_g": 2.5, "gi_category": "tinggi"},
    {"name": "Minuman Isotonik", "portion": "1 botol (350ml)", "calories": 80, "carbs_g": 20.0, "protein_g": 0.0, "fat_g": 0.0, "gi_category": "tinggi"},
    {"name": "Jus Jeruk Kemasan", "portion": "1 kotak (250ml)", "calories": 110, "carbs_g": 26.0, "protein_g": 0.5, "fat_g": 0.0, "gi_category": "tinggi"},

    # Snack
    {"name": "Biskuit Gandum",     "portion": "4 keping (30g)",  "calories": 130, "carbs_g": 20.0, "protein_g": 3.0,  "fat_g": 4.5,  "gi_category": "sedang"},
    {"name": "Kacang Tanah",       "portion": "1 genggam (30g)", "calories": 170, "carbs_g": 4.5,  "protein_g": 7.5,  "fat_g": 14.0, "gi_category": "rendah"},
    {"name": "Kuaci Biji Bunga Matahari", "portion": "1 kantong kecil (30g)", "calories": 165, "carbs_g": 6.0, "protein_g": 6.0, "fat_g": 14.0, "gi_category": "rendah"},
    {"name": "Yogurt Tawar",       "portion": "1 cup (150g)",    "calories": 90,  "carbs_g": 12.0, "protein_g": 8.0,  "fat_g": 0.5,  "gi_category": "rendah"},
    {"name": "Keripik Tempe", "portion": "1 genggam (30g)", "calories": 145, "carbs_g": 12.0, "protein_g": 8.0, "fat_g": 7.0, "gi_category": "rendah"},
    {"name": "Keripik Pisang", "portion": "1 genggam (30g)", "calories": 150, "carbs_g": 20.0, "protein_g": 1.0, "fat_g": 7.5, "gi_category": "tinggi"},
    {"name": "Keripik Singkong", "portion": "1 genggam (30g)", "calories": 155, "carbs_g": 22.0, "protein_g": 1.0, "fat_g": 7.0, "gi_category": "tinggi"},
    {"name": "Keripik Kentang", "portion": "1 bungkus kecil (28g)", "calories": 150, "carbs_g": 15.0, "protein_g": 2.0, "fat_g": 10.0, "gi_category": "tinggi"},
    {"name": "Emping Melinjo", "portion": "1 genggam (30g)", "calories": 135, "carbs_g": 18.0, "protein_g": 3.5, "fat_g": 6.0, "gi_category": "sedang"},
    {"name": "Kacang Edamame", "portion": "1/2 cup (80g)", "calories": 95, "carbs_g": 8.0, "protein_g": 8.5, "fat_g": 4.0, "gi_category": "rendah"},
    {"name": "Kacang Almond", "portion": "1 genggam (28g)", "calories": 165, "carbs_g": 6.0, "protein_g": 6.0, "fat_g": 14.0, "gi_category": "rendah"},
    {"name": "Kacang Mete", "portion": "1 genggam (28g)", "calories": 160, "carbs_g": 9.0, "protein_g": 5.0, "fat_g": 13.0, "gi_category": "rendah"},
    {"name": "Kacang Hijau Rebus", "portion": "1/2 cup (100g)", "calories": 105, "carbs_g": 19.0, "protein_g": 7.0, "fat_g": 0.4, "gi_category": "rendah"},
    {"name": "Roti Kukus", "portion": "1 buah", "calories": 120, "carbs_g": 22.0, "protein_g": 3.5, "fat_g": 2.0, "gi_category": "sedang"},
    {"name": "Beng-Beng", "portion": "1 buah (22g)", "calories": 110, "carbs_g": 15.0, "protein_g": 1.5, "fat_g": 5.5, "gi_category": "tinggi"},
    {"name": "Wafer Coklat", "portion": "3 keping (30g)", "calories": 145, "carbs_g": 20.0, "protein_g": 2.0, "fat_g": 7.0, "gi_category": "tinggi"},
    {"name": "Dark Chocolate (70%)", "portion": "2 kotak (20g)", "calories": 110, "carbs_g": 9.0, "protein_g": 2.0, "fat_g": 7.5, "gi_category": "rendah"},
    {"name": "Agar-agar Tanpa Gula", "portion": "1 cup (150g)", "calories": 10, "carbs_g": 2.0, "protein_g": 0.2, "fat_g": 0.0, "gi_category": "rendah"},
    {"name": "Puding Susu", "portion": "1 cup (150g)", "calories": 130, "carbs_g": 20.0, "protein_g": 4.0, "fat_g": 4.0, "gi_category": "sedang"},
]


def _to_dict(e: DietEntry) -> dict:
    return {
        "id":          e.id,
        "patient_id":  e.patient_id,
        "entry_date":  e.entry_date,
        "meal_type":   e.meal_type,
        "food_name":   e.food_name,
        "portion":     e.portion,
        "calories":    e.calories,
        "carbs_g":     float(e.carbs_g)   if e.carbs_g   else None,
        "protein_g":   float(e.protein_g) if e.protein_g else None,
        "fat_g":       float(e.fat_g)     if e.fat_g     else None,
        "gi_category": e.gi_category,
        "notes":       e.notes,
        "created_at":  e.created_at,
    }


def _summary(entries: list, calorie_target: int = 1800) -> dict:
    total_cal   = sum(e.calories or 0 for e in entries)
    total_carbs = sum(float(e.carbs_g or 0) for e in entries)
    total_prot  = sum(float(e.protein_g or 0) for e in entries)
    total_fat   = sum(float(e.fat_g or 0) for e in entries)
    pct         = round(total_cal / calorie_target * 100, 1) if calorie_target > 0 else 0

    if pct <= 80:   status, status_color = "Kurang",  "blue"
    elif pct <= 110: status, status_color = "Normal",  "green"
    else:            status, status_color = "Berlebih","red"

    return {
        "total_calories":  total_cal,
        "calorie_target":  calorie_target,
        "calorie_pct":     pct,
        "status":          status,
        "status_color":    status_color,
        "total_carbs_g":   round(total_carbs, 1),
        "total_protein_g": round(total_prot,  1),
        "total_fat_g":     round(total_fat,   1),
        "entry_count":     len(entries),
    }


# ── GET /diet/foods/ — daftar makanan referensi ────────────
@router.get("/foods/")
def get_food_database():
    return FOOD_DATABASE


# ── POST /diet/entries/ — catat makanan ───────────────────
@router.post("/entries/", status_code=201)
def add_diet_entry(
    data: DietEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Hanya pasien yang bisa mencatat diet")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")

    if data.meal_type not in MEAL_ORDER:
        raise HTTPException(400, "meal_type harus: sarapan|makan_siang|makan_malam|snack")

    entry = DietEntry(
        patient_id  = patient.id,
        entry_date  = data.entry_date or date.today(),
        meal_type   = data.meal_type,
        food_name   = data.food_name.strip(),
        portion     = data.portion,
        calories    = data.calories,
        carbs_g     = data.carbs_g,
        protein_g   = data.protein_g,
        fat_g       = data.fat_g,
        gi_category = data.gi_category,
        notes       = data.notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _to_dict(entry)


# ── GET /diet/entries/today — makanan hari ini ─────────────
@router.get("/entries/today")
def get_today_entries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")

    entries = (
        db.query(DietEntry)
        .filter(DietEntry.patient_id == patient.id,
                DietEntry.entry_date == date.today())
        .order_by(DietEntry.created_at)
        .all()
    )
    return [_to_dict(e) for e in entries]


# ── GET /diet/entries/?date= — makanan per tanggal ─────────
@router.get("/entries/")
def get_entries_by_date(
    entry_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")

    target = entry_date or date.today()
    entries = (
        db.query(DietEntry)
        .filter(DietEntry.patient_id == patient.id,
                DietEntry.entry_date == target)
        .order_by(DietEntry.created_at)
        .all()
    )
    return [_to_dict(e) for e in entries]


# ── GET /diet/summary/today — ringkasan kalori hari ini ────
@router.get("/summary/today")
def get_today_summary(
    calorie_target: int = 1800,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")

    entries = (
        db.query(DietEntry)
        .filter(DietEntry.patient_id == patient.id,
                DietEntry.entry_date == date.today())
        .all()
    )
    return _summary(entries, calorie_target)


# ── GET /diet/history/ — riwayat kalori per hari ──────────
@router.get("/history/")
def get_diet_history(
    days: int = 7,
    calorie_target: int = 1800,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(404, "Pasien tidak ditemukan")

    start = date.today() - timedelta(days=days - 1)
    entries = (
        db.query(DietEntry)
        .filter(DietEntry.patient_id == patient.id,
                DietEntry.entry_date >= start)
        .order_by(DietEntry.entry_date)
        .all()
    )

    # Group per tanggal
    from collections import defaultdict
    daily: dict = defaultdict(list)
    for e in entries:
        daily[str(e.entry_date)].append(e)

    result = []
    for i in range(days):
        d = start + timedelta(days=i)
        key = str(d)
        day_entries = daily.get(key, [])
        s = _summary(day_entries, calorie_target)
        s["date"] = key
        result.append(s)

    return result


# ── DELETE /diet/entries/{id} — hapus entri ────────────────
@router.delete("/entries/{entry_id}")
def delete_diet_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "pasien":
        raise HTTPException(403, "Akses ditolak")
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    entry = db.query(DietEntry).filter(
        DietEntry.id == entry_id,
        DietEntry.patient_id == patient.id,
    ).first()
    if not entry:
        raise HTTPException(404, "Entri tidak ditemukan")
    db.delete(entry)
    db.commit()
    return {"message": "Entri dihapus"}