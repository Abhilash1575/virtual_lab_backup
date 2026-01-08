# Virtual Lab - Remote Embedded Systems Laboratory

A Flask-based web application for remote access to embedded systems laboratories with support for multiple microcontroller boards, WebRTC audio streaming, and real-time sensor data visualization.

## Supported Operating Systems

The `install.sh` script is designed for **Debian-based Linux distributions only**:

| OS | Compatible | Package Manager | Init System |
|-----|------------|-----------------|-------------|
| Raspberry Pi OS | ✅ Yes | apt | systemd |
| Debian | ✅ Yes | apt | systemd |
| Ubuntu | ✅ Yes | apt | systemd |
| Diet Pi | ✅ Yes | apt | systemd |
| Armbian | ✅ Yes (most) | apt | systemd |
| Fedora | ❌ No | dnf | systemd |
| Alpine Linux | ❌ No | apk | OpenRC/runits |
| Arch Linux | ❌ No | pacman | systemd |
| Windows | ❌ No | - | - |

For non-Debian systems, use **Manual Installation** below.

## Features

- **Multi-board Support**: ESP32, ESP8266, Arduino, ATtiny, STM32, MSP430, TIVA, and more
- **Firmware Flashing**: Flash firmware via web interface using esptool, avrdude, openocd, mspdebug
- **Real-time Serial Communication**: Bidirectional communication with embedded devices
- **Sensor Data Visualization**: Real-time charts with WebSocket support
- **WebRTC Audio Streaming**: Live audio from laboratory environment
- **Session Management**: Time-limited access sessions with secure keys

## Installation

### Automated Multi-OS Installation

The installer automatically detects your Linux distribution and installs the correct packages:

```bash
git clone https://github.com/Abhilash1575/virtual_lab.git
cd virtual_lab
cd install
chmod +x install.sh
./install.sh
```

**Supported Operating Systems:**

| Distribution | Package Manager | Installer Script |
|--------------|-----------------|------------------|
| Raspberry Pi OS | apt | install-apt.sh |
| Debian | apt | install-apt.sh |
| Ubuntu | apt | install-apt.sh |
| Linux Mint | apt | install-apt.sh |
| Pop!_OS | apt | install-apt.sh |
| Fedora | dnf | install-dnf.sh |
| RHEL/CentOS | dnf | install-dnf.sh |
| Rocky Linux | dnf | install-dnf.sh |
| AlmaLinux | dnf | install-dnf.sh |
| Alpine Linux | apk | install-apk.sh |
| Arch Linux | pacman | install-pacman.sh |
| Manjaro | pacman | install-pacman.sh |

### Manual Installation

For any Linux distribution:

```bash
# Install system dependencies (adjust package manager for your distro)
# Debian/Ubuntu:
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev git avrdude openocd esptool libportaudio2 ffmpeg ustreamer

# Fedora:
sudo dnf install -y python3-pip python3-venv python3-devel git avrdude openocd esptool-python portaudio-devel ffmpeg

# Arch:
sudo pacman -S --noconfirm python-pip python-virtualenv python base-devel git avrdude openocd esptool portaudio ffmpeg

# Clone and setup
git clone https://github.com/Abhilash1575/virtual_lab.git
cd virtual_lab

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir -p uploads default_fw static/sop

# Setup systemd service (if using systemd)
sudo cp services/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vlabiisc.service audio_stream.service mjpg-streamer.service
sudo systemctl start vlabiisc

# Add user to serial group
# Debian/Ubuntu/Pi OS:
sudo usermod -a -G dialout $USER
# Arch Linux:
sudo usermod -a -G uucp $USER
```

## Project Structure

```
virtual_lab/
├── app.py                 # Main Flask application
├── install.sh             # Installation script for fresh Pi
├── setup-git.sh          # GitHub repository setup script
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/            # HTML templates
│   ├── homepage.html
│   ├── index.html
│   ├── chart.html
│   └── camera.html
├── static/               # Static files
│   └── sop/             # Standard Operating Procedures PDFs
├── Audio/               # WebRTC audio streaming
│   ├── server.py
│   └── client.html
├── my_webrtc/           # Additional WebRTC modules
│   ├── appp.py
│   └── camera.py
├── default_fw/          # Default firmware files
│   ├── esp32_default.bin
│   ├── arduino_default.hex
│   └── ...
├── uploads/             # User uploaded firmware
├── lm4tools/           # LM4F flash tools
└── firmware_assets/    # Additional firmware assets
```

## Usage

1. Access the web interface at `http://YOUR_PI_IP:5000`
2. Create a session for time-limited access
3. Connect to serial port for your microcontroller
4. Flash firmware or send commands
5. View real-time sensor data on charts

## Supported Boards

| Board | Flash Command |
|-------|--------------|
| ESP32 | esptool.py --chip esp32 --port <port> write_flash 0x10000 <firmware> |
| ESP8266 | esptool.py --port <port> write_flash 0x00000 <firmware> |
| Arduino | avrdude -v -p atmega328p -c arduino -P <port> -b115200 -D -U flash:w:<firmware>:i |
| ATtiny | avrdude -v -p attiny85 -c usbasp -P <port> -U flash:w:<firmware>:i |
| STM32 | openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c "program <firmware> 0x08000000 verify reset exit" |
| TIVA | openocd -f board/ti_ek-tm4c123gxl.cfg -c "program <firmware> verify reset exit" |

## API Endpoints

- `POST /flash` - Flash firmware to board
- `POST /factory_reset` - Restore default firmware
- `GET /ports` - List available serial ports
- `GET /chart` - Sensor data visualization
- `GET /camera` - Camera streaming interface

## License

MIT License
