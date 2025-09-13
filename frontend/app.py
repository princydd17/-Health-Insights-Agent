# Health Insights Agent - Complete Flask Application
from flask import Flask, render_template_string, jsonify, request, send_file
import sys
import os
import asyncio
import json
import base64
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path for inference
sys.path.append('../backend')
from inference import run_inference

# Import your camera and emergency components
sys.path.append('./components')
from components.camera_component import DocumentCamera, DocumentType, CameraConfig
from components.emergency_profile_system import EmergencyProfileManager, BloodType, SeverityLevel
from components.health_manager import HealthInsightsManager

app = Flask(__name__)

# Initialize health system
health_manager = HealthInsightsManager("./health_data")

# Global variable to track setup status
is_patient_setup = False

# HTML Template for the complete web app
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Health Insights Agent</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #eee;
        }
        .header h1 {
            color: #667eea;
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        .header p {
            color: #666;
            margin: 10px 0 0 0;
            font-size: 1.1em;
        }
        .tabs {
            display: flex;
            margin-bottom: 30px;
            border-bottom: 1px solid #ddd;
        }
        .tab {
            flex: 1;
            padding: 15px;
            text-align: center;
            cursor: pointer;
            background: none;
            border: none;
            font-size: 16px;
            transition: all 0.3s;
        }
        .tab.active {
            background: #667eea;
            color: white;
            border-radius: 10px 10px 0 0;
        }
        .tab-content {
            display: none;
            padding: 20px 0;
        }
        .tab-content.active {
            display: block;
        }
        .btn {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px;
            transition: transform 0.2s;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        .btn.secondary {
            background: #6c757d;
        }
        .btn.danger {
            background: #dc3545;
        }
        .btn.success {
            background: #28a745;
        }
        .form-group {
            margin: 15px 0;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #555;
        }
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        .document-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .document-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 15px;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .document-card h3 {
            margin: 0 0 10px 0;
            color: #333;
        }
        .document-card p {
            margin: 5px 0;
            color: #666;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-processed {
            background: #28a745;
        }
        .status-unprocessed {
            background: #ffc107;
        }
        .emergency-qr {
            text-align: center;
            padding: 30px;
            background: #f8f9fa;
            border-radius: 15px;
            margin: 20px 0;
        }
        .emergency-qr img {
            max-width: 300px;
            border: 3px solid #dc3545;
            border-radius: 10px;
        }
        .emergency-info {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        .timeline {
            margin: 20px 0;
        }
        .timeline-item {
            display: flex;
            margin: 15px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            align-items: center;
        }
        .timeline-date {
            min-width: 120px;
            font-weight: 600;
            color: #667eea;
        }
        .timeline-content {
            flex: 1;
            margin-left: 20px;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 2s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .alert {
            padding: 15px;
            margin: 15px 0;
            border-radius: 8px;
            font-weight: 500;
        }
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .alert-danger {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .alert-warning {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏥 Health Insights Agent</h1>
            <p>Your privacy-first, on-device health companion</p>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('setup')">Patient Setup</button>
            <button class="tab" onclick="showTab('documents')">Medical Documents</button>
            <button class="tab" onclick="showTab('timeline')">Health Timeline</button>
            <button class="tab" onclick="showTab('emergency')">Emergency Profile</button>
            <button class="tab" onclick="showTab('ai')">AI Inference</button>
        </div>
        
        <!-- Patient Setup Tab -->
        <div id="setup" class="tab-content active">
            <h2>Patient Profile Setup</h2>
            <div id="setup-form">
                <div class="form-group">
                    <label for="patient-name">Full Name:</label>
                    <input type="text" id="patient-name" placeholder="Enter patient name">
                </div>
                <div class="form-group">
                    <label for="patient-dob">Date of Birth:</label>
                    <input type="date" id="patient-dob">
                </div>
                <div class="form-group">
                    <label for="blood-type">Blood Type:</label>
                    <select id="blood-type">
                        <option value="A_POSITIVE">A+</option>
                        <option value="A_NEGATIVE">A-</option>
                        <option value="B_POSITIVE">B+</option>
                        <option value="B_NEGATIVE">B-</option>
                        <option value="AB_POSITIVE">AB+</option>
                        <option value="AB_NEGATIVE">AB-</option>
                        <option value="O_POSITIVE">O+</option>
                        <option value="O_NEGATIVE">O-</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="gender">Gender:</label>
                    <select id="gender">
                        <option value="Male">Male</option>
                        <option value="Female">Female</option>
                        <option value="Other">Other</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="emergency-name">Emergency Contact Name:</label>
                    <input type="text" id="emergency-name" placeholder="Enter emergency contact name">
                </div>
                <div class="form-group">
                    <label for="emergency-phone">Emergency Contact Phone:</label>
                    <input type="tel" id="emergency-phone" placeholder="+1-555-123-4567">
                </div>
                <button class="btn" onclick="setupPatient()">Save Patient Profile</button>
            </div>
            
            <!-- Allergies Section -->
            <h3>Allergies</h3>
            <div class="form-group">
                <label for="allergy-substance">Allergy Substance:</label>
                <input type="text" id="allergy-substance" placeholder="e.g., Penicillin, Shellfish">
            </div>
            <div class="form-group">
                <label for="allergy-reaction">Reaction:</label>
                <input type="text" id="allergy-reaction" placeholder="e.g., Rash, Difficulty breathing">
            </div>
            <div class="form-group">
                <label for="allergy-severity">Severity:</label>
                <select id="allergy-severity">
                    <option value="LOW">Low</option>
                    <option value="MODERATE">Moderate</option>
                    <option value="HIGH">High</option>
                    <option value="CRITICAL">Critical</option>
                </select>
            </div>
            <button class="btn secondary" onclick="addAllergy()">Add Allergy</button>
            
            <!-- Medications Section -->
            <h3>Current Medications</h3>
            <div class="form-group">
                <label for="med-name">Medication Name:</label>
                <input type="text" id="med-name" placeholder="e.g., Metformin">
            </div>
            <div class="form-group">
                <label for="med-dosage">Dosage:</label>
                <input type="text" id="med-dosage" placeholder="e.g., 500mg">
            </div>
            <div class="form-group">
                <label for="med-frequency">Frequency:</label>
                <input type="text" id="med-frequency" placeholder="e.g., Twice daily">
            </div>
            <div class="form-group">
                <label for="med-doctor">Prescribing Doctor:</label>
                <input type="text" id="med-doctor" placeholder="e.g., Dr. Smith">
            </div>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="med-critical"> This is a critical medication
                </label>
            </div>
            <button class="btn secondary" onclick="addMedication()">Add Medication</button>
        </div>
        
        <!-- Documents Tab -->
        <div id="documents" class="tab-content">
            <h2>Medical Documents</h2>
            <div style="text-align: center; margin: 20px 0;">
                <button class="btn" onclick="captureDocument('prescription')">📋 Capture Prescription</button>
                <button class="btn" onclick="captureDocument('lab_report')">🧪 Capture Lab Report</button>
                <button class="btn secondary" onclick="importDocument()">📁 Import Document</button>
            </div>
            
            <div id="documents-list" class="document-grid">
                <!-- Documents will be loaded here -->
            </div>
        </div>
        
        <!-- Timeline Tab -->
        <div id="timeline" class="tab-content">
            <h2>Health Timeline</h2>
            <button class="btn" onclick="loadTimeline()">🔄 Refresh Timeline</button>
            <div id="timeline-content" class="timeline">
                <!-- Timeline will be loaded here -->
            </div>
        </div>
        
        <!-- Emergency Tab -->
        <div id="emergency" class="tab-content">
            <h2>Emergency Profile</h2>
            <div class="emergency-info">
                <h3>⚠️ Emergency Information</h3>
                <p>This QR code contains critical medical information for first responders. Keep this easily accessible on your phone.</p>
            </div>
            
            <div style="text-align: center;">
                <button class="btn danger" onclick="generateEmergencyQR()">🚨 Generate Emergency QR Code</button>
                <button class="btn secondary" onclick="getEmergencyText()">📄 Get Text Backup</button>
            </div>
            
            <div id="emergency-qr-container" class="emergency-qr" style="display: none;">
                <h3>Emergency Medical QR Code</h3>
                <img id="emergency-qr-image" src="" alt="Emergency QR Code">
                <p><strong>Show this QR code to first responders in case of emergency</strong></p>
            </div>
            
            <div id="emergency-text" style="display: none;">
                <h3>Emergency Profile (Text Backup)</h3>
                <textarea id="emergency-text-content" rows="15" readonly style="width: 100%;"></textarea>
            </div>
        </div>
        
        <!-- AI Tab -->
        <div id="ai" class="tab-content">
            <h2>AI Inference</h2>
            <p>Test the AI inference engine for document processing.</p>
            <button class="btn" onclick="runInference()">🤖 Run AI Inference</button>
            <div id="ai-result" style="margin-top: 20px; font-size: 18px;"></div>
        </div>
        
        <!-- Loading Spinner -->
        <div id="loading" class="loading">
            <div class="spinner"></div>
            <p>Processing...</p>
        </div>
        
        <!-- Messages -->
        <div id="messages"></div>
    </div>
    
    <script>
        let currentTab = 'setup';
        
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            currentTab = tabName;
            
            // Load data for specific tabs
            if (tabName === 'documents') {
                loadDocuments();
            } else if (tabName === 'timeline') {
                loadTimeline();
            }
        }
        
        function showMessage(message, type = 'success') {
            const messagesDiv = document.getElementById('messages');
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${type}`;
            alertDiv.textContent = message;
            messagesDiv.appendChild(alertDiv);
            
            // Remove after 5 seconds
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
        }
        
        function showLoading(show = true) {
            document.getElementById('loading').style.display = show ? 'block' : 'none';
        }
        
        async function setupPatient() {
            const patientData = {
                name: document.getElementById('patient-name').value,
                dob: document.getElementById('patient-dob').value,
                blood_type: document.getElementById('blood-type').value,
                gender: document.getElementById('gender').value,
                emergency_name: document.getElementById('emergency-name').value,
                emergency_phone: document.getElementById('emergency-phone').value
            };
            
            if (!patientData.name || !patientData.dob) {
                showMessage('Please fill in all required fields', 'danger');
                return;
            }
            
            showLoading(true);
            try {
                const response = await fetch('/setup_patient', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(patientData)
                });
                
                const result = await response.json();
                if (result.success) {
                    showMessage('Patient profile saved successfully!');
                } else {
                    showMessage(result.error || 'Failed to save patient profile', 'danger');
                }
            } catch (error) {
                showMessage('Error: ' + error.message, 'danger');
            } finally {
                showLoading(false);
            }
        }
        
        async function addAllergy() {
            const allergyData = {
                substance: document.getElementById('allergy-substance').value,
                reaction: document.getElementById('allergy-reaction').value,
                severity: document.getElementById('allergy-severity').value
            };
            
            if (!allergyData.substance || !allergyData.reaction) {
                showMessage('Please fill in allergy substance and reaction', 'warning');
                return;
            }
            
            showLoading(true);
            try {
                const response = await fetch('/add_allergy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(allergyData)
                });
                
                const result = await response.json();
                if (result.success) {
                    showMessage(`Added allergy: ${allergyData.substance}`);
                    // Clear form
                    document.getElementById('allergy-substance').value = '';
                    document.getElementById('allergy-reaction').value = '';
                } else {
                    showMessage(result.error || 'Failed to add allergy', 'danger');
                }
            } catch (error) {
                showMessage('Error: ' + error.message, 'danger');
            } finally {
                showLoading(false);
            }
        }
        
        async function addMedication() {
            const medData = {
                name: document.getElementById('med-name').value,
                dosage: document.getElementById('med-dosage').value,
                frequency: document.getElementById('med-frequency').value,
                doctor: document.getElementById('med-doctor').value,
                is_critical: document.getElementById('med-critical').checked
            };
            
            if (!medData.name || !medData.dosage) {
                showMessage('Please fill in medication name and dosage', 'warning');
                return;
            }
            
            showLoading(true);
            try {
                const response = await fetch('/add_medication', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(medData)
                });
                
                const result = await response.json();
                if (result.success) {
                    showMessage(`Added medication: ${medData.name}`);
                    // Clear form
                    document.getElementById('med-name').value = '';
                    document.getElementById('med-dosage').value = '';
                    document.getElementById('med-frequency').value = '';
                    document.getElementById('med-doctor').value = '';
                    document.getElementById('med-critical').checked = false;
                } else {
                    showMessage(result.error || 'Failed to add medication', 'danger');
                }
            } catch (error) {
                showMessage('Error: ' + error.message, 'danger');
            } finally {
                showLoading(false);
            }
        }
        
        async function captureDocument(docType) {
            showLoading(true);
            try {
                const response = await fetch('/capture_document', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ document_type: docType })
                });
                
                const result = await response.json();
                if (result.success) {
                    showMessage(`Successfully captured ${docType}`);
                    loadDocuments(); // Refresh documents list
                } else {
                    showMessage(result.error || 'Failed to capture document', 'danger');
                }
            } catch (error) {
                showMessage('Error: ' + error.message, 'danger');
            } finally {
                showLoading(false);
            }
        }
        
        async function loadDocuments() {
            try {
                const response = await fetch('/get_documents');
                const result = await response.json();
                
                const container = document.getElementById('documents-list');
                if (result.documents && result.documents.length > 0) {
                    container.innerHTML = result.documents.map(doc => `
                        <div class="document-card">
                            <h3>
                                <span class="status-indicator ${doc.is_processed ? 'status-processed' : 'status-unprocessed'}"></span>
                                ${doc.document_type.replace('_', ' ').toUpperCase()}
                            </h3>
                            <p><strong>Captured:</strong> ${new Date(doc.capture_date).toLocaleDateString()}</p>
                            <p><strong>Size:</strong> ${(doc.file_size / 1024).toFixed(1)} KB</p>
                            <p><strong>Status:</strong> ${doc.is_processed ? 'Processed' : 'Pending AI Processing'}</p>
                            ${doc.ocr_text ? `<p><strong>Extracted Text:</strong> ${doc.ocr_text.substring(0, 100)}...</p>` : ''}
                        </div>
                    `).join('');
                } else {
                    container.innerHTML = '<p style="text-align: center; color: #666;">No documents captured yet. Use the buttons above to capture your first medical document.</p>';
                }
            } catch (error) {
                showMessage('Error loading documents: ' + error.message, 'danger');
            }
        }
        
        async function loadTimeline() {
            try {
                const response = await fetch('/get_timeline');
                const result = await response.json();
                
                const container = document.getElementById('timeline-content');
                if (result.timeline && result.timeline.length > 0) {
                    container.innerHTML = result.timeline.map(item => `
                        <div class="timeline-item">
                            <div class="timeline-date">${new Date(item.date).toLocaleDateString()}</div>
                            <div class="timeline-content">
                                <strong>${item.category.replace('_', ' ').toUpperCase()}</strong><br>
                                ${item.description}
                            </div>
                        </div>
                    `).join('');
                } else {
                    container.innerHTML = '<p style="text-align: center; color: #666;">No health events recorded yet.</p>';
                }
            } catch (error) {
                showMessage('Error loading timeline: ' + error.message, 'danger');
            }
        }
        
        async function generateEmergencyQR() {
            showLoading(true);
            try {
                const response = await fetch('/generate_emergency_qr');
                const result = await response.json();
                
                if (result.success) {
                    const container = document.getElementById('emergency-qr-container');
                    const img = document.getElementById('emergency-qr-image');
                    
                    img.src = 'data:image/png;base64,' + result.qr_base64;
                    container.style.display = 'block';
                    
                    showMessage('Emergency QR code generated successfully!');
                } else {
                    showMessage(result.error || 'Failed to generate QR code', 'danger');
                }
            } catch (error) {
                showMessage('Error: ' + error.message, 'danger');
            } finally {
                showLoading(false);
            }
        }
        
        async function getEmergencyText() {
            showLoading(true);
            try {
                const response = await fetch('/get_emergency_text');
                const result = await response.json();
                
                if (result.success) {
                    const container = document.getElementById('emergency-text');
                    const textarea = document.getElementById('emergency-text-content');
                    
                    textarea.value = result.text;
                    container.style.display = 'block';
                    
                    showMessage('Emergency text profile generated!');
                } else {
                    showMessage(result.error || 'Failed to generate text profile', 'danger');
                }
            } catch (error) {
                showMessage('Error: ' + error.message, 'danger');
            } finally {
                showLoading(false);
            }
        }
        
        async function runInference() {
            showLoading(true);
            try {
                const response = await fetch('/run');
                const result = await response.json();
                document.getElementById('ai-result').innerHTML = result.result;
                showMessage('AI inference completed!');
            } catch (error) {
                showMessage('Error running inference: ' + error.message, 'danger');
            } finally {
                showLoading(false);
            }
        }
        
        // Load documents when page loads
        document.addEventListener('DOMContentLoaded', function() {
            loadDocuments();
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/setup_patient', methods=['POST'])
def setup_patient():
    try:
        data = request.json
        
        # Convert date string to datetime
        dob = datetime.strptime(data['dob'], '%Y-%m-%d')
        
        # Setup patient profile
        health_manager.setup_patient_profile(
            name=data['name'],
            dob=dob,
            blood_type=BloodType(data['blood_type']),
            gender=data['gender']
        )
        
        # Set emergency contact
        if data.get('emergency_name') and data.get('emergency_phone'):
            health_manager.set_emergency_contact(
                name=data['emergency_name'],
                relationship="Emergency Contact",
                phone=data['emergency_phone']
            )
        
        global is_patient_setup
        is_patient_setup = True
        
        return jsonify({"success": True, "message": "Patient profile setup completed"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/add_allergy', methods=['POST'])
def add_allergy():
    try:
        data = request.json
        
        health_manager.add_allergy_info(
            substance=data['substance'],
            reaction=data['reaction'],
            severity=SeverityLevel(data['severity'])
        )
        
        return jsonify({"success": True, "message": "Allergy added successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/add_medication', methods=['POST'])
def add_medication():
    try:
        data = request.json
        
        health_manager.add_medication_info(
            name=data['name'],
            dosage=data['dosage'],
            frequency=data['frequency'],
            doctor=data['doctor'],
            start_date=datetime.now(),
            is_critical=data.get('is_critical', False)
        )
        
        return jsonify({"success": True, "message": "Medication added successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/capture_document', methods=['POST'])
def capture_document():
    try:
        data = request.json
        doc_type = DocumentType(data['document_type'].upper())
        
        # For demo purposes, we'll simulate document capture
        # In real implementation, this would use the camera
        # For now, create a mock document
        
        # Since we can't actually access camera in web browser easily,
        # we'll create a placeholder that shows the system works
        
        # You could enhance this to:
        # 1. Accept file uploads
        # 2. Use WebRTC to access camera
        # 3. Accept drag & drop files
        
        return jsonify({
            "success": True, 
            "message": f"Document capture simulated for {doc_type.value}",
            "note": "In production, this would capture from camera or file upload"
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/get_documents')
def get_documents():
    try:
        documents = health_manager.get_all_documents()
        
        # Convert documents to JSON-serializable format
        doc_list = []
        for doc in documents:
            doc_list.append({
                "id": doc.id,
                "document_type": doc.document_type.value,
                "capture_date": doc.capture_date.isoformat(),
                "file_size": doc.file_size,
                "is_processed": doc.is_processed,
                "ocr_text": doc.ocr_text
            })
        
        return jsonify({"documents": doc_list})
    
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/get_timeline')
def get_timeline():
    try:
        timeline = health_manager.get_health_timeline()
        
        # Convert timeline to JSON-serializable format
        timeline_list = []
        for item in timeline:
            timeline_list.append({
                "date": item["date"].isoformat(),
                "type": item["type"],
                "category": item["category"],
                "description": item["description"]
            })
        
        return jsonify({"timeline": timeline_list})
    
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/generate_emergency_qr')
def generate_emergency_qr():
    try:
        if not is_patient_setup:
            return jsonify({"success": False, "error": "Please setup patient profile first"})
        
        # Generate QR code as base64
        qr_base64 = health_manager.get_emergency_qr_base64()
        
        return jsonify({
            "success": True,
            "qr_base64": qr_base64,
            "message": "Emergency QR code generated successfully"
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/get_emergency_text')
def get_emergency_text():
    try:
        if not is_patient_setup:
            return jsonify({"success": False, "error": "Please setup patient profile first"})
        
        # Get emergency profile as text
        emergency_text = health_manager.get_emergency_profile_text()
        
        return jsonify({
            "success": True,
            "text": emergency_text,
            "message": "Emergency text profile generated"
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/run')
def run():
    """Original inference endpoint"""
    try:
        value = run_inference()
        return jsonify(result=f'Inference result: {value}')
    except Exception as e:
        return jsonify(result=f'Inference error: {str(e)}')

# Additional endpoints for wearable data (for future integration)
@app.route('/add_wearable_data', methods=['POST'])
def add_wearable_data():
    try:
        data = request.json
        
        health_manager.add_wearable_data(
            metric_type=data['metric_type'],
            value=data['value'],
            unit=data['unit'],
            source=data.get('source', 'wearable'),
            is_abnormal=data.get('is_abnormal', False)
        )
        
        return jsonify({"success": True, "message": "Wearable data added successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    # Ensure health data directory exists
    os.makedirs('./health_data', exist_ok=True)
    
    print("🏥 Health Insights Agent starting...")
    print("📱 Access the app at: http://localhost:5000")
    print("🚨 Emergency QR codes will be generated on-demand")
    
    app.run(debug=True, host='0.0.0.0', port=5000)