#!/bin/bash

# Virtual Embedded Lab - Multi-OS Installer
# Entry point script - detects OS and runs appropriate installer

set -e

echo "========================================"
echo "Virtual Embedded Lab - Linux Installer"
echo "========================================"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/install"

# Check if os-release exists
if [ ! -f /etc/os-release ]; then
    echo "❌ Error: Cannot detect OS (/etc/os-release not found)"
    exit 1
fi

# Source os-release
. /etc/os-release

echo "🔍 Detected OS: $NAME ($ID)"
echo ""

# Case statement for different OS families
case "$ID" in
    debian|raspbian|ubuntu|linuxmint|pop|elementary|deepin)
        echo "📦 Detected APT-based Linux: $ID"
        echo "   Running Debian/Ubuntu installation..."
        echo ""
        bash "$INSTALL_DIR/install-apt.sh"
        ;;
    fedora|rhel|centos|rocky|almalinux)
        echo "📦 Detected DNF-based Linux: $ID"
        echo "   Running Fedora/RHEL installation..."
        echo ""
        bash "$INSTALL_DIR/install-dnf.sh"
        ;;
    alpine)
        echo "📦 Detected APK-based Linux: $ID"
        echo "   Running Alpine Linux installation..."
        echo ""
        bash "$INSTALL_DIR/install-apk.sh"
        ;;
    arch|manjaro|endeavouros)
        echo "📦 Detected Pacman-based Linux: $ID"
        echo "   Running Arch Linux installation..."
        echo ""
        bash "$INSTALL_DIR/install-pacman.sh"
        ;;
    *)
        echo "❌ Unsupported Linux distribution: $ID"
        echo ""
        echo "Supported distributions:"
        echo "  APT-based:  Debian, Raspberry Pi OS, Ubuntu, Linux Mint, Pop!_OS"
        echo "  DNF-based:  Fedora, RHEL, CentOS, Rocky Linux, AlmaLinux"
        echo "  APK-based:  Alpine Linux"
        echo "  Pacman:     Arch Linux, Manjaro, EndeavourOS"
        exit 1
        ;;
esac

echo ""
echo "========================================"
echo "✅ Installation completed successfully!"
echo "========================================"
