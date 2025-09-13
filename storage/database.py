import sqlite3
from pathlib import Path

def init_db():
    db_path = Path("data/database.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Patient Profile Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS patient_profiles (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        dob DATE NOT NULL,
        blood_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Documents Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY,
        filename TEXT NOT NULL,
        document_type TEXT,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ocr_text TEXT,
        patient_id INTEGER,
        FOREIGN KEY (patient_id) REFERENCES patient_profiles (id)
    )
    ''')
    
    # Medications Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS medications (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        dosage TEXT,
        frequency TEXT,
        patient_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patient_profiles (id)
    )
    ''')
    
    conn.commit()
    conn.close()