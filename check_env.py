import sys
try:
    # We switch from PyQt6 to PyQt5
    from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QMessageBox
    from PyQt5.QtCore import Qt
    import serial
    import serial.tools.list_ports
except ImportError as e:
    print(f"Error: Missing library - {e}")
    sys.exit(1)

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # --- Setup UI ---
        self.setWindowTitle("MFKB Companion - Env Check (PyQt5)")
        self.setMinimumSize(400, 200)

        # Main Layout
        layout = QVBoxLayout()

        # Status Label
        self.label = QLabel("Click the button to check Serial Ports")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        # Test Button
        self.btn = QPushButton("Scan for Arduino Mega")
        self.btn.clicked.connect(self.scan_serial)
        layout.addWidget(self.btn)

        # Container
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    # --- Logic ---
    def scan_serial(self):
        """Checks for available COM ports to verify pyserial is working."""
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            result_text = "PySerial is OK, but no devices were found."
        else:
            port_list = "\n".join([f"{p.device} ({p.description})" for p in ports])
            result_text = f"Found {len(ports)} port(s):\n{port_list}"

        self.label.setText("Scan Complete!")
        QMessageBox.information(self, "Environment Check", 
                                f"PyQt5 is working on your MacBook 7,1!\n\n{result_text}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_()) # Note the underscore in exec_() for PyQt5