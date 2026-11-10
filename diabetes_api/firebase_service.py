import json
import os
import time
import re
import httpx
import asyncio

# Amankan direktori dasar proyek
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

_raw_credentials_path = os.getenv(
    "FIREBASE_CREDENTIALS",
    "sobatgula-firebase-adminsdk-fbsvc-e2f7cdc8f7.json"
)

# Validasi Path Traversal tingkat lanjut menggunakan os.path.commonpath
_resolved_base = os.path.abspath(BASE_DIR)
_target_path = os.path.abspath(os.path.join(_resolved_base, _raw_credentials_path))

try:
    if os.path.commonpath([_resolved_base, _target_path]) != _resolved_base:
        raise ValueError("Path Traversal terdeteksi")
except Exception:
    raise ValueError("Keamanan Terdeteksi: Path kredensial Firebase berada di luar direktori yang diizinkan.")

CREDENTIALS_FILE = _target_path

_cached: dict = {"token": None, "expires_at": 0, "project_id": None}


def _get_access_token() -> str:
    """Ambil OAuth2 access token, cache 50 menit."""
    now = time.time()
    if _cached["token"] and now < _cached["expires_at"]:
        return _cached["token"]

    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as GoogleRequest

    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(f"File kredensial Firebase tidak ditemukan di: {CREDENTIALS_FILE}")

    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/firebase.messaging"],
    )
    creds.refresh(GoogleRequest())
    _cached["token"] = creds.token
    _cached["expires_at"] = now + 3000
    print(f"[FCM] access token refreshed ✓")
    return creds.token


def _get_project_id() -> str:
    if _cached["project_id"]:
        return _cached["project_id"]
    
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(f"File kredensial Firebase tidak ditemukan di: {CREDENTIALS_FILE}")

    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        try:
            pid = json.load(f)["project_id"]
        except (KeyError, json.JSONDecodeError):
            raise ValueError("Format file kredensial Firebase tidak valid.")

    # ── PERBAIKAN SONARQUBE: Sanitasi & Validasi Konten File ──
    # Project ID Google Cloud hanya boleh berisi huruf kecil, angka, dan tanda hubung (max 30 char)
    if not isinstance(pid, str) or not re.match(r"^[a-z0-9\-]{6,30}$", pid):
        raise ValueError("Project ID Firebase tidak valid (mengandung karakter berbahaya).")

    _cached["project_id"] = pid
    return pid


async def send_push(
    fcm_token: str,
    title: str,
    body: str,
    data: dict = None,
) -> bool:
    """Kirim push notifikasi ke satu device. Return True jika berhasil."""
    if not fcm_token:
        print(f"[FCM] ✗ skip: fcm_token kosong")
        return False
    try:
        access_token = _get_access_token()
        project_id   = _get_project_id()
        
        # URL dibentuk dari project_id yang sudah divalidasi ketat
        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

        payload = {
            "message": {
                "token": fcm_token,
                "notification": {"title": title, "body": body},
                "android": {
                    "priority": "high",
                    "notification": {
                        "sound": "default",
                        "channel_id": "sobatgula_channel",
                        "notification_priority": "PRIORITY_HIGH",
                        "visibility": "PUBLIC",
                    },
                },
                "apns": {
                    "payload": {"aps": {"sound": "default", "badge": 1}}
                },
            }
        }
        if data:
            payload["message"]["data"] = {k: str(v) for k, v in data.items()}

        print(f"[FCM] sending → title={title!r} token={fcm_token[:20]}...")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code == 200:
            print(f"[FCM] ✓ push sent: {title!r}")
            return True
        else:
            print(f"[FCM] ✗ error {resp.status_code}: {resp.text[:300]}")
            if resp.status_code == 404:
                print(f"[FCM] token tidak valid, perlu login ulang di app")
            return False

    except Exception as e:
        print(f"[FCM] exception: {e}")
        return False


async def send_push_multi(
    tokens: list,
    title: str,
    body: str,
    data: dict = None,
) -> int:
    """Kirim ke banyak token sekaligus. Return jumlah yang berhasil."""
    if not tokens:
        print(f"[FCM] send_push_multi: tidak ada token, skip")
        return 0

    print(f"[FCM] send_push_multi: {len(tokens)} token, title={title!r}")

    # Filter token kosong/None sebelum dikirim
    valid_tokens = [t for t in tokens if t]
    
    results = await asyncio.gather(
        *[send_push(t, title, body, data) for t in valid_tokens],
        return_exceptions=True,
    )
    ok = sum(1 for r in results if r is True)
    print(f"[FCM] send_push_multi selesai: {ok}/{len(valid_tokens)} berhasil")
    return ok
