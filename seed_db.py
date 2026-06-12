import datetime
import models
import crud
from database import SessionLocal, engine, Base

def seed_database():
    # Make sure tables exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("Starting database seeding...")
        
        # 1. Seed System Configuration
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
                totp_secret="JBSWY3DPEHPK3PXP" # Base32 TOTP secret key
            )
            db.add(config)
            print("OK: System configurations initialized.")
        else:
            print("OK: System configurations already exist.")
            
        # 2. Seed Default Admin
        admin = db.query(models.Admin).filter(models.Admin.username == "admin").first()
        if not admin:
            crud.create_admin(db, "admin", "adminpassword")
            print("OK: Default admin user created (Username: admin, Password: adminpassword).")
        else:
            print("OK: Admin user 'admin' already exists.")
            
        # 3. Seed Teachers
        teachers_to_seed = [
            {"name": "Ramesh Kumar", "employee_code": "100201", "phone": "9876543210"},
            {"name": "Sunita Sharma", "employee_code": "100202", "phone": "9876543211"},
            {"name": "Anil Verma", "employee_code": "100203", "phone": "9876543212"},
            {"name": "Pooja Patel", "employee_code": "100204", "phone": "9876543213"},
            {"name": "Amit Singh", "employee_code": "100205", "phone": "9876543214"},
        ]
        
        for teacher_data in teachers_to_seed:
            existing = db.query(models.Teacher).filter(models.Teacher.employee_code == teacher_data["employee_code"]).first()
            if not existing:
                crud.create_teacher(db, teacher_data["name"], teacher_data["employee_code"], teacher_data["phone"])
                print(f"OK: Seeded teacher: {teacher_data['name']} (Code: {teacher_data['employee_code']})")
            else:
                print(f"OK: Teacher with code {teacher_data['employee_code']} already exists ({existing.name}).")
                
        # 4. Commit all seeds
        db.commit()
        print("Database seeding completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"ERROR: Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
