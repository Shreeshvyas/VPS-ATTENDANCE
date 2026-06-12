from sqlalchemy import Column, Integer, String, Float, Boolean, Date, Time, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime
from database import Base

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    device_fingerprint = Column(String, nullable=True)  # Lock to teacher's primary device
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    attendances = relationship("Attendance", back_populates="teacher")
    leaves = relationship("Leave", back_populates="teacher")

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    date = Column(Date, index=True, default=datetime.date.today, nullable=False)
    check_in_time = Column(Time, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    distance_meters = Column(Float, nullable=True)
    status = Column(String, nullable=False)  # "Present", "Late", "Absent", "On Leave"
    device_fingerprint = Column(String, nullable=True)
    is_verified = Column(Boolean, default=True)
    verification_notes = Column(String, nullable=True)  # Flags like "Bypassed GPS", "Duplicate Device", etc.
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    teacher = relationship("Teacher", back_populates="attendances")

class Leave(Base):
    __tablename__ = "leaves"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    leave_type = Column(String, nullable=False)  # "Casual", "Medical", "Earned", "Other"
    status = Column(String, default="Pending", nullable=False)  # "Pending", "Approved", "Rejected"
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    teacher = relationship("Teacher", back_populates="leaves")

class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True)
    school_name = Column(String, default="VPS High School")
    school_latitude = Column(Float, default=24.12345)
    school_longitude = Column(Float, default=77.12345)
    allowed_radius_meters = Column(Float, default=100.0)
    check_in_start_time = Column(String, default="07:30")  # HH:MM format
    late_threshold_time = Column(String, default="08:30")  # HH:MM format
    check_in_end_time = Column(String, default="10:00")    # HH:MM format
    totp_secret = Column(String, default="JBSWY3DPEHPK3PXP")  # Default base32 key
    enable_dynamic_qr = Column(Boolean, default=False)

class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
