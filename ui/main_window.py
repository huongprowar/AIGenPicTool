"""
Main Window - Cửa sổ chính của ứng dụng
"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QCloseEvent

from ui.create_tab import CreateTab
from ui.settings_tab import SettingsTab
from services.config_service import config_service


class MainWindow(QMainWindow):
    """
    Cửa sổ chính của ứng dụng AI Image Generator
    - Tab Tạo ảnh
    - Tab Cài đặt
    """

    APP_TITLE = "AI Image Generator"
    APP_VERSION = "1.0.0"

    def __init__(self):
        super().__init__()
        self._init_ui()
        self._check_config()

    def _init_ui(self):
        """Khởi tạo UI"""
        # Window settings
        self.setWindowTitle(f"{self.APP_TITLE} v{self.APP_VERSION}")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: white;
            }
            QTabBar::tab {
                padding: 12px 30px;
                font-size: 14px;
                min-width: 120px;
            }
            QTabBar::tab:selected {
                background: #2196F3;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:!selected {
                background: #e0e0e0;
            }
            QTabBar::tab:hover:!selected {
                background: #bdbdbd;
            }
        """)

        # Create tab
        self.create_tab = CreateTab()
        self.tab_widget.addTab(self.create_tab, "Tạo Ảnh")

        # Settings tab
        self.settings_tab = SettingsTab()
        self.settings_tab.settings_saved.connect(self._on_settings_saved)
        self.tab_widget.addTab(self.settings_tab, "Cài Đặt")

        layout.addWidget(self.tab_widget)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

    def _check_config(self):
        """Kiểm tra config và thông báo nếu chưa cấu hình"""
        if not config_service.is_valid():
            # Chuyển sang tab Settings
            self.tab_widget.setCurrentIndex(1)

            QMessageBox.information(
                self,
                "Cấu hình lần đầu",
                "Chào mừng bạn đến với AI Image Generator!\n\n"
                "Vui lòng cấu hình API Keys và thư mục lưu ảnh trước khi sử dụng."
            )

    def _on_settings_saved(self):
        """Handler khi settings được lưu"""
        self._update_status_bar()

        # Nếu config hợp lệ, chuyển về tab Tạo ảnh
        if config_service.is_valid():
            self.tab_widget.setCurrentIndex(0)

    def _update_status_bar(self):
        """Cập nhật status bar"""
        config = config_service.config

        chatgpt_status = "OK" if config.chatgpt_api_key else "Chưa cấu hình"
        gemini_status = "OK" if config.gemini_api_key else "Chưa cấu hình"
        output_status = config.output_directory[:30] + "..." if len(config.output_directory) > 30 else config.output_directory

        self.status_bar.showMessage(
            f"ChatGPT: {chatgpt_status} | "
            f"Gemini: {gemini_status} | "
            f"Output: {output_status or 'Chưa cấu hình'}"
        )

    def closeEvent(self, event: QCloseEvent):
        """Handler khi đóng ứng dụng"""
        # Có thể thêm logic cleanup ở đây nếu cần
        event.accept()
