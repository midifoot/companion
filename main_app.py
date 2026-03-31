import sys
import re
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QPushButton, 
                             QFrame, QGridLayout, QLineEdit, QCheckBox, QTextEdit)
from PyQt5.QtCore import Qt, QTimer

# --- THE STYLESHEET (Golden v1.0) ---
STYLE_SHEET = """
QMainWindow { background-color: #0a0a0a; }
#ConnBar { background-color: #161b22; border-bottom: 1px solid #30363d; }
QLabel { color: #ffffff; }

QTabWidget::pane { border: 1px solid #30363d; top: -1px; background: #0a0a0a; }
QTabBar::tab { 
    background: #161b22; color: #8b949e; padding: 8px 30px;
    border: 1px solid #30363d; border-bottom: none; margin-right: 2px; font-size: 11px;
}
QTabBar::tab:selected { background: #2ecc71; color: #000000; font-weight: normal; }

/* UNIFIED BUTTON STYLE */
QPushButton#ChannelBtn, QPushButton#NoteBtn, #UtilityBtn {
    background-color: #21262d; border: 1px solid #30363d;
    color: #8b949e; border-radius: 4px; font-weight: bold; font-size: 12px;
}
QPushButton#ChannelBtn:checked, QPushButton#NoteBtn:checked {
    background-color: #2ecc71; color: #000000; border: 1px solid #ffffff;
}
QPushButton#ChannelBtn:hover, QPushButton#NoteBtn:hover, #UtilityBtn:hover { border-color: #2ecc71; }

QPushButton#NoteBtn[locked="true"] { border: 2px solid #ff4444; }

QLineEdit {
    background-color: #0d1117; border: 1px solid #30363d;
    padding: 8px; border-radius: 4px; color: #e6edf3;
    font-family: monospace; font-size: 14px;
}

QTextEdit#ResultBox {
    background-color: #000000;
    border: 1px solid #30363d;
    color: #2ecc71;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    border-radius: 4px;
}
"""

class MFKBApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.note_masks = [0] * 25 
        self.selected_notes = set() 
        self.chan_buttons = []
        self.note_buttons = []
        
        self.known_boards = [
            {'vid': 0x1a86, 'pid': 0x7523, 'name': 'CH340 (AZ-Delivery)'},
            {'vid': 0x2341, 'pid': 0x0042, 'name': 'Mega 2560 (Elegoo/Official)'}
        ]
        self.init_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_detect_hardware)
        self.timer.start(2000)

    def init_ui(self):
        self.setWindowTitle("MFKB Companion App v1.0")
        self.setFixedSize(800, 550) 
        self.setStyleSheet(STYLE_SHEET)

        central = QWidget(); self.setCentralWidget(central)
        main_layout = QVBoxLayout(central); main_layout.setContentsMargins(0, 0, 0, 0)

        # --- CONNECTION BAR ---
        self.conn_bar = QFrame(); self.conn_bar.setObjectName("ConnBar")
        conn_lay = QHBoxLayout(self.conn_bar)
        self.status_dot = QLabel("●"); self.status_dot.setStyleSheet("color: #e74c3c; font-size: 14px; margin-left: 10px;")
        self.status_text = QLabel("Scanning Hardware..."); self.status_text.setStyleSheet("color: #8b949e; font-size: 10px;")
        conn_lay.addWidget(self.status_dot); conn_lay.addWidget(self.status_text); conn_lay.addStretch(); main_layout.addWidget(self.conn_bar)

        # --- TABS ---
        self.tabs = QTabWidget(); main_layout.addWidget(self.tabs)
        self.tab_gen = QWidget(); self.tabs.addTab(self.tab_gen, "MidiMap Generator")
        self.tabs.addTab(QWidget(), "SD Card Manager"); self.tabs.addTab(QWidget(), "Firmware Uploader")

        self.setup_bitmasker_tab()

    def setup_bitmasker_tab(self):
        layout = QVBoxLayout(self.tab_gen); layout.setContentsMargins(25, 10, 25, 15); layout.setSpacing(5)

        # --- STEP 1: ID & NAME ---
        layout.addWidget(QLabel("STEP 1 : ID & NAME", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        input_row = QHBoxLayout()
        self.map_id_edit = QLineEdit("01"); self.map_id_edit.setFixedWidth(45); self.map_id_edit.textChanged.connect(self.on_id_name_changed)
        self.map_name_edit = QLineEdit("Default_Map"); self.map_name_edit.setFixedWidth(200); self.map_name_edit.textChanged.connect(self.on_id_name_changed)
        
        self.btn_check_name = QPushButton("Check Name"); self.btn_check_name.setObjectName("UtilityBtn")
        self.btn_check_name.setFixedWidth(90)
        # Placeholder for future SD lookup
        
        input_row.addWidget(QLabel("ID:")); input_row.addWidget(self.map_id_edit)
        input_row.addWidget(QLabel("NAME:")); input_row.addWidget(self.map_name_edit)
        input_row.addWidget(self.btn_check_name)
        input_row.addStretch()
        layout.addLayout(input_row)

        # --- STEP 2: NOTE SELECTION ---
        note_head = QHBoxLayout()
        note_head.addWidget(QLabel("STEP 2 : SELECT NOTES", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        self.note_all_chk = QCheckBox("Select All"); self.note_all_chk.setStyleSheet("color: white; font-size: 10px;")
        self.note_all_chk.stateChanged.connect(self.on_note_select_all)
        note_head.addStretch(); note_head.addWidget(self.note_all_chk); layout.addLayout(note_head)

        note_grid = QGridLayout(); note_grid.setSpacing(4)
        for i in range(25):
            btn = QPushButton(str(i+1)); btn.setObjectName("NoteBtn"); btn.setCheckable(True); btn.setFixedSize(32, 32)
            btn.clicked.connect(self.on_note_clicked); self.note_buttons.append(btn)
            note_grid.addWidget(btn, i // 13, i % 13)
        layout.addLayout(note_grid)

        # --- STEP 3: CHANNEL SELECTION ---
        chan_head = QHBoxLayout()
        chan_head.addWidget(QLabel("STEP 3 : MAP CHANNELS", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        self.chan_all_chk = QCheckBox("Select All"); self.chan_all_chk.setStyleSheet("color: white; font-size: 10px;")
        self.chan_all_chk.stateChanged.connect(self.on_chan_select_all)
        chan_head.addStretch(); chan_head.addWidget(self.chan_all_chk); layout.addLayout(chan_head)

        chan_grid = QGridLayout(); chan_grid.setSpacing(6)
        for i in range(16):
            btn = QPushButton(str(i+1)); btn.setObjectName("ChannelBtn"); btn.setCheckable(True); btn.setFixedSize(75, 40)
            btn.clicked.connect(self.on_channel_clicked); self.chan_buttons.append(btn)
            chan_grid.addWidget(btn, i // 8, i % 8)
        layout.addLayout(chan_grid)

        # --- CLEAR MAP BUTTON ---
        self.btn_clear = QPushButton("CLEAR CURRENT MAP"); self.btn_clear.setObjectName("UtilityBtn")
        self.btn_clear.setFixedHeight(30); self.btn_clear.setStyleSheet("color: #ff4444; font-size: 10px;")
        self.btn_clear.clicked.connect(self.clear_map)
        layout.addWidget(self.btn_clear)

        # --- RESULT AREA ---
        layout.addStretch()
        layout.addWidget(QLabel("STEP 4 : copy/paste the result in the file MIDIMAPS.FKB", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        layout.addWidget(QLabel("FINAL MIDI MAP LINE", styleSheet="color: #8b949e; font-weight: bold; font-size: 9px;"))
        res_box_lay = QHBoxLayout()
        self.result_box = QTextEdit(); self.result_box.setObjectName("ResultBox"); self.result_box.setReadOnly(True); self.result_box.setFixedHeight(60)
        self.btn_copy = QPushButton("COPY"); self.btn_copy.setFixedSize(80, 60); self.btn_copy.setStyleSheet("background-color: #2ecc71; color: black; font-weight: bold;")
        self.btn_copy.clicked.connect(self.copy_result)
        res_box_lay.addWidget(self.result_box); res_box_lay.addWidget(self.btn_copy); layout.addLayout(res_box_lay)
        self.update_result_string()

    # --- LOGIC ---
    def clear_map(self):
        """Resets the entire mapping to zero."""
        self.note_masks = [0] * 25
        self.selected_notes.clear()
        for btn in self.note_buttons:
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.setProperty("locked", "false")
            btn.style().unpolish(btn); btn.style().polish(btn)
            btn.blockSignals(False)
        for btn in self.chan_buttons:
            btn.blockSignals(True); btn.setChecked(False); btn.blockSignals(False)
        self.note_all_chk.setChecked(False)
        self.chan_all_chk.setChecked(False)
        self.update_result_string()

    def on_note_clicked(self):
        btn = self.sender(); idx = int(btn.text()) - 1
        if not (QApplication.keyboardModifiers() == Qt.ControlModifier):
            target_mask = self.note_masks[idx]
            self.selected_notes.clear()
            if target_mask > 0:
                for i, m in enumerate(self.note_masks):
                    if m == target_mask: self.selected_notes.add(i)
            else: self.selected_notes.add(idx)
            for i, b in enumerate(self.note_buttons): b.setChecked(i in self.selected_notes)
            self.sync_channels_to_mask(target_mask)
        else:
            if btn.isChecked(): self.selected_notes.add(idx)
            else: self.selected_notes.discard(idx)

    def on_channel_clicked(self):
        mask = 0
        for i, btn in enumerate(self.chan_buttons):
            if btn.isChecked(): mask |= (1 << i)
        for idx in self.selected_notes:
            self.note_masks[idx] = mask
            btn = self.note_buttons[idx]
            btn.setProperty("locked", "true" if mask > 0 else "false")
            btn.style().unpolish(btn); btn.style().polish(btn)
        self.update_result_string()

    def sync_channels_to_mask(self, mask):
        for i, btn in enumerate(self.chan_buttons):
            btn.blockSignals(True); btn.setChecked(bool(mask & (1 << i))); btn.blockSignals(False)

    def on_note_select_all(self, state):
        is_all = (state == Qt.Checked)
        for i, btn in enumerate(self.note_buttons):
            btn.setChecked(is_all)
            if is_all: self.selected_notes.add(i)
            else: self.selected_notes.discard(i)

    def on_chan_select_all(self, state):
        is_all = (state == Qt.Checked)
        for btn in self.chan_buttons: btn.setChecked(is_all)
        self.on_channel_clicked()

    def on_id_name_changed(self):
        self.update_result_string()

    def update_result_string(self):
        mid = self.map_id_edit.text().zfill(2)
        name = self.map_name_edit.text()
        hex_data = ",".join([f"{m:04X}" for m in self.note_masks])
        self.result_box.setText(f"MM{mid}:{name}:{hex_data}")

    def copy_result(self):
        QApplication.clipboard().setText(self.result_box.toPlainText())
        self.btn_copy.setText("COPIED!")
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("COPY"))

    def auto_detect_hardware(self):
        ports = list(serial.tools.list_ports.comports())
        found = False
        for p in ports:
            for board in self.known_boards:
                if p.vid == board['vid'] and p.pid == board['pid']:
                    self.status_dot.setStyleSheet("color: #2ecc71; font-size: 14px; margin-left: 10px;")
                    self.status_text.setText(f"Connected: {board['name']} ({p.device})")
                    found = True; break
        if not found:
            self.status_dot.setStyleSheet("color: #e74c3c; font-size: 14px; margin-left: 10px;")
            self.status_text.setText("No Device Detected")

if __name__ == "__main__":
    app = QApplication(sys.argv); window = MFKBApp(); window.show(); sys.exit(app.exec_())