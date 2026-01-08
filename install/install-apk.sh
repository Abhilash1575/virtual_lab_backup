#!/bin/bash

# Virtual Embedded Lab - APK-based Installer
# For: Alpine Linux

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "Installing for APK-based Linux (Alpine)"
echo "========================================"
echo ""

# Get the project directory (parent of install/)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo -e "${YELLOW}Step 1: Updating package index...${NC}"
sudo apk update

echo -e "${YELLOW}Step 2: Installing system dependencies...${NC}"
sudo apk add \
    python3 \
    py3-pip \
    py3-venv \
    python3-dev \
    git \
    avrdude \
    openocd \
    esptool \
    alsa-utils \
    portaudio-dev \
    ffmpeg

# Note: ustreamer might need to be built from source on Alpine
# Check if available
if apk search ustreamer 2>/dev/null | grep -q ustreamer; then
    sudo apk add ustreamer
    echo "  ustreamer installed"
else
    echo "  ⚠️  ustreamer not available in repos (optional, build from source if needed)"
fi

echo -e "${YELLOW}Step 3: Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
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

# Alpine Linux uses OpenRC by default, but systemd is available
# Check if systemd is installed
if [ -d /run/systemd/system ]; then
    # systemd is running
    if [ -d "services" ]; then
        for service_file in services/*.service; do
            if [ -f "$service_file" ]; then
                service_name=$(basename "$service_file")
                echo "  Installing $service_name..."
                sudo cp "$service_file" /etc/systemd/system/
                sudo chmod 644 "/etc/systemd/system/$service_name"
            fi
        done
    fi
    
    sudo systemctl daemon-reload
    sudo systemctl enable vlabiisc.service audio_stream.service mjpg-streamer.service
else
    # Using OpenRC - create OpenRC init scripts instead
    echo "  ⚠️  systemd not detected, using OpenRC"
    echo "  Please configure services manually or install systemd"
    
    # Create a simple start script for OpenRC
    cat > "$PROJECT_DIR/start-openrc.sh" << 'OPENRC_EOF'
#!/bin/bash
# Start script for OpenRC systems
cd /home/pi/virtual_lab
source venv/bin/activate
python app.py
OPENRC_EOF
    chmod +x "$PROJECT_DIR/start-openrc.sh"
    echo "  Created start-openrc.sh for manual startup"
fi

echo -e "${YELLOW}Step 7: Configuring permissions...${NC}"
# On Alpine, dialout group might be different or not exist
if getent group dialout > /dev/null 2>&1; then
    sudo usermod -a -G dialout $USER
else
    echo "  ⚠️  dialout group not found, serial access may need manual configuration"
fi

echo -e "${YELLOW}Step 8: Fixing ALSA config for venv...${NC}"
# Create ALSA config directory for virtual environment
sudo mkdir -p /tmp/vendor/share/alsa
sudo cp -r /usr/share/alsa/* /tmp/vendor/share/alsa/

echo ""
echo "========================================"
echo "✅ APK installation completed!"
echo "========================================"
echo ""
echo "To start the server (systemd):"
echo "  sudo systemctl start vlabiisc"
echo ""
echo "To start the server (OpenRC):"
echo "  cd /home/pi/virtual_lab && ./start-openrc.sh"
echo ""
echo "To check status:"
echo "  sudo systemctl status vlabiisc"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u vlabiisc -f"
echo ""
echo -e "${YELLOW}Note: Please reboot for serial port permissions to take effect${NC}"
echo "  sudo reboot"
