#!/bin/bash

# Virtual Lab Installation Script
# Run this script on a fresh Raspberry Pi to set up the virtual lab

set -e

echo "========================================"
echo "Virtual Lab Installation Script"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
    ffmpeg

echo -e "${YELLOW}Step 3: Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo -e "${YELLOW}Step 4: Installing Python dependencies...${NC}"
# Fix pip if it's broken in venv
python3 -m ensurepip --upgrade || python3 -m pip install --upgrade pip
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${YELLOW}Step 5: Creating required directories...${NC}"
mkdir -p uploads
mkdir -p default_fw
mkdir -p static/sop

echo -e "${YELLOW}Step 6: Setting up systemd service...${NC}"
# Create systemd service file (vlabiisc.service)
cat > vlabiisc.service << 'EOF'
[Unit]
Description=Virtual Embedded Lab
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/virtual_lab
ExecStart=/home/pi/virtual_lab/venv/bin/python app.py
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Copy service file to systemd directory
sudo cp vlabiisc.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/vlabiisc.service

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable vlabiisc.service

echo -e "${YELLOW}Step 7: Configuring permissions...${NC}"
sudo usermod -a -G dialout $USER

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Installation completed successfully!${NC}"
echo -e "${GREEN}========================================"
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
