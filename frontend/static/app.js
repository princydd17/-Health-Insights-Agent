// Section switching
function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(sectionId).classList.add('active');
}

// Default section
document.addEventListener('DOMContentLoaded', () => {
    showSection('profile');
    fetchProfileData();
    loadProfile();
});

// Form submission handler
document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch(`/api/${e.target.id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
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

// Document upload
async function handleDocumentUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const documentType = document.getElementById('documentType').value;
    const formData = new FormData();
    formData.append('document', file);
    formData.append('document_type', documentType);

    try {
        const response = await fetch('/api/upload-document', { method: 'POST', body: formData });
        if (response.ok) {
            alert('Document uploaded successfully!');
        } else {
            alert('Error uploading document');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error uploading document');
    }
}

// Chat
function addMessage(message, sender) {
    const chatContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('chat-message', sender + '-message');
    messageDiv.textContent = message;
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    input.value = '';

    setTimeout(() => {
        addMessage("This is a placeholder response. Integrate your LLM backend here.", 'bot');
    }, 1000);
}

document.getElementById('chatInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') sendMessage();
});

// Profile & QR
async function fetchProfileData() {
    try {
        const response = await fetch('/api/get-profile');
        const data = await response.json();
        if (data.status === 'success') {
            document.getElementById('qr-code').src = 'data:image/png;base64,' + data.qr_code;
        }
    } catch (error) {
        console.error('Error fetching profile data:', error);
    }
}

// Vitals
document.getElementById('vitalsForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());

    try {
        const response = await fetch('/api/vital-metrics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (response.ok) {
            alert('Vital metrics saved successfully!');
            loadProfile();
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
            document.getElementById('qr-code').src = `data:image/png;base64,${data.qr_code}`;
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
