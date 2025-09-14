from flask import Flask, render_template, jsonify, request
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from werkzeug.utils import secure_filename
import time
from pathlib import Path
import sqlite3
from components.emergency_profile_system import EmergencyProfileManager, BloodType, SeverityLevel
from datetime import datetime
from storage.database import init_db
from backend.inference import Chatbot


app = Flask(__name__)

# Initialize Emergency Profile Manager
profile_manager = EmergencyProfileManager("./storage")

# Add configuration
app.config['UPLOAD_FOLDER'] = os.path.join("data","documents")
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/profileForm', methods=['POST'])
def save_profile():
    try:
        data = request.json
        # Save to main database
        conn = sqlite3.connect('data/database.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO patient_profiles (name, dob, blood_type)
            VALUES (?, ?, ?)
        ''', (data['name'], data['dob'], data['bloodType']))
        
        patient_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Save to emergency profile
        profile_manager.update_patient_info(
            name=data['name'],
            dob=datetime.strptime(data['dob'], '%Y-%m-%d'),
            blood_type=BloodType[data['bloodType'].replace('+', '_POSITIVE').replace('-', '_NEGATIVE')],
            gender=data.get('gender', 'Not Specified'),
            weight_kg=data.get('weight'),
            height_cm=data.get('height')
        )
        
        return jsonify({
            "status": "success",
            "message": "Profile saved successfully",
            "patient_id": patient_id
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/medicationForm', methods=['POST'])
def save_medication():
    data = request.json
    # TODO: Save medication data
    return jsonify({"status": "success"})

@app.route('/api/emergencyForm', methods=['POST'])
def save_emergency_contact():
    try:
        data = request.json
        profile_manager.set_emergency_contact(
            name=data['emergencyName'],
            relationship=data.get('relationship', 'Not Specified'),
            phone=data['emergencyPhone'],
            alternate_phone=data.get('alternatePhone')
        )
        return jsonify({"status": "success", "message": "Emergency contact saved"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/upload-document', methods=['POST'])
def upload_document():
    if 'document' not in request.files:
        return jsonify({"status": "error", "message": "No file provided"}), 400
    
    file = request.files['document']
    document_type = request.form.get('document_type')
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400
        
    if file and allowed_file(file.filename):
        try:
            # Create a subfolder based on document type

            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            
            # Ensure directory exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            # Save file
            file.save(file_path)
            print(file_path)
            # Make a call to backend to get data
            chatbot = Chatbot()
            print("Making the call")
            print(chatbot.get_text_content(file_path,document_type))

            
            # Add to database
            conn = sqlite3.connect('data/database.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO documents (filename, document_type, upload_date)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (filename, file.content_type))
            doc_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return jsonify({
                "status": "success",
                "message": "Document uploaded successfully",
                "document_id": doc_id
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/get-profile', methods=['GET'])
def get_profile():
    try:
        # Generate emergency profile with QR
        profile = profile_manager.generate_emergency_profile()
        qr_base64 = profile_manager.get_qr_as_base64(profile)
        
        # Get documents from main database
        conn = sqlite3.connect('data/database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documents ORDER BY upload_date DESC')
        documents = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "status": "success",
            "profile": profile.to_emergency_dict(),
            "qr_code": qr_base64,
            "documents": documents
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/vital-metrics', methods=['POST'])
def add_vital_metrics():
    try:
        data = request.json
        profile_manager.add_vital_metric(
            metric_type=data['type'],
            value=data['value'],
            unit=data['unit'],
            source=data.get('source', 'manual'),
            is_abnormal=data.get('is_abnormal', False)
        )
        return jsonify({"status": "success", "message": "Vital metrics added"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Initialize database
    init_db()
    os.makedirs('data/documents', exist_ok=True)
    os.makedirs('storage', exist_ok=True)
    print("🏥 Health Insights Agent starting...")
    print("📱 Access the app at: http://localhost:5000")
    app.run(debug=True, port=5000)