import serial
import time
import sys
from gpiozero import LED
from serial.tools import list_ports

# --- CONFIGURATION ---
RESET_PIN_GPIO = 17     # GPIO 17 is Physical Pin 11 on the Pi

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

def send_firmware(filename):
    # Get serial port
    PORT = get_serial_port()
    if not PORT:
        return

    # 1. TRIGGER RESET
    reset_dsp()

    # 2. START FLASHING
    print(f"🔌 Opening port {PORT}...")
    try:
        ser = serial.Serial(PORT, 9600, timeout=2)
    except Exception as e:
        print(f"❌ Error opening serial port: {e}")
        return

    print("Step 2: Performing Autobaud (Sending 'A')...")
    # Send 'A' continuously for a moment to catch the DSP as it wakes up
    ser.write(b'A')
    
    response = ser.read(1)
    if response == b'A':
        print("✅ DSP Ack received! Connection established.")
    else:
        print(f"❌ Failed. DSP did not reply. Received: {response}")
        print("Check: Is the Reset wire (Pin 11) connected to J6 Pin 56?")
        return

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
            print(f"Sending {total} bytes...")
            
            count = 0
            for val in data_bytes:
                ser.write(bytes([val]))
                count += 1
                if count % 100 == 0:
                     sys.stdout.write(f"\rProgress: {int(count/total*100)}%")
                     sys.stdout.flush()
                     
    except FileNotFoundError:
        print(f"❌ Error: File '{filename}' not found.")
        return

    print("\n✅ Upload Complete! The LED should be blinking.")
    ser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 flash_tool.py <your_file.txt>")
    else:
        send_firmware(sys.argv[1])