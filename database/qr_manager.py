# qr_manager.py
import json
from pathlib import Path
from datetime import datetime
import qrcode

from database_manager import get_user, get_health_metrics, upsert_emergency_profile

QR_DIR = Path("qr_profiles")
QR_DIR.mkdir(exist_ok=True)

def generate_emergency_qr(user_id: int) -> str:
    user = get_user(user_id)
    if not user:
        raise ValueError("User not found")
    payload = {
        "id": user["id"],
        "name": user["name"],
        "blood_type": user["blood_type"],
        "allergies": user["allergies"],
        "emergency_contact": user["emergency_contact"],
        "generated_at": datetime.utcnow().isoformat()
    }
    data = json.dumps(payload, ensure_ascii=False)
    img = qrcode.make(data)
    filename = QR_DIR / f"user_{user_id}_emergency.png"
    img.save(filename)
    upsert_emergency_profile(user_id, str(filename))
    print(f"Saved emergency QR to {filename}")
    return str(filename)


def generate_health_metric_qrs(user_id: int, limit: int = 10) -> list:
    rows = get_health_metrics(user_id, limit=limit)
    paths = []
    for r in rows:
        payload = {
            "metric_id": r["id"],
            "user_id": r["user_id"],
            "timestamp": r["timestamp"],
            "heart_rate": r["heart_rate"],
            "steps": r["steps"],
            "calories": r["calories"],
            "sleep_hours": r["sleep_hours"],
        }
        data = json.dumps(payload, default=str)
        img = qrcode.make(data)
        filename = QR_DIR / f"metric_{r['id']}.png"
        img.save(filename)
        paths.append(str(filename))
    print(f"Saved {len(paths)} metric QR(s) in {QR_DIR}.")
    return paths


if __name__ == "__main__":
    # quick test - only run after DB + user exist
    print("Run qr_manager.generate_emergency_qr(user_id) or run via run_demo.py")
