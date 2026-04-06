import sys
import os
import re
import time
import serial
import serial.tools.list_ports
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QPushButton, 
                             QFrame, QGridLayout, QLineEdit, QCheckBox, QTextEdit, 
                             QComboBox, QFileDialog, QListWidget, QDialog, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, QProcess
from PyQt5.QtGui import QTextCursor

# --- THE STYLESHEET (Golden v1.8.1) ---
STYLE_SHEET = """
QMainWindow, QDialog { background-color: #0a0a0a; }
#ConnBar { background-color: #161b22; border-bottom: 1px solid #30363d; }
QLabel { color: #ffffff; }

QTabWidget::pane { border: 1px solid #30363d; top: -1px; background: #0a0a0a; }
QTabBar::tab { 
    background: #161b22; color: #8b949e; padding: 8px 30px;
    border: 1px solid #30363d; border-bottom: none; margin-right: 2px; font-size: 11px;
}
QTabBar::tab:selected { background: #2ecc71; color: #000000; font-weight: normal; }

QPushButton#ChannelBtn, QPushButton#NoteBtn, #UtilityBtn, #FlashBtn, #BackupBtn, #SD_Btn {
    background-color: #21262d; border: 1px solid #30363d;
    color: #8b949e; border-radius: 4px; font-weight: bold; font-size: 12px;
}
QPushButton#FlashBtn { background-color: #2ecc71; color: #000000; border: none; }
QPushButton#FlashBtn:disabled, #BackupBtn:disabled, #SD_Btn:disabled { 
    background-color: #30363d; color: #4d535e; border: 1px solid #21262d; 
}
QPushButton#ChannelBtn:hover, QPushButton#NoteBtn:hover, #UtilityBtn:hover, 
#FlashBtn:hover, #BackupBtn:hover, #SD_Btn:hover { 
    border-color: #2ecc71; 
}

QPushButton#DelBtn {
    background-color: #21262d; border: 1px solid #30363d;
    color: #ff4444; border-radius: 4px; font-weight: bold;
}
QPushButton#DelBtn:hover { border-color: #ff4444; }

QLineEdit, QComboBox {
    background-color: #0d1117; border: 1px solid #30363d;
    padding: 8px; border-radius: 4px; color: #8b949e;
    font-family: monospace; font-size: 12px;
}

QListWidget { 
    background-color: #0d1117; border: 1px solid #30363d; 
    color: #e6edf3; border-radius: 4px; padding: 5px; 
}
QListWidget::item:selected { background-color: #2ecc71; color: #000000; }

QTextEdit#ResultBox, QTextEdit#ConsoleBox, #SD_Console, #EditorArea {
    background-color: #000000; border: 1px solid #30363d; color: #2ecc71;
    font-family: 'Courier New', monospace; font-size: 11px; border-radius: 4px;
}
"""

class FileEditor(QDialog):
    """Expanded Editor with Search and Validation."""
    def __init__(self, filename, content, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.parent_app = parent
        self.setWindowTitle(f"MFKB Editor - {filename}")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(STYLE_SHEET)
        
        layout = QVBoxLayout(self)
        
        # Search Control
        search_bar = QHBoxLayout()
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Enter text to find...")
        self.btn_find = QPushButton("FIND NEXT")
        self.btn_find.setObjectName("SD_Btn")
        self.btn_find.setFixedWidth(100)
        self.btn_find.clicked.connect(self.do_find)
        self.search_field.returnPressed.connect(self.do_find)
        
        search_bar.addWidget(QLabel("FIND:"))
        search_bar.addWidget(self.search_field)
        search_bar.addWidget(self.btn_find)
        layout.addLayout(search_bar)
        
        self.editor = QTextEdit()
        self.editor.setObjectName("EditorArea")
        self.editor.setPlainText(content)
        self.editor.setAcceptRichText(False)
        layout.addWidget(self.editor)
        
        btn_row = QHBoxLayout()
        self.btn_validate = QPushButton("VALIDATE FORMAT")
        self.btn_validate.setObjectName("SD_Btn")
        self.btn_validate.clicked.connect(self.run_local_validation)
        
        self.btn_save = QPushButton("SAVE CHANGES")
        self.btn_save.setObjectName("SD_Btn")
        self.btn_save.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setObjectName("SD_Btn")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_row.addWidget(self.btn_validate)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

    def do_find(self):
        query = self.search_field.text()
        if not query:
            return
        
        found = self.editor.find(query)
        if not found:
            # Wrap to start
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(query)

    def run_local_validation(self):
        text = self.editor.toPlainText()
        lines = text.split('\n')
        errors = []
        
        # Scan local assets for references
        self.parent_app.pre_scan_assets()
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            res = self.parent_app.validate_fkb_line(self.filename.upper(), line, deep=True)
            if res is not True:
                errors.append(f"Line {i+1}: {res}")
        
        if len(errors) == 0:
            self.editor.append("\n# [SUCCESS] Validation Passed.")
        else:
            self.editor.append("\n# [FAILED] Errors detected:")
            for e in errors:
                self.editor.append(f"# {e}")

class MFKBApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.note_masks = [0] * 25 
        self.selected_notes = set() 
        self.chan_buttons = []
        self.note_buttons = []
        self.current_port = None
        self.ser = None 
        
        # Database for cross-file checking
        self.asset_db = {
            "CHORDS": set(),
            "SCALES": set(),
            "PRESETS": set(),
            "KEYMAPS": set(),
            "MIDIMAPS": set()
        }
        
        self.tools_path = "./tools/avrdude"
        self.conf_path = "./tools/avrdude_linux.conf"
        self.firmware_dir = "./firmware"
        self.sd_local_dir = "./sdcard"
        self.sd_backup_dir = "./sdcard/backups"
        
        for p in [self.sd_local_dir, self.sd_backup_dir, self.firmware_dir]:
            if not os.path.exists(p):
                os.makedirs(p)
        
        self.known_boards = [
            {'vid': 0x1a86, 'pid': 0x7523, 'name': 'CH340 (AZ-Delivery)'},
            {'vid': 0x2341, 'pid': 0x0042, 'name': 'Mega 2560 (Elegoo/Official)'}
        ]
        
        self.process = QProcess(self)
        self.process.readyReadStandardError.connect(self.on_console_output)
        self.process.readyReadStandardOutput.connect(self.on_console_output)
        self.process.finished.connect(self.on_flash_finished)

        self.init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_detect_hardware)
        self.timer.start(2000)
        
        self.refresh_firmware_list()
        self.refresh_local_sd_list()

    def init_ui(self):
        self.setWindowTitle("MFKB Companion App v1.8.1")
        self.setFixedSize(850, 650) 
        self.setStyleSheet(STYLE_SHEET)
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Connection Header
        self.conn_bar = QFrame()
        self.conn_bar.setObjectName("ConnBar")
        conn_lay = QHBoxLayout(self.conn_bar)
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 14px; margin-left: 10px;")
        self.status_text = QLabel("Scanning Hardware...")
        self.status_text.setStyleSheet("color: #8b949e; font-size: 10px;")
        conn_lay.addWidget(self.status_dot)
        conn_lay.addWidget(self.status_text)
        conn_lay.addStretch()
        main_layout.addWidget(self.conn_bar)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.tab_gen = QWidget()
        self.tabs.addTab(self.tab_gen, "MidiMap Generator")
        self.tab_sd = QWidget()
        self.tabs.addTab(self.tab_sd, "SD Card Manager")
        self.tab_flash = QWidget()
        self.tabs.addTab(self.tab_flash, "Firmware Uploader")

        self.setup_bitmasker_tab()
        self.setup_uploader_tab()
        self.setup_sd_tab()

    def setup_sd_tab(self):
        layout = QVBoxLayout(self.tab_sd)
        layout.setContentsMargins(20, 20, 20, 20)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("SD CARD MANAGER", styleSheet="color: #2ecc71; font-weight: bold; font-size: 12px;"))
        header.addWidget(QLabel("Caution : make backups prior to any edition/transfer and Edit only LOCAL FILES !", styleSheet="color: #FF0000; font-weight: bold; font-size: 10px;"))
        header.addStretch()
        self.btn_full_backup = QPushButton("FULL SD BACKUP")
        self.btn_full_backup.setObjectName("SD_Btn")
        self.btn_full_backup.setFixedWidth(140)
        self.btn_full_backup.clicked.connect(self.run_full_backup)
        header.addWidget(self.btn_full_backup)
        layout.addLayout(header)
        
        panes = QHBoxLayout()
        
        # Left
        left_box = QVBoxLayout()
        left_box.addWidget(QLabel("LOCAL (PC)", styleSheet="color: #8b949e; font-size: 10px;"))
        self.list_local = QListWidget()
        left_box.addWidget(self.list_local)
        self.btn_validate = QPushButton("CHECK INTEGRITY")
        self.btn_validate.setObjectName("SD_Btn")
        self.btn_validate.clicked.connect(self.run_integrity_check)
        left_box.addWidget(self.btn_validate)
        panes.addLayout(left_box)
        
        # Actions (Center)
        mid_box = QVBoxLayout()
        mid_box.setAlignment(Qt.AlignCenter)
        
        self.btn_to_sd = QPushButton(">>")
        self.btn_to_sd.setObjectName("SD_Btn")
        self.btn_to_sd.setFixedSize(50, 50)
        self.btn_to_sd.clicked.connect(self.upload_selected)
        
        self.btn_edit = QPushButton("EDIT")
        self.btn_edit.setObjectName("SD_Btn")
        self.btn_edit.setFixedSize(50, 50)
        self.btn_edit.clicked.connect(self.open_editor)

        self.btn_del = QPushButton("DEL")
        self.btn_del.setObjectName("DelBtn")
        self.btn_del.setFixedSize(50, 50)
        self.btn_del.clicked.connect(self.delete_selected_remote)
        
        self.btn_from_sd = QPushButton("<<")
        self.btn_from_sd.setObjectName("SD_Btn")
        self.btn_from_sd.setFixedSize(50, 50)
        self.btn_from_sd.clicked.connect(self.download_selected)
        
        mid_box.addWidget(self.btn_to_sd)
        mid_box.addSpacing(10)
        mid_box.addWidget(self.btn_edit)
        mid_box.addSpacing(10)
        mid_box.addWidget(self.btn_del)
        mid_box.addSpacing(10)
        mid_box.addWidget(self.btn_from_sd)
        panes.addLayout(mid_box)
        
        # Right
        right_box = QVBoxLayout()
        right_box.addWidget(QLabel("REMOTE (SD)", styleSheet="color: #8b949e; font-size: 10px;"))
        self.list_remote = QListWidget()
        right_box.addWidget(self.list_remote)
        self.btn_refresh = QPushButton("REFRESH SD LIST")
        self.btn_refresh.setObjectName("SD_Btn")
        self.btn_refresh.clicked.connect(self.request_sd_list)
        right_box.addWidget(self.btn_refresh)
        panes.addLayout(right_box)
        
        layout.addLayout(panes)
        
        self.sd_console = QTextEdit()
        self.sd_console.setObjectName("SD_Console")
        self.sd_console.setFixedHeight(100)
        self.sd_console.setReadOnly(True)
        layout.addWidget(self.sd_console)

    # --- FEEDBACK HELPERS ---

    def set_ui_busy(self, busy):
        enabled = not busy
        self.btn_to_sd.setEnabled(enabled)
        self.btn_from_sd.setEnabled(enabled)
        self.btn_edit.setEnabled(enabled)
        self.btn_del.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled)
        self.btn_validate.setEnabled(enabled)
        self.btn_full_backup.setEnabled(enabled)
        QApplication.processEvents()

    def update_prog_bar(self, cur, total, msg="Task"):
        pct = int((cur / total) * 100)
        marks = int(20 * cur // total)
        bar = "#" * marks + "-" * (20 - marks)
        if pct % 10 == 0 or cur == total:
            self.sd_console.append(f"{msg}: [{bar}] {pct}%")
            QApplication.processEvents()

    # --- SD OPERATIONS ---

    def request_sd_list(self):
        if not self.current_port:
            return
        self.set_ui_busy(True)
        self.sd_console.clear()
        self.sd_console.append("SCANNING SD CARD...")
        try:
            with serial.Serial(self.current_port, 115200, timeout=1) as ser:
                time.sleep(2)
                ser.reset_input_buffer()
                ser.write(b"SD_LS\n")
                self.list_remote.clear()
                while True:
                    line = ser.readline().decode().strip()
                    if line == "SD_END" or not line:
                        break
                    if line.startswith("FILE:"):
                        name = line.replace("FILE:", "").split("|")[0]
                        self.list_remote.addItem(name)
                self.sd_console.append("Done.")
        except Exception as e:
            self.sd_console.append(f"Error: {e}")
        self.set_ui_busy(False)

    def delete_selected_remote(self):
        item = self.list_remote.currentItem()
        if not item or not self.current_port:
            return
            
        fname = item.text()
        confirm = QMessageBox.question(self, "Confirm Delete", f"Delete {fname} from SD card?", QMessageBox.Yes | QMessageBox.No)
        
        if confirm == QMessageBox.Yes:
            try:
                with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                    time.sleep(2)
                    ser.write(f"SD_DEL:{fname}\n".encode())
                    if ser.readline().decode().strip() == "DEL_OK":
                        self.sd_console.append(f"Deleted: {fname}")
                        self.request_sd_list()
            except Exception as e:
                self.sd_console.append(f"Delete Failed: {e}")

    def upload_selected(self):
        item = self.list_local.currentItem()
        if not item or not self.current_port:
            return
        fname = item.text()
        path = os.path.join(self.sd_local_dir, fname)
        self.set_ui_busy(True)
        try:
            with open(path, 'r') as f:
                lines = f.readlines()
            total = len(lines)
            with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                time.sleep(2)
                ser.write(f"SD_WRITE:{fname}\n".encode())
                while ser.readline().decode().strip() != "READY_TO_RECEIVE":
                    pass
                for i, line in enumerate(lines):
                    ser.write(f"{line.strip()}\n".encode())
                    ser.readline() # ACK
                    self.update_prog_bar(i + 1, total, "Upload")
                ser.write(b"SD_EOF\n")
                self.sd_console.append(f"Stored: {fname}")
                self.request_sd_list()
        except Exception as e:
            self.sd_console.append(f"Upload Error: {e}")
        self.set_ui_busy(False)

    def download_selected(self):
        item = self.list_remote.currentItem()
        if not item or not self.current_port:
            return
        fname = item.text()
        path = os.path.join(self.sd_local_dir, fname)
        self.set_ui_busy(True)
        try:
            with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                time.sleep(2)
                ser.write(f"SD_READ:{fname}\n".encode())
                buffer = []
                while True:
                    line = ser.readline().decode().strip()
                    if line == "END_FILE":
                        break
                    if not line.startswith("START_FILE:"):
                        buffer.append(line)
                with open(path, 'w') as f:
                    f.write("\n".join(buffer))
                self.sd_console.append(f"Downloaded: {fname}")
                self.refresh_local_sd_list()
        except Exception as e:
            self.sd_console.append(f"Download Error: {e}")
        self.set_ui_busy(False)

    def run_full_backup(self):
        count = self.list_remote.count()
        if count == 0:
            return
        self.set_ui_busy(True)
        now = datetime.now().strftime("%Y-%m-%d_%H-%M")
        target = os.path.join(self.sd_backup_dir, now)
        os.makedirs(target, exist_ok=True)
        self.sd_console.append(f"BACKUP START: {now}")
        for i in range(count):
            fname = self.list_remote.item(i).text()
            self.update_prog_bar(i + 1, count, "Archiving")
            try:
                with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                    time.sleep(2)
                    ser.write(f"SD_READ:{fname}\n".encode())
                    buffer = []
                    while True:
                        line = ser.readline().decode().strip()
                        if line == "END_FILE": break
                        if not line.startswith("START_FILE:"): buffer.append(line)
                    with open(os.path.join(target, fname), 'w') as f:
                        f.write("\n".join(buffer))
            except:
                self.sd_console.append(f"Skipped: {fname}")
        self.sd_console.append("Backup Finished.")
        self.set_ui_busy(False)

    # --- CROSS-FILE VALIDATOR ---

    def pre_scan_assets(self):
        """Builds maps of IDs from local files."""
        for k in self.asset_db:
            self.asset_db[k].clear()
        if not os.path.exists(self.sd_local_dir):
            return
        for f in os.listdir(self.sd_local_dir):
            up = f.upper()
            path = os.path.join(self.sd_local_dir, f)
            try:
                with open(path, 'r') as file:
                    for line in file:
                        line = line.strip()
                        if not line or line.startswith("#"): continue
                        parts = line.split(":")
                        if len(parts) > 1:
                            id_val = parts[0]
                            if up == "CHORDS.FKB": self.asset_db["CHORDS"].add(id_val)
                            elif up == "SCALES.FKB": self.asset_db["SCALES"].add(id_val)
                            elif up == "PRESETS.FKB": self.asset_db["PRESETS"].add(id_val)
                            elif up == "KEYMAPS.FKB": self.asset_db["KEYMAPS"].add(id_val)
                            elif up == "MIDIMAPS.FKB": self.asset_db["MIDIMAPS"].add(id_val)
            except: pass

    def run_integrity_check(self):
        item = self.list_local.currentItem()
        if not item: return
        fname = item.text()
        self.sd_console.clear()
        self.sd_console.append(f"VALIDATING: {fname}...")
        self.pre_scan_assets()
        try:
            path = os.path.join(self.sd_local_dir, fname)
            with open(path, 'r') as f:
                lines = f.readlines()
            errs = 0
            for i, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith("#"): continue
                check = self.validate_fkb_line(fname.upper(), line, deep=True)
                if check is not True:
                    self.sd_console.append(f"Line {i+1}: {check}")
                    errs += 1
            if errs == 0: self.sd_console.append("Deep Check: Success.")
            else: self.sd_console.append(f"Deep Check: {errs} Errors.")
        except Exception as e:
            self.sd_console.append(f"Error: {e}")

    def validate_fkb_line(self, fname, line, deep=False):
        # SCALES -> Chords
        if fname == "SCALES.FKB":
            parts = line.split(":")
            if len(parts) < 3: return "Incomplete"
            chords = parts[2].split(",")
            if len(chords) != 12: return f"Expected 12 chords"
            if deep:
                for c in chords:
                    if c.strip() not in self.asset_db["CHORDS"]:
                        return f"Chord {c} missing in CHORDS.FKB"
            return True

        # PRESETS -> Scales(S), Keymap(KM), Midimap(MM)
        if fname == "PRESETS.FKB":
            parts = line.split(":")
            if len(parts) < 3: return "Incomplete"
            data = parts[2].split(",")
            if len(data) != 10: return "Need 10 params"
            if deep:
                # data[1]=BS, [2]=ES, [3]=KM, [4]=MM
                if data[1].strip() not in self.asset_db["SCALES"]: return f"Scale {data[1]} missing"
                if data[2].strip() not in self.asset_db["SCALES"]: return f"Scale {data[2]} missing"
                if data[3].strip() not in self.asset_db["KEYMAPS"]: return f"Keymap {data[3]} missing"
                if data[4].strip() not in self.asset_db["MIDIMAPS"]: return f"Midimap {data[4]} missing"
            return True

        # LIVEMAP -> Chords
        if fname == "LIVEMAP.FKB":
            chords = line.split(",")
            if len(chords) != 13: return "Need 13 chords"
            if deep:
                for c in chords:
                    if c.strip() not in self.asset_db["CHORDS"]: return f"Chord {c} missing"
            return True

        # FAVS -> Preset Name
        if fname == "FAVS.FKB":
            if not line.startswith("F"): return "Missing 'F'"
            # Cross check preset name if present
            return True

        # CHORDS / KM / MM Basic Formatting
        if fname == "CHORDS.FKB" or fname == "KEYMAPS.FKB" or fname == "MIDIMAPS.FKB":
            if ":" not in line: return "Format Error"
            return True
            
        return True

    def open_editor(self):
        item = self.list_local.currentItem()
        if not item: return
        fname = item.text()
        path = os.path.join(self.sd_local_dir, fname)
        try:
            with open(path, 'r') as f:
                content = f.read()
            dlg = FileEditor(fname, content, self)
            if dlg.exec_() == QDialog.Accepted:
                with open(path, 'w') as f:
                    f.write(dlg.editor.toPlainText())
                self.sd_console.append(f"Saved: {fname}")
        except Exception as e:
            self.sd_console.append(f"Editor Error: {e}")

    def refresh_local_sd_list(self):
        self.list_local.clear()
        if os.path.exists(self.sd_local_dir):
            files = sorted([f for f in os.listdir(self.sd_local_dir) if f.lower().endswith(".fkb")])
            self.list_local.addItems(files)

    # --- ANCHORED TABS (Flash/Generator) ---

    def setup_uploader_tab(self):
        layout = QVBoxLayout(self.tab_flash); layout.setContentsMargins(30, 20, 30, 20)
        header_row = QHBoxLayout(); header_row.addWidget(QLabel("FIRMWARE UPDATE (ATmega2560)", styleSheet="color: #2ecc71; font-weight: bold; font-size: 14px;")); header_row.addStretch()
        self.btn_backup_fw = QPushButton("BACKUP FIRMWARE"); self.btn_backup_fw.setObjectName("BackupBtn"); self.btn_backup_fw.setFixedSize(180, 30); self.btn_backup_fw.setEnabled(False); self.btn_backup_fw.clicked.connect(self.start_backup_fw); header_row.addWidget(self.btn_backup_fw); layout.addLayout(header_row)
        layout.addWidget(QLabel("Select .hex to flash.", styleSheet="color: #8b949e; font-size: 11px;")); layout.addSpacing(20)
        sel_row = QHBoxLayout(); self.combo_hex = QComboBox(); self.combo_hex.setMinimumWidth(300); self.btn_refresh_fw = QPushButton("Refresh List"); self.btn_refresh_fw.setObjectName("UtilityBtn"); self.btn_refresh_fw.clicked.connect(self.refresh_firmware_list); sel_row.addWidget(self.combo_hex); sel_row.addWidget(self.btn_refresh_fw); sel_row.addStretch(); layout.addLayout(sel_row); layout.addSpacing(10)
        self.btn_flash = QPushButton("FLASH PROCESS"); self.btn_flash.setObjectName("FlashBtn"); self.btn_flash.setFixedHeight(50); self.btn_flash.setEnabled(False); self.btn_flash.clicked.connect(self.start_flash); layout.addWidget(self.btn_flash); layout.addSpacing(20); layout.addWidget(QLabel("CONSOLE", styleSheet="color: #8b949e; font-weight: bold; font-size: 9px;"))
        self.console_box = QTextEdit(); self.console_box.setObjectName("ConsoleBox"); self.console_box.setReadOnly(True); self.console_box.setFixedHeight(120); layout.addWidget(self.console_box)

    def setup_bitmasker_tab(self):
        layout = QVBoxLayout(self.tab_gen); layout.setContentsMargins(25, 10, 25, 15); layout.setSpacing(5)
        layout.addWidget(QLabel("STEP 1 : ID & NAME", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        input_row = QHBoxLayout(); self.map_id_edit = QLineEdit("01"); self.map_id_edit.setFixedWidth(45); self.map_id_edit.textChanged.connect(self.update_result_string); self.map_name_edit = QLineEdit("Default_Map"); self.map_name_edit.setFixedWidth(200); self.map_name_edit.textChanged.connect(self.update_result_string); self.btn_check_name = QPushButton("Check Name"); self.btn_check_name.setObjectName("UtilityBtn"); self.btn_check_name.setFixedWidth(90); input_row.addWidget(QLabel("ID:")); input_row.addWidget(self.map_id_edit); input_row.addWidget(QLabel("NAME:")); input_row.addWidget(self.map_name_edit); input_row.addWidget(self.btn_check_name); input_row.addStretch(); layout.addLayout(input_row)
        note_head = QHBoxLayout(); note_head.addWidget(QLabel("STEP 2 : SELECT NOTES", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;")); self.note_all_chk = QCheckBox("Select All"); self.note_all_chk.setStyleSheet("color: white; font-size: 10px;"); self.note_all_chk.stateChanged.connect(self.on_note_select_all); note_head.addStretch(); note_head.addWidget(self.note_all_chk); layout.addLayout(note_head)
        note_grid = QGridLayout(); note_grid.setSpacing(4)
        for i in range(25):
            btn = QPushButton(str(i+1)); btn.setObjectName("NoteBtn"); btn.setCheckable(True); btn.setFixedSize(32, 32); btn.clicked.connect(self.on_note_clicked); self.note_buttons.append(btn); note_grid.addWidget(btn, i // 13, i % 13)
        layout.addLayout(note_grid); chan_head = QHBoxLayout(); chan_head.addWidget(QLabel("STEP 3 : MAP CHANNELS", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;")); self.chan_all_chk = QCheckBox("Select All"); self.chan_all_chk.setStyleSheet("color: white; font-size: 10px;"); self.chan_all_chk.stateChanged.connect(self.on_chan_select_all); chan_head.addStretch(); chan_head.addWidget(self.chan_all_chk); layout.addLayout(chan_head)
        chan_grid = QGridLayout(); chan_grid.setSpacing(6)
        for i in range(16):
            btn = QPushButton(str(i+1)); btn.setObjectName("ChannelBtn"); btn.setCheckable(True); btn.setFixedSize(75, 40); btn.clicked.connect(self.on_channel_clicked); self.chan_buttons.append(btn); chan_grid.addWidget(btn, i // 8, i % 8)
        layout.addLayout(chan_grid); self.btn_clear = QPushButton("CLEAR CURRENT MAP"); self.btn_clear.setObjectName("UtilityBtn"); self.btn_clear.setFixedHeight(30); self.btn_clear.setStyleSheet("color: #ff4444; font-size: 10px;"); self.btn_clear.clicked.connect(self.clear_map); layout.addWidget(self.btn_clear); layout.addStretch(); layout.addWidget(QLabel("STEP 4 : Copy to MIDIMAPS.FKB", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;")); layout.addWidget(QLabel("FINAL LINE", styleSheet="color: #8b949e; font-weight: bold; font-size: 9px;"))
        res_box_lay = QHBoxLayout(); self.result_box = QTextEdit(); self.result_box.setObjectName("ResultBox"); self.result_box.setReadOnly(True); self.result_box.setFixedHeight(60); self.btn_copy = QPushButton("COPY"); self.btn_copy.setFixedSize(80, 60); self.btn_copy.setStyleSheet("background-color: #2ecc71; color: black; font-weight: bold;"); self.btn_copy.clicked.connect(self.copy_result); res_box_lay.addWidget(self.result_box); res_box_lay.addWidget(self.btn_copy); layout.addLayout(res_box_lay); self.update_result_string()

    def refresh_firmware_list(self):
        self.combo_hex.clear()
        if os.path.exists(self.firmware_dir):
            files = sorted([f for f in os.listdir(self.firmware_dir) if f.endswith(".hex")])
            if not files: self.combo_hex.addItem("No .hex files"); self.btn_flash.setEnabled(False)
            else: self.combo_hex.addItems(files); 
            if self.current_port: self.btn_flash.setEnabled(True)

    def start_flash(self):
        hex_file = os.path.join(self.firmware_dir, self.combo_hex.currentText())
        self.btn_flash.setEnabled(False); self.btn_backup_fw.setEnabled(False); self.btn_refresh_fw.setEnabled(False)
        self.console_box.clear(); self.console_box.append(f"Flashing: {self.combo_hex.currentText()}")
        args = ["-C", self.conf_path, "-v", "-p", "m2560", "-c", "wiring", "-P", self.current_port, "-b", "115200", "-D", "-U", f"flash:w:{hex_file}:i"]
        self.process.start(self.tools_path, args)

    def start_backup_fw(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save FW", os.path.join(self.firmware_dir, "backup.hex"), "Hex Files (*.hex)")
        if not file_path: return
        self.btn_flash.setEnabled(False); self.btn_backup_fw.setEnabled(False)
        args = ["-C", self.conf_path, "-v", "-p", "m2560", "-c", "wiring", "-P", self.current_port, "-b", "115200", "-U", f"flash:r:{file_path}:i"]
        self.process.start(self.tools_path, args)

    def on_console_output(self):
        data = self.process.readAllStandardError().data().decode()
        if not data: data = self.process.readAllStandardOutput().data().decode()
        self.console_box.insertPlainText(data); self.console_box.ensureCursorVisible()

    def on_flash_finished(self):
        if self.current_port: self.btn_flash.setEnabled(True); self.btn_backup_fw.setEnabled(True)
        self.btn_refresh_fw.setEnabled(True); self.console_box.append("\nDone."); self.refresh_firmware_list()

    def clear_map(self):
        self.note_masks = [0] * 25; self.selected_notes.clear()
        for btn in self.note_buttons:
            btn.blockSignals(True); btn.setChecked(False); btn.setProperty("locked", "false"); btn.style().unpolish(btn); btn.style().polish(btn); btn.blockSignals(False)
        for btn in self.chan_buttons:
            btn.blockSignals(True); btn.setChecked(False); btn.blockSignals(False)
        self.note_all_chk.setChecked(False); self.chan_all_chk.setChecked(False); self.update_result_string()

    def on_note_clicked(self):
        btn = self.sender(); idx = int(btn.text()) - 1
        if not (QApplication.keyboardModifiers() == Qt.ControlModifier):
            target_mask = self.note_masks[idx]; self.selected_notes.clear()
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
            self.note_masks[idx] = mask; btn = self.note_buttons[idx]; btn.setProperty("locked", "true" if mask > 0 else "false"); btn.style().unpolish(btn); btn.style().polish(btn)
        self.update_result_string()

    def sync_channels_to_mask(self, mask):
        for i, btn in enumerate(self.chan_buttons): btn.blockSignals(True); btn.setChecked(bool(mask & (1 << i))); btn.blockSignals(False)

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

    def update_result_string(self):
        mid = self.map_id_edit.text().zfill(2); name = self.map_name_edit.text()
        hex_data = ",".join([f"{m:04X}" for m in self.note_masks]); self.result_box.setText(f"MM{mid}:{name}:{hex_data}")

    def copy_result(self):
        QApplication.clipboard().setText(self.result_box.toPlainText()); self.btn_copy.setText("COPIED!")
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("COPY"))

    def auto_detect_hardware(self):
        ports = list(serial.tools.list_ports.comports()); found = False
        for p in ports:
            for board in self.known_boards:
                if p.vid == board['vid'] and p.pid == board['pid']:
                    self.status_dot.setStyleSheet("color: #2ecc71; font-size: 14px; margin-left: 10px;")
                    self.status_text.setText(f"Connected: {board['name']} ({p.device})")
                    self.current_port = p.device; self.btn_backup_fw.setEnabled(True)
                    if self.combo_hex.currentText().endswith(".hex"): self.btn_flash.setEnabled(True)
                    found = True; break
        if not found:
            self.status_dot.setStyleSheet("color: #e74c3c; font-size: 14px; margin-left: 10px;")
            self.status_text.setText("No Device Detected"); self.current_port = None; self.btn_flash.setEnabled(False); self.btn_backup_fw.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv); window = MFKBApp(); window.show(); sys.exit(app.exec_())