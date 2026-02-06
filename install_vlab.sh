#!/bin/bash

# Virtual Embedded Lab - Complete Automated Installer
# Single-command setup for new Raspberry Pi systems

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/Abhilash1575/virtual_lab.git"
PROJECT_NAME="virtual_lab"
INSTALL_UPS_HAT=true  # Set to false to skip UPS HAT setup

# Functions
print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${CYAN}           Virtual Embedded Lab - Complete Installer${BLUE}           ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${YELLOW}➤ ${1}${NC}"
}

print_success() {
    echo -e "${GREEN}✓ ${1}${NC}"
}

print_error() {
    echo -e "${RED}✗ ${1}${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ ${1}${NC}"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as a regular user with sudo access."
   exit 1
fi

# Main installation function
main() {
    print_header

    print_info "Starting complete Virtual Lab installation..."
    echo ""

    # Step 1: Clone repository if not already in it
    if [[ ! -d "install" ]] || [[ ! -f "app.py" ]]; then
        print_step "Cloning Virtual Lab repository..."

        # Remove any existing incomplete installation
        if [[ -d "$PROJECT_NAME" ]]; then
            print_info "Removing existing incomplete installation..."
            rm -rf "$PROJECT_NAME"
        fi

        git clone "$REPO_URL" "$PROJECT_NAME"
        cd "$PROJECT_NAME"
        print_success "Repository cloned successfully"
    else
        print_info "Already in Virtual Lab directory, continuing with installation..."
    fi

    # Step 2: Run the automated installer
    print_step "Running system installation..."
    cd install
    chmod +x install.sh
    ./install.sh

    cd ..
    print_success "System installation completed"

    # Step 3: Configure environment
    print_step "Configuring environment settings..."

    if [[ ! -f ".env" ]]; then
        print_error ".env file not found!"
        exit 1
    fi

    # Generate a random secret key
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/your-secret-key-here-change-in-production/$SECRET_KEY/" .env

    print_success "Environment configured with secure settings"

    # Step 4: Optional UPS HAT setup
    if [[ "$INSTALL_UPS_HAT" == "true" ]]; then
        print_step "Setting up UPS HAT (optional)..."
        if [[ -f "setup_ups.sh" ]]; then
            chmod +x setup_ups.sh
            sudo ./setup_ups.sh
            print_success "UPS HAT configured"
        else
            print_info "UPS HAT setup script not found, skipping..."
        fi
    else
        print_info "Skipping UPS HAT setup as requested"
    fi

    # Step 5: Initialize database and create admin user
    print_step "Initializing database..."
    source venv/bin/activate

    # Run database initialization
    python3 -c "
from app import app, db
from models import User, Experiment

with app.app_context():
    db.create_all()

    # Create admin user if not exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@virtuallab.com', role='admin')
        admin.set_password('admin123!@#')  # Default password, should be changed
        db.session.add(admin)

        # Create sample experiments
        experiments = [
            Experiment(name='DSP Signal Processing', description='Learn digital signal processing using TMS320F28377S DSP board', board_type='tms320f28377s', duration_minutes=45),
            Experiment(name='Arduino Microcontroller', description='Basic microcontroller programming and interfacing', board_type='arduino', duration_minutes=30),
            Experiment(name='ESP32 IoT Development', description='Internet of Things development with WiFi and Bluetooth', board_type='esp32', duration_minutes=60),
            Experiment(name='STM32 ARM Cortex-M', description='Advanced microcontroller development with ARM Cortex-M', board_type='stm32', duration_minutes=45)
        ]
        for exp in experiments:
            db.session.add(exp)

        db.session.commit()
        print('Database initialized with admin user and sample experiments')
    "

    print_success "Database initialized"

    # Step 6: Final instructions
    echo ""
    print_success "🎉 Virtual Lab installation completed successfully!"
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${YELLOW}                     ACCESS INFORMATION${CYAN}                      ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║${NC} Admin Login:                                                    ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}   Username: admin                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}   Password: admin123!@#                                        ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC} To start the server:                                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}   cd $PROJECT_NAME                                             ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}   source venv/bin/activate                                     ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}   python3 app.py                                               ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC} Web Interface: http://[YOUR_IP]:5000                        ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC} Admin Dashboard: http://[YOUR_IP]:5000/admin                ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT SECURITY NOTICE:${NC}"
    echo -e "${YELLOW}   • Change the default admin password immediately!${NC}"
    echo -e "${YELLOW}   • Configure email settings in .env for notifications${NC}"
    echo -e "${YELLOW}   • Add SSL certificates for HTTPS (optional)${NC}"
    echo ""
    echo -e "${GREEN}🚀 Ready to start your Virtual Lab!${NC}"
}

# Run main function
main "$@"