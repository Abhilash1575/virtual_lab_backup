import serial
import time
import sys
import struct
from gpiozero import LED
from serial.tools import list_ports

# --- CONFIGURATION ---
RESET_PIN_GPIO = 17     # GPIO 17 is Physical Pin 11 on the Pi
FLASH_MODE = False      # Default to RAM mode for backward compatibility

def get_serial_port():
    ports = list_ports.comports()
    if not ports:
        print("❌ No serial ports found. Please connect the DSP board.")
        return None

    # Prefer /dev/ttyUSB0 if available
    ttyusb0 = next((p for p in ports if p.device == '/dev/ttyUSB0'), None)
    if ttyusb0:
        port = ttyusb0.device
    else:
        # Fallback to first USB port or any port
        usb_ports = [p for p in ports if 'USB' in p.description.upper() or 'ttyUSB' in p.device]
        if usb_ports:
            port = usb_ports[0].device
        else:
            port = ports[0].device

    print(f"🔌 Auto-detected serial port: {port}")
    return port

def reset_dsp():
    print(f"🔄 Resetting DSP via GPIO {RESET_PIN_GPIO}...")
    
    # Configure the pin. 
    # active_high=False means: .on() will pull it LOW (Resetting the board)
    # initial_value=False means: It starts in the "Released" state (High)
    try:
        reset_pin = LED(RESET_PIN_GPIO, active_high=False, initial_value=False)
        
        reset_pin.on()   # Pulls signal LOW -> Board Resets
        time.sleep(0.2)  # Hold it down for 200ms
        reset_pin.off()  # Release signal HIGH -> Board Wakes up
        
        reset_pin.close() # Release the GPIO resource
        time.sleep(0.5)   # Wait a bit for the DSP to fully wake up
        print("✅ DSP Reset complete.")
        
    except Exception as e:
        print(f"⚠️ Warning: Could not control GPIO. Is the library installed? Error: {e}")
        print("👉 Please press the RESET button manually now.")

def load_to_ram(filename):
    """Load firmware to RAM (existing functionality)"""
    print("🎯 Loading firmware to RAM (volatile memory)...")

    # Get serial port
    PORT = get_serial_port()
    if not PORT:
        return False

    # 1. TRIGGER RESET
    reset_dsp()

    # 2. START LOADING
    print(f"🔌 Opening port {PORT}...")
    try:
        ser = serial.Serial(PORT, 9600, timeout=2)
    except Exception as e:
        print(f"❌ Error opening serial port: {e}")
        return False

    print("Step 2: Performing Autobaud (Sending 'A')...")
    # Send 'A' continuously for a moment to catch the DSP as it wakes up
    ser.write(b'A')

    response = ser.read(1)
    if response == b'A':
        print("✅ DSP Ack received! Connection established.")
    else:
        print(f"❌ Failed. DSP did not reply. Received: {response}")
        print("Check: Is the Reset wire (Pin 11) connected to J6 Pin 56?")
        ser.close()
        return False

    print(f"Step 3: Loading Firmware from {filename}...")
    try:
        with open(filename, 'r') as f:
            # Clean up the file content (removes newlines and garbage chars)
            content = f.read().replace('\n', ' ').replace('\r', ' ')
            tokens = content.split()

            data_bytes = []
            for token in tokens:
                try:
                    # Convert Hex string (e.g. "AA") to Integer (170)
                    data_bytes.append(int(token, 16))
                except ValueError:
                    pass # Skip non-hex garbage

            total = len(data_bytes)
            print(f"Sending {total} bytes to RAM...")

            count = 0
            for val in data_bytes:
                ser.write(bytes([val]))
                count += 1
                if count % 100 == 0:
                     sys.stdout.write(f"\rProgress: {int(count/total*100)}%")
                     sys.stdout.flush()

    except FileNotFoundError:
        print(f"❌ Error: File '{filename}' not found.")
        ser.close()
        return False

    print("\n✅ RAM Load Complete! Program will run until power cycle.")
    ser.close()
    return True

def flash_to_memory(filename):
    """Flash firmware to Flash memory (persistent across power cycles)"""
    print("💾 Flashing firmware to Flash memory (persistent)...")
    print("⚠️  This will overwrite existing flash content!")

    # Get serial port
    PORT = get_serial_port()
    if not PORT:
        return False

    # Load firmware data
    try:
        with open(filename, 'r') as f:
            content = f.read().replace('\n', ' ').replace('\r', ' ')
            tokens = content.split()

            data_bytes = []
            for token in tokens:
                try:
                    data_bytes.append(int(token, 16))
                except ValueError:
                    pass # Skip non-hex garbage

    except FileNotFoundError:
        print(f"❌ Error: File '{filename}' not found.")
        return False

    total = len(data_bytes)
    print(f"📏 Firmware size: {total} bytes")

    # For TMS320F28377S, we need to use a special flash programming sequence
    # This typically involves:
    # 1. Entering flash programming mode
    # 2. Erasing flash sectors
    # 3. Programming flash sectors
    # 4. Verifying the programmed data

    print("🔌 Opening port for Flash programming...")
    try:
        ser = serial.Serial(PORT, 115200, timeout=5)  # Higher baud rate for flash programming
    except Exception as e:
        print(f"❌ Error opening serial port: {e}")
        return False

    try:
        # Step 1: Enter Flash Programming Mode
        print("Step 1: Entering Flash Programming Mode...")
        # Send special command sequence to enter flash mode
        # This is DSP-specific and may need adjustment based on the exact DSP model
        enter_flash_cmd = b'FLASH_MODE\x00'  # Custom command
        ser.write(enter_flash_cmd)

        response = ser.read(4)
        if response != b'OK\x00\x00':
            print(f"❌ Failed to enter flash mode. Response: {response}")
            ser.close()
            return False

        print("✅ Flash mode entered successfully.")

        # Step 2: Erase Flash Sectors
        print("Step 2: Erasing Flash sectors...")
        # Calculate number of sectors needed (assuming 4KB sectors)
        sector_size = 4096
        num_sectors = (total + sector_size - 1) // sector_size  # Ceiling division

        for sector in range(num_sectors):
            erase_cmd = struct.pack('<I', 0xEF000000 | sector)  # Erase command
            ser.write(erase_cmd)
            response = ser.read(4)
            if response != b'EROK':
                print(f"❌ Failed to erase sector {sector}. Response: {response}")
                ser.close()
                return False

        print(f"✅ Erased {num_sectors} flash sectors.")

        # Step 3: Program Flash Sectors
        print("Step 3: Programming Flash memory...")
        address = 0x08000000  # Starting flash address (adjust as needed)

        chunk_size = 256  # Program in chunks
        for i in range(0, total, chunk_size):
            chunk = data_bytes[i:i+chunk_size]
            chunk_len = len(chunk)

            # Send program command with address and data
            prog_cmd = struct.pack('<II', 0xPF000000 | chunk_len, address + i)
            ser.write(prog_cmd + bytes(chunk))

            response = ser.read(4)
            if response != b'PROK':
                print(f"❌ Failed to program chunk at address 0x{address + i:08X}. Response: {response}")
                ser.close()
                return False

            # Progress update
            progress = int((i + chunk_len) / total * 100)
            sys.stdout.write(f"\rProgress: {progress}%")
            sys.stdout.flush()

        print("\n✅ Flash programming complete.")

        # Step 4: Verify Flash Content
        print("Step 4: Verifying Flash content...")
        for i in range(0, total, chunk_size):
            chunk = data_bytes[i:i+chunk_size]
            chunk_len = len(chunk)

            # Send verify command
            verify_cmd = struct.pack('<II', 0xVF000000 | chunk_len, address + i)
            ser.write(verify_cmd)

            response = ser.read(chunk_len)
            if response != bytes(chunk):
                print(f"❌ Verification failed at address 0x{address + i:08X}")
                ser.close()
                return False

        print("✅ Flash verification successful!")

        # Step 5: Exit Flash Programming Mode
        print("Step 5: Exiting Flash Programming Mode...")
        exit_flash_cmd = b'FLASH_EXIT\x00'
        ser.write(exit_flash_cmd)

        response = ser.read(4)
        if response != b'EXIT':
            print(f"⚠️  Warning: Flash exit response unexpected: {response}")

        print("✅ Flash programming completed successfully!")
        print("💡 The program will persist across power cycles.")

    except Exception as e:
        print(f"❌ Error during flash programming: {e}")
        ser.close()
        return False

    ser.close()
    return True

def send_firmware(filename):
    """Main firmware sending function - routes to RAM or Flash based on global setting"""
    if FLASH_MODE:
        return flash_to_memory(filename)
    else:
        return load_to_ram(filename)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 flash_tool.py [--flash] <your_file.txt>")
        print("  --flash    Flash to Flash memory (persistent)")
        print("  (default)  Load to RAM only (volatile)")
        sys.exit(1)

    # Parse command line arguments
    global FLASH_MODE
    filename = None

    for arg in sys.argv[1:]:
        if arg == '--flash':
            FLASH_MODE = True
        elif not arg.startswith('-'):
            filename = arg

    if not filename:
        print("❌ Error: No filename specified.")
        print("Usage: python3 flash_tool.py [--flash] <your_file.txt>")
        sys.exit(1)

    # Execute based on mode
    success = send_firmware(filename)
    sys.exit(0 if success else 1)
