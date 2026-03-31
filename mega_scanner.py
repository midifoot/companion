import serial.tools.list_ports

def scan_ports():
    print("--- MFKB Hardware Scanner ---")
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print("No USB devices detected. Is the Mega plugged in?")
        return

    for p in ports:
        print(f"\n[ Device Found ]")
        print(f"Port: {p.device}")
        print(f"Description: {p.description}")
        print(f"Hardware ID: {p.hwid}")
        
        # Extract VID and PID if available
        if p.vid:
            print(f"VID: {hex(p.vid)} (Hex)")
        if p.pid:
            print(f"PID: {hex(p.pid)} (Hex)")
        
        # Look for typical Mega signatures
        if "CH340" in p.description or "Arduino Mega" in p.description:
            print(">> Status: Potential MFKB Target Detected!")
        else:
            print(">> Status: Unknown Device")
    print("\n-----------------------------")

if __name__ == "__main__":
    scan_ports()