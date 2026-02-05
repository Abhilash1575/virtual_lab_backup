# Virtual Embedded Lab - Complete Remote Laboratory Platform

A comprehensive Flask-based web application for remote access to embedded systems laboratories with enterprise-grade features including UPS HAT integration, secure authentication, experiment booking, and real-time power management.

## 🌟 Key Features

### 🔋 **UPS HAT Integration & Power Management**
- **Automatic UPS Setup**: EEPROM configuration, I2C communication, GPIO control
- **Battery Monitoring**: Real-time voltage, capacity, and low-voltage shutdown
- **Power Loss Detection**: AC power monitoring with automatic alerts
- **Session-Based Power Control**: GPIO-controlled relays for experiment power supply
- **Power Conservation**: Automatic power-off when sessions end

### 🔐 **Enterprise Security & Authentication**
- **User Database**: SQLAlchemy with secure user management
- **Password Policies**: Complexity requirements, 90-day expiry, account lockout
- **Role-Based Access**: Admin and user roles with protected routes
- **HTTPS Support**: SSL/TLS encryption when certificates are available
- **Session Enforcement**: Single-user sessions, concurrent access prevention

### 📧 **Communication & Notifications**
- **Email Integration**: SMTP-based notifications for bookings and reminders
- **Calendar Integration**: Session reminders and scheduling alerts
- **Real-time WebSocket**: Live updates for power status, sensor data, flashing progress

### 🏗️ **Advanced Experiment Management**
- **Experiment Booking**: Time-slot based reservations with conflict prevention
- **Admin Dashboard**: Complete system oversight and device management
- **Remote OTA Updates**: Over-the-air system and firmware updates
- **DSP Programming**: Dual-mode flashing (RAM for testing, Flash for persistence)

### 🔌 **Enhanced Hardware Support**
- **Multi-board Support**: ESP32, ESP8266, Arduino, ATtiny, STM32, MSP430, TIVA, TMS320F28377S
- **Dual DSP Flashing**: RAM mode (volatile) and Flash mode (persistent across power cycles)
- **Real-time Serial Communication**: Bidirectional device communication
- **WebRTC Streaming**: Live audio and video from laboratory environment
- **Sensor Visualization**: Real-time charts with WebSocket data streaming

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

### 🚀 Single-Command Complete Setup (Recommended)

For a completely automated installation on any fresh Raspberry Pi:

```bash
wget -O install_vlab.sh https://raw.githubusercontent.com/Abhilash1575/virtual_lab/main/install_all.sh && chmod +x install_vlab.sh && ./install_vlab.sh
```

**Alternative: Clone and Install**

If you prefer to clone the repository first:

```bash
git clone https://github.com/Abhilash1575/virtual_lab.git
cd virtual_lab
./install_all.sh
```

This single command will:
- ✅ Clone the repository
- ✅ Detect and install system dependencies
- ✅ Set up Python virtual environment
- ✅ Install all Python packages
- ✅ Configure UPS HAT (optional)
- ✅ Initialize database with admin user
- ✅ Set up systemd services
- ✅ Generate secure configuration

### 🔧 Advanced Installation Options

#### Automated Multi-OS Installation

For manual control over the installation process:

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
├── app.py                    # Main Flask application with all features
├── models.py                 # Database models (User, Experiment, Session, etc.)
├── install_all.sh           # 🚀 Single-command complete installer
├── install.sh               # Multi-OS installer entry point
├── setup_ups.sh            # UPS HAT configuration script
├── requirements.txt          # Python dependencies (updated)
├── .env                     # Environment configuration
├── README.md                # This comprehensive documentation
├── venv/                    # Python virtual environment (auto-created)
├── templates/               # HTML templates
│   ├── index.html          # Main experiment interface
│   ├── dashboard.html      # User dashboard
│   ├── login.html          # Authentication
│   ├── admin/              # Admin dashboard templates
│   └── ...
├── static/                  # Static files (CSS, JS, images)
├── uploads/                 # User uploaded firmware files
├── default_fw/             # Default firmware for factory reset
├── x120x/                  # 🔋 UPS HAT scripts and tools
│   ├── bat.py              # Battery monitoring
│   ├── pld.py              # Power loss detection
│   ├── qtx120x.py          # Comprehensive UPS GUI
│   └── ...
├── dsp/                    # DSP programming tools
│   ├── flash_tool.py       # Enhanced DSP flasher (RAM/Flash modes)
│   ├── sci_flash_pi.py     # Serial communication interface
│   └── ...
├── install/                # Installation scripts
│   ├── install.sh          # OS detection script
│   ├── install-apt.sh      # Debian/Ubuntu installer
│   └── ...
├── services/               # Systemd service files
├── Audio/                  # WebRTC audio streaming
├── my_webrtc/             # Additional WebRTC modules
└── lm4tools/              # Legacy flash tools
```

## Usage

### 🚀 Getting Started

1. **Access the Platform**: Navigate to `http://YOUR_PI_IP:5000`
2. **Initial Setup**: Login with admin credentials (see installation output)
3. **User Registration**: Create user accounts or register new users
4. **Configure Experiments**: Set up available experiments via admin dashboard
5. **Start Experimenting**: Book time slots and begin remote lab sessions

### 👤 User Workflow

1. **Login** → Access user dashboard
2. **Book Experiment** → Select time slot (conflict prevention active)
3. **Start Session** → Automatic power-on and session initialization
4. **Connect Hardware** → Serial communication with microcontroller
5. **Flash Firmware** → Choose RAM (testing) or Flash (persistent) mode
6. **Monitor & Control** → Real-time sensor data and power status
7. **End Session** → Automatic power-off and cleanup

### 👨‍💼 Admin Workflow

1. **System Monitoring** → View device status, active sessions, system health
2. **User Management** → Create/edit users, manage roles and permissions
3. **Experiment Management** → Configure available experiments and settings
4. **OTA Updates** → Deploy system/firmware updates remotely
5. **Email Configuration** → Set up notification preferences

## Hardware Support

### 🎛️ Supported Boards

| Board | Flashing Tool | RAM Mode | Flash Mode | Special Features |
|-------|---------------|----------|------------|------------------|
| **TMS320F28377S** | Enhanced DSP Flasher | ✅ Yes | ✅ Yes | Dual-mode with persistence |
| ESP32 | esptool.py | ✅ Yes | ✅ Yes | WiFi/BT, multi-core |
| ESP8266 | esptool.py | ✅ Yes | ✅ Yes | WiFi, cost-effective |
| Arduino | avrdude | ✅ Yes | ✅ Yes | Beginner-friendly |
| ATtiny | avrdude | ✅ Yes | ✅ Yes | Low-power, small form |
| STM32 | openocd | ✅ Yes | ✅ Yes | ARM Cortex-M, powerful |
| MSP430 | mspdebug | ✅ Yes | ✅ Yes | Ultra-low power |
| TIVA (TM4C) | openocd | ✅ Yes | ✅ Yes | ARM Cortex-M4F |

### 🔋 UPS HAT Integration

| Feature | Description | Status |
|---------|-------------|--------|
| **EEPROM Config** | Automatic power settings | ✅ Automated |
| **I2C Communication** | Real-time battery monitoring | ✅ Working |
| **GPIO Power Control** | Session-based power management | ✅ Implemented |
| **Power Loss Detection** | AC failure alerts | ✅ Active |
| **Low Voltage Shutdown** | Safe system protection | ✅ 3.00V threshold |

## API Endpoints

### 🔐 Authentication
- `GET/POST /login` - User login
- `GET/POST /register` - User registration
- `POST /logout` - User logout
- `GET/POST /change_password` - Password management

### 📊 Dashboard & Admin
- `GET /dashboard` - User dashboard
- `GET /admin` - Admin dashboard
- `GET /admin/devices` - Device management
- `GET /admin/users` - User management
- `GET /admin/experiments` - Experiment configuration
- `GET/POST /admin/ota` - Remote updates
- `GET /admin/system_status` - System monitoring

### 🧪 Experiments & Booking
- `GET /experiments` - Available experiments
- `GET/POST /book_experiment/<id>` - Time slot booking
- `GET /my_bookings` - User's bookings
- `GET /available_slots/<id>` - Check availability
- `GET /experiment` - Active experiment session

### 🔌 Hardware Control
- `POST /flash` - Firmware flashing (with Flash/RAM mode)
- `POST /factory_reset` - Restore default firmware
- `GET /ports` - Available serial ports
- `WebSocket /serial` - Real-time serial communication
- `WebSocket /sensor_data` - Live sensor streaming

### 📡 Media & Streaming
- `GET /chart` - Sensor data visualization
- `GET /camera` - Video streaming interface
- `WebSocket /audio` - Audio streaming (WebRTC)

### ⚙️ Session Management
- `POST /add_session` - Create experiment session
- `POST /remove_session` - End experiment session
- `WebSocket /power_status` - Power control updates

## License

MIT License
