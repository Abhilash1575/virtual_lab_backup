#!/bin/bash

# Virtual Embedded Lab - APT-based Installer
# FINAL version (Ubuntu + Raspberry Pi OS compatible)

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

# Get project root directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo -e "${YELLOW}Step 1: Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

echo -e "${YELLOW}Step 2: Installing system dependencies...${NC}"
sudo apt install -y \
    python3 \
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
    ustreamer

echo -e "${YELLOW}Step 3: Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

VENV_PY="$PROJECT_DIR/venv/bin/python"

echo -e "${YELLOW}Step 4: Installing Python dependencies (venv safe)...${NC}"
$VENV_PY -m pip install --upgrade pip
$VENV_PY -m pip install -r requirements.txt

echo -e "${YELLOW}Step 5: Creating required directories...${NC}"
mkdir -p uploads
mkdir -p default_fw
mkdir -p static/sop

echo -e "${YELLOW}Step 6: Setting up systemd services...${NC}"
if [ -d "services" ]; then
    for service_file in services/*.service; do
        service_name=$(basename "$service_file")
        echo "  Installing $service_name..."
        sudo cp "$service_file" /etc/systemd/system/
        sudo chmod 644 "/etc/systemd/system/$service_name"
    done
else
    echo -e "${RED}Error: services folder not found!${NC}"
    exit 1
fi

sudo systemctl daemon-reload
sudo systemctl enable vlabiisc.service audio_stream.service mjpg-streamer.service

echo -e "${YELLOW}Step 7: Configuring permissions...${NC}"
sudo usermod -a -G dialout "$USER"

echo -e "${YELLOW}Step 8: Fixing ALSA config for venv...${NC}"
sudo mkdir -p /tmp/vendor/share/alsa
sudo cp -r /usr/share/alsa/* /tmp/vendor/share/alsa/

echo ""
echo "========================================"
echo "✅ INSTALLATION COMPLETED SUCCESSFULLY"
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
echo -e "${YELLOW}Reboot required for serial permissions${NC}"
echo "  sudo reboot"
