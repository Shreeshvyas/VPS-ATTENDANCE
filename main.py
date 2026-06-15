from fastapi import FastAPI, Depends, HTTPException, Form, Request, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import datetime
import time
import base64
import json
import csv
from io import StringIO

import models
import crud
import utils
from database import engine, get_db, SessionLocal

# Create database tables
models.Base.metadata.create_all(bind=engine)

def auto_init_db():
    db = SessionLocal()
    try:
        # 0. Run schema migrations for existing database tables
        try:
            from sqlalchemy import text
            db.execute(text("ALTER TABLE attendance ADD COLUMN check_out_time TIME"))
            db.commit()
            print("Migration: Added check_out_time column to attendance table.")
        except Exception as e:
            print(f"Migration note: {e}")
            db.rollback()

        # 1. Initialize system configuration if empty
        config = db.query(models.SystemConfig).first()
        if not config:
            config = models.SystemConfig(
                school_name="VPS High School",
                school_latitude=24.12345,
                school_longitude=77.12345,
                allowed_radius_meters=100.0,
                check_in_start_time="07:30",
                late_threshold_time="08:30",
                check_in_end_time="10:00",
                totp_secret="JBSWY3DPEHPK3PXP",
                enable_dynamic_qr=False
            )
            db.add(config)
            db.commit()
            print("Auto-Init: Default system config created.")
            
        # 2. Initialize default admin if empty
        admin = db.query(models.Admin).filter(models.Admin.username == "admin").first()
        if not admin:
            crud.create_admin(db, "admin", "adminpassword")
            print("Auto-Init: Default admin created (admin/adminpassword).")
    except Exception as e:
        print(f"Auto-Init Error: {e}")
    finally:
        db.close()

auto_init_db()

app = FastAPI(title="VPS Attendance System")

# Mount Static assets and Jinja Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Helper: Parse device fingerprint base64 JSON
def get_device_uuid(fingerprint_b64: str) -> str:
    try:
        if not fingerprint_b64:
            return "unknown_device"
        decoded = base64.b64decode(fingerprint_b64).decode('utf-8')
        data = json.loads(decoded)
        return data.get("uuid", "unknown_device")
    except Exception:
        return fingerprint_b64 or "unknown_device"

# Helper: Verify if admin is authenticated via session cookies
def is_admin_authenticated(request: Request) -> bool:
    session = request.cookies.get("admin_session")
    return session == "vps_admin_authenticated_session_key_2026"

# Root redirect to check-in screen
@app.get("/")
def read_root():
    return RedirectResponse(url="/checkin")

# Serve Service Worker in root scope for PWA installation
@app.get("/sw.js")
def get_service_worker():
    return FileResponse("static/sw.js", media_type="application/javascript")

# ==========================================
# TEACHER CHECK-IN ROUTES
# ==========================================

@app.get("/checkin", response_class=HTMLResponse)
def get_checkin(request: Request, token: str = None, db: Session = Depends(get_db)):
    config = crud.get_system_config(db)
    error_msg = None
    
    if config.enable_dynamic_qr:
        if not token:
            error_msg = "Scan token is missing. Please scan the QR code at the entrance."
        else:
            # Validate TOTP token
            is_valid = utils.verify_totp_token(config.totp_secret, token)
            if not is_valid:
                error_msg = "Expired QR code. The token rotated. Please scan the active QR code."
    else:
        # Static QR mode: Bypass token checking
        token = "static_bypass"
            
    return templates.TemplateResponse("index.html", {
        "request": request,
        "token": token,
        "error_msg": error_msg
    })

@app.post("/api/attendance")
def api_submit_attendance(
    employee_code: str = Form(...),
    token: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    device_fingerprint: str = Form(...),
    db: Session = Depends(get_db)
):
    config = crud.get_system_config(db)
    
    # 1. Validate Token if dynamic QR is enabled
    if config.enable_dynamic_qr:
        if not utils.verify_totp_token(config.totp_secret, token):
            raise HTTPException(status_code=400, detail="Invalid or expired QR code. Please scan the active QR at the entrance.")
        
    # 2. Check Teacher
    teacher = crud.get_teacher_by_code(db, employee_code)
    if not teacher:
        raise HTTPException(status_code=404, detail="Invalid Employee Code. Please verify your 6-digit number.")
        
    # 3. Decode & Verify Device Fingerprint
    incoming_uuid = get_device_uuid(device_fingerprint)
    
    if not teacher.device_fingerprint:
        # Register this device as the teacher's primary device
        teacher.device_fingerprint = incoming_uuid
        db.commit()
    elif teacher.device_fingerprint != incoming_uuid:
        raise HTTPException(
            status_code=400, 
            detail="Device Mismatch. This Employee Code is linked to another phone. Contact Admin to reset."
        )
        
    # 4. Check School Hours (Localized to IST UTC+5:30)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = datetime.datetime.now(ist_tz)
    current_time_str = now.strftime("%H:%M")
    
    if current_time_str < config.check_in_start_time or current_time_str > config.check_in_end_time:
        raise HTTPException(status_code=400, detail=f"Check-in closed. School shift hours are {config.check_in_start_time} to {config.check_in_end_time}.")
        
    # Determine Status (Present vs Late)
    status_val = "Present"
    if current_time_str > config.late_threshold_time:
        status_val = "Late"
        
    # 5. Geofence Boundary Check
    distance = utils.haversine_distance(
        config.school_latitude, config.school_longitude,
        latitude, longitude
    )
    
    is_verified = True
    notes_list = []
    
    if distance > config.allowed_radius_meters:
        # Log failed attempt before throwing exception
        event_record = models.AttendanceEvent(
            teacher_id=teacher.id,
            event_type="Check-In",
            latitude=latitude,
            longitude=longitude,
            distance_meters=distance,
            device_fingerprint=incoming_uuid,
            is_verified=False,
            verification_notes=f"Out of Bounds: {int(distance)}m away"
        )
        db.add(event_record)
        db.commit()
        
        raise HTTPException(
            status_code=400, 
            detail=f"Out of Bounds. You are {int(distance)}m away. Check-in allowed up to {int(config.allowed_radius_meters)}m."
        )
        
    # 6. Device Proxy check (Did other teachers check-in with this device today?)
    today = datetime.date.today()
    existing_attendance = crud.get_attendance_by_teacher_and_date(db, teacher.id, today)
    today_records = crud.get_attendance_for_date(db, today)
    shared_device_count = 0
    for record in today_records:
        if record.device_fingerprint == incoming_uuid and record.teacher_id != teacher.id:
            shared_device_count += 1
            other_teacher = crud.get_teacher(db, record.teacher_id)
            if other_teacher:
                notes_list.append(f"Proxy Alert: Same device used by {other_teacher.name} today.")
                is_verified = False
                
    if not is_verified:
        verification_notes = ", ".join(notes_list)
    else:
        verification_notes = "GPS and Device Verified"
        
    # 7. Log Attendance Event (Audit log of every click)
    event_record = models.AttendanceEvent(
        teacher_id=teacher.id,
        event_type="Check-In",
        latitude=latitude,
        longitude=longitude,
        distance_meters=distance,
        device_fingerprint=incoming_uuid,
        is_verified=is_verified,
        verification_notes=verification_notes
    )
    db.add(event_record)
    db.commit()

    # 8. Log/Update Daily Attendance Summary
    if existing_attendance:
        # Keep original status if it is Present or Late, otherwise update
        if existing_attendance.status not in ["Present", "Late"]:
            existing_attendance.status = status_val
        # Keep original first check_in_time
        if existing_attendance.check_in_time is None:
            existing_attendance.check_in_time = now.time()
        existing_attendance.latitude = latitude
        existing_attendance.longitude = longitude
        existing_attendance.distance_meters = distance
        existing_attendance.device_fingerprint = incoming_uuid
        existing_attendance.is_verified = is_verified and existing_attendance.is_verified
        if existing_attendance.verification_notes and "Proxy" in existing_attendance.verification_notes:
            pass # Keep proxy warning
        else:
            existing_attendance.verification_notes = verification_notes
        db.commit()
        db.refresh(existing_attendance)
        record = existing_attendance
    else:
        record = crud.mark_attendance(
            db=db,
            teacher_id=teacher.id,
            status=status_val,
            check_in_time=now.time(),
            latitude=latitude,
            longitude=longitude,
            distance_meters=distance,
            device_fingerprint=incoming_uuid,
            is_verified=is_verified,
            verification_notes=verification_notes
        )
    
    return {
        "status": record.status,
        "teacher_name": teacher.name,
        "check_in_time": record.check_in_time.strftime("%I:%M:%S %p"),
        "distance_meters": distance
    }

@app.post("/api/checkout")
def api_submit_checkout(
    employee_code: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    device_fingerprint: str = Form(...),
    db: Session = Depends(get_db)
):
    config = crud.get_system_config(db)
    
    # 1. Check Teacher
    teacher = crud.get_teacher_by_code(db, employee_code)
    if not teacher:
        raise HTTPException(status_code=404, detail="Invalid Employee Code. Please verify your 6-digit number.")
        
    # 2. Decode & Verify Device Fingerprint
    incoming_uuid = get_device_uuid(device_fingerprint)
    
    if not teacher.device_fingerprint:
        raise HTTPException(status_code=400, detail="You must check in first to register your device.")
    elif teacher.device_fingerprint != incoming_uuid:
        raise HTTPException(
            status_code=400, 
            detail="Device Mismatch. This Employee Code is linked to another phone."
        )
        
    # 3. Geofence Boundary Check
    distance = utils.haversine_distance(
        config.school_latitude, config.school_longitude,
        latitude, longitude
    )
    
    is_verified = True
    notes_list = []
    
    if distance > config.allowed_radius_meters:
        # Log failed attempt before throwing exception
        event_record = models.AttendanceEvent(
            teacher_id=teacher.id,
            event_type="Check-Out",
            latitude=latitude,
            longitude=longitude,
            distance_meters=distance,
            device_fingerprint=incoming_uuid,
            is_verified=False,
            verification_notes=f"Out of Bounds: {int(distance)}m away"
        )
        db.add(event_record)
        db.commit()
        
        raise HTTPException(
            status_code=400, 
            detail=f"Out of Bounds. You are {int(distance)}m away. Clock-out allowed up to {int(config.allowed_radius_meters)}m."
        )
        
    # 4. Check if checked in today
    today = datetime.date.today()
    existing_attendance = crud.get_attendance_by_teacher_and_date(db, teacher.id, today)
    if not existing_attendance:
         raise HTTPException(status_code=400, detail="No check-in record found for today. You must check in first.")
         
    # 5. Device Proxy check
    today_records = crud.get_attendance_for_date(db, today)
    for record in today_records:
        if record.device_fingerprint == incoming_uuid and record.teacher_id != teacher.id:
            other_teacher = crud.get_teacher(db, record.teacher_id)
            if other_teacher:
                notes_list.append(f"Proxy Alert: Same device used by {other_teacher.name} today.")
                is_verified = False
                
    if not is_verified:
        verification_notes = ", ".join(notes_list)
    else:
        verification_notes = "GPS and Device Verified"
        
    # 6. Log Clock-Out Event (Audit log of every click)
    event_record = models.AttendanceEvent(
        teacher_id=teacher.id,
        event_type="Check-Out",
        latitude=latitude,
        longitude=longitude,
        distance_meters=distance,
        device_fingerprint=incoming_uuid,
        is_verified=is_verified,
        verification_notes=verification_notes
    )
    db.add(event_record)
    db.commit()

    # 7. Update Daily Attendance Summary (Localized to IST UTC+5:30)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = datetime.datetime.now(ist_tz)
    existing_attendance.check_out_time = now.time()
    existing_attendance.is_verified = is_verified and existing_attendance.is_verified
    if existing_attendance.verification_notes and "Proxy" in existing_attendance.verification_notes:
        pass
    else:
        existing_attendance.verification_notes = verification_notes
    db.commit()
    db.refresh(existing_attendance)
    
    return {
        "status": "Checked Out",
        "teacher_name": teacher.name,
        "check_out_time": existing_attendance.check_out_time.strftime("%I:%M:%S %p"),
        "distance_meters": distance
    }

# ==========================================
# DYNAMIC QR CODE DISPLAY ROUTE
# ==========================================

@app.get("/qr-display", response_class=HTMLResponse)
def get_qr_display(request: Request, db: Session = Depends(get_db)):
    config = crud.get_system_config(db)
    return templates.TemplateResponse("qr_display.html", {
        "request": request,
        "school_name": config.school_name
    })

@app.get("/api/qr-token")
def api_get_qr_token(db: Session = Depends(get_db)):
    config = crud.get_system_config(db)
    token = utils.generate_totp_token(config.totp_secret)
    # Remaining seconds in the current 30s window
    expires_in = 30 - (int(time.time()) % 30)
    return {
        "token": token,
        "expires_in": expires_in
    }

# ==========================================
# ADMIN AUTHENTICATION
# ==========================================

@app.get("/admin/login", response_class=HTMLResponse)
def get_admin_login(request: Request):
    if is_admin_authenticated(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": None})

@app.post("/admin/login")
def post_admin_login(
    response: Response,
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    admin = crud.get_admin_by_username(db, username)
    if not admin or not crud.verify_admin_password(password, admin.password_hash):
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Invalid username or password credentials."
        })
        
    # Successful login, set session cookie
    response = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="admin_session", 
        value="vps_admin_authenticated_session_key_2026", 
        httponly=True, 
        max_age=3600 * 8 # 8 hours session
    )
    return response

@app.get("/admin/logout")
def get_admin_logout(response: Response):
    response = RedirectResponse(url="/admin/login")
    response.delete_cookie(key="admin_session")
    return response

# ==========================================
# ADMIN DASHBOARD & CONTROLS
# ==========================================

@app.get("/admin", response_class=HTMLResponse)
def get_admin_dashboard(request: Request, db: Session = Depends(get_db)):
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
        
    config = crud.get_system_config(db)
    teachers = crud.get_teachers(db)
    today = datetime.date.today()
    
    # 1. Fetch Today's Attendance Logs
    attendance_records = crud.get_attendance_for_date(db, today)
    attendance_map = {r.teacher_id: r for r in attendance_records}
    
    # 2. Get active leaves overlapping today
    active_leaves = crud.get_leaves_active_on_date(db, today)
    leave_teacher_ids = {l.teacher_id for l in active_leaves}
    
    logs_summary = []
    
    # Counts
    present_count = 0
    late_count = 0
    absent_count = 0
    leave_count = 0
    
    # Process all active teachers to compile today's log
    for teacher in teachers:
        if not teacher.is_active:
            continue
            
        record = attendance_map.get(teacher.id)
        
        # Determine status
        if record:
            status_val = record.status
            check_in_time = record.check_in_time.strftime("%I:%M:%S %p") if record.check_in_time else "--"
            check_out_time = record.check_out_time.strftime("%I:%M:%S %p") if record.check_out_time else "--"
            distance_meters = record.distance_meters
            flagged = not record.is_verified
            flag_reason = record.verification_notes if flagged else ""
            
            if status_val == "Present":
                present_count += 1
            elif status_val == "Late":
                late_count += 1
            elif status_val == "On Leave":
                leave_count += 1
            elif status_val == "Absent":
                absent_count += 1
        elif teacher.id in leave_teacher_ids:
            status_val = "On Leave"
            check_in_time = "--"
            check_out_time = "--"
            distance_meters = None
            flagged = False
            flag_reason = ""
            leave_count += 1
        else:
            status_val = "Absent"
            check_in_time = "--"
            check_out_time = "--"
            distance_meters = None
            flagged = False
            flag_reason = ""
            absent_count += 1
            
        logs_summary.append({
            "teacher_id": teacher.id,
            "employee_code": teacher.employee_code,
            "name": teacher.name,
            "check_in_time": check_in_time,
            "check_out_time": check_out_time,
            "distance_meters": distance_meters,
            "status": status_val,
            "flagged": flagged,
            "flag_reason": flag_reason
        })
        
    # Fetch all historical leaves
    leaves_records = db.query(models.Leave).order_by(models.Leave.created_at.desc()).all()
    leaves_summary = []
    for leave in leaves_records:
        leaves_summary.append({
            "id": leave.id,
            "teacher_name": leave.teacher.name if leave.teacher else "Deleted Teacher",
            "leave_type": leave.leave_type,
            "start_date": leave.start_date.strftime("%Y-%m-%d"),
            "end_date": leave.end_date.strftime("%Y-%m-%d"),
            "reason": leave.reason,
            "status": leave.status
        })

    # Fetch today's detailed click events (Check-In & Check-Out)
    events_records = db.query(models.AttendanceEvent).filter(
        models.AttendanceEvent.date == today
    ).order_by(models.AttendanceEvent.timestamp.desc()).all()
    events_summary = []
    for event in events_records:
        # Convert UTC timestamp to IST (UTC+5:30) for localized admin view
        ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        local_time = event.timestamp.replace(tzinfo=datetime.timezone.utc).astimezone(ist_tz)
        events_summary.append({
            "name": event.teacher.name if event.teacher else "Unknown",
            "employee_code": event.teacher.employee_code if event.teacher else "--",
            "time": local_time.strftime("%I:%M:%S %p"),
            "event_type": event.event_type,
            "distance_meters": int(event.distance_meters) if event.distance_meters is not None else 0,
            "latitude": f"{event.latitude:.6f}" if event.latitude is not None else None,
            "longitude": f"{event.longitude:.6f}" if event.longitude is not None else None,
            "is_verified": event.is_verified,
            "verification_notes": event.verification_notes or "",
            "device": event.device_fingerprint[:8] if event.device_fingerprint else "--"
        })

    metrics = {
        "present": present_count,
        "late": late_count,
        "absent": absent_count,
        "leave": leave_count
    }
    
    current_date = today.strftime("%B %d, %Y")
    current_month_val = today.strftime("%Y-%m")
    
    # Retrieve current admin details
    admin_username = "admin" # Default
    admin_session_cookie = request.cookies.get("admin_session")
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "config": config,
        "teachers": teachers,
        "logs": logs_summary,
        "leaves": leaves_summary,
        "events": events_summary,
        "metrics": metrics,
        "current_date": current_date,
        "current_month_val": current_month_val,
        "admin_username": admin_username
    })

# ==========================================
# ADMIN REST API ENDPOINTS
# ==========================================

# Middleware check for admin endpoints
def verify_admin_api(request: Request):
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized admin session.")

# Save / Update Config
@app.post("/api/admin/settings", dependencies=[Depends(verify_admin_api)])
def api_update_settings(
    data: dict,
    db: Session = Depends(get_db)
):
    crud.update_system_config(
        db=db,
        school_name=data.get("school_name"),
        school_latitude=data.get("school_latitude"),
        school_longitude=data.get("school_longitude"),
        allowed_radius_meters=data.get("allowed_radius_meters"),
        check_in_start_time=data.get("check_in_start_time"),
        late_threshold_time=data.get("late_threshold_time"),
        check_in_end_time=data.get("check_in_end_time"),
        totp_secret=data.get("totp_secret"),
        enable_dynamic_qr=data.get("enable_dynamic_qr", True)
    )
    return {"status": "success", "detail": "Configurations saved."}

# Add Teacher
@app.post("/api/admin/teachers", dependencies=[Depends(verify_admin_api)])
def api_add_teacher(data: dict, db: Session = Depends(get_db)):
    # Check if employee code already exists
    existing = crud.get_teacher_by_code(db, data.get("employee_code"))
    if existing:
        raise HTTPException(status_code=400, detail="Employee code already registered.")
        
    teacher = crud.create_teacher(
        db=db,
        name=data.get("name"),
        employee_code=data.get("employee_code"),
        phone=data.get("phone")
    )
    return {"status": "success", "id": teacher.id}

# Edit Teacher
@app.put("/api/admin/teachers/{id}", dependencies=[Depends(verify_admin_api)])
def api_edit_teacher(id: int, data: dict, db: Session = Depends(get_db)):
    teacher = crud.update_teacher(
        db=db,
        teacher_id=id,
        name=data.get("name"),
        employee_code=data.get("employee_code"),
        phone=data.get("phone"),
        is_active=data.get("is_active", True)
    )
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    return {"status": "success"}

# Delete Teacher
@app.delete("/api/admin/teachers/{id}", dependencies=[Depends(verify_admin_api)])
def api_delete_teacher(id: int, db: Session = Depends(get_db)):
    success = crud.delete_teacher(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Teacher record not found.")
    return {"status": "success"}

# Reset Teacher Device Bind
@app.post("/api/admin/teachers/{id}/reset-device", dependencies=[Depends(verify_admin_api)])
def api_reset_device(id: int, db: Session = Depends(get_db)):
    teacher = crud.get_teacher(db, id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    teacher.device_fingerprint = None
    db.commit()
    return {"status": "success"}

# Force manual check-in
@app.post("/api/admin/attendance/force", dependencies=[Depends(verify_admin_api)])
def api_force_attendance(data: dict, db: Session = Depends(get_db)):
    teacher_id = data.get("teacher_id")
    status_val = data.get("status")
    notes = data.get("notes", "Manual Override by Admin")
    
    teacher = crud.get_teacher(db, teacher_id)
    if not teacher:
         raise HTTPException(status_code=404, detail="Teacher not found.")
         
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    crud.mark_attendance(
        db=db,
        teacher_id=teacher.id,
        status=status_val,
        check_in_time=datetime.datetime.now(ist_tz).time() if status_val != "Absent" else None,
        latitude=None,
        longitude=None,
        distance_meters=None,
        device_fingerprint="admin_override",
        is_verified=True,
        verification_notes=notes
    )
    return {"status": "success"}

# Submit Leave request (Admin panel)
@app.post("/api/admin/leaves", dependencies=[Depends(verify_admin_api)])
def api_submit_leave(data: dict, db: Session = Depends(get_db)):
    # Parse dates
    start_date = datetime.datetime.strptime(data.get("start_date"), "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime(data.get("end_date"), "%Y-%m-%d").date()
    
    crud.create_leave(
        db=db,
        teacher_id=data.get("teacher_id"),
        start_date=start_date,
        end_date=end_date,
        leave_type=data.get("leave_type"),
        reason=data.get("reason")
    )
    return {"status": "success"}

# Approve/Reject Leave status
@app.put("/api/admin/leaves/{id}/status", dependencies=[Depends(verify_admin_api)])
def api_update_leave_status(id: int, data: dict, db: Session = Depends(get_db)):
    status_val = data.get("status") # "Approved" or "Rejected"
    crud.update_leave_status(db, id, status_val)
    return {"status": "success"}

# CSV Attendance Export
@app.get("/admin/export/csv", dependencies=[Depends(verify_admin_api)])
def export_attendance_csv(month: str, db: Session = Depends(get_db)):
    try:
        # month format YYYY-MM
        year_val, month_val = map(int, month.split("-"))
        start_date = datetime.date(year_val, month_val, 1)
        # Find end date of that month
        if month_val == 12:
            end_date = datetime.date(year_val + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.date(year_val, month_val + 1, 1) - datetime.timedelta(days=1)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid month format. Expected YYYY-MM.")
        
    # Query all active teachers
    teachers = crud.get_teachers(db)
    
    # Query attendance records in that date range
    records = db.query(models.Attendance).filter(
        models.Attendance.date >= start_date,
        models.Attendance.date <= end_date
    ).all()
    
    # Create CSV memory buffer
    stream = StringIO()
    # Add BOM for Excel UTF-8 display compatibility
    stream.write('\ufeff')
    writer = csv.writer(stream)
    
    # Headers
    writer.writerow([
        "Date", "Employee Code", "Teacher Name", 
        "Check-In Time", "Check-Out Time", "Distance (m)", "Status", 
        "Verified", "Verification Notes"
    ])
    
    # Populate rows
    for record in sorted(records, key=lambda x: (x.date, x.teacher.name if x.teacher else "")):
        teacher_name = record.teacher.name if record.teacher else "Deleted Teacher"
        emp_code = record.teacher.employee_code if record.teacher else "--"
        checkin_time_str = record.check_in_time.strftime("%I:%M:%S %p") if record.check_in_time else "--"
        checkout_time_str = record.check_out_time.strftime("%I:%M:%S %p") if record.check_out_time else "--"
        distance_str = f"{int(record.distance_meters)}m" if record.distance_meters is not None else "--"
        verified_str = "Yes" if record.is_verified else "No"
        
        writer.writerow([
            record.date.strftime("%Y-%m-%d"),
            emp_code,
            teacher_name,
            checkin_time_str,
            checkout_time_str,
            distance_str,
            record.status,
            verified_str,
            record.verification_notes or ""
        ])
        
    # Prepare streaming response
    response_data = stream.getvalue()
    response = StreamingResponse(iter([response_data]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=VPS_Attendance_{month}.csv"
    return response
