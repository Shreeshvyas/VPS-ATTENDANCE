// Teacher Check-in script

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize device fingerprint
    initDeviceFingerprint();
    
    // 2. Request GPS Coordinates
    requestLocation();
});

// Generate and store a unique persistent ID for this device
function initDeviceFingerprint() {
    let deviceUuid = localStorage.getItem('vps_device_uuid');
    if (!deviceUuid) {
        // Simple UUID generator
        deviceUuid = 'device_' + Math.random().toString(36).substring(2, 15) + '_' + Date.now().toString(36);
        localStorage.setItem('vps_device_uuid', deviceUuid);
    }
    
    // Create a fingerprint string combining system settings & UUID to make spoofing harder
    const fingerprintInfo = {
        uuid: deviceUuid,
        ua: navigator.userAgent,
        screen: `${window.screen.width}x${window.screen.height}`,
        lang: navigator.language,
        tz: Intl.DateTimeFormat().resolvedOptions().timeZone
    };
    
    // Simple hash/string to send
    const fingerprintStr = btoa(JSON.stringify(fingerprintInfo));
    document.getElementById('device-fingerprint').value = fingerprintStr;
}

// Request location from browser
function requestLocation() {
    const statusAlert = document.getElementById('status-alert');
    const statusText = document.getElementById('status-text');
    const checkinForm = document.getElementById('checkin-form');
    
    if (!statusText) return; // Error template displayed

    if (!navigator.geolocation) {
        showStatus('error', '<i class="fa-solid fa-triangle-exclamation"></i> Geolocation is not supported by your browser.');
        return;
    }

    const geoOptions = {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 0
    };

    navigator.geolocation.getCurrentPosition(
        (position) => {
            // Success
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            const accuracy = position.coords.accuracy;

            document.getElementById('latitude').value = lat;
            document.getElementById('longitude').value = lng;
            document.getElementById('accuracy').value = accuracy;

            // Update status
            statusAlert.style.display = 'none';
            
            // Show location acquired pill
            const locationPill = document.getElementById('location-pill');
            const locationPillText = document.getElementById('location-pill-text');
            locationPillText.textContent = `GPS Connected (Accurate to ${Math.round(accuracy)}m)`;
            locationPill.style.display = 'inline-flex';

            // Show Form
            checkinForm.style.display = 'block';
        },
        (error) => {
            // Error
            let errorMessage = "Unable to retrieve your location.";
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    errorMessage = "Location permission denied. Please allow GPS access in your browser settings to proceed.";
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMessage = "GPS signal unavailable. Please ensure your phone location/GPS is turned ON.";
                    break;
                case error.TIMEOUT:
                    errorMessage = "Location request timed out. Please refresh and try again in an open area.";
                    break;
            }
            showStatus('danger', `<i class="fa-solid fa-triangle-exclamation"></i> ${errorMessage}`);
            
            // Show failure screen instead of form
            document.getElementById('checkin-form').style.display = 'none';
            document.getElementById('failure-screen').style.display = 'block';
            document.getElementById('failure-reason').textContent = errorMessage;
            document.getElementById('retry-btn').style.display = 'block';
        },
        geoOptions
    );
}

function showStatus(type, message) {
    const statusAlert = document.getElementById('status-alert');
    const statusText = document.getElementById('status-text');
    
    statusAlert.className = `alert alert-${type}`;
    statusText.innerHTML = message;
    statusAlert.style.display = 'flex';
}

function submitCheckin(event) {
    event.preventDefault();
    
    const submitBtn = document.getElementById('submit-btn');
    const employeeCode = document.getElementById('employee-code').value;
    const token = document.getElementById('qr-token').value;
    const lat = document.getElementById('latitude').value;
    const lng = document.getElementById('longitude').value;
    const deviceFingerprint = document.getElementById('device-fingerprint').value;
    
    // Disable submit button
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Submitting...';
    
    // Prepare data
    const formData = new FormData();
    formData.append('employee_code', employeeCode);
    formData.append('token', token);
    formData.append('latitude', lat);
    formData.append('longitude', lng);
    formData.append('device_fingerprint', deviceFingerprint);
    
    fetch('/api/attendance', {
        method: 'POST',
        body: formData
    })
    .then(async response => {
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Server validation failed.");
        }
        return data;
    })
    .then(data => {
        // Success
        document.getElementById('checkin-form').style.display = 'none';
        
        // Populate Success details
        document.getElementById('success-name').textContent = data.teacher_name;
        document.getElementById('success-time').textContent = `Logged at ${data.check_in_time} (Status: ${data.status})`;
        document.getElementById('success-dist-text').textContent = `Distance: ${Math.round(data.distance_meters)} meters from school`;
        
        document.getElementById('success-screen').style.display = 'block';
    })
    .catch(error => {
        // Failure
        document.getElementById('checkin-form').style.display = 'none';
        document.getElementById('failure-reason').textContent = error.message;
        document.getElementById('failure-screen').style.display = 'block';
    });
}

function retryLocation() {
    document.getElementById('failure-screen').style.display = 'none';
    document.getElementById('checkin-form').style.display = 'none';
    
    // Show loading indicator
    showStatus('info', '<i class="fa-solid fa-location-crosshairs fa-spin"></i> Requesting GPS location permission...');
    
    requestLocation();
}

function resetForm() {
    // Reset inputs and screen state
    document.getElementById('employee-code').value = '';
    document.getElementById('success-screen').style.display = 'none';
    
    const submitBtn = document.getElementById('submit-btn');
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<i class="fa-solid fa-signature" style="margin-right: 8px;"></i> Mark Attendance';
    
    // Request new coordinates and show form
    retryLocation();
}
