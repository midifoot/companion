import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QPushButton, QFrame)
from PyQt5.QtCore import Qt, QTimer
import serial.tools.list_ports

class MFKBApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # Hardware Whitelist (From our previous tests)
        self.known_boards = [
            {'vid': 0x1a86, 'pid': 0x7523, 'name': 'CH340 (AZ-Delivery)'},
            {'vid': 0x2341, 'pid': 0x0042, 'name': 'Mega 2560 (Elegoo/Official)'}
        ]
        self.init_ui()
        
        # Start a timer to check for hardware every 2 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_detect_hardware)
        self.timer.start(2000)

    def init_ui(self):
        self.setWindowTitle("MFKB Companion App v0.1")
        self.setMinimumSize(900, 700)
        self.setStyleSheet("background-color: #0a0a0a; color: #e6edf3;")

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # --- 1. CONNECTION BAR (TOP) ---
        self.conn_bar = QFrame()
        self.conn_bar.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
        conn_layout = QHBoxLayout(self.conn_bar)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 20px;") # Default Red
        
        self.status_text = QLabel("No Device Detected")
        self.status_text.setStyleSheet("font-weight: bold; color: #8b949e;")
        
        self.refresh_btn = QPushButton("Force Scan")
        self.refresh_btn.clicked.connect(self.auto_detect_hardware)
        self.refresh_btn.setStyleSheet("background: #21262d; padding: 5px 15px; border-radius: 4px;")

        conn_layout.addWidget(self.status_dot)
        conn_layout.addWidget(self.status_text)
        conn_layout.addStretch()
        conn_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(self.conn_bar)

        # --- 2. TAB SYSTEM ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { background: #161b22; padding: 10px 30px; border: 1px solid #30363d; }
            QTabBar::tab:selected { background: #2ecc71; color: black; font-weight: bold; }
            QTabWidget::pane { border: 1px solid #30363d; top: -1px; background: #0a0a0a; }
        """)

        # Create the Tab Placeholders
        self.tab_bitmask = QWidget()
        self.tab_sd_manager = QWidget()
        self.tab_firmware = QWidget()

        self.tabs.addTab(self.tab_bitmask, "Mapping Generator")
        self.tabs.addTab(self.tab_sd_manager, "SD Card Manager")
        self.tabs.addTab(self.tab_firmware, "Firmware Uploader")

        layout.addWidget(self.tabs)

        # Initialize the Bitmasker inside its tab
        self.setup_bitmasker_tab()

    def setup_bitmasker_tab(self):
        # (We will move your Bitmasker code here in the next step)
        temp_layout = QVBoxLayout(self.tab_bitmask)
        temp_layout.addWidget(QLabel("Bitmasker UI will live here...", alignment=Qt.AlignCenter))

    def auto_detect_hardware(self):
        """Checks ports against our whitelist."""
        ports = list(serial.tools.list_ports.comports())
        found = False
        
        for p in ports:
            for board in self.known_boards:
                if p.vid == board['vid'] and p.pid == board['pid']:
                    self.status_dot.setStyleSheet("color: #2ecc71; font-size: 20px;") # Green
                    self.status_text.setText(f"Connected: {board['name']} on {p.device}")
                    found = True
                    break
        
        if not found:
            self.status_dot.setStyleSheet("color: #e74c3c; font-size: 20px;") # Red
            self.status_text.setText("No Device Detected")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MFKBApp()
    window.show()
    sys.exit(app.exec_())