#!/bin/bash

# Virtual Embedded Lab - Pacman-based Installer
# For: Arch Linux, Manjaro, EndeavourOS, etc.

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "Installing for Pacman-based Linux (Arch)"
echo "========================================"
echo ""

# Get the project directory (parent of install/)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo -e "${YELLOW}Step 1: Updating package database...${NC}"
sudo pacman -Sy --noconfirm

echo -e "${YELLOW}Step 2: Installing system dependencies...${NC}"
sudo pacman -S --noconfirm \
    python-pip \
    python-virtualenv \
    python \
    base-devel \
    git \
    avrdude \
    openocd \
    esptool \
    alsa-utils \
    portaudio \
    ffmpeg

# Note: ustreamer is in AUR, check if available
if pacman -Qs ustreamer > /dev/null 2>&1; then
    echo "  ustreamer installed"
elif command -v yay > /dev/null 2>&1; then
    echo "  Installing ustreamer from AUR..."
    yay -S --noconfirm ustreamer
else
    echo "  ⚠️  ustreamer not in repos (optional, install from AUR if needed)"
fi

echo -e "${YELLOW}Step 3: Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python -m venv venv
fi
source venv/bin/activate

echo -e "${YELLOW}Step 4: Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

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
# On Arch, serial ports are usually in uucp group (not dialout)
if getent group uucp > /dev/null 2>&1; then
    sudo usermod -a -G uucp $USER
    echo "  Added user to uucp group for serial port access"
elif getent group dialout > /dev/null 2>&1; then
    sudo usermod -a -G dialout $USER
    echo "  Added user to dialout group for serial port access"
else
    echo "  ⚠️  No serial group found, serial access may need manual configuration"
fi

echo -e "${YELLOW}Step 8: Fixing ALSA config for venv...${NC}"
# Create ALSA config directory for virtual environment
sudo mkdir -p /tmp/vendor/share/alsa
sudo cp -r /usr/share/alsa/* /tmp/vendor/share/alsa/

echo ""
echo "========================================"
echo "✅ Pacman installation completed!"
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
