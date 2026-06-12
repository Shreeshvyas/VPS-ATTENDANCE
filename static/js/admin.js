// Admin Control Panel scripts

function switchTab(tabId) {
    // 1. Deactivate all menu items and hide all tab contents
    document.querySelectorAll('.sidebar-menu .menu-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // 2. Activate selected menu item and tab content
    document.getElementById(`menu-${tabId}`).classList.add('active');
    document.getElementById(`tab-${tabId}`).classList.add('active');
    
    // 3. Adjust Header elements dynamically
    const pageTitle = document.getElementById('page-title');
    const pageSubtitle = document.getElementById('page-subtitle');
    const addTeacherBtn = document.getElementById('add-teacher-btn');
    
    // Default show/hide values
    addTeacherBtn.style.display = 'none';
    
    switch(tabId) {
        case 'logs':
            pageTitle.textContent = "Today's Attendance";
            pageSubtitle.textContent = `Real-time activity logs`;
            break;
        case 'teachers':
            pageTitle.textContent = "Teachers Directory";
            pageSubtitle.textContent = "Manage staff profiles and device bindings";
            addTeacherBtn.style.display = 'inline-flex';
            break;
        case 'leaves':
            pageTitle.textContent = "Leave Management";
            pageSubtitle.textContent = "Review leave applications and logs";
            break;
        case 'reports':
            pageTitle.textContent = "Monthly Reports";
            pageSubtitle.textContent = "Export historical monthly attendance files";
            break;
        case 'settings':
            pageTitle.textContent = "School Config";
            pageSubtitle.textContent = "Define geolocation boundaries and shift hours";
            break;
    }
}

// Modal actions
function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
    
    // Reset forms if it was a create form
    if (modalId === 'add-teacher-modal') {
        document.getElementById('teacher-form').reset();
        document.getElementById('edit-teacher-id').value = '';
        document.getElementById('teacher-modal-title').innerHTML = '<i class="fa-solid fa-user-plus"></i> Add New Teacher';
        document.getElementById('teacher-status-group').style.display = 'none';
        document.getElementById('teacher-code').readOnly = false;
    }
}

// Teacher Operations
function saveTeacher(event) {
    event.preventDefault();
    const id = document.getElementById('edit-teacher-id').value;
    const name = document.getElementById('teacher-name').value;
    const code = document.getElementById('teacher-code').value;
    const phone = document.getElementById('teacher-phone').value;
    
    let url = '/api/admin/teachers';
    let method = 'POST';
    
    const bodyData = { name, employee_code: code, phone };
    
    if (id) {
        url = `/api/admin/teachers/${id}`;
        method = 'PUT';
        bodyData.is_active = document.getElementById('teacher-active').value === 'true';
    }
    
    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyData)
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to save record.");
        return data;
    })
    .then(data => {
        alert("Teacher record saved successfully.");
        window.location.reload();
    })
    .catch(err => alert("Error: " + err.message));
}

function editTeacher(id, name, code, phone, isActive) {
    document.getElementById('edit-teacher-id').value = id;
    document.getElementById('teacher-name').value = name;
    document.getElementById('teacher-code').value = code;
    document.getElementById('teacher-code').readOnly = true; // Emp code should remain constant
    document.getElementById('teacher-phone').value = phone;
    
    // Status settings
    document.getElementById('teacher-active').value = isActive ? 'true' : 'false';
    document.getElementById('teacher-status-group').style.display = 'block';
    
    document.getElementById('teacher-modal-title').innerHTML = '<i class="fa-solid fa-user-pen"></i> Edit Teacher Profile';
    openModal('add-teacher-modal');
}

function deleteTeacher(id) {
    if (!confirm("Are you sure you want to delete this teacher? This will permanently delete their history as well!")) return;
    
    fetch(`/api/admin/teachers/${id}`, { method: 'DELETE' })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to delete teacher.");
        return data;
    })
    .then(() => {
        alert("Teacher profile deleted successfully.");
        window.location.reload();
    })
    .catch(err => alert("Error: " + err.message));
}

function resetDevice(id) {
    if (!confirm("Reset device binding? This teacher will be able to register a new mobile phone on their next check-in.")) return;
    
    fetch(`/api/admin/teachers/${id}/reset-device`, { method: 'POST' })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to reset device link.");
        return data;
    })
    .then(() => {
        alert("Device binding reset successfully.");
        window.location.reload();
    })
    .catch(err => alert("Error: " + err.message));
}

// Force manual checkin
function submitForceCheckin(event) {
    event.preventDefault();
    const teacherId = document.getElementById('force-teacher-id').value;
    const status = document.getElementById('force-status').value;
    const notes = document.getElementById('force-notes').value;
    
    fetch(`/api/admin/attendance/force`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ teacher_id: parseInt(teacherId), status, notes })
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Override submit failed.");
        return data;
    })
    .then(() => {
        alert("Manual check-in override successful.");
        window.location.reload();
    })
    .catch(err => alert("Error: " + err.message));
}

// Force a teacher absent for today
function forceAbsent(teacherId) {
    if (!confirm("Mark this teacher Absent for today? This will override any existing logs for today.")) return;
    
    fetch(`/api/admin/attendance/force`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            teacher_id: parseInt(teacherId), 
            status: 'Absent', 
            notes: 'Marked Absent manually by Admin' 
        })
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Update failed.");
        return data;
    })
    .then(() => {
        alert("Teacher marked absent.");
        window.location.reload();
    })
    .catch(err => alert("Error: " + err.message));
}

// Leave Handling
function submitLeave(event) {
    event.preventDefault();
    const teacherId = document.getElementById('leave-teacher-id').value;
    const leaveType = document.getElementById('leave-type').value;
    const startDate = document.getElementById('leave-start-date').value;
    const endDate = document.getElementById('leave-end-date').value;
    const reason = document.getElementById('leave-reason').value;
    
    fetch('/api/admin/leaves', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            teacher_id: parseInt(teacherId),
            leave_type: leaveType,
            start_date: startDate,
            end_date: endDate,
            reason
        })
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to submit leave.");
        return data;
    })
    .then(() => {
        alert("Leave request submitted successfully.");
        window.location.reload();
    })
    .catch(err => alert("Error: " + err.message));
}

function actionLeave(leaveId, status) {
    if (!confirm(`Are you sure you want to mark this leave as ${status}?`)) return;
    
    fetch(`/api/admin/leaves/${leaveId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Status change failed.");
        return data;
    })
    .then(() => {
        alert(`Leave request ${status.toLowerCase()} successfully.`);
        window.location.reload();
    })
    .catch(err => alert("Error: " + err.message));
}

// Export CSV
function exportCSV() {
    const monthVal = document.getElementById('report-month').value;
    if (!monthVal) {
        alert("Please select a valid month.");
        return;
    }
    
    // Redirect browser to trigger direct file download
    window.location.href = `/admin/export/csv?month=${monthVal}`;
}

// Save Configurations
function saveSettings(event) {
    event.preventDefault();
    const name = document.getElementById('school-name').value;
    const lat = parseFloat(document.getElementById('school-lat').value);
    const lng = parseFloat(document.getElementById('school-lng').value);
    const radius = parseFloat(document.getElementById('allowed-radius').value);
    const start = document.getElementById('start-time').value;
    const late = document.getElementById('late-time').value;
    const end = document.getElementById('end-time').value;
    const secret = document.getElementById('totp-secret').value;
    const qrType = document.getElementById('qr-type').value;
    
    fetch('/api/admin/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            school_name: name,
            school_latitude: lat,
            school_longitude: lng,
            allowed_radius_meters: radius,
            check_in_start_time: start,
            late_threshold_time: late,
            check_in_end_time: end,
            totp_secret: secret,
            enable_dynamic_qr: qrType === 'dynamic'
        })
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update configuration settings.");
        return data;
    })
    .then(() => {
        alert("System configurations updated.");
        window.location.reload();
    })
    .catch(err => alert("Error: " + err.message));
}

// Admin browser location locator helper
function detectAdminGPS() {
    if (!navigator.geolocation) {
        alert("Geolocation is not supported by this browser.");
        return;
    }
    
    navigator.geolocation.getCurrentPosition(
        (position) => {
            document.getElementById('school-lat').value = position.coords.latitude.toFixed(6);
            document.getElementById('school-lng').value = position.coords.longitude.toFixed(6);
            alert("Acquired current GPS coordinates for school center point!");
        },
        (error) => {
            alert("Unable to acquire location: " + error.message);
        },
        { enableHighAccuracy: true }
    );
}

// Secret Key Generator
function regenerateSecret() {
    if (!confirm("Regenerate the TOTP cryptographic secret? All teachers currently trying to scan might receive error states until the office screen page refreshes.")) return;
    
    // Generate a fresh random base32 token
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
    let newSecret = "";
    for (let i = 0; i < 16; i++) {
        newSecret += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    document.getElementById('totp-secret').value = newSecret;
}

// Toggle static/dynamic QR code settings rendering
function toggleQrSettingsView() {
    const qrType = document.getElementById('qr-type').value;
    const section = document.getElementById('static-qr-section');
    const qrContainer = document.getElementById('static-qrcode-container');
    const qrUrlSpan = document.getElementById('static-qr-url');
    
    if (qrType === 'static') {
        section.style.display = 'block';
        const staticUrl = window.location.origin + "/checkin";
        qrUrlSpan.textContent = staticUrl;
        
        // Clear previous QR if any and render
        qrContainer.innerHTML = "";
        new QRCode(qrContainer, {
            text: staticUrl,
            width: 180,
            height: 180,
            colorDark : "#0b0f19",
            colorLight : "#ffffff",
            correctLevel : QRCode.CorrectLevel.M
        });
    } else {
        section.style.display = 'none';
    }
}

// Print static QR code with clean styled sheet layout
function printStaticQR() {
    const qrContainer = document.getElementById("static-qrcode-container");
    if (!qrContainer) return;
    
    const qrImg = qrContainer.querySelector("img");
    const qrSrc = qrImg ? qrImg.src : "";
    
    const win = window.open("", "_blank");
    win.document.write(`
        <html>
        <head>
            <title>Print School Attendance QR Code</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    text-align: center;
                    padding: 40px;
                    color: #333;
                }
                .container {
                    border: 4px double #6366f1;
                    padding: 40px;
                    display: inline-block;
                    border-radius: 20px;
                    max-width: 500px;
                }
                .qr-box {
                    background-color: white;
                    padding: 20px;
                    display: inline-block;
                    margin: 30px 0;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                    border-radius: 10px;
                    border: 1px solid #eee;
                }
                .qr-box img {
                    width: 250px;
                    height: 250px;
                    display: block;
                }
                h1 { font-size: 32px; font-weight: 800; margin: 0 0 10px 0; color: #1e293b; }
                p { font-size: 16px; margin: 5px 0; color: #475569; }
                .notice { font-size: 14px; font-weight: 600; color: #dc2626; margin-top: 20px; text-transform: uppercase; letter-spacing: 0.05em; }
            </style>
        </head>
        <body onload="window.print(); window.close();">
            <div class="container">
                <h1>VPS Attendance Check-In</h1>
                <p>Scan this QR code using your smartphone browser camera to log your daily attendance.</p>
                <div class="qr-box">
                    <img src="${qrSrc}">
                </div>
                <p class="notice">Geofencing Boundary Active</p>
                <p style="font-size: 13px; color: #475569; margin-top: 5px;">You must be inside the school radius for validation to succeed.</p>
            </div>
        </body>
        </html>
    `);
    win.document.close();
}

// Auto init on settings tab load
document.addEventListener('DOMContentLoaded', () => {
    // If we load onto settings and it's static mode, initialize static QR rendering
    setTimeout(() => {
        const qrType = document.getElementById('qr-type');
        if (qrType && qrType.value === 'static') {
            toggleQrSettingsView();
        }
    }, 500);
});
