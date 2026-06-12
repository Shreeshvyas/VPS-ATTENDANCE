#!/usr/bin/env python
import sys
import subprocess

def main():
    args = sys.argv[1:]
    if len(args) > 0 and args[0] == "runserver":
        print("FastAPI System: Redirecting 'manage.py runserver' to Uvicorn dev server...")
        
        host = "0.0.0.0"
        port = "8000"
        
        # Check if user specified custom host/port (e.g. 8080 or 127.0.0.1:8080)
        for arg in args[1:]:
            if ":" in arg:
                host, port = arg.split(":")
            elif arg.isdigit():
                port = arg
                
        try:
            # Try running uvicorn directly in python context
            import uvicorn
            uvicorn.run("main:app", host=host, port=int(port), reload=True)
        except Exception:
            # Fall back to running subprocess uvicorn
            subprocess.run([
                sys.executable, "-m", "uvicorn", 
                "main:app", "--host", host, 
                "--port", port, "--reload"
            ])
            
    elif len(args) > 0 and args[0] == "migrate":
        print("FastAPI System: Redirecting 'manage.py migrate' to database creation and seeding...")
        import seed_db
        seed_db.seed_database()
        
    else:
        print("FastAPI Attendance System - manage.py wrapper")
        print("Available Commands:")
        print("  python manage.py runserver [host:port]  - Boots the FastAPI application")
        print("  python manage.py migrate                - Initializes SQLite tables and seeds test teachers")

if __name__ == "__main__":
    main()
