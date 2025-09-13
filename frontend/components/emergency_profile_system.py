"""
Emergency Profile & QR Code System
Generates critical medical information QR codes for emergency situations
"""

import json
import qrcode
import io
import base64
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any
from enum import Enum
from pathlib import Path
import sqlite3


class BloodType(Enum):
    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"
    UNKNOWN = "Unknown"


class SeverityLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


@dataclass
class EmergencyContact:
    name: str
    relationship: str
    phone: str
    alternate_phone: Optional[str] = None


@dataclass
class Allergy:
    substance: str
    reaction: str
    severity: SeverityLevel
    verified_date: Optional[datetime] = None


@dataclass
class Medication:
    name: str
    dosage: str
    frequency: str
    prescribing_doctor: str
    start_date: datetime
    is_critical: bool = False  # Life-threatening to stop
    notes: Optional[str] = None


@dataclass
class MedicalCondition:
    condition: str
    diagnosed_date: datetime
    severity: SeverityLevel
    current_status: str  # "active", "managed", "resolved"
    treating_doctor: Optional[str] = None


@dataclass
class Surgery:
    procedure: str
    date: datetime
    hospital: str
    complications: Optional[str] = None
    implants_devices: Optional[str] = None


@dataclass
class VitalMetric:
    metric_type: str  # "blood_pressure", "glucose", "heart_rate", etc.
    value: str
    unit: str
    recorded_date: datetime
    source: str  # "wearable", "lab_test", "home_monitor"
    is_abnormal: bool = False


@dataclass
class EmergencyProfile:
    """Complete emergency medical profile"""
    # Basic Information (required)
    patient_name: str
    date_of_birth: datetime
    blood_type: BloodType
    gender: str
    
    # Critical Information (required)
    allergies: List[Allergy]
    medications: List[Medication]
    medical_conditions: List[MedicalCondition]
    surgeries: List[Surgery]
    emergency_contact: EmergencyContact
    recent_vitals: List[VitalMetric]
    
    # Metadata (required)
    last_updated: datetime
    
    # Optional Information
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    primary_doctor: Optional[str] = None
    primary_doctor_phone: Optional[str] = None
    medical_devices: List[str] = field(default_factory=list)
    advance_directives: Optional[str] = None
    insurance_info: Optional[str] = None
    profile_version: str = "1.0"
    
    def to_emergency_dict(self) -> Dict[str, Any]:
        """Convert to dictionary optimized for emergency responders"""
        return {
            "patient": {
                "name": self.patient_name,
                "age": self._calculate_age(),
                "dob": self.date_of_birth.strftime("%Y-%m-%d"),
                "blood_type": self.blood_type.value,
                "gender": self.gender,
                "weight_kg": self.weight_kg,
                "height_cm": self.height_cm
            },
            "critical_allergies": [
                {
                    "substance": allergy.substance,
                    "reaction": allergy.reaction,
                    "severity": allergy.severity.value
                }
                for allergy in self.allergies 
                if allergy.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
            ],
            "current_medications": [
                {
                    "name": med.name,
                    "dosage": med.dosage,
                    "critical": med.is_critical
                }
                for med in self.medications
            ],
            "conditions": [
                {
                    "condition": cond.condition,
                    "status": cond.current_status,
                    "severity": cond.severity.value
                }
                for cond in self.medical_conditions
                if cond.current_status == "active"
            ],
            "devices": self.medical_devices,
            "emergency_contact": {
                "name": self.emergency_contact.name,
                "phone": self.emergency_contact.phone,
                "relationship": self.emergency_contact.relationship
            },
            "doctor": {
                "name": self.primary_doctor,
                "phone": self.primary_doctor_phone
            },
            "recent_vitals": [
                {
                    "type": vital.metric_type,
                    "value": vital.value,
                    "date": vital.recorded_date.strftime("%Y-%m-%d"),
                    "abnormal": vital.is_abnormal
                }
                for vital in self.recent_vitals[-10:]  # Last 10 readings
                if vital.is_abnormal or vital.recorded_date > datetime.now() - timedelta(days=3)
            ],
            "major_surgeries": [
                {
                    "procedure": surgery.procedure,
                    "date": surgery.date.strftime("%Y-%m-%d"),
                    "implants": surgery.implants_devices
                }
                for surgery in self.surgeries[-5:]  # Last 5 surgeries
            ],
            "directives": self.advance_directives,
            "updated": self.last_updated.strftime("%Y-%m-%d %H:%M")
        }
    
    def _calculate_age(self) -> int:
        """Calculate current age"""
        today = datetime.now().date()
        birth_date = self.date_of_birth.date()
        age = today.year - birth_date.year
        if today < birth_date.replace(year=today.year):
            age -= 1
        return age


class EmergencyProfileManager:
    """Manages emergency profile data and QR code generation"""
    
    def __init__(self, storage_directory: str):
        self.storage_path = Path(storage_directory)
        self.storage_path.mkdir(exist_ok=True)
        self.db_path = self.storage_path / "emergency_profile.db"
        self.qr_cache_path = self.storage_path / "emergency_qr.png"
        self._init_database()
    
    def _init_database(self):
        """Initialize emergency profile database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Patient basic info
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patient_info (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                blood_type TEXT NOT NULL,
                gender TEXT NOT NULL,
                weight_kg REAL,
                height_cm REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Allergies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS allergies (
                id INTEGER PRIMARY KEY,
                substance TEXT NOT NULL,
                reaction TEXT NOT NULL,
                severity TEXT NOT NULL,
                verified_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Medications
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medications (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                dosage TEXT NOT NULL,
                frequency TEXT NOT NULL,
                prescribing_doctor TEXT NOT NULL,
                start_date TEXT NOT NULL,
                is_critical BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Medical conditions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medical_conditions (
                id INTEGER PRIMARY KEY,
                condition TEXT NOT NULL,
                diagnosed_date TEXT NOT NULL,
                severity TEXT NOT NULL,
                current_status TEXT NOT NULL,
                treating_doctor TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Emergency contact
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emergency_contact (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                relationship TEXT NOT NULL,
                phone TEXT NOT NULL,
                alternate_phone TEXT,
                is_primary BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Recent vitals (from wearables and tests)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vitals (
                id INTEGER PRIMARY KEY,
                metric_type TEXT NOT NULL,
                value TEXT NOT NULL,
                unit TEXT NOT NULL,
                recorded_date TEXT NOT NULL,
                source TEXT NOT NULL,
                is_abnormal BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def update_patient_info(self, name: str, dob: datetime, blood_type: BloodType, 
                          gender: str, weight_kg: float = None, height_cm: float = None):
        """Update basic patient information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO patient_info 
            (id, name, date_of_birth, blood_type, gender, weight_kg, height_cm)
            VALUES (1, ?, ?, ?, ?, ?, ?)
        ''', (name, dob.isoformat(), blood_type.value, gender, weight_kg, height_cm))
        
        conn.commit()
        conn.close()
        self._invalidate_qr_cache()
    
    def add_allergy(self, substance: str, reaction: str, severity: SeverityLevel):
        """Add or update allergy information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO allergies 
            (substance, reaction, severity, verified_date)
            VALUES (?, ?, ?, ?)
        ''', (substance, reaction, severity.value, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        self._invalidate_qr_cache()
    
    def add_medication(self, name: str, dosage: str, frequency: str, 
                      doctor: str, start_date: datetime, is_critical: bool = False):
        """Add current medication"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO medications 
            (name, dosage, frequency, prescribing_doctor, start_date, is_critical)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, dosage, frequency, doctor, start_date.isoformat(), is_critical))
        
        conn.commit()
        conn.close()
        self._invalidate_qr_cache()
    
    def add_vital_metric(self, metric_type: str, value: str, unit: str, 
                        source: str, is_abnormal: bool = False):
        """Add vital sign measurement"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO vitals 
            (metric_type, value, unit, recorded_date, source, is_abnormal)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (metric_type, value, unit, datetime.now().isoformat(), source, is_abnormal))
        
        conn.commit()
        conn.close()
        self._invalidate_qr_cache()
    
    def set_emergency_contact(self, name: str, relationship: str, phone: str, 
                            alternate_phone: str = None):
        """Set primary emergency contact"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO emergency_contact 
            (id, name, relationship, phone, alternate_phone, is_primary)
            VALUES (1, ?, ?, ?, ?, TRUE)
        ''', (name, relationship, phone, alternate_phone))
        
        conn.commit()
        conn.close()
        self._invalidate_qr_cache()
    
    def generate_emergency_profile(self) -> EmergencyProfile:
        """Generate complete emergency profile from stored data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get patient info
        cursor.execute('SELECT * FROM patient_info WHERE id = 1')
        patient_row = cursor.fetchone()
        if not patient_row:
            raise ValueError("Patient information not set. Please update patient info first.")
        
        # Get allergies
        cursor.execute('SELECT * FROM allergies')
        allergy_rows = cursor.fetchall()
        allergies = [
            Allergy(
                substance=row[1],
                reaction=row[2],
                severity=SeverityLevel(row[3]),
                verified_date=datetime.fromisoformat(row[4]) if row[4] else None
            )
            for row in allergy_rows
        ]
        
        # Get active medications
        cursor.execute('SELECT * FROM medications WHERE is_active = TRUE')
        med_rows = cursor.fetchall()
        medications = [
            Medication(
                name=row[1],
                dosage=row[2],
                frequency=row[3],
                prescribing_doctor=row[4],
                start_date=datetime.fromisoformat(row[5]),
                is_critical=bool(row[6]),
                notes=row[8]
            )
            for row in med_rows
        ]
        
        # Get emergency contact
        cursor.execute('SELECT * FROM emergency_contact WHERE is_primary = TRUE')
        contact_row = cursor.fetchone()
        emergency_contact = EmergencyContact(
            name=contact_row[1] if contact_row else "Not Set",
            relationship=contact_row[2] if contact_row else "Unknown",
            phone=contact_row[3] if contact_row else "Not Set",
            alternate_phone=contact_row[4] if contact_row else None
        )
        
        # Get recent vitals (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        cursor.execute('SELECT * FROM vitals WHERE recorded_date > ? ORDER BY recorded_date DESC', (week_ago,))
        vital_rows = cursor.fetchall()
        recent_vitals = [
            VitalMetric(
                metric_type=row[1],
                value=row[2],
                unit=row[3],
                recorded_date=datetime.fromisoformat(row[4]),
                source=row[5],
                is_abnormal=bool(row[6])
            )
            for row in vital_rows
        ]
        
        conn.close()
        
        # Create emergency profile
        profile = EmergencyProfile(
            patient_name=patient_row[1],
            date_of_birth=datetime.fromisoformat(patient_row[2]),
            blood_type=BloodType(patient_row[3]),
            gender=patient_row[4],
            allergies=allergies,
            medications=medications,
            medical_conditions=[],  # TODO: Implement if needed
            surgeries=[],  # TODO: Implement if needed
            emergency_contact=emergency_contact,
            recent_vitals=recent_vitals,
            last_updated=datetime.now()
        )
        
        return profile
    
    def generate_emergency_qr(self, profile: EmergencyProfile = None) -> str:
        """Generate QR code with emergency information"""
        if profile is None:
            profile = self.generate_emergency_profile()
        
        # Check if cached QR is still valid (less than 1 hour old)
        if (self.qr_cache_path.exists() and 
            datetime.fromtimestamp(self.qr_cache_path.stat().st_mtime) > 
            datetime.now() - timedelta(hours=1)):
            return str(self.qr_cache_path)
        
        # Create emergency data dict
        emergency_data = profile.to_emergency_dict()
        
        # Convert to JSON
        json_data = json.dumps(emergency_data, separators=(',', ':'))  # Compact format
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Add header for medical QR codes
        qr_content = f"MEDICAL_EMERGENCY:{json_data}"
        qr.add_data(qr_content)
        qr.make(fit=True)
        
        # Create QR image
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code
        qr_image.save(self.qr_cache_path)
        
        return str(self.qr_cache_path)
    
    def get_qr_as_base64(self, profile: EmergencyProfile = None) -> str:
        """Get QR code as base64 string for display in app"""
        qr_path = self.generate_emergency_qr(profile)
        
        with open(qr_path, 'rb') as f:
            qr_bytes = f.read()
        
        return base64.b64encode(qr_bytes).decode('utf-8')
    
    def _invalidate_qr_cache(self):
        """Remove cached QR code when data changes"""
        if self.qr_cache_path.exists():
            self.qr_cache_path.unlink()
    
    def export_emergency_profile_text(self, profile: EmergencyProfile = None) -> str:
        """Export emergency profile as readable text (backup method)"""
        if profile is None:
            profile = self.generate_emergency_profile()
        
        text_lines = [
            "=== EMERGENCY MEDICAL INFORMATION ===",
            f"Patient: {profile.patient_name}",
            f"DOB: {profile.date_of_birth.strftime('%Y-%m-%d')} (Age: {profile._calculate_age()})",
            f"Blood Type: {profile.blood_type.value}",
            f"Gender: {profile.gender}",
            "",
            "CRITICAL ALLERGIES:",
        ]
        
        critical_allergies = [a for a in profile.allergies if a.severity == SeverityLevel.CRITICAL]
        if critical_allergies:
            for allergy in critical_allergies:
                text_lines.append(f"  - {allergy.substance}: {allergy.reaction}")
        else:
            text_lines.append("  None reported")
        
        text_lines.extend([
            "",
            "CURRENT MEDICATIONS:",
        ])
        
        if profile.medications:
            for med in profile.medications:
                critical_flag = " [CRITICAL]" if med.is_critical else ""
                text_lines.append(f"  - {med.name} {med.dosage} {med.frequency}{critical_flag}")
        else:
            text_lines.append("  None reported")
        
        text_lines.extend([
            "",
            f"Emergency Contact: {profile.emergency_contact.name} ({profile.emergency_contact.relationship})",
            f"Phone: {profile.emergency_contact.phone}",
            f"Updated: {profile.last_updated.strftime('%Y-%m-%d %H:%M')}"
        ])
        
        return "\n".join(text_lines)


# Integration with existing camera component
def integrate_emergency_system_with_camera():
    """Example of how to integrate emergency system with existing camera component"""
    
    # In your main app, you would do:
    from components.camera_component import DocumentCamera, DocumentType, CameraConfig
    
    def setup_emergency_integration():
        # Initialize both systems
        camera_config = CameraConfig(save_directory="./health_documents")
        camera = DocumentCamera(camera_config)
        emergency_manager = EmergencyProfileManager("./health_documents")
        
        # Extract medical info from captured documents
        def process_prescription_for_emergency(document):
            """Extract medication info from prescription OCR"""
            if document.ocr_text and document.document_type == DocumentType.PRESCRIPTION:
                # This would use AI to extract structured data from OCR text
                # For now, manual entry or simple parsing
                pass
        
        # Set up emergency profile
        def setup_patient_profile():
            emergency_manager.update_patient_info(
                name="John Doe",
                dob=datetime(1980, 5, 15),
                blood_type=BloodType.A_POSITIVE,
                gender="Male",
                weight_kg=75.0,
                height_cm=180.0
            )
            
            emergency_manager.add_allergy("Penicillin", "Severe rash, difficulty breathing", SeverityLevel.CRITICAL)
            emergency_manager.add_medication("Metformin", "500mg", "Twice daily", "Dr. Smith", datetime(2024, 1, 1), True)
            emergency_manager.set_emergency_contact("Jane Doe", "Spouse", "+1-555-123-4567")
        
        return camera, emergency_manager
    
    return setup_emergency_integration


# Example usage for testing
async def test_emergency_system():
    """Test emergency profile system"""
    print("Testing Emergency Profile System...")
    
    manager = EmergencyProfileManager("./test_emergency")
    
    # Set up test patient
    manager.update_patient_info(
        name="Test Patient",
        dob=datetime(1985, 3, 20),
        blood_type=BloodType.O_NEGATIVE,
        gender="Female",
        weight_kg=65.0,
        height_cm=165.0
    )
    
    # Add critical medical info
    manager.add_allergy("Shellfish", "Anaphylaxis", SeverityLevel.CRITICAL)
    manager.add_allergy("Latex", "Contact dermatitis", SeverityLevel.MODERATE)
    
    manager.add_medication("Insulin", "10 units", "Before meals", "Dr. Johnson", datetime(2024, 1, 1), True)
    manager.add_medication("Lisinopril", "10mg", "Once daily", "Dr. Johnson", datetime(2024, 2, 1))
    
    manager.set_emergency_contact("John Smith", "Husband", "+1-555-987-6543", "+1-555-111-2222")
    
    # Add some vital signs
    manager.add_vital_metric("glucose", "180", "mg/dL", "home_monitor", True)
    manager.add_vital_metric("blood_pressure", "140/90", "mmHg", "home_monitor", True)
    
    # Generate emergency profile
    profile = manager.generate_emergency_profile()
    print(f"Generated profile for: {profile.patient_name}")
    
    # Generate QR code
    qr_path = manager.generate_emergency_qr(profile)
    print(f"Emergency QR code saved to: {qr_path}")
    
    # Export text version
    text_profile = manager.export_emergency_profile_text(profile)
    print("\nEmergency Profile Text:")
    print(text_profile)
    
    print("\nEmergency system test complete!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_emergency_system())