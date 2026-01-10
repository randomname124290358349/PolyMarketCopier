
import sys
import os
import asyncio
import logging
import qasync
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QTabWidget, QFormLayout, QComboBox, 
                             QSpinBox, QDoubleSpinBox, QCheckBox, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, pyqtSlot
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon
from dotenv import load_dotenv, set_key, dotenv_values
from modules.PolyClasses import PolyMarketController


# Setup Logging to Signal
class LogSignalHandler(logging.Handler, QObject):
    log_signal = pyqtSignal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_signal.emit(msg)
        except RuntimeError:
            # Catch "wrapped C/C++ object has been deleted" during shutdown
            pass
        except Exception:
            pass

class Worker(QThread):
    finished = pyqtSignal()
    
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.loop = None
        self._is_running = True

    def run(self):
        # Create a new event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            # We run the controller.run() blocking call
            self.loop.run_until_complete(self.controller.run())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Worker thread error: {e}")
        finally:
            try:
                # Cancel any pending tasks if not already done
                pending = asyncio.all_tasks(self.loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                self.loop.close()
            except Exception:
                pass
            self.finished.emit()

    def stop(self):
        if self.loop and self.loop.is_running():
            # Schedule the cancellation in the loop
            self.loop.call_soon_threadsafe(self.cancel_all_tasks)

    def cancel_all_tasks(self):
        # This will cancel all tasks including the main run() task if it's wrapped
        for task in asyncio.all_tasks(self.loop):
            task.cancel()


class GlassStyle(QObject):
    STYLESHEET = """
    QMainWindow {
        background-color: #1e1e2e;
        color: #cdd6f4;
    }
    QLabel {
        color: #cdd6f4;
        font-size: 14px;
        font-weight: 500;
        font-family: 'Segoe UI', sans-serif;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: rgba(49, 50, 68, 0.5);
        border: 1px solid #45475a;
        border-radius: 6px;
        color: #cdd6f4;
        padding: 8px;
        font-size: 13px;
        selection-background-color: #585b70;
    }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
        border: 1px solid #89b4fa;
        background-color: rgba(49, 50, 68, 0.8);
    }
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #89b4fa, stop:1 #74c7ec);
        color: #1e1e2e;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: bold;
        font-size: 14px;
        font-family: 'Segoe UI', sans-serif;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b4befe, stop:1 #89b4fa);
    }
    QPushButton:pressed {
        background-color: #74c7ec;
        padding-top: 11px;
        padding-left: 21px;
    }
    QPushButton#StopButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f38ba8, stop:1 #eba0ac);
        color: #1e1e2e;
    }
    QPushButton#StopButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eba0ac, stop:1 #f38ba8);
    }
    QTextEdit {
        background-color: rgba(24, 24, 37, 0.6);
        color: #a6adc8;
        border: 1px solid #313244;
        border-radius: 8px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 12px;
        selection-background-color: #585b70;
    }
    QGroupBox {
        border: 1px solid #313244;
        border-radius: 8px;
        margin-top: 20px;
        font-weight: bold;
        color: #89b4fa;
        background-color: rgba(30, 30, 46, 0.3);
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top center;
        padding: 5px 10px;
        background-color: #1e1e2e;
        border-radius: 4px;
    }
    QSplitter::handle {
        background-color: #313244;
        width: 2px;
    }
    """

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PolyMarketCopier")
        self.resize(1500, 550)
        
        # Apply Style
        self.setStyleSheet(GlassStyle.STYLESHEET)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main Layout (Split View)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Splitter
        from PyQt6.QtWidgets import QSplitter, QScrollArea
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # --- LEFT PANEL: CONFIG ---
        self.config_container = QWidget()
        
        # Make config scrollable if needed
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.config_container)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        config_layout = QVBoxLayout(self.config_container)
        config_layout.setContentsMargins(0, 0, 20, 0) # Right margin for spacing
        config_layout.setSpacing(15)
        
        # Title/Header
        title_lbl = QLabel("Configuration")
        title_lbl.setStyleSheet("font-size: 18px; color: #89b4fa; font-weight: bold;")
        config_layout.addWidget(title_lbl)
        
        # Form Container
        form_container = QWidget()
        form_layout = QFormLayout(form_container)
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # FIELDS
        self.input_private_key = QLineEdit()
        self.input_private_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_private_key.setPlaceholderText("Enter Private Key")
        
        self.input_funder = QLineEdit()
        self.input_funder.setPlaceholderText("0x...")
        
        # Wallets File
        file_layout = QHBoxLayout()
        self.input_wallets_path = QLineEdit()
        self.btn_browse = QPushButton("...")
        self.btn_browse.setFixedWidth(40)
        self.btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(self.input_wallets_path)
        file_layout.addWidget(self.btn_browse)
        
        self.input_order_type = QComboBox()
        self.input_order_type.addItems(["market", "limit"])
        
        self.input_timeout = QSpinBox()
        self.input_timeout.setRange(1, 3600)
        self.input_timeout.setSuffix(" s")
        self.input_timeout.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        
        self.input_fixed_amount = QDoubleSpinBox()
        self.input_fixed_amount.setRange(0.1, 1000000.0)
        self.input_fixed_amount.setPrefix("$ ")
        self.input_fixed_amount.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        
        self.input_min_share = QCheckBox("Min Share Possible")
        self.input_min_share.setStyleSheet("QCheckBox { spacing: 8px; font-size: 13px; color: #bac2de; } QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #45475a; } QCheckBox::indicator:checked { background-color: #89b4fa; border-color: #89b4fa; }")
        
        form_layout.addRow("Private Key", self.input_private_key)
        form_layout.addRow("Funder Address", self.input_funder)
        form_layout.addRow("Wallets File", file_layout)
        form_layout.addRow("Order Type", self.input_order_type)
        form_layout.addRow("Limit Order Timeout", self.input_timeout)
        form_layout.addRow("Market Order Fixed Amount", self.input_fixed_amount)
        form_layout.addRow("", self.input_min_share)
        
        config_layout.addWidget(form_container)
        
        # Action Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_save = QPushButton("Save Configuration")
        self.btn_save.clicked.connect(self.save_config)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.btn_start = QPushButton("Start Bot")
        self.btn_start.clicked.connect(self.toggle_bot)
        self.btn_start.setCheckable(True)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setFixedHeight(45) # Make the start button bigger
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_start)
        
        config_layout.addStretch()
        config_layout.addLayout(btn_layout)
        
        # --- RIGHT PANEL: CONSOLE ---
        console_panel = QWidget()
        # Give console a bit of background to distinguish
        console_panel.setStyleSheet("background-color: rgba(30, 30, 46, 0.5); border-radius: 8px;")
        
        console_layout = QVBoxLayout(console_panel)
        console_layout.setContentsMargins(15, 15, 15, 15)
        console_layout.setSpacing(10)
        
        console_lbl = QLabel("Live Console")
        console_lbl.setStyleSheet("font-size: 16px; color: #a6adc8; font-weight: bold; background: transparent;")
        
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setPlaceholderText("Waiting for bot execution...")
        self.console_output.setStyleSheet("border: none; background-color: transparent;")
        
        console_layout.addWidget(console_lbl)
        console_layout.addWidget(self.console_output)
        
        # Add panels to splitter
        # We wrap config in a widget that holds the layout? No, scrollArea is a widget.
        self.splitter.addWidget(self.scroll_area)
        self.splitter.addWidget(console_panel)
        
        # Set initial sizes (40% config, 60% console)
        self.splitter.setSizes([350, 550])
        self.splitter.setCollapsible(0, False) # Don't collapse config completely
        
        # Load Config
        self.env_path = ".env"
        self.load_config()
        
        # Worker
        self.worker = None

        # Setup Logs
        self.log_handler = LogSignalHandler()
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.log_handler.log_signal.connect(self.append_log)
        
        # Hook into root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        root_logger.setLevel(logging.INFO)

    def closeEvent(self, event):
        try:
            logging.getLogger().removeHandler(self.log_handler)
        except:
            pass
        if self.worker:
            self.stop_bot()
            if self.worker:
                self.worker.wait(1000) # Give it a second to close logic
        super().closeEvent(event)

    def browse_file(self):
        # Prefer current dir or existing path
        start_dir = "./"
        current_path = self.input_wallets_path.text()
        if os.path.exists(current_path):
            start_dir = os.path.dirname(current_path)
            
        fname, _ = QFileDialog.getOpenFileName(self, "Select Wallets File", start_dir, "Text Files (*.txt);;All Files (*)")
        if fname:
            self.input_wallets_path.setText(fname)

    def load_config(self):
        # Load from .env
        config = dotenv_values(self.env_path)
        
        self.input_private_key.setText(config.get("PRIVATE_KEY", ""))
        self.input_funder.setText(config.get("FUNDER_ADDRESS", ""))
        self.input_wallets_path.setText(config.get("WALLETS_TXT_PATH", ""))
        
        order_type = config.get("ORDER_TYPE", "market").lower()
        idx = self.input_order_type.findText(order_type)
        if idx >= 0:
            self.input_order_type.setCurrentIndex(idx)
            
        try:
            self.input_timeout.setValue(int(config.get("LIMIT_ORDER_TIMEOUT", 10)))
        except:
            self.input_timeout.setValue(10)
            
        try:
            self.input_fixed_amount.setValue(float(config.get("MARKET_ORDER_FIXED_AMMOUNT", 1.0)))
        except:
            self.input_fixed_amount.setValue(1.0)
            
        min_share = config.get("MIN_SHARE_POSSIBLE", "false").lower() == "true"
        self.input_min_share.setChecked(min_share)

    def save_config(self):
        # Save to .env using set_key
        vars_to_save = {
            "PRIVATE_KEY": self.input_private_key.text(),
            "FUNDER_ADDRESS": self.input_funder.text(),
            "WALLETS_TXT_PATH": self.input_wallets_path.text(),
            "ORDER_TYPE": self.input_order_type.currentText(),
            "LIMIT_ORDER_TIMEOUT": str(self.input_timeout.value()),
            "MARKET_ORDER_FIXED_AMMOUNT": str(self.input_fixed_amount.value()),
            "MIN_SHARE_POSSIBLE": str(self.input_min_share.isChecked())
        }
        
        try:
            if not os.path.exists(self.env_path):
                open(self.env_path, 'w').close()
            
            for key, value in vars_to_save.items():
                set_key(self.env_path, key, value)
            
            QMessageBox.information(self, "Success", "Configuration saved!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save config: {str(e)}")

    def toggle_bot(self):
        if self.btn_start.isChecked():
            # START
            self.start_bot()
        else:
            # STOP
            self.stop_bot()

    def start_bot(self):
        if self.worker is not None:
             return

        self.btn_start.setText("Stop Bot")
        self.btn_start.setObjectName("StopButton")
        # Force style update
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)
        
        # Disable inputs while running
        self.input_private_key.setEnabled(False)
        self.input_funder.setEnabled(False)
        self.input_wallets_path.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.input_order_type.setEnabled(False)
        self.input_timeout.setEnabled(False)
        self.input_fixed_amount.setEnabled(False)
        self.input_min_share.setEnabled(False)
        self.btn_save.setEnabled(False)

        self.console_output.clear()
        self.console_output.append(">>> Starting Bot...")

        # Initialize Controller
        try:
            pmc = PolyMarketController(
                private_key = self.input_private_key.text(),
                founder_key = self.input_funder.text(),
                wallets_txt_path = self.input_wallets_path.text(),
                order_type = self.input_order_type.currentText(),
                limit_order_timeout = self.input_timeout.value(),
                market_order_fixed_ammount = self.input_fixed_amount.value(),
                min_share_possible = self.input_min_share.isChecked()
            )
            
            self.worker = Worker(pmc)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.start()
            self.btn_start.setChecked(True)
            
        except Exception as e:
            self.console_output.append(f"ERROR Initializing: {e}")
            self.stop_bot(force_ui_reset=True)

    def stop_bot(self, force_ui_reset=False):
        if self.worker:
            self.console_output.append(">>> Stopping Bot (waiting for loops to cancel)...")
            self.worker.stop()
            # We wait for finished signal to reset UI
        elif force_ui_reset:
            self.reset_start_button()

    def on_worker_finished(self):
        self.console_output.append(">>> Bot Stopped.")
        self.reset_start_button()
        self.worker = None

    def reset_start_button(self):
        self.input_private_key.setEnabled(True)
        self.input_funder.setEnabled(True)
        self.input_wallets_path.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.input_order_type.setEnabled(True)
        self.input_timeout.setEnabled(True)
        self.input_fixed_amount.setEnabled(True)
        self.input_min_share.setEnabled(True)
        self.btn_save.setEnabled(True)

        self.btn_start.setChecked(False)
        self.btn_start.setText("Start Bot")
        self.btn_start.setObjectName("")
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)

    @pyqtSlot(str)
    def append_log(self, msg):
        self.console_output.append(msg)
        # Auto scroll
        sb = self.console_output.verticalScrollBar()
        sb.setValue(sb.maximum())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set Fusion style for better cross-platform base
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
