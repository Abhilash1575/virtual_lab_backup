#!/bin/bash
# Automated UPS HAT Setup Script for Raspberry Pi 5

echo "========================================"
echo "UPS HAT Automated Setup Starting..."
echo "========================================"

# Update system
echo "Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Install required dependencies
echo "Installing required dependencies..."
sudo apt-get install python3-pip python3-smbus python3-libgpiod i2c-tools -y

# Enable I2C
echo "Enabling I2C interface..."
sudo raspi-config nonint do_i2c 0

# Clone UPS repository if not exists
if [ ! -d "x120x" ]; then
    echo "Cloning UPS repository..."
    git clone https://github.com/suptronics/x120x.git
else
    echo "UPS repository already exists."
fi

# Configure EEPROM for UPS
echo "Configuring EEPROM for UPS..."
sudo rpi-eeprom-config --apply << EOF
[all]
BOOT_UART=1
POWER_OFF_ON_HALT=1
BOOT_ORDER=0xf461
PSU_MAX_CURRENT=5000
EOF

# Install UPS monitoring service
echo "Installing UPS monitoring service..."
sudo cp x120x/bat.py /usr/local/bin/ups_battery_monitor.py
sudo cp x120x/pld-trixie.py /usr/local/bin/ups_pld_monitor.py

# Create systemd service for battery monitoring
sudo tee /etc/systemd/system/ups-battery-monitor.service > /dev/null << EOF
[Unit]
Description=UPS Battery Monitor
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/ups_battery_monitor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for PLD monitoring
sudo tee /etc/systemd/system/ups-pld-monitor.service > /dev/null << EOF
[Unit]
Description=UPS Power Loss Detection Monitor
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/ups_pld_monitor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
echo "Enabling and starting UPS services..."
sudo systemctl enable ups-battery-monitor.service
sudo systemctl enable ups-pld-monitor.service
sudo systemctl start ups-battery-monitor.service
sudo systemctl start ups-pld-monitor.service

# Test I2C connection
echo "Testing I2C connection..."
echo "Detected I2C devices:"
sudo i2cdetect -y 1

echo "========================================"
echo "UPS HAT Setup Complete!"
echo "Please reboot your Raspberry Pi to apply EEPROM changes."
echo "========================================"