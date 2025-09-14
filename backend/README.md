# Health Insights Agent 🏥

A comprehensive healthcare management system that helps users manage their medical records, track vital metrics, and provide quick access to critical medical information through QR codes in emergency situations.

## Features 🌟

### 1. Patient Profile Management
- Create and manage patient profiles
- Store basic medical information
- Blood type tracking
- Emergency contact information

### 2. Document Management 📄
- Upload and store medical documents
- Separate sections for:
  - Lab Reports
  - Medication Prescriptions
- OCR processing using TrOCR
- Secure document storage

### 3. Emergency QR System 🆘
- Generate QR codes containing critical medical information
- Quick access to:
  - Patient details
  - Blood type
  - Allergies
  - Current medications
  - Emergency contacts
  - Recent vital signs

### 4. Vital Metrics Tracking 📊
- Record and monitor vital signs
- Support for multiple metrics:
  - Blood Pressure
  - Blood Glucose
  - Heart Rate
  - Temperature
  - Oxygen Saturation
- Track abnormal readings

### 5. AI Health Assistant 🤖
- Interactive chat interface
- Medical query assistance
- Health insights and recommendations

## Technology Stack 🛠️

- **Backend**: Python/Flask
- **Frontend**: HTML/CSS/JavaScript
- **Database**: SQLite
- **OCR**: TrOCR
- **QR Generation**: qrcode library
- **Data Processing**: Python data classes

## Project Structure 📁

```
health_insights_agent/
│
├── backend/                  # Backend server
│   ├── app.py                # Main application file
│   ├── models.py             # Database models
│   ├── routes.py             # API routes
│   ├── services/             # Business logic
│   ├── utils/                # Utility functions
│   └── requirements.txt      # Python dependencies
│
├── frontend/                 # Frontend application
│   ├── index.html            # Main HTML file
│   ├── styles.css            # CSS styles
│   ├── app.js                # JavaScript code
│   └── assets/               # Images, fonts, etc.
│
├── documents/                # Sample medical documents
│   ├── lab_reports/          # Lab report samples
│   └── prescriptions/        # Prescription samples
│
├── tests/                    # Test cases
│   ├── unit/                 # Unit tests
│   └── integration/          # Integration tests
│
├── .gitignore                # Git ignore file
├── README.md                 # Project documentation
└── requirements.txt          # Python dependencies
```

## Installation 🔧

1. Clone the repository:
```bash
git clone https://github.com/princydd17/Health-Insights-Agent.git
cd Health-Insights-Agent
```
