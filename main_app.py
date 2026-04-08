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
from PyQt5.QtCore import Qt, QTimer, QProcess, QEvent
from PyQt5.QtGui import QTextCursor, QIntValidator

# --- PATH CONFIGURATION ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- THE STYLESHEET (Golden v2.1.0) ---
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
    padding: 8px 12px; 
    border: 1px solid #30363d; 
    border-bottom: none; 
    margin-right: 2px; 
    font-size: 10px;
}
QTabBar::tab:selected { 
    background: #2ecc71; 
    color: #000000; 
}

/* GENERATOR BUTTONS */
QPushButton#NoteBtn, QPushButton#ChannelBtn, QPushButton#MidiGridBtn, QPushButton#IntervalBtn {
    background-color: #21262d; 
    border: 1px solid #30363d;
    color: #8b949e; 
    border-radius: 4px; 
    font-weight: bold; 
    font-size: 10px;
}

/* HOVER EFFECT */
QPushButton#NoteBtn:hover, QPushButton#ChannelBtn:hover, 
QPushButton#MidiGridBtn:hover, QPushButton#IntervalBtn:hover, 
QPushButton#UtilityBtn:hover, QPushButton#FlashBtn:hover, 
QPushButton#BackupBtn:hover, QPushButton#SD_Btn:hover { 
    border-color: #2ecc71; 
}

/* SELECTION STATES */
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

/* INPUT BOX POINTER STYLING */
QLineEdit#KeyInput, QLineEdit#ChordSlot {
    background-color: #0d1117; 
    border: 1px solid #30363d;
    padding: 4px; 
    border-radius: 4px; 
    color: #8b949e;
    font-family: monospace; 
    font-size: 11px;
}
QLineEdit#KeyInput[active="true"], QLineEdit#ChordSlot[active="true"] {
    border: 1px solid #2ecc71;
    background-color: #1c2128;
    color: #ffffff;
}

/* UTILITY BUTTONS BASE */
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
    padding: 6px; 
    border-radius: 4px; 
    color: #8b949e;
    font-family: monospace; 
    font-size: 11px;
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
    """Integrated Modal Editor with line numbers and search."""
    def __init__(self, filename, content, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.parent_app = parent
        self.setWindowTitle(f"MFKB Editor - {filename}")
        self.setMinimumSize(900, 650)
        self.setStyleSheet(STYLE_SHEET)
        
        main_layout = QVBoxLayout(self)
        
        # Search Layout
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("FIND:"))
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search text...")
        search_layout.addWidget(self.search_field)
        
        self.btn_find = QPushButton("FIND NEXT")
        self.btn_find.setObjectName("SD_Btn")
        self.btn_find.setFixedWidth(120)
        self.btn_find.clicked.connect(self.do_find)
        self.search_field.returnPressed.connect(self.do_find)
        search_layout.addWidget(self.btn_find)
        
        main_layout.addLayout(search_layout)
        
        # Gutter and Editor Area
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
        
        # Connect scrolling
        self.editor.verticalScrollBar().valueChanged.connect(self.sync_scroll)
        self.editor.textChanged.connect(self.update_line_counts)
        
        editor_hbox.addWidget(self.line_gutter)
        editor_hbox.addWidget(self.editor)
        main_layout.addLayout(editor_hbox)
        
        # Footer
        footer = QHBoxLayout()
        self.btn_val = QPushButton("VALIDATE FORMAT")
        self.btn_val.setObjectName("SD_Btn")
        self.btn_val.setFixedWidth(150)
        self.btn_val.clicked.connect(self.run_editor_validation)
        footer.addWidget(self.btn_val)
        
        footer.addStretch()
        
        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setObjectName("SD_Btn")
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)
        
        self.btn_save = QPushButton("SAVE CHANGES")
        self.btn_save.setObjectName("SD_Btn")
        self.btn_save.clicked.connect(self.accept)
        footer.addWidget(self.btn_save)
        
        main_layout.addLayout(footer)
        self.update_line_counts()

    def sync_scroll(self, value):
        self.line_gutter.verticalScrollBar().setValue(value)

    def update_line_counts(self):
        line_count = self.editor.document().blockCount()
        numbers = []
        for i in range(1, line_count + 1):
            numbers.append(str(i))
        self.line_gutter.setPlainText("\n".join(numbers))
        self.sync_scroll(self.editor.verticalScrollBar().value())

    def do_find(self):
        query = self.search_field.text()
        if not query:
            return
        
        found = self.editor.find(query)
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(query)

    def run_editor_validation(self):
        self.parent_app.pre_scan_assets()
        text_content = self.editor.toPlainText()
        lines = text_content.split('\n')
        errors = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            
            res = self.parent_app.validate_fkb_line(self.filename.upper(), line, deep=True)
            if res is not True:
                errors.append(f"Line {i+1}: {res}")
        
        if len(errors) == 0:
            self.editor.append("\n# [SUCCESS] Content Validated.")
        else:
            self.editor.append("\n# [FAILED] Format Errors detected:")
            for err in errors:
                self.editor.append(f"# {err}")
        
        self.editor.moveCursor(QTextCursor.End)


class MFKBApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # INITIALIZE CORE CLASS ATTRIBUTES IMMEDIATELY
        self.current_port = None
        self.ser = None 
        
        # Application State
        self.note_masks = [0] * 25 
        self.selected_notes = set() 
        self.chan_buttons = []
        self.note_buttons = []
        
        # Pointer States
        self.keymap_inputs = []
        self.active_km_index = 0
        self.chord_inputs = []
        self.active_chord_index = 0
        
        # Deep Validation Database (IDs and Names)
        self.asset_db = {
            "CHORDS_ID": set(), "CHORDS_NAME": set(),
            "SCALES_ID": set(), "SCALES_NAME": set(),
            "PRESETS_ID": set(), "PRESETS_NAME": set(),
            "KEYMAPS_ID": set(), "KEYMAPS_NAME": set(),
            "MIDIMAPS_ID": set(), "MIDIMAPS_NAME": set()
        }
        
        # Paths
        self.tools_path = os.path.join(BASE_DIR, "tools", "avrdude")
        self.conf_path = os.path.join(BASE_DIR, "tools", "avrdude_linux.conf")
        self.firmware_dir = os.path.join(BASE_DIR, "firmware")
        self.sd_local_dir = os.path.join(BASE_DIR, "sdcard")
        self.sd_backup_dir = os.path.join(BASE_DIR, "sdcard", "backups")
        
        # Create Dirs
        target_paths = [self.sd_local_dir, self.sd_backup_dir, self.firmware_dir]
        for path in target_paths:
            if not os.path.exists(path):
                os.makedirs(path)
        
        self.known_boards = [
            {'vid': 0x1a86, 'pid': 0x7523, 'name': 'CH340 (AZ-Delivery)'},
            {'vid': 0x2341, 'pid': 0x0042, 'name': 'Mega 2560 (Elegoo/Official)'}
        ]
        
        # Flashing Process
        self.process = QProcess(self)
        self.process.readyReadStandardError.connect(self.on_console_output)
        self.process.readyReadStandardOutput.connect(self.on_console_output)
        self.process.finished.connect(self.on_flash_finished)

        # Verification Debouncer
        self.verify_timer = QTimer()
        self.verify_timer.setSingleShot(True)
        self.verify_timer.timeout.connect(self.perform_live_verification)

        self.init_ui()
        
        # Auto-detect Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_detect_hardware)
        self.timer.start(2000)
        
        self.refresh_firmware_list()
        self.refresh_local_sd_list()

    def init_ui(self):
        self.setWindowTitle("MFKB Companion App v2.1.0")
        self.setFixedSize(850, 750) 
        self.setStyleSheet(STYLE_SHEET)
        
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Connection Header
        self.conn_bar = QFrame()
        self.conn_bar.setObjectName("ConnBar")
        self.conn_bar.setFixedHeight(40)
        conn_lay = QHBoxLayout(self.conn_bar)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #e74c3c; font-size: 14px; margin-left: 10px;")
        conn_lay.addWidget(self.status_dot)
        
        self.status_text = QLabel("Scanning Hardware Interface...")
        self.status_text.setStyleSheet("color: #8b949e; font-size: 10px;")
        conn_lay.addWidget(self.status_text)
        
        conn_lay.addStretch()
        main_layout.addWidget(self.conn_bar)

        # 2. Main Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        self.tab_midimap = QWidget()
        self.tabs.addTab(self.tab_midimap, "MidiMap Generator")
        
        self.tab_keymap = QWidget()
        self.tabs.addTab(self.tab_keymap, "KeyMap Generator")
        
        self.tab_chord = QWidget()
        self.tabs.addTab(self.tab_chord, "Chord Generator")

        self.tab_preset = QWidget()
        self.tabs.addTab(self.tab_preset, "Preset Generator")
        
        self.tab_sd = QWidget()
        self.tabs.addTab(self.tab_sd, "SD Card Manager")
        
        self.tab_flash = QWidget()
        self.tabs.addTab(self.tab_flash, "Firmware Uploader")

        # 3. Setup Contents
        self.setup_bitmasker_tab()
        self.setup_keymap_tab()
        self.setup_chord_tab()
        self.setup_preset_tab()
        self.setup_sd_tab()
        self.setup_uploader_tab()

    # --- LIVE VERIFICATION SYSTEM ---

    def trigger_verification(self):
        self.verify_timer.start(500)

    def perform_live_verification(self):
        """Silently scans local files and checks OR condition for ID/Name."""
        self.pre_scan_assets()
        current_idx = self.tabs.currentIndex()
        tab_name = self.tabs.tabText(current_idx)

        # 1. MidiMap
        if tab_name == "MidiMap Generator":
            raw_id = self.map_id_edit.text().strip()
            norm_id = "MM" + str(int(raw_id)) if raw_id.isdigit() else "MM" + raw_id
            name_val = self.map_name_edit.text().strip()
            self.apply_live_feedback(self.midimap_status, norm_id, name_val, "MIDIMAPS_ID", "MIDIMAPS_NAME")

        # 2. KeyMap
        elif tab_name == "KeyMap Generator":
            raw_id = self.km_id_edit.text().strip()
            norm_id = "KM" + str(int(raw_id)) if raw_id.isdigit() else "KM" + raw_id
            name_val = self.km_name_edit.text().strip()
            self.apply_live_feedback(self.keymap_status, norm_id, name_val, "KEYMAPS_ID", "KEYMAPS_NAME")

        # 3. Chord
        elif tab_name == "Chord Generator":
            raw_id = self.chord_id_edit.text().strip()
            norm_id = "C" + str(int(raw_id)) if raw_id.isdigit() else "C" + raw_id
            name_val = self.chord_name_edit.text().strip()
            self.apply_live_feedback(self.chord_status, norm_id, name_val, "CHORDS_ID", "CHORDS_NAME")

        # 4. Preset
        elif tab_name == "Preset Generator":
            raw_id = self.pre_id_edit.text().strip()
            norm_id = "P" + str(int(raw_id)) if raw_id.isdigit() else "P" + raw_id
            name_val = self.pre_name_edit.text().strip()
            self.apply_live_feedback(self.preset_status, norm_id, name_val, "PRESETS_ID", "PRESETS_NAME")

    def apply_live_feedback(self, label_obj, id_val, name_val, id_key, name_key):
        if not id_val and not name_val:
            label_obj.setText("")
            return

        is_id_taken = id_val in self.asset_db[id_key]
        is_name_taken = name_val in self.asset_db[name_key]

        if is_id_taken or is_name_taken:
            label_obj.setText("⚠ Warning: Duplicate ID or Name detected in local file")
            label_obj.setStyleSheet("color: #e74c3c; font-size: 9px; font-weight: bold;")
        else:
            label_obj.setText("✓ ID and Name are available")
            label_obj.setStyleSheet("color: #2ecc71; font-size: 9px; font-weight: bold;")

    # --- TAB 1: BITMASKER ---

    def setup_bitmasker_tab(self):
        layout = QVBoxLayout(self.tab_midimap)
        layout.setContentsMargins(25, 10, 25, 15)
        layout.setSpacing(5)
        
        layout.addWidget(QLabel("STEP 1 : ID & NAME", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        inp = QHBoxLayout()
        self.map_id_edit = QLineEdit("1")
        self.map_id_edit.setFixedWidth(45)
        self.map_id_edit.textChanged.connect(self.update_result_string)
        self.map_id_edit.textChanged.connect(self.trigger_verification)
        
        self.map_name_edit = QLineEdit("Default_Map")
        self.map_name_edit.setFixedWidth(200)
        self.map_name_edit.textChanged.connect(self.update_result_string)
        self.map_name_edit.textChanged.connect(self.trigger_verification)
        
        inp.addWidget(QLabel("ID:"))
        inp.addWidget(self.map_id_edit)
        inp.addWidget(QLabel("NAME:"))
        inp.addWidget(self.map_name_edit)
        inp.addStretch()
        layout.addLayout(inp)

        self.midimap_status = QLabel("")
        layout.addWidget(self.midimap_status)
        
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
        res = QHBoxLayout()
        self.result_box = QTextEdit(); self.result_box.setObjectName("ResultBox"); self.result_box.setReadOnly(True); self.result_box.setFixedHeight(60)
        self.btn_copy = QPushButton("COPY"); self.btn_copy.setFixedSize(80, 60); self.btn_copy.setStyleSheet("background-color: #2ecc71; color: black; font-weight: bold;")
        self.btn_copy.clicked.connect(self.copy_result); res.addWidget(self.result_box); res.addWidget(self.btn_copy); layout.addLayout(res)
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
        mid = self.map_id_edit.text()
        name = self.map_name_edit.text()
        hex_data = ",".join([f"{m:04X}" for m in self.note_masks])
        self.result_box.setText(f"MM{mid}:{name}:{hex_data}")

    def copy_result(self):
        QApplication.clipboard().setText(self.result_box.toPlainText())
        self.btn_copy.setText("COPIED!"); QTimer.singleShot(1500, lambda: self.btn_copy.setText("COPY"))

    def clear_map(self):
        self.note_masks = [0] * 25
        self.selected_notes.clear()
        for btn in self.note_buttons:
            btn.blockSignals(True); btn.setChecked(False); btn.setProperty("locked", "false")
            btn.style().unpolish(btn); btn.style().polish(btn); btn.blockSignals(False)
        for btn in self.chan_buttons:
            btn.blockSignals(True); btn.setChecked(False); btn.blockSignals(False)
        self.note_all_chk.setChecked(False); self.chan_all_chk.setChecked(False); self.update_result_string()

    # --- TAB 2: KEYMAP GENERATOR ---

    def setup_keymap_tab(self):
        layout = QVBoxLayout(self.tab_keymap)
        layout.setContentsMargins(25, 10, 25, 15)
        layout.setSpacing(5)
        layout.addWidget(QLabel("STEP 1 : ID & NAME", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        h1 = QHBoxLayout()
        self.km_id_edit = QLineEdit("1")
        self.km_id_edit.setFixedWidth(45); self.km_id_edit.textChanged.connect(self.update_keymap_output)
        self.km_id_edit.textChanged.connect(self.trigger_verification)
        
        self.km_name_edit = QLineEdit("Standard")
        self.km_name_edit.setFixedWidth(200); self.km_name_edit.setMaxLength(12); self.km_name_edit.textChanged.connect(self.update_keymap_output)
        self.km_name_edit.textChanged.connect(self.trigger_verification)
        
        h1.addWidget(QLabel("KM ID:")); h1.addWidget(self.km_id_edit); h1.addWidget(QLabel("NAME:")); h1.addWidget(self.km_name_edit); h1.addStretch()
        layout.addLayout(h1)

        self.keymap_status = QLabel("")
        layout.addWidget(self.keymap_status)
        
        layout.addWidget(QLabel("STEP 2 : SELECT A MIDI NOTE", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        grid_frame = QFrame(); grid_frame.setStyleSheet("background-color: #161b22; border-radius: 4px; border: 1px solid #30363d;"); grid_lay = QGridLayout(grid_frame)
        grid_lay.setSpacing(2); grid_lay.setColumnMinimumWidth(0, 40)
        midi_notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        for i, name in enumerate(midi_notes):
            lbl = QLabel(name); lbl.setAlignment(Qt.AlignCenter); lbl.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 10px;")
            grid_lay.addWidget(lbl, 0, i + 1)
        for row in range(11):
            lbl_oct = QLabel(f"Oct {row-1}"); lbl_oct.setFixedWidth(40); lbl_oct.setStyleSheet("color: #FFF; font-size: 8px;")
            grid_lay.addWidget(lbl_oct, row + 1, 0)
            for col in range(12):
                val = row * 12 + col
                if val <= 127:
                    btn = QPushButton(str(val)); btn.setObjectName("MidiGridBtn"); btn.setFixedSize(28, 20)
                    btn.clicked.connect(lambda checked, v=val: self.on_midi_grid_click(v)); grid_lay.addWidget(btn, row + 1, col + 1)
        layout.addWidget(grid_frame)
        layout.addWidget(QLabel("STEP 3 : CHOOSE THE KEY", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        cols_hbox = QHBoxLayout(); splits = [6, 6, 6, 7]; k_ptr = 0
        for sz in splits:
            vbox = QVBoxLayout()
            for _ in range(sz):
                row = QHBoxLayout(); key_lbl = QLabel(f"Key {str(k_ptr + 1).zfill(2)}:"); key_lbl.setStyleSheet("color: #8b949e; font-size: 9px;"); key_lbl.setFixedWidth(40)
                box = QLineEdit(str(60 + k_ptr)); box.setObjectName("KeyInput"); box.setFixedWidth(40); box.setValidator(QIntValidator(0, 127))
                box.installEventFilter(self); box.textChanged.connect(self.update_keymap_output); self.keymap_inputs.append(box)
                row.addWidget(key_lbl); row.addWidget(box); vbox.addLayout(row); k_ptr += 1
            vbox.addStretch(); cols_hbox.addLayout(vbox)
        layout.addLayout(cols_hbox)
        res_row = QHBoxLayout(); self.km_res_box = QTextEdit(); self.km_res_box.setObjectName("ResultBox"); self.km_res_box.setFixedHeight(50); self.km_res_box.setReadOnly(True)
        self.btn_copy_km = QPushButton("COPY"); self.btn_copy_km.setFixedSize(80, 50); self.btn_copy_km.setStyleSheet("background-color: #2ecc71; color: black; font-weight: bold;")
        self.btn_copy_km.clicked.connect(self.copy_keymap_result); res_row.addWidget(self.km_res_box); res_row.addWidget(self.btn_copy_km); layout.addLayout(res_row)
        self.update_active_km_pointer(0); self.update_keymap_output()

    # --- TAB 3: CHORD GENERATOR ---

    def setup_chord_tab(self):
        layout = QVBoxLayout(self.tab_chord)
        layout.setContentsMargins(25, 10, 25, 15)
        layout.setSpacing(5)
        layout.addWidget(QLabel("STEP 1 : ASSIGN ID & NAME", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        h1 = QHBoxLayout()
        self.chord_id_edit = QLineEdit("1")
        self.chord_id_edit.setFixedWidth(45); self.chord_id_edit.textChanged.connect(self.update_chord_output)
        self.chord_id_edit.textChanged.connect(self.trigger_verification)
        
        self.chord_name_edit = QLineEdit("Maj")
        self.chord_name_edit.setFixedWidth(200); self.chord_name_edit.setMaxLength(12); self.chord_name_edit.textChanged.connect(self.update_chord_output)
        self.chord_name_edit.textChanged.connect(self.trigger_verification)
        
        h1.addWidget(QLabel("C ID:")); h1.addWidget(self.chord_id_edit); h1.addWidget(QLabel("NAME:")); h1.addWidget(self.chord_name_edit); h1.addStretch()
        layout.addLayout(h1)

        self.chord_status = QLabel("")
        layout.addWidget(self.chord_status)
        
        layout.addWidget(QLabel("STEP 2 : SELECT AN INTERVAL", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        grid_frame = QFrame(); grid_frame.setStyleSheet("background-color: #161b22; border-radius: 4px; border: 1px solid #30363d;"); grid_lay = QGridLayout(grid_frame); grid_lay.setSpacing(4); grid_lay.addWidget(QLabel("Bass:"), 0, 0)
        for i, val in enumerate([-24, -12]):
            btn = QPushButton(f"{val} (Oct)"); btn.setObjectName("IntervalBtn"); btn.setFixedSize(55, 25)
            btn.clicked.connect(lambda checked, v=val: self.on_interval_grid_click(v)); grid_lay.addWidget(btn, 0, i + 1)
        int_names = ["Root", "m2", "M2", "m3", "M3", "P4", "Tri", "P5", "m6", "M6", "m7", "M7", "Oct"]
        for octave in range(3):
            base = octave * 12
            for st in range(1, 13):
                val = base + st; label = f"+{val}"
                if st < len(int_names): label += f" ({int_names[st]})"
                btn = QPushButton(label); btn.setObjectName("IntervalBtn"); btn.setFixedSize(65, 25)
                btn.clicked.connect(lambda checked, v=val: self.on_interval_grid_click(v)); grid_lay.addWidget(btn, octave + 1, st - 1)
        layout.addWidget(grid_frame)
        layout.addWidget(QLabel("STEP 3 : CHORD VOICES", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        slots_hbox = QHBoxLayout()
        for i in range(6):
            vbox = QVBoxLayout(); lbl = QLabel(f"Voice {i+1}:"); lbl.setStyleSheet("color: #8b949e; font-size: 9px;")
            box = QLineEdit(); box.setObjectName("ChordSlot"); box.setFixedWidth(55); box.installEventFilter(self); box.textChanged.connect(self.update_chord_output); self.chord_inputs.append(box)
            vbox.addWidget(lbl); vbox.addWidget(box); slots_hbox.addLayout(vbox)
        slots_hbox.addStretch(); layout.addLayout(slots_hbox)
        res_row = QHBoxLayout(); self.chord_res_box = QTextEdit(); self.chord_res_box.setObjectName("ResultBox"); self.chord_res_box.setFixedHeight(50); self.chord_res_box.setReadOnly(True)
        self.btn_copy_chord = QPushButton("COPY"); self.btn_copy_chord.setFixedSize(80, 50); self.btn_copy_chord.setStyleSheet("background-color: #2ecc71; color: black; font-weight: bold;")
        self.btn_copy_chord.clicked.connect(self.copy_chord_result); res_row.addWidget(self.chord_res_box); res_row.addWidget(self.btn_copy_chord); layout.addLayout(res_row)
        self.update_active_chord_pointer(0); self.update_chord_output()

    # --- TAB 4: PRESET GENERATOR ---

    def setup_preset_tab(self):
        layout = QVBoxLayout(self.tab_preset)
        layout.setContentsMargins(25, 10, 25, 15)
        layout.setSpacing(5)
        layout.addWidget(QLabel("STEP 1 : REF + NAME", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        h1 = QHBoxLayout()
        self.pre_id_edit = QLineEdit("1")
        self.pre_id_edit.setFixedWidth(45); self.pre_id_edit.setValidator(QIntValidator(0, 999)); self.pre_id_edit.textChanged.connect(self.update_preset_output)
        self.pre_id_edit.textChanged.connect(self.trigger_verification)
        
        self.pre_name_edit = QLineEdit("Piano")
        self.pre_name_edit.setFixedWidth(120); self.pre_name_edit.setMaxLength(7); self.pre_name_edit.textChanged.connect(self.update_preset_output)
        self.pre_name_edit.textChanged.connect(self.trigger_verification)
        
        h1.addWidget(QLabel("REF (P):")); h1.addWidget(self.pre_id_edit); h1.addWidget(QLabel("NAME:")); h1.addWidget(self.pre_name_edit); h1.addStretch()
        layout.addLayout(h1)

        self.preset_status = QLabel("")
        layout.addWidget(self.preset_status)
        
        layout.addWidget(QLabel("STEP 2 : LINK ASSETS", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        grid_frame = QFrame(); grid_frame.setStyleSheet("background-color: #161b22; border-radius: 4px; border: 1px solid #30363d;"); grid_link = QGridLayout(grid_frame)
        self.pre_root_combo = QComboBox(); self.pre_root_combo.addItems(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]); self.pre_root_combo.currentIndexChanged.connect(self.update_preset_output)
        self.pre_bs_combo = QComboBox(); self.pre_bs_combo.setEditable(True); self.pre_bs_combo.lineEdit().textChanged.connect(self.update_preset_output)
        self.pre_es_combo = QComboBox(); self.pre_es_combo.setEditable(True); self.pre_es_combo.lineEdit().textChanged.connect(self.update_preset_output)
        self.pre_km_combo = QComboBox(); self.pre_km_combo.setEditable(True); self.pre_km_combo.lineEdit().textChanged.connect(self.update_preset_output)
        self.pre_mm_combo = QComboBox(); self.pre_mm_combo.setEditable(True); self.pre_mm_combo.lineEdit().textChanged.connect(self.update_preset_output)
        grid_link.addWidget(QLabel("Root Note:"), 0, 0); grid_link.addWidget(self.pre_root_combo, 0, 1)
        grid_link.addWidget(QLabel("Basic Scale (S):"), 1, 0); grid_link.addWidget(self.pre_bs_combo, 1, 1)
        grid_link.addWidget(QLabel("Enh. Scale (S):"), 2, 0); grid_link.addWidget(self.pre_es_combo, 2, 1)
        grid_link.addWidget(QLabel("KeyMap (KM):"), 1, 2); grid_link.addWidget(self.pre_km_combo, 1, 3)
        grid_link.addWidget(QLabel("MidiMap (MM):"), 2, 2); grid_link.addWidget(self.pre_mm_combo, 2, 3)
        layout.addWidget(grid_frame)
        layout.addWidget(QLabel("STEP 3 : MIDI DEFAULTS", styleSheet="color: #2ecc71; font-weight: bold; font-size: 10px;"))
        h_defaults = QHBoxLayout()
        self.pre_vol = QLineEdit("100"); self.pre_vol.setFixedWidth(40); self.pre_vol.setValidator(QIntValidator(0, 127))
        self.pre_vel = QLineEdit("100"); self.pre_vel.setFixedWidth(40); self.pre_vel.setValidator(QIntValidator(0, 127))
        self.pre_chan = QLineEdit("1"); self.pre_chan.setFixedWidth(30); self.pre_chan.setValidator(QIntValidator(1, 16))
        self.pre_trans = QComboBox()
        for v in range(-48, 49, 12): self.pre_trans.addItem(str(v))
        self.pre_trans.setCurrentText("0"); self.pre_vol.textChanged.connect(self.update_preset_output); self.pre_vel.textChanged.connect(self.update_preset_output); self.pre_chan.textChanged.connect(self.update_preset_output); self.pre_trans.currentIndexChanged.connect(self.update_preset_output)
        h_defaults.addWidget(QLabel("Volume:")); h_defaults.addWidget(self.pre_vol); h_defaults.addWidget(QLabel("Velocity:")); h_defaults.addWidget(self.pre_vel); h_defaults.addWidget(QLabel("Transpose:")); h_defaults.addWidget(self.pre_trans); h_defaults.addWidget(QLabel("Channel:")); h_defaults.addWidget(self.pre_chan); h_defaults.addStretch(); layout.addLayout(h_defaults)
        res_row = QHBoxLayout(); self.pre_res_box = QTextEdit(); self.pre_res_box.setObjectName("ResultBox"); self.pre_res_box.setFixedHeight(50); self.pre_res_box.setReadOnly(True)
        self.btn_copy_pre = QPushButton("COPY"); self.btn_copy_pre.setFixedSize(80, 50); self.btn_copy_pre.setStyleSheet("background-color: #2ecc71; color: black; font-weight: bold;")
        self.btn_copy_pre.clicked.connect(self.copy_preset_result); res_row.addWidget(self.pre_res_box); res_row.addWidget(self.btn_copy_pre); layout.addLayout(res_row)
        self.tabs.currentChanged.connect(self.on_tab_changed_preset_refresh); self.update_preset_output()

    # --- SHARED UI ACTIONS ---

    def on_tab_changed_preset_refresh(self, index):
        if self.tabs.tabText(index) == "Preset Generator":
            self.refresh_preset_dropdowns()

    def refresh_preset_dropdowns(self):
        self.pre_scan_assets()
        bs_txt = self.pre_bs_combo.currentText(); es_txt = self.pre_es_combo.currentText()
        km_txt = self.pre_km_combo.currentText(); mm_txt = self.pre_mm_combo.currentText()
        self.pre_bs_combo.clear(); self.pre_bs_combo.addItems(sorted(list(self.asset_db["SCALES_ID"])))
        self.pre_es_combo.clear(); self.pre_es_combo.addItems(sorted(list(self.asset_db["SCALES_ID"])))
        self.pre_km_combo.clear(); self.pre_km_combo.addItems(sorted(list(self.asset_db["KEYMAPS_ID"])))
        self.pre_mm_combo.clear(); self.pre_mm_combo.addItems(sorted(list(self.asset_db["MIDIMAPS_ID"])))
        self.pre_bs_combo.setCurrentText(bs_txt); self.pre_es_combo.setCurrentText(es_txt)
        self.pre_km_combo.setCurrentText(km_txt); self.pre_mm_combo.setCurrentText(mm_txt)

    def update_preset_output(self):
        p_id = self.pre_id_edit.text()
        p_name = self.pre_name_edit.text()
        root = self.pre_root_combo.currentText(); bs = self.pre_bs_combo.currentText()
        es = self.pre_es_combo.currentText(); km = self.pre_km_combo.currentText(); mm = self.pre_mm_combo.currentText()
        vol = self.pre_vol.text(); vel = self.pre_vel.text(); tr = self.pre_trans.currentText(); ch = self.pre_chan.text()
        data = f"{root},{bs},{es},{km},{mm},{vol},{vel},{tr},{ch},0"
        self.pre_res_box.setText(f"P{p_id}:{p_name}:{data}")

    def copy_preset_result(self):
        QApplication.clipboard().setText(self.pre_res_box.toPlainText())
        self.btn_copy_pre.setText("COPIED!"); QTimer.singleShot(1500, lambda: self.btn_copy_pre.setText("COPY"))

    def on_midi_grid_click(self, value):
        if self.active_km_index < 25:
            self.keymap_inputs[self.active_km_index].setText(str(value))
            if self.active_km_index < 24:
                self.update_active_km_pointer(self.active_km_index + 1)
        self.update_keymap_output()

    def on_interval_grid_click(self, value):
        if self.active_chord_index < 6:
            self.chord_inputs[self.active_chord_index].setText(str(value))
            if self.active_chord_index < 5:
                self.update_active_chord_pointer(self.active_chord_index + 1)
        self.update_chord_output()

    def update_active_km_pointer(self, index):
        self.active_km_index = index
        for i, box in enumerate(self.keymap_inputs):
            box.setProperty("active", "true" if i == index else "false")
            box.style().unpolish(box); box.style().polish(box)

    def update_active_chord_pointer(self, index):
        self.active_chord_index = index
        for i, box in enumerate(self.chord_inputs):
            box.setProperty("active", "true" if i == index else "false")
            box.style().unpolish(box); box.style().polish(box)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if obj in self.keymap_inputs:
                self.update_active_km_pointer(self.keymap_inputs.index(obj))
            if obj in self.chord_inputs:
                self.update_active_chord_pointer(self.chord_inputs.index(obj))
        return super().eventFilter(obj, event)

    def update_keymap_output(self):
        kid = self.km_id_edit.text()
        out = [box.text() if box.text() else "0" for box in self.keymap_inputs]
        self.km_res_box.setText(f"KM{kid}:{self.km_name_edit.text()}:{','.join(out)}")

    def copy_keymap_result(self):
        QApplication.clipboard().setText(self.km_res_box.toPlainText())
        self.btn_copy_km.setText("COPIED!"); QTimer.singleShot(1500, lambda: self.btn_copy_km.setText("COPY"))

    def update_chord_output(self):
        cid = self.chord_id_edit.text()
        formula = ",".join([box.text().strip() for box in self.chord_inputs if box.text().strip()])
        self.chord_res_box.setText(f"C{cid}:{self.chord_name_edit.text()}:{formula}")

    def copy_chord_result(self):
        QApplication.clipboard().setText(self.chord_res_box.toPlainText())
        self.btn_copy_chord.setText("COPIED!"); QTimer.singleShot(1500, lambda: self.btn_copy_chord.setText("COPY"))

    # --- TAB 4: SD MANAGER ---

    def setup_sd_tab(self):
        layout = QVBoxLayout(self.tab_sd)
        layout.setContentsMargins(20, 20, 20, 20)
        h_row = QHBoxLayout()
        h_row.addWidget(QLabel("SD CARD MANAGER", styleSheet="color: #2ecc71; font-weight: bold; font-size: 12px;"))
        h_row.addWidget(QLabel("Caution: Edit LOCAL FILES!", styleSheet="color: #FF0000; font-weight: bold; font-size: 10px;"))
        h_row.addStretch()
        self.btn_full_backup = QPushButton("FULL SD BACKUP"); self.btn_full_backup.setObjectName("SD_Btn")
        self.btn_full_backup.setFixedWidth(140); self.btn_full_backup.clicked.connect(self.run_full_backup); h_row.addWidget(self.btn_full_backup); layout.addLayout(h_row)
        
        panes = QHBoxLayout()
        left_box = QVBoxLayout(); left_box.addWidget(QLabel("LOCAL (PC)", styleSheet="color: #8b949e; font-size: 10px;"))
        self.list_local = QListWidget(); left_box.addWidget(self.list_local)
        self.btn_integrity = QPushButton("CHECK INTEGRITY"); self.btn_integrity.setObjectName("SD_Btn"); self.btn_integrity.setFixedHeight(30)
        self.btn_integrity.clicked.connect(self.run_integrity_check); left_box.addWidget(self.btn_integrity); panes.addLayout(left_box)
        
        mid_box = QVBoxLayout(); mid_box.setAlignment(Qt.AlignCenter)
        self.btn_to_sd = QPushButton(">>"); self.btn_to_sd.setObjectName("SD_Btn"); self.btn_to_sd.setFixedSize(50, 50); self.btn_to_sd.clicked.connect(self.upload_selected)
        self.btn_edit_sd = QPushButton("EDIT"); self.btn_edit_sd.setObjectName("SD_Btn"); self.btn_edit_sd.setFixedSize(50, 50); self.btn_edit_sd.clicked.connect(self.open_editor)
        self.btn_del = QPushButton("DEL"); self.btn_del.setObjectName("DelBtn"); self.btn_del.setFixedSize(50, 50); self.btn_del.clicked.connect(self.delete_selected_remote)
        self.btn_from_sd = QPushButton("<<"); self.btn_from_sd.setObjectName("SD_Btn"); self.btn_from_sd.setFixedSize(50, 50); self.btn_from_sd.clicked.connect(self.download_selected)
        mid_box.addWidget(self.btn_to_sd); mid_box.addSpacing(10); mid_box.addWidget(self.btn_edit_sd); mid_box.addSpacing(10); mid_box.addWidget(self.btn_del); mid_box.addSpacing(10); mid_box.addWidget(self.btn_from_sd); panes.addLayout(mid_box)
        
        right_box = QVBoxLayout(); right_box.addWidget(QLabel("REMOTE (SD)", styleSheet="color: #8b949e; font-size: 10px;"))
        self.list_remote = QListWidget(); right_box.addWidget(self.list_remote)
        self.btn_refresh = QPushButton("REFRESH SD LIST"); self.btn_refresh.setObjectName("SD_Btn"); self.btn_refresh.clicked.connect(self.request_sd_list)
        right_box.addWidget(self.btn_refresh); panes.addLayout(right_box); layout.addLayout(panes)
        
        self.sd_console = QTextEdit(); self.sd_console.setObjectName("SD_Console"); self.sd_console.setFixedHeight(120); self.sd_console.setReadOnly(True)
        layout.addWidget(self.sd_console)

    def set_busy(self, busy):
        st = not busy
        self.btn_to_sd.setEnabled(st); self.btn_from_sd.setEnabled(st); self.btn_edit_sd.setEnabled(st)
        self.btn_del.setEnabled(st); self.btn_refresh.setEnabled(st); self.btn_integrity.setEnabled(st)
        self.btn_full_backup.setEnabled(st); QApplication.processEvents()

    def update_prog_bar(self, cur, tot, msg="Task"):
        pct = int((cur / tot) * 100); marks = int(25 * cur // tot); bar = "#" * marks + "-" * (25 - marks)
        if pct % 10 == 0 or cur == tot: self.sd_console.append(f"{msg}: [{bar}] {pct}%"); QApplication.processEvents()

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
                        if ln.startswith("FILE:"): self.list_remote.addItem(ln.replace("FILE:", "").split("|")[0])
                self.sd_console.append("Scan Successful.")
        except Exception as e: self.sd_console.append(f"Error: {e}")
        self.set_busy(False)

    def delete_selected_remote(self):
        item = self.list_remote.currentItem()
        if not item or not self.current_port: return
        if QMessageBox.question(self, "Delete", f"Erase {item.text()}?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                    time.sleep(2); ser.write(f"SD_DEL:{item.text()}\n".encode())
                    if ser.readline().decode().strip() == "DEL_OK": self.sd_console.append(f"Deleted: {item.text()}"); self.request_sd_list()
            except Exception as e: self.sd_console.append(f"Fail: {e}")

    def upload_selected(self):
        item = self.list_local.currentItem()
        if not item or not self.current_port: return
        path = os.path.join(self.sd_local_dir, item.text())
        self.set_busy(True)
        try:
            with open(path, 'r') as f: lines = f.readlines()
            total = len(lines)
            with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                time.sleep(2); ser.write(f"SD_WRITE:{item.text()}\n".encode())
                while ser.readline().decode().strip() != "READY_TO_RECEIVE": pass
                for i, ln in enumerate(lines):
                    ser.write(f"{ln.strip()}\n".encode()); ser.readline(); self.update_prog_bar(i + 1, total, "Upload")
                ser.write(b"SD_EOF\n"); self.sd_console.append(f"Stored: {item.text()}"); self.request_sd_list()
        except Exception as e: self.sd_console.append(f"Error: {e}")
        self.set_busy(False)

    def download_selected(self):
        item = self.list_remote.currentItem()
        if not item or not self.current_port: return
        path = os.path.join(self.sd_local_dir, item.text())
        self.set_busy(True)
        try:
            with serial.Serial(self.current_port, 115200, timeout=2) as ser:
                time.sleep(2); ser.write(f"SD_READ:{item.text()}\n".encode()); buf = []
                while True:
                    ln = ser.readline().decode().strip()
                    if ln == "END_FILE": break
                    if not ln.startswith("START_FILE:"): buf.append(ln)
                with open(path, 'w') as f: f.write("\n".join(buf))
                self.sd_console.append(f"Downloaded: {item.text()}"); self.refresh_local_sd_list()
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
                        r = ser.readline().decode().strip();
                        if r == "END_FILE": break
                        if not r.startswith("START_FILE:"): b.append(r)
                    with open(os.path.join(dest, fname), 'w') as f: f.write("\n".join(b))
            except: pass
        self.sd_console.append("Backup Complete."); self.set_busy(False)

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
                            id_v = pts[0].strip(); lbl_v = pts[1].strip()
                            if up == "CHORDS.FKB":
                                self.asset_db["CHORDS_ID"].add(id_v); self.asset_db["CHORDS_NAME"].add(lbl_v)
                            elif up == "SCALES.FKB":
                                self.asset_db["SCALES_ID"].add(id_v); self.asset_db["SCALES_NAME"].add(lbl_v)
                            elif up == "PRESETS.FKB":
                                self.asset_db["PRESETS_ID"].add(id_v); self.asset_db["PRESETS_NAME"].add(lbl_v)
                            elif up == "KEYMAPS.FKB":
                                self.asset_db["KEYMAPS_ID"].add(id_v); self.asset_db["KEYMAPS_NAME"].add(lbl_v)
                            elif up == "MIDIMAPS.FKB":
                                self.asset_db["MIDIMAPS_ID"].add(id_v); self.asset_db["MIDIMAPS_NAME"].add(lbl_v)
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
            if deep:
                for c in p[2].split(","):
                    if c.strip() not in self.asset_db["CHORDS_ID"]: return f"Chord {c} missing"
            return True
        if fname == "PRESETS.FKB":
            p = line.split(":"); 
            if len(p) < 3: return "Bad structure"
            dm = p[2].split(",")
            if deep:
                if dm[1].strip() not in self.asset_db["SCALES_ID"]: return f"Scale {dm[1]} missing"
                if dm[2].strip() not in self.asset_db["SCALES_ID"]: return f"Scale {dm[2]} missing"
                if dm[3].strip() not in self.asset_db["KEYMAPS_ID"]: return f"Keymap {dm[3]} missing"
                if dm[4].strip() not in self.asset_db["MIDIMAPS_ID"]: return f"Midimap {dm[4]} missing"
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
                self.sd_console.append(f"Updated: {item.text()}"); self.refresh_local_sd_list()
        except Exception as e: self.sd_console.append(f"Error: {e}")

    def refresh_local_sd_list(self):
        self.list_local.clear()
        if os.path.exists(self.sd_local_dir):
            files = sorted([f for f in os.listdir(self.sd_local_dir) if f.lower().endswith(".fkb")])
            self.list_local.addItems(files)

    # --- TAB 5: FIRMWARE ---

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
            if files: self.combo_hex.addItems(files)
            if self.current_port and files: self.btn_flash.setEnabled(True)
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
        msg = self.process.readAllStandardError().data().decode()
        if not msg:
            msg = self.process.readAllStandardOutput().data().decode()
        self.console_box.insertPlainText(msg)
        self.console_box.ensureCursorVisible()

    def on_flash_finished(self):
        if self.current_port:
            self.btn_flash.setEnabled(True); self.btn_backup_fw.setEnabled(True)
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