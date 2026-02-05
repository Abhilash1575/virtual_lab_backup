#!/bin/bash

# Virtual Embedded Lab - APT-based Installer
# For: Debian, Raspberry Pi OS, Ubuntu, Linux Mint, Pop!_OS, etc.

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "Installing for APT-based Linux"
echo "========================================"
echo ""

# Get the project directory (parent of install/)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR=$(dirname "$PROJECT_DIR")
REAL_USER=$(basename "$HOME_DIR")
cd "$PROJECT_DIR"

echo -e "${YELLOW}Step 1: Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

echo -e "${YELLOW}Step 2: Installing system dependencies...${NC}"
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    avrdude \
    openocd \
    esptool \
    alsa-utils \
    libportaudio2 \
    ffmpeg \
    ustreamer \
    wget \
    i2c-tools \
    python3-smbus \
    python3-libgpiod \
    raspi-config \
    sqlite3 \
    nginx \
    certbot \
    python3-certbot-nginx

echo -e "${YELLOW}Step 2.5: Installing UniFlash for TI TMS320F28377S...${NC}"
# Note: UniFlash requires manual installation from TI website as it's not directly downloadable on ARM systems
echo -e "${YELLOW}⚠️  UniFlash is only available for x86-64 Linux systems${NC}"
echo -e "${YELLOW}Please download and install UniFlash on an x86-64 system from: https://www.ti.com/tool/download/UNIFLASH${NC}"
echo -e "${YELLOW}For ARM systems (like Raspberry Pi), use cross-platform development:${NC}"
echo -e "${YELLOW}  1. Develop code on x86-64 machine${NC}"
echo -e "${YELLOW}  2. Build .out files with CCS${NC}"
echo -e "${YELLOW}  3. Flash using UniFlash on x86-64${NC}"
echo -e "${YELLOW}  4. Deploy to ARM system for runtime${NC}"

echo -e "${YELLOW}Step 3: Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo -e "${YELLOW}Step 4: Installing Python dependencies...${NC}"
if [ ! -f "venv/bin/pip" ]; then
    curl -sSL https://bootstrap.pypa.io/get-pip.py | ./venv/bin/python
fi
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements.txt

echo -e "${YELLOW}Step 5: Creating required directories...${NC}"
mkdir -p uploads
mkdir -p default_fw
mkdir -p static/sop

echo -e "${YELLOW}Step 6: Setting up systemd services...${NC}"

# Copy service files from services folder
if [ -d "services" ]; then
    for service_file in services/*.service; do
        if [ -f "$service_file" ]; then
            service_name=$(basename "$service_file")
            echo "  Installing $service_name..."
            sudo cp "$service_file" /etc/systemd/system/
            # Replace placeholders with actual values
            sudo sed -i "s|/home/pi|$HOME_DIR|g" "/etc/systemd/system/$service_name"
            sudo sed -i "s|User=%i|User=$REAL_USER|g" "/etc/systemd/system/$service_name"
            sudo sed -i "s|%h|$HOME_DIR|g" "/etc/systemd/system/$service_name"
            sudo chmod 644 "/etc/systemd/system/$service_name"
        fi
    done
else
    echo -e "${RED}Error: services folder not found!${NC}"
    exit 1
fi

# Reload systemd and enable all services
sudo systemctl daemon-reload
sudo systemctl enable vlabiisc.service audio_stream.service mjpg-streamer.service

echo -e "${YELLOW}Step 7: Configuring permissions...${NC}"
sudo usermod -a -G dialout $USER

echo -e "${YELLOW}Step 8: Fixing ALSA config for venv...${NC}"
# Create ALSA config directory for virtual environment
sudo mkdir -p /tmp/vendor/share/alsa
sudo cp -r /usr/share/alsa/* /tmp/vendor/share/alsa/

echo ""
echo "========================================"
echo "✅ APT installation completed!"
echo "========================================"
echo ""
echo "To start the server:"
echo "  sudo systemctl start vlabiisc"
echo ""
echo "To check status:"
echo "  sudo systemctl status vlabiisc"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u vlabiisc -f"
echo ""
echo -e "${YELLOW}Note: Please reboot for serial port permissions to take effect${NC}"
echo "  sudo reboot"
