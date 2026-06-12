#!/bin/bash

# VPS Attendance System - Automated AWS Ubuntu Deployment Script
# Targets: Ubuntu 22.04 LTS / 24.04 LTS

set -e

DOMAIN="vyaspublicschool.in"
DB_NAME="vps_attendance"
DB_USER="vps_admin"
DB_PASS="vps_secure_db_pass_2026"

echo "========================================================"
echo "Starting VPS Attendance deployment on Ubuntu..."
echo "========================================================"

# 1. Update system packages
echo "Updating apt repositories..."
sudo apt update -y
sudo apt upgrade -y

# 2. Install Python, PostgreSQL, Nginx, Certbot
echo "Installing system dependencies..."
sudo apt install -y python3-pip python3-venv python3-dev postgresql postgresql-contrib nginx certbot python3-certbot-nginx git curl libpq-dev python3.12 python3.12-venv python3.12-dev

# 3. Setup PostgreSQL database and user
echo "Configuring PostgreSQL database..."
sudo -i -u postgres psql -c "CREATE DATABASE $DB_NAME;" || echo "DB already exists"
sudo -i -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" || echo "User already exists"
sudo -i -u postgres psql -c "ALTER ROLE $DB_USER SET client_encoding TO 'utf8';"
sudo -i -u postgres psql -c "ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';"
sudo -i -u postgres psql -c "ALTER ROLE $DB_USER SET timezone TO 'UTC';"
sudo -i -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
# Grant schema permissions for SQLAlchemy
sudo -i -u postgres psql -d $DB_NAME -c "GRANT ALL ON SCHEMA public TO $DB_USER;"

# 4. Configure Python virtual environment
echo "Setting up Python virtual environment..."
if command -v python3.12 &> /dev/null; then
    PYTHON_EXE="python3.12"
elif command -v python3.10 &> /dev/null; then
    PYTHON_EXE="python3.10"
else
    PYTHON_EXE="python3"
fi

echo "Using Python: $PYTHON_EXE"
# Clean up old virtual env if exists
rm -rf .venv
$PYTHON_EXE -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Create environment file (.env) for database URL
echo "Writing environment variables..."
cat << EOF > .env
DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME
PYTHON_VERSION=3.11.9
EOF

# 6. Setup FastAPI Systemd background service
echo "Creating systemd service configuration..."
sudo bash -c "cat << EOF > /etc/systemd/system/vps-attendance.service
[Unit]
Description=FastAPI VPS Attendance Application
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
Environment=PATH=$(pwd)/.venv/bin:/usr/bin:/usr/local/bin
EnvironmentFile=$(pwd)/.env

[Install]
WantedBy=multi-user.target
EOF"

# Enable and start the service
echo "Starting FastAPI background service..."
sudo systemctl daemon-reload
sudo systemctl enable vps-attendance.service
sudo systemctl restart vps-attendance.service

# 7. Configure Nginx reverse proxy
echo "Configuring Nginx Reverse Proxy..."
sudo bash -c "cat << EOF > /etc/nginx/sites-available/vps-attendance
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF"

# Enable Nginx config and disable default
sudo ln -sf /etc/nginx/sites-available/vps-attendance /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx and reload
sudo nginx -t
sudo systemctl restart nginx

echo "========================================================"
echo "FastAPI & Nginx deployment successful!"
echo "========================================================"
echo "Note: Before running SSL setup, ensure you have pointed your domain DNS records to this IP!"
echo "To secure your site with HTTPS, run:"
echo "sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo "========================================================"
