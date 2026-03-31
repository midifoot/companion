import sys
import os
import re
import subprocess
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QPushButton, 
                             QFrame, QGridLayout, QLineEdit, QCheckBox, QTextEdit, 
                             QComboBox, QFileDialog) # Added QFileDialog
from PyQt5.QtCore import Qt, QTimer, QProcess

# --- THE STYLESHEET (Golden v1.2 - Added Backup & Layout Fixes) ---
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

QPushButton#ChannelBtn, QPushButton#NoteBtn, #UtilityBtn, #FlashBtn, #BackupBtn {
    background-color: #21262d; border: 1px solid #30363d;
    color: #8b949e; border-radius: 4px; font-weight: bold; font-size: 12px;
}
QPushButton#ChannelBtn:checked, QPushButton#NoteBtn:checked {
    background-color: #2ecc71; color: #000000; border: 1px solid #ffffff;
}
QPushButton#FlashBtn { background-color: #2ecc71; color: #000000; border: none; }
QPushButton#FlashBtn:disabled, #BackupBtn:disabled { background-color: #30363d; color: #4d535e; border: 1px solid #21262d; }
QPushButton#BackupBtn { background-color: #161b22; color: #e6edf3; border-color: #30363d; padding: 0 10px; }
QPushButton#ChannelBtn:hover, QPushButton#NoteBtn:hover, #UtilityBtn:hover, #FlashBtn:hover, #BackupBtn:hover { border-color: #2ecc71; }

QPushButton#NoteBtn[locked="true"] { border: 2px solid #ff4444; }

QLineEdit, QComboBox {
    background-color: #0d1117; border: 1px solid #30363d;
    padding: 8px; border-radius: 4px; color: #8b949e;
    font-family: monospace; font-size: 12px;
}

QTextEdit#ResultBox, QTextEdit#ConsoleBox {
    background-color: #000000;
    border: 1px solid #30363d;
    color: #2ecc71;
    font-family: 'Courier New', monospace;
    font-size: 11px;
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
        self.current_port = None
        self.operation_type = "FLASH" # Helper to track FLASH vs BACKUP
        
        # Paths Configuration
        self.tools_path = "./tools/avrdude"
        self.conf_path = "./tools/avrdude_linux.conf"
        self.firmware_dir = os.path.abspath("./firmware")
        
        self.known_boards = [
            {'vid': 0x1a86, 'pid': 0x7523, 'name': 'CH340 (AZ-Delivery)'},
            {'vid': 0x2341, 'pid': 0x0042, 'name': 'Mega 2560 (Elegoo/Official)'}
        ]
        
        # Initialize Process for Avrdude
        self.process = QProcess(self)
        self.process.readyReadStandardError.connect(self.on_console_output)
        self.process.readyReadStandardOutput.connect(self.on_console_output)
        self.process.finished.connect(self.on_flash_finished)

        self.init_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_detect_hardware)
        self.timer.start(2000)
        
        self.refresh_firmware_list()

    def init_ui(self):
        self.setWindowTitle("MFKB Companion App v1.2")
        self.setFixedSize(800, 600) 
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
        self.tab_sd = QWidget(); self.tabs.addTab(self.tab_sd, "SD Card Manager")
        self.tab_flash = QWidget(); self.tabs.addTab(self.tab_flash, "Firmware Uploader")

        self.setup_bitmasker_tab()
        self.setup_uploader_tab()

    def setup_uploader_tab(self):
        layout = QVBoxLayout(self.tab_flash); layout.setContentsMargins(30, 20, 30, 20)
        
        # Header with Backup Button
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("FIRMWARE UPDATE (ATmega2560)", styleSheet="color: #2ecc71; font-weight: bold; font-size: 14px;"))
        header_row.addStretch()
        self.btn_backup = QPushButton("BACKUP CURRENT FIRMWARE"); self.btn_backup.setObjectName("BackupBtn")
        self.btn_backup.setFixedSize(220, 30); self.btn_backup.setEnabled(False)
        self.btn_backup.clicked.connect(self.start_backup)
        header_row.addWidget(self.btn_backup)
        layout.addLayout(header_row)

        layout.addWidget(QLabel("Select the version to upload to your MFKB device.", styleSheet="color: #8b949e; font-size: 11px;"))
        layout.addSpacing(20)

        # Selection Row
        sel_row = QHBoxLayout()
        self.combo_hex = QComboBox(); self.combo_hex.setMinimumWidth(300)
        self.btn_refresh = QPushButton("Refresh List"); self.btn_refresh.setObjectName("UtilityBtn")
        self.btn_refresh.setFixedSize(80, 30);
        self.btn_refresh.clicked.connect(self.refresh_firmware_list)
        sel_row.addWidget(self.combo_hex); sel_row.addWidget(self.btn_refresh); sel_row.addStretch()
        layout.addLayout(sel_row)
        
        layout.addSpacing(10)
        
        # Flash Button
        self.btn_flash = QPushButton("START FLASHING PROCESS"); self.btn_flash.setObjectName("FlashBtn")
        self.btn_flash.setFixedHeight(50); self.btn_flash.setEnabled(False)
        self.btn_flash.clicked.connect(self.start_flash)
        layout.addWidget(self.btn_flash)
        
        layout.addSpacing(20)
        
        # Console Output (SHRUNK)
        layout.addWidget(QLabel("OUTPUT CONSOLE", styleSheet="color: #8b949e; font-weight: bold; font-size: 9px;"))
        self.console_box = QTextEdit(); self.console_box.setObjectName("ConsoleBox"); self.console_box.setReadOnly(True)
        self.console_box.setFixedHeight(120) # Shrinked height
        layout.addWidget(self.console_box)

    def setup_bitmasker_tab(self):
        layout = QVBoxLayout(self.tab_gen); layout.setContentsMargins(25, 10, 25, 15); layout.setSpacing(5)

        # --- STEP 1: ID & NAME ---
        layout.addWidget(QLabel("STEP 1 : ID & NAME", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        input_row = QHBoxLayout()
        self.map_id_edit = QLineEdit("01"); self.map_id_edit.setFixedWidth(45); self.map_id_edit.textChanged.connect(self.on_id_name_changed)
        self.map_name_edit = QLineEdit("Default_Map"); self.map_name_edit.setFixedWidth(200); self.map_name_edit.textChanged.connect(self.on_id_name_changed)
        
        self.btn_check_name = QPushButton("Check Name"); self.btn_check_name.setObjectName("UtilityBtn")
        self.btn_check_name.setFixedWidth(90)
        
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

    # --- FIRMWARE LOGIC ---
    def refresh_firmware_list(self):
        self.combo_hex.clear()
        if not os.path.exists(self.firmware_dir):
            os.makedirs(self.firmware_dir)
        
        files = sorted([f for f in os.listdir(self.firmware_dir) if f.endswith(".hex")])
        if not files:
            self.combo_hex.addItem("No .hex files found in /firmware")
            self.btn_flash.setEnabled(False)
        else:
            self.combo_hex.addItems(files)
            if self.current_port: self.btn_flash.setEnabled(True)

    def start_flash(self):
        hex_file = os.path.join(self.firmware_dir, self.combo_hex.currentText())
        if not os.path.exists(self.tools_path):
            self.console_box.append("ERROR: avrdude binary not found in /tools")
            return

        self.operation_type = "FLASH"
        self.btn_flash.setEnabled(False)
        self.btn_backup.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.console_box.clear()
        self.console_box.append(f"--- Starting Upload: {self.combo_hex.currentText()} ---")
        
        args = [
            "-C", self.conf_path,
            "-v",
            "-p", "m2560",
            "-c", "wiring",
            "-P", self.current_port,
            "-b", "115200",
            "-D",
            "-U", f"flash:w:{hex_file}:i"
        ]
        self.process.start(self.tools_path, args)

    def start_backup(self):
        # Open System File Manager
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Current Firmware As", 
                                                  os.path.join(self.firmware_dir, "my_backup.hex"), 
                                                  "Hex Files (*.hex);;All Files (*)", options=options)
        
        if not file_path:
            return

        self.operation_type = "BACKUP"
        self.btn_flash.setEnabled(False)
        self.btn_backup.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.console_box.clear()
        self.console_box.append(f"--- Starting Backup to: {os.path.basename(file_path)} ---")
        
        # Build Command for Reading
        args = [
            "-C", self.conf_path,
            "-v",
            "-p", "m2560",
            "-c", "wiring",
            "-P", self.current_port,
            "-b", "115200",
            "-U", f"flash:r:{file_path}:i"
        ]
        self.process.start(self.tools_path, args)

    def on_console_output(self):
        data = self.process.readAllStandardError().data().decode()
        if not data:
            data = self.process.readAllStandardOutput().data().decode()
        self.console_box.insertPlainText(data)
        self.console_box.ensureCursorVisible()

    def on_flash_finished(self):
        self.btn_flash.setEnabled(True if self.current_port else False)
        self.btn_backup.setEnabled(True if self.current_port else False)
        self.btn_refresh.setEnabled(True)
        self.console_box.append(f"\n--- {self.operation_type} Process Finished ---")
        # Auto refresh list in case a new backup was saved in /firmware
        self.refresh_firmware_list()

    # --- CORE LOGIC ---
    def clear_map(self):
        self.note_masks = [0] * 25
        self.selected_notes.clear()
        for btn in self.note_buttons:
            btn.blockSignals(True); btn.setChecked(False); btn.setProperty("locked", "false")
            btn.style().unpolish(btn); btn.style().polish(btn); btn.blockSignals(False)
        for btn in self.chan_buttons:
            btn.blockSignals(True); btn.setChecked(False); btn.blockSignals(False)
        self.note_all_chk.setChecked(False); self.chan_all_chk.setChecked(False)
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
                    self.current_port = p.device
                    # Enable buttons if device is found
                    self.btn_backup.setEnabled(True)
                    if self.combo_hex.currentText().endswith(".hex"):
                        self.btn_flash.setEnabled(True)
                    found = True; break
        if not found:
            self.status_dot.setStyleSheet("color: #e74c3c; font-size: 14px; margin-left: 10px;")
            self.status_text.setText("No Device Detected")
            self.current_port = None
            self.btn_flash.setEnabled(False)
            self.btn_backup.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv); window = MFKBApp(); window.show(); sys.exit(app.exec_())