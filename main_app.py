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
from PyQt5.QtGui import QTextCursor, QFont

# --- PATH CONFIGURATION FOR COMPILED VERSION ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- THE STYLESHEET (Golden v1.9.7 - Restored Selection Colors) ---
STYLE_SHEET = """
QMainWindow, QDialog { 
    background-color: #0a0a0a; 
}
#ConnBar { 
    background-color: #161b22; 
    border-bottom: 1px solid #30363d; 
}
QLabel { 
    color: #ffffff; 
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
}

/* BITMASKER BUTTON STYLING */
QPushButton#NoteBtn, QPushButton#ChannelBtn {
    background-color: #21262d; 
    border: 1px solid #30363d;
    color: #8b949e; 
    border-radius: 4px; 
    font-weight: bold; 
    font-size: 12px;
}
QPushButton#NoteBtn:checked { 
    background-color: #27ae60; 
    color: #ffffff; 
}
QPushButton#NoteBtn[locked="true"] { 
    background-color: #2ecc71; 
    color: #000000; 
    border: none; 
}
QPushButton#ChannelBtn:checked { 
    background-color: #2ecc71; 
    color: #000000; 
    border: none; 
}

/* UTILITY BUTTONS */
QPushButton#UtilityBtn, QPushButton#FlashBtn, QPushButton#BackupBtn, QPushButton#SD_Btn {
    background-color: #21262d; 
    border: 1px solid #30363d;
    color: #8b949e; 
    border-radius: 4px; 
    font-weight: bold; 
    font-size: 12px;
}
QPushButton#FlashBtn { 
    background-color: #2ecc71; 
    color: #000000; 
    border: none; 
}
QPushButton#FlashBtn:disabled, #BackupBtn:disabled, #SD_Btn:disabled { 
    background-color: #30363d; 
    color: #4d535e; 
}
QPushButton#ChannelBtn:hover, QPushButton#NoteBtn:hover, #UtilityBtn:hover, 
#FlashBtn:hover, #BackupBtn:hover, #SD_Btn:hover { 
    border-color: #2ecc71; 
}

QPushButton#DelBtn {
    background-color: #21262d; 
    border: 1px solid #30363d;
    color: #ff4444; 
    border-radius: 4px; 
    font-weight: bold;
}
QPushButton#DelBtn:hover { 
    border-color: #ff4444; 
}

QLineEdit, QComboBox {
    background-color: #0d1117; 
    border: 1px solid #30363d;
    padding: 8px; 
    border-radius: 4px; 
    color: #8b949e;
    font-family: monospace; 
    font-size: 12px;
}
QListWidget { 
    background-color: #0d1117; 
    border: 1px solid #30363d; 
    color: #e6edf3; 
    border-radius: 4px; 
    padding: 5px; 
}
QListWidget::item:selected { 
    background-color: #2ecc71; 
    color: #000000; 
}
QTextEdit#ResultBox, QTextEdit#ConsoleBox, #SD_Console, #EditorArea {
    background-color: #000000; 
    border: 1px solid #30363d; 
    color: #2ecc71;
    font-family: 'Courier New', monospace; 
    font-size: 11px; 
    border-radius: 4px;
}
QTextEdit#LineGutter {
    background-color: #161b22; 
    border: 1px solid #30363d; 
    color: #4d535e;
    font-family: 'Courier New', monospace; 
    font-size: 11px;
    border-radius: 4px;
}
"""

class FileEditor(QDialog):
    """Expanded Modal Editor with Line Numbers and Find bar."""
    def __init__(self, filename, content, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.parent_app = parent
        self.setWindowTitle(f"MFKB Editor - {filename}")
        self.setMinimumSize(900, 650)
        self.setStyleSheet(STYLE_SHEET)
        
        layout = QVBoxLayout(self)
        
        # 1. Search Bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("FIND:"))
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Find text...")
        search_layout.addWidget(self.search_field)
        self.btn_find = QPushButton("FIND NEXT")
        self.btn_find.setObjectName("SD_Btn")
        self.btn_find.setFixedWidth(100)
        self.btn_find.clicked.connect(self.find_text)
        self.search_field.returnPressed.connect(self.find_text)
        search_layout.addWidget(self.btn_find)
        layout.addLayout(search_layout)
        
        # 2. Text Editor with Sync Gutter
        editor_hbox = QHBoxLayout()
        self.line_gutter = QTextEdit()
        self.line_gutter.setObjectName("LineGutter")
        self.line_gutter.setFixedWidth(50)
        self.line_gutter.setReadOnly(True)
        self.line_gutter.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.line_gutter.setAlignment(Qt.AlignRight)
        
        self.editor = QTextEdit()
        self.editor.setObjectName("EditorArea")
        self.editor.setPlainText(content)
        self.editor.setAcceptRichText(False)
        self.editor.setLineWrapMode(QTextEdit.NoWrap)
        
        self.editor.verticalScrollBar().valueChanged.connect(self.line_gutter.verticalScrollBar().setValue)
        self.editor.textChanged.connect(self.refresh_numbers)
        
        editor_hbox.addWidget(self.line_gutter)
        editor_hbox.addWidget(self.editor)
        layout.addLayout(editor_hbox)
        
        # 3. Actions
        footer = QHBoxLayout()
        self.btn_val = QPushButton("VALIDATE")
        self.btn_val.setObjectName("SD_Btn")
        self.btn_val.clicked.connect(self.run_editor_check)
        footer.addWidget(self.btn_val)
        footer.addStretch()
        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setObjectName("SD_Btn")
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)
        self.btn_save = QPushButton("SAVE & EXIT")
        self.btn_save.setObjectName("SD_Btn")
        self.btn_save.clicked.connect(self.accept)
        footer.addWidget(self.btn_save)
        layout.addLayout(footer)
        
        self.refresh_numbers()

    def refresh_numbers(self):
        count = self.editor.document().blockCount()
        nums = [str(i) for i in range(1, count + 1)]
        self.line_gutter.setPlainText("\n".join(nums))

    def find_text(self):
        query = self.search_field.text()
        if not query:
            return
        if not self.editor.find(query):
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(query)

    def run_editor_check(self):
        self.parent_app.pre_scan_assets()
        lines = self.editor.toPlainText().split('\n')
        errors = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            res = self.parent_app.validate_fkb_line(self.filename.upper(), line, deep=True)
            if res is not True:
                errors.append(f"Line {i+1}: {res}")
        if not errors:
            self.editor.append("\n# [SUCCESS] No errors found.")
        else:
            self.editor.append("\n# [FAILED] Format Errors:")
            for e in errors:
                self.editor.append(f"# {e}")
        self.editor.moveCursor(QTextCursor.End)


class MFKBApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # State
        self.note_masks = [0] * 25 
        self.selected_notes = set() 
        self.chan_buttons = []
        self.note_buttons = []
        self.current_port = None
        self.ser = None 
        
        # Deep Validation Database
        self.asset_db = {
            "CHORDS": set(), "SCALES": set(), "PRESETS": set(), 
            "KEYMAPS": set(), "MIDIMAPS": set()
        }
        
        # Paths
        self.tools_path = os.path.join(BASE_DIR, "tools", "avrdude")
        self.conf_path = os.path.join(BASE_DIR, "tools", "avrdude_linux.conf")
        self.firmware_dir = os.path.join(BASE_DIR, "firmware")
        self.sd_local_dir = os.path.join(BASE_DIR, "sdcard")
        self.sd_backup_dir = os.path.join(BASE_DIR, "sdcard", "backups")
        
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
        self.setWindowTitle("MFKB Companion App v1.9.7")
        self.setFixedSize(850, 720) 
        self.setStyleSheet(STYLE_SHEET)
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Connection Header
        self.conn_bar = QFrame()
        self.conn_bar.setObjectName("ConnBar")
        self.conn_bar.setFixedHeight(40)
        conn_lay = QHBoxLayout(self.conn_bar)
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 14px; margin-left: 10px;")
        self.status_text = QLabel("Scanning Hardware...")
        self.status_text.setStyleSheet("color: #8b949e; font-size: 10px;")
        conn_lay.addWidget(self.status_dot)
        conn_lay.addWidget(self.status_text)
        conn_lay.addStretch()
        main_layout.addWidget(self.conn_bar)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.tab_gen = QWidget()
        self.tabs.addTab(self.tab_gen, "MidiMap Generator")
        self.tab_sd = QWidget()
        self.tabs.addTab(self.tab_sd, "SD Card Manager")
        self.tab_flash = QWidget()
        self.tabs.addTab(self.tab_flash, "Firmware Uploader")

        self.setup_bitmasker_tab()
        self.setup_sd_tab()
        self.setup_uploader_tab()

    # --- TAB 1: BITMASKER (RESTORED SELECTION LOGIC) ---

    def setup_bitmasker_tab(self):
        layout = QVBoxLayout(self.tab_gen)
        layout.setContentsMargins(25, 10, 25, 15)
        layout.setSpacing(5)
        
        layout.addWidget(QLabel("STEP 1 : ID & NAME", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        inp = QHBoxLayout()
        self.map_id_edit = QLineEdit("01")
        self.map_id_edit.setFixedWidth(45)
        self.map_id_edit.textChanged.connect(self.update_result_string)
        self.map_name_edit = QLineEdit("Default_Map")
        self.map_name_edit.setFixedWidth(200)
        self.map_name_edit.textChanged.connect(self.update_result_string)
        self.btn_check_name = QPushButton("Check Name")
        self.btn_check_name.setObjectName("UtilityBtn")
        self.btn_check_name.setFixedWidth(90)
        
        inp.addWidget(QLabel("ID:"))
        inp.addWidget(self.map_id_edit)
        inp.addWidget(QLabel("NAME:"))
        inp.addWidget(self.map_name_edit)
        inp.addWidget(self.btn_check_name)
        inp.addStretch()
        layout.addLayout(inp)
        
        nh = QHBoxLayout()
        nh.addWidget(QLabel("STEP 2 : SELECT NOTES", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        self.note_all_chk = QCheckBox("Select All")
        self.note_all_chk.setStyleSheet("color: white; font-size: 10px;")
        self.note_all_chk.stateChanged.connect(self.on_note_select_all)
        nh.addStretch()
        nh.addWidget(self.note_all_chk)
        layout.addLayout(nh)
        
        note_grid = QGridLayout()
        note_grid.setSpacing(4)
        for i in range(25):
            btn = QPushButton(str(i+1))
            btn.setObjectName("NoteBtn")
            btn.setCheckable(True)
            btn.setFixedSize(32, 32)
            btn.clicked.connect(self.on_note_clicked)
            self.note_buttons.append(btn)
            note_grid.addWidget(btn, i // 13, i % 13)
        layout.addLayout(note_grid)
        
        ch = QHBoxLayout()
        ch.addWidget(QLabel("STEP 3 : MAP CHANNELS", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        self.chan_all_chk = QCheckBox("Select All")
        self.chan_all_chk.setStyleSheet("color: white; font-size: 10px;")
        self.chan_all_chk.stateChanged.connect(self.on_chan_select_all)
        ch.addStretch()
        ch.addWidget(self.chan_all_chk)
        layout.addLayout(ch)
        
        chan_grid = QGridLayout()
        chan_grid.setSpacing(6)
        for i in range(16):
            btn = QPushButton(str(i+1))
            btn.setObjectName("ChannelBtn")
            btn.setCheckable(True)
            btn.setFixedSize(75, 40)
            btn.clicked.connect(self.on_channel_clicked)
            self.chan_buttons.append(btn)
            chan_grid.addWidget(btn, i // 8, i % 8)
        layout.addLayout(chan_grid)
        
        self.btn_clear = QPushButton("CLEAR CURRENT MAP")
        self.btn_clear.setObjectName("UtilityBtn")
        self.btn_clear.setFixedHeight(30)
        self.btn_clear.setStyleSheet("color: #ff4444; font-size: 10px;")
        self.btn_clear.clicked.connect(self.clear_map)
        layout.addWidget(self.btn_clear)
        
        layout.addStretch()
        layout.addWidget(QLabel("STEP 4 : Copy result in MIDIMAPS.FKB", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        
        res = QHBoxLayout()
        self.result_box = QTextEdit()
        self.result_box.setObjectName("ResultBox")
        self.result_box.setReadOnly(True)
        self.result_box.setFixedHeight(60)
        self.btn_copy = QPushButton("COPY")
        self.btn_copy.setFixedSize(80, 60)
        self.btn_copy.setStyleSheet("background-color: #2ecc71; color: black; font-weight: bold;")
        self.btn_copy.clicked.connect(self.copy_result)
        res.addWidget(self.result_box)
        res.addWidget(self.btn_copy)
        layout.addLayout(res)
        self.update_result_string()

    def on_note_clicked(self):
        btn = self.sender()
        idx = int(btn.text()) - 1
        if not (QApplication.keyboardModifiers() == Qt.ControlModifier):
            target_mask = self.note_masks[idx]
            self.selected_notes.clear()
            if target_mask > 0:
                for i, m in enumerate(self.note_masks):
                    if m == target_mask:
                        self.selected_notes.add(i)
            else:
                self.selected_notes.add(idx)
            for i, b in enumerate(self.note_buttons):
                b.setChecked(i in self.selected_notes)
            self.sync_channels_to_mask(target_mask)
        else:
            if btn.isChecked():
                self.selected_notes.add(idx)
            else:
                self.selected_notes.discard(idx)

    def on_channel_clicked(self):
        mask = 0
        for i, btn in enumerate(self.chan_buttons):
            if btn.isChecked():
                mask |= (1 << i)
        for idx in self.selected_notes:
            self.note_masks[idx] = mask
            btn = self.note_buttons[idx]
            btn.setProperty("locked", "true" if mask > 0 else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.update_result_string()

    def sync_channels_to_mask(self, mask):
        for i, btn in enumerate(self.chan_buttons):
            btn.blockSignals(True)
            btn.setChecked(bool(mask & (1 << i)))
            btn.blockSignals(False)

    def on_note_select_all(self, state):
        is_all = (state == Qt.Checked)
        for i, btn in enumerate(self.note_buttons):
            btn.setChecked(is_all)
            if is_all:
                self.selected_notes.add(i)
            else:
                self.selected_notes.discard(i)

    def on_chan_select_all(self, state):
        is_all = (state == Qt.Checked)
        for btn in self.chan_buttons:
            btn.setChecked(is_all)
        self.on_channel_clicked()

    def update_result_string(self):
        mid = self.map_id_edit.text().zfill(2)
        name = self.map_name_edit.text()
        hex_data = ",".join([f"{m:04X}" for m in self.note_masks])
        self.result_box.setText(f"MM{mid}:{name}:{hex_data}")

    def copy_result(self):
        QApplication.clipboard().setText(self.result_box.toPlainText())
        self.btn_copy.setText("COPIED!")
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("COPY"))

    def clear_map(self):
        self.note_masks = [0] * 25
        self.selected_notes.clear()
        for btn in self.note_buttons:
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.setProperty("locked", "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.blockSignals(False)
        for btn in self.chan_buttons:
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        self.note_all_chk.setChecked(False)
        self.chan_all_chk.setChecked(False)
        self.update_result_string()

    # --- TAB 2: SD MANAGER ---

    def setup_sd_tab(self):
        layout = QVBoxLayout(self.tab_sd)
        layout.setContentsMargins(20, 20, 20, 20)
        h_row = QHBoxLayout()
        h_row.addWidget(QLabel("SD CARD MANAGER", styleSheet="color: #2ecc71; font-weight: bold; font-size: 12px;"))
        h_row.addWidget(QLabel("Caution: Edit LOCAL FILES!", styleSheet="color: #ff0000; font-weight: bold; font-size: 10px;"))
        h_row.addStretch()
        self.btn_full_backup = QPushButton("FULL SD BACKUP")
        self.btn_full_backup.setObjectName("SD_Btn")
        self.btn_full_backup.setFixedWidth(140)
        self.btn_full_backup.clicked.connect(self.run_full_backup)
        h_row.addWidget(self.btn_full_backup)
        layout.addLayout(h_row)
        
        panes = QHBoxLayout()
        left_box = QVBoxLayout()
        left_box.addWidget(QLabel("LOCAL (PC)", styleSheet="color: #8b949e; font-size: 10px;"))
        self.list_local = QListWidget()
        left_box.addWidget(self.list_local)
        self.btn_validate = QPushButton("CHECK INTEGRITY")
        self.btn_validate.setObjectName("SD_Btn")
        self.btn_validate.clicked.connect(self.run_integrity_check)
        left_box.addWidget(self.btn_validate)
        panes.addLayout(left_box)
        
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
        self.sd_console.setFixedHeight(120)
        self.sd_console.setReadOnly(True)
        layout.addWidget(self.sd_console)

    def set_busy(self, busy):
        state = not busy
        self.btn_to_sd.setEnabled(state); self.btn_from_sd.setEnabled(state); self.btn_edit.setEnabled(state)
        self.btn_del.setEnabled(state); self.btn_refresh.setEnabled(state); self.btn_validate.setEnabled(state)
        self.btn_full_backup.setEnabled(state); QApplication.processEvents()

    def update_prog_bar(self, cur, tot, msg="Task"):
        pct = int((cur / tot) * 100); marks = int(25 * cur // tot); bar = "#" * marks + "-" * (25 - marks)
        if pct % 10 == 0 or cur == tot:
            self.sd_console.append(f"{msg}: [{bar}] {pct}%"); QApplication.processEvents()

    def request_sd_list(self):
        if not self.current_port: return
        self.set_busy(True); self.sd_console.clear()
        try:
            with serial.Serial(self.current_port, 115200, timeout=1) as ser:
                time.sleep(2); ser.reset_input_buffer(); ser.write(b"SD_LS\n"); self.list_remote.clear()
                start = time.time()
                while (time.time() - start) < 5:
                    if ser.in_waiting:
                        ln = ser.readline().decode().strip()
                        if ln == "SD_END" or not ln: break
                        if ln.startswith("FILE:"):
                            self.list_remote.addItem(ln.replace("FILE:", "").split("|")[0])
                self.sd_console.append("Scan Done.")
        except Exception as e: self.sd_console.append(f"Error: {e}")
        self.set_busy(False)

    def delete_selected_remote(self):
        item = self.list_remote.currentItem()
        if not item or not self.current_port: return
        fname = item.text()
        if QMessageBox.question(self, "Delete", f"Erase {fname}?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                    time.sleep(2); ser.write(f"SD_DEL:{fname}\n".encode())
                    if ser.readline().decode().strip() == "DEL_OK":
                        self.sd_console.append(f"Deleted: {fname}"); self.request_sd_list()
            except Exception as e: self.sd_console.append(f"Fail: {e}")

    def upload_selected(self):
        item = self.list_local.currentItem()
        if not item or not self.current_port: return
        fname = item.text(); path = os.path.join(self.sd_local_dir, fname)
        self.set_busy(True)
        try:
            with open(path, 'r') as f: lines = f.readlines()
            total = len(lines)
            with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                time.sleep(2); ser.write(f"SD_WRITE:{fname}\n".encode())
                while ser.readline().decode().strip() != "READY_TO_RECEIVE": pass
                for i, ln in enumerate(lines):
                    ser.write(f"{ln.strip()}\n".encode()); ser.readline(); self.update_prog_bar(i + 1, total, "Upload")
                ser.write(b"SD_EOF\n"); self.sd_console.append(f"Stored: {fname}"); self.request_sd_list()
        except Exception as e: self.sd_console.append(f"Error: {e}")
        self.set_busy(False)

    def download_selected(self):
        item = self.list_remote.currentItem()
        if not item or not self.current_port: return
        fname = item.text(); path = os.path.join(self.sd_local_dir, fname)
        self.set_busy(True)
        try:
            with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                time.sleep(2); ser.write(f"SD_READ:{fname}\n".encode()); buf = []
                while True:
                    ln = ser.readline().decode().strip()
                    if ln == "END_FILE": break
                    if not ln.startswith("START_FILE:"): buf.append(ln)
                with open(path, 'w') as f: f.write("\n".join(buf))
                self.sd_console.append(f"Saved: {fname}"); self.refresh_local_sd_list()
        except Exception as e: self.sd_console.append(f"Error: {e}")
        self.set_busy(False)

    def run_full_backup(self):
        cnt = self.list_remote.count()
        if cnt == 0: return
        self.set_busy(True); ts = datetime.now().strftime("%Y-%m-%d_%H-%M"); dest = os.path.join(self.sd_backup_dir, ts); os.makedirs(dest, exist_ok=True)
        for i in range(cnt):
            fname = self.list_remote.item(i).text(); self.update_prog_bar(i + 1, cnt, "Archiving")
            try:
                with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                    time.sleep(2); ser.write(f"SD_READ:{fname}\n".encode()); b = []
                    while True:
                        ln = ser.readline().decode().strip();
                        if ln == "END_FILE": break
                        if not ln.startswith("START_FILE:"): b.append(ln)
                    with open(os.path.join(dest, fname), 'w') as f: f.write("\n".join(b))
            except: pass
        self.sd_console.append("Backup Complete."); self.set_busy(False)

    # --- CROSS-FILE VALIDATOR ---

    def pre_scan_assets(self):
        for k in self.asset_db: self.asset_db[k].clear()
        if not os.path.exists(self.sd_local_dir): return
        for fn in os.listdir(self.sd_local_dir):
            up = fn.upper(); pth = os.path.join(self.sd_local_dir, fn)
            try:
                with open(pth, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"): continue
                        pts = line.split(":")
                        if len(pts) > 1:
                            id_v = pts[0].strip()
                            if up == "CHORDS.FKB": self.asset_db["CHORDS"].add(id_v)
                            elif up == "SCALES.FKB": self.asset_db["SCALES"].add(id_v)
                            elif up == "PRESETS.FKB": self.asset_db["PRESETS"].add(id_v)
                            elif up == "KEYMAPS.FKB": self.asset_db["KEYMAPS"].add(id_v)
                            elif up == "MIDIMAPS.FKB": self.asset_db["MIDIMAPS"].add(id_v)
            except: pass

    def run_integrity_check(self):
        item = self.list_local.currentItem()
        if not item: return
        self.sd_console.clear(); self.pre_scan_assets()
        try:
            path = os.path.join(self.sd_local_dir, item.text())
            with open(path, 'r') as f: lines = f.readlines()
            errs = 0
            for i, ln in enumerate(lines):
                ln = ln.strip()
                if not ln or ln.startswith("#"): continue
                res = self.validate_fkb_line(item.text().upper(), ln, deep=True)
                if res is not True: self.sd_console.append(f"L{i + 1}: {res}"); errs += 1
            self.sd_console.append(f"Result: {errs} Errors.")
        except Exception as e: self.sd_console.append(f"Error: {e}")

    def validate_fkb_line(self, fname, line, deep=False):
        if fname == "SCALES.FKB":
            p = line.split(":"); 
            if len(p) < 3: return "Bad structure"
            ch = p[2].split(",")
            if deep:
                for c in ch:
                    if c.strip() not in self.asset_db["CHORDS"]: return f"Chord {c} missing"
            return True
        if fname == "PRESETS.FKB":
            p = line.split(":"); 
            if len(p) < 3: return "Bad structure"
            dm = p[2].split(",")
            if deep:
                if dm[1].strip() not in self.asset_db["SCALES"]: return f"Scale {dm[1]} missing"
                if dm[2].strip() not in self.asset_db["SCALES"]: return f"Scale {dm[2]} missing"
                if dm[3].strip() not in self.asset_db["KEYMAPS"]: return f"Keymap {dm[3]} missing"
                if dm[4].strip() not in self.asset_db["MIDIMAPS"]: return f"Midimap {dm[4]} missing"
            return True
        return True

    def open_editor(self):
        item = self.list_local.currentItem()
        if not item: return
        path = os.path.join(self.sd_local_dir, item.text())
        try:
            with open(path, 'r') as f: text = f.read()
            dlg = FileEditor(item.text(), text, self)
            if dlg.exec_() == QDialog.Accepted:
                with open(path, 'w') as f: f.write(dlg.editor.toPlainText())
                self.sd_console.append(f"Updated: {item.text()}")
        except Exception as e: self.sd_console.append(f"Error: {e}")

    def refresh_local_sd_list(self):
        self.list_local.clear()
        if os.path.exists(self.sd_local_dir):
            files = sorted([f for f in os.listdir(self.sd_local_dir) if f.lower().endswith(".fkb")])
            self.list_local.addItems(files)

    # --- TAB 3: FIRMWARE ---

    def setup_uploader_tab(self):
        layout = QVBoxLayout(self.tab_flash); layout.setContentsMargins(30, 20, 30, 20)
        h = QHBoxLayout(); h.addWidget(QLabel("FIRMWARE UPDATE", styleSheet="color: #2ecc71; font-weight: bold; font-size: 14px;")); h.addStretch()
        self.btn_backup_fw = QPushButton("BACKUP FIRMWARE"); self.btn_backup_fw.setObjectName("BackupBtn"); self.btn_backup_fw.setFixedSize(180, 30); self.btn_backup_fw.setEnabled(False); self.btn_backup_fw.clicked.connect(self.start_backup_fw); h.addWidget(self.btn_backup_fw); layout.addLayout(h)
        s = QHBoxLayout(); self.combo_hex = QComboBox(); self.combo_hex.setMinimumWidth(300); self.btn_refresh_fw = QPushButton("Refresh"); self.btn_refresh_fw.setObjectName("UtilityBtn"); self.btn_refresh_fw.clicked.connect(self.refresh_firmware_list); s.addWidget(self.combo_hex); s.addWidget(self.btn_refresh_fw); s.addStretch(); layout.addLayout(s)
        self.btn_flash = QPushButton("START FLASHING"); self.btn_flash.setObjectName("FlashBtn"); self.btn_flash.setFixedHeight(50); self.btn_flash.setEnabled(False); self.btn_flash.clicked.connect(self.start_flash_process); layout.addWidget(self.btn_flash); layout.addSpacing(20); self.console_box = QTextEdit(); self.console_box.setObjectName("ConsoleBox"); self.console_box.setReadOnly(True); self.console_box.setFixedHeight(150); layout.addWidget(self.console_box)

    def refresh_firmware_list(self):
        self.combo_hex.clear()
        if os.path.exists(self.firmware_dir):
            files = sorted([f for f in os.listdir(self.firmware_dir) if f.endswith(".hex")])
            if files:
                self.combo_hex.addItems(files)
                if self.current_port: self.btn_flash.setEnabled(True)
            else: self.btn_flash.setEnabled(False)

    def start_flash_process(self):
        pth = os.path.join(self.firmware_dir, self.combo_hex.currentText()); self.btn_flash.setEnabled(False); self.btn_backup_fw.setEnabled(False)
        self.console_box.clear(); self.console_box.append(f"Flashing: {self.combo_hex.currentText()}")
        args = ["-C", self.conf_path, "-v", "-p", "m2560", "-c", "wiring", "-P", self.current_port, "-b", "115200", "-D", "-U", f"flash:w:{pth}:i"]
        self.process.start(self.tools_path, args)

    def start_backup_fw(self):
        dest, _ = QFileDialog.getSaveFileName(self, "Backup", os.path.join(self.firmware_dir, "backup.hex"), "Hex (*.hex)")
        if dest:
            self.btn_flash.setEnabled(False); self.btn_backup_fw.setEnabled(False)
            args = ["-C", self.conf_path, "-v", "-p", "m2560", "-c", "wiring", "-P", self.current_port, "-b", "115200", "-U", f"flash:r:{dest}:i"]
            self.process.start(self.tools_path, args)

    def on_console_output(self):
        m = self.process.readAllStandardError().data().decode()
        if not m: m = self.process.readAllStandardOutput().data().decode()
        self.console_box.insertPlainText(m); self.console_box.ensureCursorVisible()

    def on_flash_finished(self):
        if self.current_port: self.btn_flash.setEnabled(True); self.btn_backup_fw.setEnabled(True)
        self.console_box.append("\nTerminated.")

    def auto_detect_hardware(self):
        plist = list(serial.tools.list_ports.comports())
        found = False
        for p in plist:
            for b in self.known_boards:
                if p.vid == b['vid'] and p.pid == b['pid']:
                    self.status_dot.setStyleSheet("color: #2ecc71; font-size: 14px; margin-left: 10px;")
                    self.status_text.setText(f"CONNECTED: {b['name']} ({p.device})")
                    self.current_port = p.device; self.btn_backup_fw.setEnabled(True)
                    if self.combo_hex.currentText().endswith(".hex"): self.btn_flash.setEnabled(True)
                    found = True; break
        if not found:
            self.status_dot.setStyleSheet("color: #e74c3c; font-size: 14px; margin-left: 10px;")
            self.status_text.setText("Device not detected"); self.current_port = None; self.btn_flash.setEnabled(False); self.btn_backup_fw.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv); window = MFKBApp(); window.show(); sys.exit(app.exec_())