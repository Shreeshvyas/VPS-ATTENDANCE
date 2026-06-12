#!/bin/bash

# VPS Multi-Domain Deployment Script
# Targets: Ubuntu 22.04 LTS / 24.04 LTS
# Deploys:
#  1. vyaspublicschool.in -> Django School Website (Port 8001)
#  2. portal.vyaspublicschool.in -> Django School ERP (Port 8002)
#  3. attendance.vyaspublicschool.in -> FastAPI Attendance (Port 8000)

set -e

DOMAIN="vyaspublicschool.in"
DB_NAME="vps_attendance"
DB_USER="vps_admin"
DB_PASS="vps_secure_db_pass_2026"

echo "========================================================"
echo "Starting VPS Multi-Domain Deployment on Ubuntu..."
echo "========================================================"

# 1. Update system packages
echo "Updating apt repositories..."
sudo apt update -y
sudo apt upgrade -y

# 2. Install dependencies
echo "Installing system dependencies..."
sudo apt install -y python3-pip python3-venv python3-dev postgresql postgresql-contrib nginx certbot python3-certbot-nginx git curl libpq-dev

# 3. Setup PostgreSQL database (for Attendance app)
echo "Configuring PostgreSQL database..."
sudo -i -u postgres psql -c "CREATE DATABASE $DB_NAME;" || echo "DB already exists"
sudo -i -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" || echo "User already exists"
sudo -i -u postgres psql -c "ALTER ROLE $DB_USER SET client_encoding TO 'utf8';"
sudo -i -u postgres psql -c "ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';"
sudo -i -u postgres psql -c "ALTER ROLE $DB_USER SET timezone TO 'UTC';"
sudo -i -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -i -u postgres psql -d $DB_NAME -c "GRANT ALL ON SCHEMA public TO $DB_USER;"

# --------------------------------------------------------
# APP 1: FastAPI Attendance System (Port 8000)
# --------------------------------------------------------
echo ">>> Setting up FastAPI Attendance System (Port 8000)..."
ATTENDANCE_DIR="/home/ubuntu/VPS-ATTENDANCE"

# Configure Python virtual environment
cd $ATTENDANCE_DIR
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Create .env for database
cat << EOF > .env
DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME
PYTHON_VERSION=3.11.9
EOF

# Setup systemd service
cat << EOF | sudo tee /etc/systemd/system/vps-attendance.service > /dev/null
[Unit]
Description=FastAPI VPS Attendance Application
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$ATTENDANCE_DIR
ExecStart=$ATTENDANCE_DIR/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
Environment=PATH=$ATTENDANCE_DIR/.venv/bin:/usr/bin:/usr/local/bin
EnvironmentFile=$ATTENDANCE_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

# --------------------------------------------------------
# APP 2: Django School Website (Port 8001)
# --------------------------------------------------------
echo ">>> Setting up Django School Website (Port 8001)..."
WEBSITE_DIR="/home/ubuntu/VPS-WEBSITE"

# Clone if directory doesn't exist
if [ ! -d "$WEBSITE_DIR" ]; then
    git clone https://github.com/Shreeshvyas/VPS-WEBSITE.git $WEBSITE_DIR
else
    cd $WEBSITE_DIR && git pull origin master
fi

cd $WEBSITE_DIR
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# Install Django and Gunicorn (and core requirements if present)
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi
pip install Django gunicorn openpyxl reportlab django-environ

# Run migrations and collect static files
python manage.py migrate
python manage.py collectstatic --noinput
deactivate

# Setup systemd service
cat << EOF | sudo tee /etc/systemd/system/vps-website.service > /dev/null
[Unit]
Description=Django VPS Website Application
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$WEBSITE_DIR
ExecStart=$WEBSITE_DIR/.venv/bin/gunicorn vyas_school_project.wsgi:application --bind 127.0.0.1:8001 --workers 2
Restart=always
Environment=PATH=$WEBSITE_DIR/.venv/bin:/usr/bin:/usr/local/bin

[Install]
WantedBy=multi-user.target
EOF

# --------------------------------------------------------
# APP 3: Django School ERP Portal (Port 8002)
# --------------------------------------------------------
echo ">>> Setting up Django School ERP Portal (Port 8002)..."
PORTAL_DIR="/home/ubuntu/VPHS"

# Clone if directory doesn't exist
if [ ! -d "$PORTAL_DIR" ]; then
    git clone https://github.com/Shreeshvyas/VPHS.git $PORTAL_DIR
else
    cd $PORTAL_DIR && git pull origin master
fi

cd $PORTAL_DIR
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# Install requirements and gunicorn
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi
pip install gunicorn

# Write environment file
cat << EOF > .env
DEBUG=False
SECRET_KEY=django-insecure-jf0=s)2&&aoix=*(hsi#rtip#v^!l3^d+k43u6seh_!n2t5%78
ALLOWED_HOSTS=portal.$DOMAIN
EOF

# Run migrations & collect static files
python manage.py migrate
python manage.py collectstatic --noinput
deactivate

# Setup systemd service
cat << EOF | sudo tee /etc/systemd/system/vps-portal.service > /dev/null
[Unit]
Description=Django VPS ERP Portal Application
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$PORTAL_DIR
ExecStart=$PORTAL_DIR/.venv/bin/gunicorn school_erp.wsgi:application --bind 127.0.0.1:8002 --workers 2
Restart=always
Environment=PATH=$PORTAL_DIR/.venv/bin:/usr/bin:/usr/local/bin

[Install]
WantedBy=multi-user.target
EOF

# --------------------------------------------------------
# SYSTEMD SERVICES ACTIVATION
# --------------------------------------------------------
echo "Activating Background Services..."
sudo systemctl daemon-reload

sudo systemctl enable vps-attendance.service
sudo systemctl restart vps-attendance.service

sudo systemctl enable vps-website.service
sudo systemctl restart vps-website.service

sudo systemctl enable vps-portal.service
sudo systemctl restart vps-portal.service

# --------------------------------------------------------
# NGINX CONFIGURATION
# --------------------------------------------------------
echo "Configuring Nginx reverse proxy routing..."
cat << EOF | sudo tee /etc/nginx/sites-available/vps-attendance > /dev/null
# 1. School Main Website (Port 8001)
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    location /static/ {
        alias $WEBSITE_DIR/staticfiles/;
    }

    location /media/ {
        alias $WEBSITE_DIR/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}

# 2. Teacher Attendance (Port 8000)
server {
    listen 80;
    server_name attendance.$DOMAIN;

    location /static/ {
        alias $ATTENDANCE_DIR/static/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}

# 3. ERP School Portal (Port 8002)
server {
    listen 80;
    server_name portal.$DOMAIN;

    location /static/ {
        alias $PORTAL_DIR/staticfiles/;
    }

    location /media/ {
        alias $PORTAL_DIR/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Link config and disable default
sudo ln -sf /etc/nginx/sites-available/vps-attendance /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Restart Nginx
sudo nginx -t
sudo systemctl restart nginx

echo "========================================================"
echo "Deployment and configuration completed successfully!"
echo "========================================================"
echo "Ensure DNS A Records exist for:"
echo " - $DOMAIN"
echo " - www.$DOMAIN"
echo " - attendance.$DOMAIN"
echo " - portal.$DOMAIN"
echo ""
echo "Then generate SSL for all subdomains by running:"
echo "sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN -d attendance.$DOMAIN -d portal.$DOMAIN"
echo "========================================================"
