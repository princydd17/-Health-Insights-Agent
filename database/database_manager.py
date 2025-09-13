# database_manager.py
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from typing import Optional, List, Dict

load_dotenv()

FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    raise RuntimeError(
        "FERNET_KEY not found in environment. Generate one with:\n"
        "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
        "then set FERNET_KEY=<key> in a .env file."
    )
fernet = Fernet(FERNET_KEY.encode())

DB_FILE = os.environ.get("DB_FILE", "secure_health_data.db")


def get_conn():
    conn = sqlite3.connect(DB_FILE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables and indexes if they don't exist."""
    with get_conn() as conn:
        cur = conn.cursor()
        # Users table (sensitive PII encrypted)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name BLOB,
            age INTEGER,
            blood_type TEXT,
            allergies BLOB,
            emergency_contact BLOB
        );
        """)
        # wearable / time-series health metrics (numeric fields left unencrypted for queries/visualization)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS health_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            heart_rate INTEGER,
            steps INTEGER,
            calories INTEGER,
            sleep_hours REAL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        # emergency profile record linking to generated QR
        cur.execute("""
        CREATE TABLE IF NOT EXISTS emergency_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            qr_code_path TEXT,
            last_updated DATETIME,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        # prescriptions and lab_reports (OCR outputs)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT NOT NULL,
            dosage TEXT,
            frequency TEXT,
            image_path TEXT UNIQUE
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS lab_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date DATE,
            metric_name TEXT,
            value BLOB,
            unit TEXT,
            image_path TEXT
        );
        """)
        # Index to speed up time-series queries:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_health_user_time ON health_metrics(user_id, timestamp);")
        conn.commit()


# --- Encryption helpers ---
def _encrypt_text(s: Optional[str]) -> Optional[bytes]:
    if s is None:
        return None
    if isinstance(s, str):
        return fernet.encrypt(s.encode())
    raise TypeError("encrypt expects str or None")


def _decrypt_text(b: Optional[bytes]) -> Optional[str]:
    if b is None:
        return None
    try:
        return fernet.decrypt(b).decode()
    except Exception:
        return None


# --- User functions ---
def create_user(name: str, age: Optional[int] = None, blood_type: Optional[str] = None,
                allergies: Optional[str] = None, emergency_contact: Optional[str] = None) -> int:
    """Create a user and return user id."""
    name_enc = _encrypt_text(name)
    allergies_enc = _encrypt_text(allergies)
    contact_enc = _encrypt_text(emergency_contact)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (name, age, blood_type, allergies, emergency_contact) VALUES (?, ?, ?, ?, ?)",
            (name_enc, age, blood_type, allergies_enc, contact_enc)
        )
        conn.commit()
        return cur.lastrowid


def get_user(user_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "name": _decrypt_text(row["name"]),
            "age": row["age"],
            "blood_type": row["blood_type"],
            "allergies": _decrypt_text(row["allergies"]),
            "emergency_contact": _decrypt_text(row["emergency_contact"]),
        }


def get_all_users() -> List[Dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users")
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "name": _decrypt_text(r["name"]),
                "age": r["age"],
                "blood_type": r["blood_type"],
            })
        return out


# --- Health metric functions ---
def insert_health_metric(user_id: int, heart_rate: Optional[int] = None, steps: Optional[int] = None,
                         calories: Optional[int] = None, sleep_hours: Optional[float] = None,
                         timestamp: Optional[datetime] = None) -> int:
    ts = timestamp or datetime.utcnow()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO health_metrics (user_id, timestamp, heart_rate, steps, calories, sleep_hours)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, ts, heart_rate, steps, calories, sleep_hours))
        conn.commit()
        return cur.lastrowid


def get_health_metrics(user_id: int, limit: int = 200) -> List[Dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, user_id, timestamp, heart_rate, steps, calories, sleep_hours
            FROM health_metrics
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        rows = cur.fetchall()
        return [dict(r) for r in rows]


# --- Emergency profile upsert ---
def upsert_emergency_profile(user_id: int, qr_code_path: str):
    last_updated = datetime.utcnow()
    with get_conn() as conn:
        cur = conn.cursor()
        # Ensure user_id is unique; use SQLite UPSERT
        cur.execute("""
            INSERT INTO emergency_profiles (user_id, qr_code_path, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                qr_code_path = excluded.qr_code_path,
                last_updated = excluded.last_updated
        """, (user_id, qr_code_path, last_updated))
        conn.commit()


def get_emergency_profile(user_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM emergency_profiles WHERE user_id = ?", (user_id,))
        r = cur.fetchone()
        if not r:
            return None
        return dict(r)


# --- Prescriptions / Lab reports (basic helpers) ---
def insert_prescription(medicine_name: str, dosage: Optional[str] = None, frequency: Optional[str] = None,
                        image_path: Optional[str] = None) -> int:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO prescriptions (medicine_name, dosage, frequency, image_path)
            VALUES (?, ?, ?, ?)
        """, (medicine_name, dosage, frequency, image_path))
        conn.commit()
        return cur.lastrowid


def insert_lab_report(report_date: Optional[str], metric_name: str, value: str, unit: Optional[str] = None,
                      image_path: Optional[str] = None) -> int:
    # for lab reports we store value as raw text / blob (encrypted if desired)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO lab_reports (report_date, metric_name, value, unit, image_path)
            VALUES (?, ?, ?, ?, ?)
        """, (report_date, metric_name, value, unit, image_path))
        conn.commit()
        return cur.lastrowid


# --- Demo convenience ---
if __name__ == "__main__":
    print("Initializing DB...")
    init_db()
    print("DB initialized.")
    # Create a sample user if none exist
    users = get_all_users()
    if not users:
        print("Creating sample user...")
        uid = create_user("Alice Example", age=30, blood_type="O+", allergies="None", emergency_contact="Jane Doe +15550100")
        print("Sample user created with id", uid)
    else:
        print("Existing users found:", users)
