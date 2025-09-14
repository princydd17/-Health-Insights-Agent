from flask import Flask, render_template_string, jsonify, request
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

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Health Insights Agent</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --primary-color: #2196F3;
            --secondary-color: #FFF;
            --text-color: #333;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            margin: 0;
            padding: 0;
            color: var(--text-color);
            background: #f5f5f5;
        }

        .navbar {
            background: var(--primary-color);
            padding: 1rem;
            color: var(--secondary-color);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }

        .card {
            background: var(--secondary-color);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .tabs {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .tab-button {
            padding: 0.5rem 1rem;
            border: none;
            background: var(--primary-color);
            color: var(--secondary-color);
            border-radius: 4px;
            cursor: pointer;
            transition: opacity 0.2s;
        }

        .tab-button:hover {
            opacity: 0.9;
        }

        .section {
            display: none;
        }

        .section.active {
            display: block;
        }

        .form-group {
            margin-bottom: 1rem;
        }

        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }

        .form-group input, .form-group select {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 1rem;
        }

        .button {
            background: var(--primary-color);
            color: var(--secondary-color);
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1rem;
        }

        .button:hover {
            opacity: 0.9;
        }

        .chat-container {
            height: 400px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 1rem;
            margin-bottom: 1rem;
            background: #f9f9f9;
        }

        .chat-message {
            margin-bottom: 1rem;
            padding: 0.8rem;
            border-radius: 8px;
            max-width: 80%;
        }

        .user-message {
            background: var(--primary-color);
            color: white;
            margin-left: auto;
        }

        .bot-message {
            background: #e9e9e9;
            margin-right: auto;
        }

        .chat-input-container {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
        }

        .chat-input {
            flex: 1;
        }

        .qr-info {
            text-align: center;
            margin-top: 1rem;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>Health Insights Agent</h1>
    </div>

    <div class="container">
        <div class="tabs">
            <button class="tab-button" onclick="showSection('profile')">Profile</button>
            <button class="tab-button" onclick="showSection('documents')">Documents</button>
            <button class="tab-button" onclick="showSection('medications')">Medications</button>
            <button class="tab-button" onclick="showSection('emergency')">Emergency</button>
            <button class="tab-button" onclick="showSection('chat')">Chat</button>
            <button class="tab-button" onclick="showSection('qr-profile')">QR Profile</button>
            <button class="tab-button" onclick="showSection('vitals')">Vital Metrics</button>
        </div>

        <div id="profile" class="section">
            <div class="card">
                <h2>Patient Profile</h2>
                <form id="profileForm">
                    <div class="form-group">
                        <label>Full Name</label>
                        <input type="text" name="name" required>
                    </div>
                    <div class="form-group">
                        <label>Date of Birth</label>
                        <input type="date" name="dob" required>
                    </div>
                    <div class="form-group">
                        <label>Blood Type</label>
                        <select name="bloodType">
                            <option>A+</option>
                            <option>A-</option>
                            <option>B+</option>
                            <option>B-</option>
                            <option>O+</option>
                            <option>O-</option>
                            <option>AB+</option>
                            <option>AB-</option>
                        </select>
                    </div>
                    <button type="submit" class="button">Save Profile</button>
                </form>
            </div>
        </div>

        <div id="documents" class="section">
            <div class="card">
                <h2>Medical Documents</h2>
                <div class="form-group">
                    <label>Upload Document</label>
                    <input type="file" accept="image/*" onchange="handleDocumentUpload(event)">
                </div>
                <div id="documentsList"></div>
            </div>
        </div>

        <div id="medications" class="section">
            <div class="card">
                <h2>Medications</h2>
                <form id="medicationForm">
                    <div class="form-group">
                        <label>Medication Name</label>
                        <input type="text" name="medName" required>
                    </div>
                    <div class="form-group">
                        <label>Dosage</label>
                        <input type="text" name="dosage" required>
                    </div>
                    <div class="form-group">
                        <label>Frequency</label>
                        <input type="text" name="frequency" required>
                    </div>
                    <button type="submit" class="button">Add Medication</button>
                </form>
            </div>
        </div>

        <div id="emergency" class="section">
            <div class="card">
                <h2>Emergency Information</h2>
                <form id="emergencyForm">
                    <div class="form-group">
                        <label>Emergency Contact Name</label>
                        <input type="text" name="emergencyName" required>
                    </div>
                    <div class="form-group">
                        <label>Emergency Contact Phone</label>
                        <input type="tel" name="emergencyPhone" required>
                    </div>
                    <button type="submit" class="button">Save Emergency Info</button>
                </form>
            </div>
        </div>

        <div id="chat" class="section">
            <div class="card">
                <h2>AI Health Assistant</h2>
                <div class="chat-container" id="chatMessages">
                    <div class="chat-message bot-message">
                        Hello! I'm your Health Assistant. How can I help you today?
                    </div>
                </div>
                <div class="chat-input-container">
                    <input type="text" id="chatInput" class="chat-input" 
                           placeholder="Type your message here..." required>
                    <button onclick="sendMessage()" class="button">Send</button>
                </div>
            </div>
        </div>

        <div id="qr-profile" class="section">
            <div class="card">
                <h2>Emergency QR Profile</h2>
                <div id="qr-display">
                    <img id="qr-code" src="" alt="Emergency QR Code">
                </div>
                <div class="qr-info">
                    <p>Scan this QR code to access emergency medical information</p>
                </div>
            </div>
        </div>

        <div id="vitals" class="section">
            <div class="card">
                <h2>Vital Metrics</h2>
                <form id="vitalsForm">
                    <div class="form-group">
                        <label>Metric Type</label>
                        <select name="type" required>
                            <option value="blood_pressure">Blood Pressure</option>
                            <option value="glucose">Blood Glucose</option>
                            <option value="heart_rate">Heart Rate</option>
                            <option value="temperature">Temperature</option>
                            <option value="oxygen">Oxygen Saturation</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Value</label>
                        <input type="text" name="value" required>
                    </div>
                    <div class="form-group">
                        <label>Unit</label>
                        <input type="text" name="unit" required>
                    </div>
                    <button type="submit" class="button">Add Vital Metric</button>
                </form>
                <div id="vitalsHistory"></div>
            </div>
        </div>
    </div>

    <script>
        function showSection(sectionId) {
            document.querySelectorAll('.section').forEach(section => {
                section.classList.remove('active');
            });
            document.getElementById(sectionId).classList.add('active');
        }

        // Show profile section by default
        document.addEventListener('DOMContentLoaded', () => {
            showSection('profile');
        });

        // Handle form submissions
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData.entries());
                
                try {
                    const response = await fetch(`/api/${e.target.id}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(data)
                    });
                    
                    if (response.ok) {
                        alert('Saved successfully!');
                    } else {
                        alert('Error saving data');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Error saving data');
                }
            });
        });

        async function handleDocumentUpload(event) {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('document', file);

            try {
                const response = await fetch('/api/upload-document', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    alert('Document uploaded successfully!');
                    // Refresh documents list
                } else {
                    alert('Error uploading document');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error uploading document');
            }
        }

        function appendMessage(role, content) {
            const messageElement = document.createElement('div');
            messageElement.classList.add('chat-message', `${role}-message`);
            messageElement.textContent = content;
            document.getElementById('chatMessages').appendChild(messageElement);
        }

        function sendMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Add user message to chat
            addMessage(message, 'user');
            
            // Clear input
            input.value = '';
            
            // Placeholder for backend integration
            // Replace this with your actual LLM integration later
            setTimeout(() => {
                addMessage("This is a placeholder response. Integrate your LLM backend here.", 'bot');
            }, 1000);
        }

        function addMessage(message, sender) {
            const chatContainer = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('chat-message');
            messageDiv.classList.add(sender + '-message');
            messageDiv.textContent = message;
            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        // Add event listener for Enter key in chat input
        document.getElementById('chatInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Fetch and display QR code and profile data
        async function fetchProfileData() {
            try {
                const response = await fetch('/api/get-profile');
                const data = await response.json();
                
                if (data.status === 'success') {
                    // Set QR code image
                    const qrCodeImg = document.getElementById('qr-code');
                    qrCodeImg.src = 'data:image/png;base64,' + data.qr_code;

                    // Display profile data in emergency section
                    document.getElementById('emergencyName').textContent = data.profile.name;
                    document.getElementById('emergencyDob').textContent = data.profile.dob;
                    document.getElementById('emergencyBloodType').textContent = data.profile.blood_type;
                }
            } catch (error) {
                console.error('Error fetching profile data:', error);
            }
        }

        // Add to your existing JavaScript
        document.getElementById('vitalsForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData.entries());
            
            try {
                const response = await fetch('/api/vital-metrics', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    alert('Vital metrics saved successfully!');
                    loadProfile(); // Refresh profile data
                } else {
                    alert('Error saving vital metrics');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error saving vital metrics');
            }
        });

        async function loadProfile() {
            try {
                const response = await fetch('/api/get-profile');
                const data = await response.json();
                
                if (data.status === 'success') {
                    // Update QR code
                    document.getElementById('qr-code').src = `data:image/png;base64,${data.qr_code}`;
                    
                    // Update vitals history
                    const vitalsHistory = document.getElementById('vitalsHistory');
                    vitalsHistory.innerHTML = `
                        <h3>Recent Vitals</h3>
                        <ul>
                            ${data.profile.recent_vitals.map(vital => `
                                <li>${vital.metric_type}: ${vital.value} ${vital.unit} 
                                    (${new Date(vital.recorded_date).toLocaleString()})
                                </li>
                            `).join('')}
                        </ul>
                    `;
                }
            } catch (error) {
                console.error('Error loading profile:', error);
            }
        }

        // Load profile when page loads
        document.addEventListener('DOMContentLoaded', () => {
            fetchProfileData();
            loadProfile();
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

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
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400
        
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Ensure directory exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            # Save file
            file.save(file_path)
            print(file_path)
            # Make a call to backend to get data
            chatbot = Chatbot()
            print(chatbot.get_text_content(file_path))

            
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