from sqlalchemy.orm import Session
import datetime
import models
import bcrypt

def get_teacher_by_code(db: Session, employee_code: str):
    return db.query(models.Teacher).filter(models.Teacher.employee_code == employee_code, models.Teacher.is_active == True).first()

def get_teacher(db: Session, teacher_id: int):
    return db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()

def get_teachers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Teacher).order_by(models.Teacher.name).offset(skip).limit(limit).all()

def create_teacher(db: Session, name: str, employee_code: str, phone: str = None):
    db_teacher = models.Teacher(name=name, employee_code=employee_code, phone=phone)
    db.add(db_teacher)
    db.commit()
    db.refresh(db_teacher)
    return db_teacher

def update_teacher(db: Session, teacher_id: int, name: str, employee_code: str, phone: str = None, is_active: bool = True):
    db_teacher = get_teacher(db, teacher_id)
    if db_teacher:
        db_teacher.name = name
        db_teacher.employee_code = employee_code
        db_teacher.phone = phone
        db_teacher.is_active = is_active
        db.commit()
        db.refresh(db_teacher)
    return db_teacher

def delete_teacher(db: Session, teacher_id: int):
    db_teacher = get_teacher(db, teacher_id)
    if db_teacher:
        # Instead of deleting, we can deactivate them, but actual deletion of records is fine if needed
        # Let's delete attendance & leaves as well to prevent foreign key issues, or just delete the teacher
        db.query(models.Attendance).filter(models.Attendance.teacher_id == teacher_id).delete()
        db.query(models.Leave).filter(models.Leave.teacher_id == teacher_id).delete()
        db.delete(db_teacher)
        db.commit()
        return True
    return False

def get_attendance_for_date(db: Session, date_val: datetime.date):
    return db.query(models.Attendance).filter(models.Attendance.date == date_val).all()

def get_attendance_by_teacher_and_date(db: Session, teacher_id: int, date_val: datetime.date):
    return db.query(models.Attendance).filter(
        models.Attendance.teacher_id == teacher_id,
        models.Attendance.date == date_val
    ).first()

def mark_attendance(
    db: Session,
    teacher_id: int,
    status: str,
    check_in_time: datetime.time = None,
    latitude: float = None,
    longitude: float = None,
    distance_meters: float = None,
    device_fingerprint: str = None,
    is_verified: bool = True,
    verification_notes: str = None
):
    # Check if attendance already exists for today
    today = datetime.date.today()
    db_attendance = get_attendance_by_teacher_and_date(db, teacher_id, today)
    
    if db_attendance:
        # Update existing attendance
        db_attendance.status = status
        db_attendance.check_in_time = check_in_time or datetime.datetime.now().time()
        db_attendance.latitude = latitude
        db_attendance.longitude = longitude
        db_attendance.distance_meters = distance_meters
        db_attendance.device_fingerprint = device_fingerprint
        db_attendance.is_verified = is_verified
        db_attendance.verification_notes = verification_notes
    else:
        # Create new attendance record
        db_attendance = models.Attendance(
            teacher_id=teacher_id,
            date=today,
            check_in_time=check_in_time or datetime.datetime.now().time(),
            status=status,
            latitude=latitude,
            longitude=longitude,
            distance_meters=distance_meters,
            device_fingerprint=device_fingerprint,
            is_verified=is_verified,
            verification_notes=verification_notes
        )
        db.add(db_attendance)
        
    db.commit()
    db.refresh(db_attendance)
    return db_attendance

def get_leaves(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Leave).order_by(models.Leave.start_date.desc()).offset(skip).limit(limit).all()

def get_leaves_active_on_date(db: Session, date_val: datetime.date):
    # Returns approved leaves that overlap with date_val
    return db.query(models.Leave).filter(
        models.Leave.status == "Approved",
        models.Leave.start_date <= date_val,
        models.Leave.end_date >= date_val
    ).all()

def create_leave(db: Session, teacher_id: int, start_date: datetime.date, end_date: datetime.date, leave_type: str, reason: str = None):
    db_leave = models.Leave(
        teacher_id=teacher_id,
        start_date=start_date,
        end_date=end_date,
        leave_type=leave_type,
        reason=reason,
        status="Pending"
    )
    db.add(db_leave)
    db.commit()
    db.refresh(db_leave)
    return db_leave

def update_leave_status(db: Session, leave_id: int, status: str):
    db_leave = db.query(models.Leave).filter(models.Leave.id == leave_id).first()
    if db_leave:
        db_leave.status = status
        
        # If approved, we can pre-populate attendance records as "On Leave" for the overlapping days
        if status == "Approved":
            # Loop from start_date to end_date and mark attendance as "On Leave"
            current_date = db_leave.start_date
            while current_date <= db_leave.end_date:
                # Only mark for today or future if needed, or retrospectively. Let's do it for all days in the range
                # if the attendance record doesn't already exist or exists as Absent.
                existing = db.query(models.Attendance).filter(
                    models.Attendance.teacher_id == db_leave.teacher_id,
                    models.Attendance.date == current_date
                ).first()
                
                if not existing:
                    new_att = models.Attendance(
                        teacher_id=db_leave.teacher_id,
                        date=current_date,
                        status="On Leave",
                        is_verified=True,
                        verification_notes="Auto-marked: Approved Leave"
                    )
                    db.add(new_att)
                elif existing.status in ["Absent", "Present", "Late"]:
                    # Update status to "On Leave" if it's not a real Present/Late checkin
                    if existing.status == "Absent":
                        existing.status = "On Leave"
                        existing.verification_notes = "Auto-updated: Approved Leave"
                
                current_date += datetime.timedelta(days=1)
                
        db.commit()
        db.refresh(db_leave)
    return db_leave

def get_system_config(db: Session):
    config = db.query(models.SystemConfig).first()
    if not config:
        # Create initial default configuration
        config = models.SystemConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config

def update_system_config(
    db: Session,
    school_name: str,
    school_latitude: float,
    school_longitude: float,
    allowed_radius_meters: float,
    check_in_start_time: str,
    late_threshold_time: str,
    check_in_end_time: str,
    totp_secret: str = None,
    enable_dynamic_qr: bool = True
):
    config = get_system_config(db)
    config.school_name = school_name
    config.school_latitude = school_latitude
    config.school_longitude = school_longitude
    config.allowed_radius_meters = allowed_radius_meters
    config.check_in_start_time = check_in_start_time
    config.late_threshold_time = late_threshold_time
    config.check_in_end_time = check_in_end_time
    config.enable_dynamic_qr = enable_dynamic_qr
    if totp_secret:
        config.totp_secret = totp_secret
    db.commit()
    db.refresh(config)
    return config

def get_admin_by_username(db: Session, username: str):
    return db.query(models.Admin).filter(models.Admin.username == username).first()

def create_admin(db: Session, username: str, password_raw: str):
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password_raw.encode('utf-8'), salt).decode('utf-8')
    db_admin = models.Admin(username=username, password_hash=password_hash)
    db.add(db_admin)
    db.commit()
    db.refresh(db_admin)
    return db_admin

def verify_admin_password(password_raw: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password_raw.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False
