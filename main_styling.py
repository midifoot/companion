import sys
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QPushButton, 
                             QFrame, QGridLayout, QLineEdit)
from PyQt5.QtCore import Qt, QTimer

# --- THE STYLESHEET (Fixed Selectors for QSS) ---
STYLE_SHEET = """
QMainWindow { background-color: #0a0a0a; }

#ConnBar { 
    background-color: #161b22; 
    border-bottom: 1px solid #30363d; 
}

QTabWidget::pane { 
    border: 1px solid #30363d; 
    top: -1px; 
    background: #0a0a0a; 
}
QTabBar::tab { 
    background: #161b22; 
    color: #8b949e;
    padding: 8px 30px;
    border: 1px solid #30363d; 
    border-bottom: none;
    margin-right: 2px;
    font-size: 11px;
}
QTabBar::tab:selected { 
    background: #2ecc71; 
    color: #000000; 
    font-weight: normal; 
}

#HexDisplay {
    background-color: #000000;
    border: 1px solid #30363d;
    border-radius: 8px;
}
#HexValue {
    font-family: 'Courier New', monospace;
    font-size: 52px; 
    font-weight: bold;
    color: #2ecc71;
}

/* TARGETING THE OBJECT NAME WITH # */
QPushButton#ChannelBtn {
    background-color: #21262d;
    border: 1px solid #30363d;
    color: #8b949e;
    border-radius: 4px;
    font-weight: bold;
    font-size: 12px;
}

/* THE FIX: Targeting the checked state of the specific ObjectName */
QPushButton#ChannelBtn:checked {
    background-color: #2ecc71;
    color: #000000;
    border: 1px solid #ffffff;
}

QPushButton#ChannelBtn:hover {
    border-color: #2ecc71;
}

QLineEdit#ManualInput {
    background-color: #0d1117;
    border: 1px solid #30363d;
    padding: 8px;
    border-radius: 4px;
    color: #e6edf3;
    font-family: monospace;
    font-size: 14px;
}
"""

class MFKBApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_mask = 0
        self.buttons = []
        self.known_boards = [
            {'vid': 0x1a86, 'pid': 0x7523, 'name': 'CH340 (AZ-Delivery)'},
            {'vid': 0x2341, 'pid': 0x0042, 'name': 'Mega 2560 (Elegoo/Official)'}
        ]
        self.init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_detect_hardware)
        self.timer.start(2000)

    def init_ui(self):
        self.setWindowTitle("MFKB Companion App v0.5")
        self.setMinimumSize(800, 600) 
        self.setStyleSheet(STYLE_SHEET)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- CONNECTION BAR ---
        self.conn_bar = QFrame()
        self.conn_bar.setObjectName("ConnBar")
        conn_layout = QHBoxLayout(self.conn_bar)
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 14px; margin-left: 10px;")
        self.status_text = QLabel("Scanning Hardware...")
        self.status_text.setStyleSheet("color: #8b949e; font-size: 10px;")
        conn_layout.addWidget(self.status_dot)
        conn_layout.addWidget(self.status_text)
        conn_layout.addStretch()
        main_layout.addWidget(self.conn_bar)

        # --- TAB SYSTEM ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.tab_bitmask = QWidget()
        self.tab_sd_manager = QWidget()
        self.tab_firmware = QWidget()
        self.tabs.addTab(self.tab_bitmask, "Mapping Generator")
        self.tabs.addTab(self.tab_sd_manager, "SD Card Manager")
        self.tabs.addTab(self.tab_firmware, "Firmware Uploader")

        self.setup_bitmasker_tab()

    def setup_bitmasker_tab(self):
        layout = QVBoxLayout(self.tab_bitmask)
        layout.setContentsMargins(25, 10, 25, 25)
        layout.setSpacing(12)

        hex_frame = QFrame()
        hex_frame.setObjectName("HexDisplay")
        hex_layout = QVBoxLayout(hex_frame)
        label_small = QLabel("CURRENT HEX CODE")
        label_small.setStyleSheet("color: #8b949e; font-size: 8px;")
        label_small.setAlignment(Qt.AlignCenter)
        self.hex_val_label = QLabel("0000")
        self.hex_val_label.setObjectName("HexValue")
        self.hex_val_label.setAlignment(Qt.AlignCenter)
        hex_layout.addWidget(label_small)
        hex_layout.addWidget(self.hex_val_label)
        layout.addWidget(hex_frame)

        layout.addWidget(QLabel("INTERACTIVE CHANNEL SELECTOR", styleSheet="color: #8b949e; font-weight: bold; font-size: 9px;"))
        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setSpacing(6)
        
        for i in range(1, 17):
            btn = QPushButton(str(i))
            btn.setObjectName("ChannelBtn") # Crucial for the style sheet
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(self.on_grid_click)
            btn.setFixedHeight(45)
            btn.setFixedWidth(75)
            self.buttons.append(btn)
            grid_layout.addWidget(btn, (i-1)//8, (i-1)%8)
        
        layout.addWidget(grid_container)

        layout.addWidget(QLabel("MANUAL INPUT / ANALYZE RANGE", styleSheet="color: #8b949e; font-weight: bold; font-size: 9px;"))
        self.manual_input = QLineEdit()
        self.manual_input.setObjectName("ManualInput")
        self.manual_input.setPlaceholderText("Ex: 1-4, 8, 10-12")
        self.manual_input.textChanged.connect(self.sync_from_input)
        layout.addWidget(self.manual_input)

    def auto_detect_hardware(self):
        ports = list(serial.tools.list_ports.comports())
        found = False
        for p in ports:
            for board in self.known_boards:
                if p.vid == board['vid'] and p.pid == board['pid']:
                    self.status_dot.setStyleSheet("color: #2ecc71; font-size: 14px; margin-left: 10px;")
                    self.status_text.setText(f"Connected: {board['name']} ({p.device})")
                    found = True
                    break
        if not found:
            self.status_dot.setStyleSheet("color: #e74c3c; font-size: 14px; margin-left: 10px;")
            self.status_text.setText("No Device Detected")

    def on_grid_click(self):
        self.calculate_mask_from_buttons()
        self.update_ui(sender="grid")

    def calculate_mask_from_buttons(self):
        new_mask = 0
        for i, btn in enumerate(self.buttons):
            if btn.isChecked():
                new_mask |= (1 << i)
        self.current_mask = new_mask

    def update_ui(self, sender=""):
        self.hex_val_label.setText(f"{self.current_mask:04X}")
        
        if sender == "input":
            for i, btn in enumerate(self.buttons):
                is_active = bool(self.current_mask & (1 << i))
                btn.setChecked(is_active)

        if sender == "grid":
            active = [str(i+1) for i in range(16) if (self.current_mask & (1 << i))]
            self.manual_input.blockSignals(True)
            self.manual_input.setText(", ".join(active))
            self.manual_input.blockSignals(False)

    def sync_from_input(self):
        text = self.manual_input.text().strip()
        if not text:
            self.current_mask = 0
        elif len(text) == 4 and all(c in "0123456789ABCDEFabcdef" for c in text):
            self.current_mask = int(text, 16)
        else:
            new_mask = 0
            parts = text.split(',')
            for p in parts:
                p = p.strip()
                try:
                    if '-' in p:
                        s, e = map(int, p.split('-'))
                        for i in range(min(s, e), max(s, e) + 1):
                            if 1 <= i <= 16: new_mask |= (1 << (i - 1))
                    else:
                        ch = int(p)
                        if 1 <= ch <= 16: new_mask |= (1 << (ch - 1))
                except (ValueError, IndexError): continue
            self.current_mask = new_mask
        self.update_ui(sender="input")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MFKBApp()
    window.show()
    sys.exit(app.exec_())