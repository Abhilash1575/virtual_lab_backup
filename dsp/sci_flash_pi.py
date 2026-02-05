import serial
import time
from gpiozero import LED

PORT = "/dev/serial0"
BAUD = 9600
RESET_GPIO = 17

CMD_FLASH_PROGRAM = 0x03
ACK = 0x00

def reset_dsp():
    rst = LED(RESET_GPIO, active_high=False)
    rst.on()
    time.sleep(0.2)
    rst.off()
    time.sleep(0.5)
    rst.close()

def wait_ack(ser):
    r = ser.read(1)
    if not r or r[0] != ACK:
        raise RuntimeError("❌ No ACK from DSP")

def autobaud(ser):
    for _ in range(5):
        ser.write(b'A')
        time.sleep(0.1)

def send_txt(ser, filename):
    with open(filename) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            bytes_line = bytes.fromhex(line)
            ser.write(bytes_line)
            wait_ack(ser)

def main():
    print("🔄 Resetting DSP...")
    reset_dsp()

    with serial.Serial(PORT, BAUD, timeout=2) as ser:
        print("🔑 Autobaud...")
        autobaud(ser)
        wait_ack(ser)

        print("🧠 Sending FLASH PROGRAM command...")
        ser.write(bytes([CMD_FLASH_PROGRAM]))
        wait_ack(ser)

        print("📤 Uploading application...")
        send_txt(ser, "led_flash.txt")

        print("✅ Flash programming complete!")

if __name__ == "__main__":
    main()
