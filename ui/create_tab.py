"""
Create Tab - Tab tạo ảnh chính của ứng dụng
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPushButton, QLabel, QScrollArea,
    QFrame, QSpinBox, QMessageBox, QDialog,
    QProgressBar, QGroupBox, QComboBox, QLineEdit
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QPixmap, QFont

import asyncio
import base64
import re
from typing import List, Optional
from datetime import datetime

from services.config_service import config_service
from services.chatgpt_service import chatgpt_service
from services.chatgpt_web_service import chatgpt_web_service
from services.gemini_service import gemini_service, ImageStatus
from utils.prompt_parser import parse_prompts, ParsedPrompt
from utils.image_downloader import ImageDownloader
from ui.image_item import ImageItemWidget

from UnlimitedAPI.providers.google_flow import (
    generate_google_flow_images,
    ImageRequest
)


def map_size_to_api_format(image_size: tuple) -> str:
    """Map tuple size sang format string cho API"""
    width, height = image_size
    # Map sang các size được hỗ trợ bởi Google Flow
    if width > height:
        return "1792x1024"  # Landscape
    elif height > width:
        return "1024x1792"  # Portrait
    else:
        return "1024x1024"  # Square


class ImageGeneratorWorker(QObject):
    """
    Worker thread để tạo ảnh không block UI
    Hỗ trợ cả ImageFX (Google Flow) và Gemini API
    """

    # Signals
    started = Signal()
    finished = Signal()
    progress = Signal(int, int)  # current, total
    image_started = Signal(int)  # index
    image_completed = Signal(int, bytes, str)  # index, data, mime_type
    image_failed = Signal(int, str)  # index, error
    log_message = Signal(str)  # log message

    def __init__(
        self,
        prompts: List[ParsedPrompt],
        image_size: tuple = (1024, 1024),
        bearer_token: str = "",
        provider: str = "imagefx",
        gemini_api_key: str = ""
    ):
        super().__init__()
        self._prompts = prompts
        self._image_size = image_size
        self._bearer_token = bearer_token
        self._provider = provider  # "imagefx" hoặc "gemini"
        self._gemini_api_key = gemini_api_key
        self._should_stop = False

    def stop(self):
        """Dừng worker"""
        self._should_stop = True

    def run(self):
        """Thực thi tạo ảnh"""
        self.started.emit()
        total = len(self._prompts)

        provider_name = "ImageFX" if self._provider == "imagefx" else "Gemini"
        self.log_message.emit(f"Sử dụng provider: {provider_name}")

        # Tạo event loop cho async (dùng cho ImageFX)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for i, prompt_obj in enumerate(self._prompts):
                if self._should_stop:
                    self.log_message.emit("Đã dừng tạo ảnh.")
                    break

                self.image_started.emit(prompt_obj.index)
                self.progress.emit(i + 1, total)
                self.log_message.emit(f"[{i+1}/{total}] Đang tạo ảnh #{prompt_obj.index} với {provider_name}...")

                try:
                    if self._provider == "imagefx":
                        self._generate_with_imagefx(loop, prompt_obj, i, total)
                    else:
                        self._generate_with_gemini(prompt_obj, i, total)

                except Exception as e:
                    error_msg = str(e)
                    self.image_failed.emit(prompt_obj.index, error_msg)
                    self.log_message.emit(f"[{i+1}/{total}] Ảnh #{prompt_obj.index} - Lỗi: {error_msg}")

        finally:
            loop.close()

        self.finished.emit()

    def _generate_with_imagefx(self, loop, prompt_obj: ParsedPrompt, i: int, total: int):
        """Tạo ảnh với ImageFX (Google Flow API)"""
        size_str = map_size_to_api_format(self._image_size)
        request = ImageRequest(
            model="IMAGEN_4",
            prompt=prompt_obj.content,
            n=1,
            size=size_str,
            response_format="b64_json"
        )

        result = loop.run_until_complete(
            generate_google_flow_images(request, self._bearer_token)
        )

        if result.data and len(result.data) > 0:
            image_data_obj = result.data[0]
            image_bytes = base64.b64decode(image_data_obj.b64_json)

            self.image_completed.emit(prompt_obj.index, image_bytes, "image/png")
            self.log_message.emit(f"[{i+1}/{total}] Ảnh #{prompt_obj.index} - Hoàn thành!")
        else:
            self.image_failed.emit(prompt_obj.index, "Không có dữ liệu ảnh trong response")
            self.log_message.emit(f"[{i+1}/{total}] Ảnh #{prompt_obj.index} - Lỗi: Không có dữ liệu ảnh")

    def _generate_with_gemini(self, prompt_obj: ParsedPrompt, i: int, total: int):
        """Tạo ảnh với Gemini API"""
        result = gemini_service.generate_image(
            prompt=prompt_obj.content,
            api_key=self._gemini_api_key,
            max_retries=3,
            retry_delay=2.0,
            image_size=self._image_size
        )

        if result.success and result.image_data:
            self.image_completed.emit(prompt_obj.index, result.image_data, result.mime_type)
            self.log_message.emit(f"[{i+1}/{total}] Ảnh #{prompt_obj.index} - Hoàn thành!")
        else:
            error_msg = result.error_message or "Không thể tạo ảnh"
            self.image_failed.emit(prompt_obj.index, error_msg)
            self.log_message.emit(f"[{i+1}/{total}] Ảnh #{prompt_obj.index} - Lỗi: {error_msg}")


class ImagePreviewDialog(QDialog):
    """Dialog xem ảnh full size"""

    def __init__(self, pixmap: QPixmap, prompt: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Xem ảnh")
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)

        # Image
        image_label = QLabel()
        scaled = pixmap.scaled(
            800, 600,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        image_label.setPixmap(scaled)
        image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(image_label)

        # Prompt
        prompt_label = QLabel(f"Prompt: {prompt[:200]}...")
        prompt_label.setWordWrap(True)
        prompt_label.setStyleSheet("color: #666; padding: 10px;")
        layout.addWidget(prompt_label)

        # Close button
        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)


class CreateTab(QWidget):
    """
    Tab tạo ảnh
    - Input prompt
    - Gọi ChatGPT để generate image prompts
    - Gọi Gemini để tạo ảnh
    - Hiển thị kết quả
    """

    def __init__(self):
        super().__init__()

        self._image_items: List[ImageItemWidget] = []
        self._parsed_prompts: List[ParsedPrompt] = []
        self._worker: Optional[ImageGeneratorWorker] = None
        self._worker_thread: Optional[QThread] = None

        self._init_ui()

    def _init_ui(self):
        """Khởi tạo UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Splitter để chia left/right
        splitter = QSplitter(Qt.Horizontal)

        # ========== LEFT PANEL ==========
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)

        # Title
        title = QLabel("Tạo Ảnh AI")
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 10px;")
        left_layout.addWidget(title)

        # ========== OPTION 1: ChatGPT Prompt (Web) ==========
        chatgpt_group = QGroupBox("Tùy chọn 1: Tạo prompt với ChatGPT (Web)")
        chatgpt_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        chatgpt_layout = QVBoxLayout()

        # Browser control buttons
        browser_layout = QHBoxLayout()

        self.open_browser_btn = QPushButton("Mở trình duyệt ChatGPT")
        self.open_browser_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 6px 12px;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.open_browser_btn.clicked.connect(self._on_open_browser_clicked)
        browser_layout.addWidget(self.open_browser_btn)

        self.browser_status_label = QLabel("Trình duyệt: Chưa mở")
        self.browser_status_label.setStyleSheet("color: #666; font-size: 11px;")
        browser_layout.addWidget(self.browser_status_label)
        browser_layout.addStretch()

        self.close_browser_btn = QPushButton("Đóng")
        self.close_browser_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                padding: 6px 12px;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #616161; }
        """)
        self.close_browser_btn.clicked.connect(self._on_close_browser_clicked)
        browser_layout.addWidget(self.close_browser_btn)

        chatgpt_layout.addLayout(browser_layout)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText(
            "Nhập mô tả ý tưởng của bạn ở đây...\n\n"
            "Ví dụ:\n"
            "- Tạo 3 ảnh về phong cảnh Việt Nam vào buổi hoàng hôn\n"
            "- Thiết kế logo cho startup công nghệ AI, phong cách minimal\n\n"
            "Lưu ý: Nhấn 'Mở trình duyệt ChatGPT' và đăng nhập trước khi tạo."
        )
        self.prompt_input.setMinimumHeight(80)
        chatgpt_layout.addWidget(self.prompt_input)

        # Number of prompts
        num_layout = QHBoxLayout()
        num_layout.addWidget(QLabel("Số lượng ảnh:"))
        self.num_prompts_spin = QSpinBox()
        self.num_prompts_spin.setRange(1, 10)
        self.num_prompts_spin.setValue(3)
        self.num_prompts_spin.setFixedWidth(60)
        num_layout.addWidget(self.num_prompts_spin)
        num_layout.addStretch()

        self.start_btn = QPushButton("Tạo với ChatGPT Web")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.start_btn.clicked.connect(self._on_start_clicked)
        num_layout.addWidget(self.start_btn)

        chatgpt_layout.addLayout(num_layout)
        chatgpt_group.setLayout(chatgpt_layout)
        left_layout.addWidget(chatgpt_group)

        # ========== OPTION 2: Direct Image Prompt ==========
        direct_group = QGroupBox("Tùy chọn 2: Nhập trực tiếp Image Prompt")
        direct_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        direct_layout = QVBoxLayout()

        self.direct_prompt_input = QTextEdit()
        self.direct_prompt_input.setPlaceholderText(
            "Nhập trực tiếp image prompt (bỏ qua ChatGPT)...\n\n"
            "Mỗi prompt trên một dòng. Ví dụ:\n"
            "1. A beautiful sunset over mountains, golden hour, realistic\n"
            "2. A cute cat playing with yarn, studio lighting\n"
            "3. Futuristic city skyline at night, cyberpunk style"
        )
        self.direct_prompt_input.setMinimumHeight(100)
        direct_layout.addWidget(self.direct_prompt_input)

        # Direct action button
        direct_btn_layout = QHBoxLayout()
        direct_btn_layout.addStretch()

        self.direct_start_btn = QPushButton("Tạo ảnh trực tiếp")
        self.direct_start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.direct_start_btn.clicked.connect(self._on_direct_start_clicked)
        direct_btn_layout.addWidget(self.direct_start_btn)

        direct_layout.addLayout(direct_btn_layout)
        direct_group.setLayout(direct_layout)
        left_layout.addWidget(direct_group)

        # ========== Common Settings ==========
        settings_group = QGroupBox("Cài đặt chung")
        settings_layout = QVBoxLayout()

        # Image Provider - Dropdown
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Tạo ảnh bằng:"))

        self.image_provider_combo = QComboBox()
        self.image_provider_combo.setMinimumWidth(220)

        self.IMAGE_PROVIDERS = [
            ("imagefx", "ImageFX (Google Labs) - Khuyến nghị"),
            ("gemini", "Gemini API"),
        ]

        for provider_value, display_name in self.IMAGE_PROVIDERS:
            self.image_provider_combo.addItem(display_name, provider_value)

        provider_layout.addWidget(self.image_provider_combo)
        provider_layout.addStretch()
        settings_layout.addLayout(provider_layout)

        # Image Size - Dropdown
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Kích thước ảnh:"))

        self.image_size_combo = QComboBox()
        self.image_size_combo.setMinimumWidth(180)

        self.IMAGE_SIZES = [
            ("1080x1920", "1080 x 1920 (Full HD 9:16)"),
            ("1024x1024", "1024 x 1024 (Vuông)"),
            ("1280x720", "1280 x 720 (HD 16:9)"),
            ("720x1280", "720 x 1280 (HD Dọc)"),
            ("custom", "Tùy chỉnh..."),
        ]

        for size_value, display_name in self.IMAGE_SIZES:
            self.image_size_combo.addItem(display_name, size_value)

        self.image_size_combo.currentIndexChanged.connect(self._on_size_changed)
        size_layout.addWidget(self.image_size_combo)

        # Custom size inputs (ẩn mặc định)
        self.custom_width_input = QLineEdit()
        self.custom_width_input.setPlaceholderText("Width")
        self.custom_width_input.setFixedWidth(70)
        self.custom_width_input.setVisible(False)
        size_layout.addWidget(self.custom_width_input)

        self.size_x_label = QLabel("x")
        self.size_x_label.setVisible(False)
        size_layout.addWidget(self.size_x_label)

        self.custom_height_input = QLineEdit()
        self.custom_height_input.setPlaceholderText("Height")
        self.custom_height_input.setFixedWidth(70)
        self.custom_height_input.setVisible(False)
        size_layout.addWidget(self.custom_height_input)

        size_layout.addStretch()

        # Stop button
        self.stop_btn = QPushButton("Dừng")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px 16px;
                font-size: 13px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #d32f2f; }
        """)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        size_layout.addWidget(self.stop_btn)

        settings_layout.addLayout(size_layout)
        settings_group.setLayout(settings_layout)
        left_layout.addWidget(settings_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        # Log Console
        log_group = QGroupBox("Log Hệ Thống")
        log_layout = QVBoxLayout()

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(200)
        self.log_console.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.log_console)

        log_group.setLayout(log_layout)
        left_layout.addWidget(log_group)

        left_layout.addStretch()

        splitter.addWidget(left_panel)

        # ========== RIGHT PANEL ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)

        # Header
        header_layout = QHBoxLayout()
        results_title = QLabel("Kết Quả")
        results_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(results_title)

        header_layout.addStretch()

        self.select_all_btn = QPushButton("Chọn tất cả")
        self.select_all_btn.clicked.connect(self._select_all)
        header_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Bỏ chọn tất cả")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        header_layout.addWidget(self.deselect_all_btn)

        right_layout.addLayout(header_layout)

        # Scroll area for image items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setAlignment(Qt.AlignTop)
        self.results_layout.setSpacing(10)

        # Placeholder
        self.placeholder = QLabel("Chưa có ảnh nào.\nHãy nhập prompt và bấm 'Bắt đầu tạo ảnh'.")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("color: #999; padding: 50px;")
        self.results_layout.addWidget(self.placeholder)

        scroll.setWidget(self.results_container)
        right_layout.addWidget(scroll)

        # Download button
        self.download_btn = QPushButton("Tải tất cả ảnh đã chọn")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download_selected)
        right_layout.addWidget(self.download_btn)

        splitter.addWidget(right_panel)

        # Set splitter sizes (40% left, 60% right)
        splitter.setSizes([400, 600])

        layout.addWidget(splitter)

    def _log(self, message: str):
        """Thêm log vào console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_console.append(f"[{timestamp}] {message}")
        # Auto scroll to bottom
        self.log_console.verticalScrollBar().setValue(
            self.log_console.verticalScrollBar().maximum()
        )

    def _on_size_changed(self, index: int):
        """Handler khi thay đổi kích thước ảnh"""
        size_value = self.image_size_combo.currentData()
        is_custom = (size_value == "custom")

        # Hiện/ẩn custom inputs
        self.custom_width_input.setVisible(is_custom)
        self.size_x_label.setVisible(is_custom)
        self.custom_height_input.setVisible(is_custom)

        if is_custom:
            # Set giá trị mặc định cho custom
            if not self.custom_width_input.text():
                self.custom_width_input.setText("1024")
            if not self.custom_height_input.text():
                self.custom_height_input.setText("1024")

    def _get_image_size(self) -> tuple:
        """
        Lấy kích thước ảnh đã chọn

        Returns:
            Tuple (width, height) hoặc (None, None) nếu không hợp lệ
        """
        size_value = self.image_size_combo.currentData()

        if size_value == "custom":
            # Lấy từ custom inputs
            try:
                width = int(self.custom_width_input.text().strip())
                height = int(self.custom_height_input.text().strip())

                # Validate range (thường Gemini hỗ trợ từ 256 đến 2048)
                if width < 256 or width > 2048 or height < 256 or height > 2048:
                    return (None, None)

                return (width, height)
            except (ValueError, AttributeError):
                return (None, None)
        else:
            # Parse từ preset (format: "1024x1024")
            try:
                parts = size_value.split("x")
                return (int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                return (1024, 1024)  # Default

    def _get_image_size_string(self) -> str:
        """Lấy chuỗi mô tả kích thước để hiển thị"""
        width, height = self._get_image_size()
        if width and height:
            return f"{width}x{height}"
        return "1024x1024"

    def _clear_results(self):
        """Xóa tất cả kết quả"""
        for item in self._image_items:
            item.deleteLater()
        self._image_items.clear()

        # Hiện placeholder
        self.placeholder.setVisible(True)

    def _on_open_browser_clicked(self):
        """Handler mở trình duyệt ChatGPT"""
        self._log("Đang mở trình duyệt Chrome...")
        self.open_browser_btn.setEnabled(False)
        self.browser_status_label.setText("Trình duyệt: Đang mở...")
        self.browser_status_label.setStyleSheet("color: #FF9800; font-size: 11px;")

        chatgpt_web_service.set_status_callback(self._log)

        import threading
        def open_browser():
            result = chatgpt_web_service.open_browser_and_wait_login()
            # Update UI in main thread
            if result.success:
                self.browser_status_label.setText("Trình duyệt: Đã sẵn sàng")
                self.browser_status_label.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold;")
            else:
                self.browser_status_label.setText(f"Lỗi: {result.error_message[:30]}...")
                self.browser_status_label.setStyleSheet("color: #f44336; font-size: 11px;")
            self.open_browser_btn.setEnabled(True)

        thread = threading.Thread(target=open_browser, daemon=True)
        thread.start()

    def _on_close_browser_clicked(self):
        """Handler đóng trình duyệt"""
        chatgpt_web_service.close_browser()
        self.browser_status_label.setText("Trình duyệt: Đã đóng")
        self.browser_status_label.setStyleSheet("color: #666; font-size: 11px;")
        self._log("Đã đóng trình duyệt ChatGPT")

    def _on_start_clicked(self):
        """Handler khi bấm nút Bắt đầu (dùng ChatGPT Web)"""
        # Validate config dựa trên provider
        if not self._validate_provider_config():
            return

        # Kiểm tra trình duyệt đã mở chưa
        if not chatgpt_web_service.is_browser_open():
            reply = QMessageBox.question(
                self,
                "Trình duyệt chưa mở",
                "Trình duyệt ChatGPT chưa được mở.\nBạn có muốn mở ngay không?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._on_open_browser_clicked()
            return

        # Validate prompt
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(
                self,
                "Lỗi",
                "Vui lòng nhập prompt!"
            )
            return

        # Validate image size
        width, height = self._get_image_size()
        if width is None or height is None:
            QMessageBox.warning(
                self,
                "Lỗi",
                "Kích thước ảnh không hợp lệ!\nWidth và Height phải từ 256 đến 2048."
            )
            return

        # Clear previous results
        self._clear_results()
        self.log_console.clear()
        self._log("Bắt đầu quy trình tạo ảnh...")
        self._log(f"Kích thước ảnh: {width}x{height}")

        # Disable controls
        self._disable_controls()

        # Step 1: Call ChatGPT Web
        self._log("Bước 1: Gửi prompt đến ChatGPT Web...")
        self._call_chatgpt_web(prompt)

    def _validate_provider_config(self) -> bool:
        """Validate config dựa trên provider được chọn"""
        provider = self._get_selected_provider()
        config = config_service.config

        if provider == "imagefx":
            if not config.google_bearer_token:
                QMessageBox.warning(
                    self,
                    "Cấu hình chưa đầy đủ",
                    "Bạn đã chọn ImageFX.\nVui lòng cấu hình Google Bearer Token trong tab Cài đặt."
                )
                return False
        else:  # gemini
            if not config.gemini_api_key:
                QMessageBox.warning(
                    self,
                    "Cấu hình chưa đầy đủ",
                    "Bạn đã chọn Gemini.\nVui lòng cấu hình Gemini API Key trong tab Cài đặt."
                )
                return False

        return True

    def _on_direct_start_clicked(self):
        """Handler khi bấm nút Tạo ảnh trực tiếp (bỏ qua ChatGPT)"""
        # Validate config dựa trên provider
        if not self._validate_provider_config():
            return

        config = config_service.config
        # Giữ lại check output directory
        if not config.output_directory:
            QMessageBox.warning(
                self,
                "Cấu hình chưa đầy đủ",
                "Vui lòng cấu hình thư mục lưu ảnh trong tab Cài đặt."
            )
            return

        # Validate prompt
        prompt_text = self.direct_prompt_input.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(
                self,
                "Lỗi",
                "Vui lòng nhập ít nhất một image prompt!"
            )
            return

        # Validate image size
        width, height = self._get_image_size()
        if width is None or height is None:
            QMessageBox.warning(
                self,
                "Lỗi",
                "Kích thước ảnh không hợp lệ!\nWidth và Height phải từ 256 đến 2048."
            )
            return

        # Parse prompts từ input (mỗi dòng là một prompt)
        lines = prompt_text.split('\n')
        self._parsed_prompts = []
        index = 1

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Loại bỏ số thứ tự đầu dòng nếu có (ví dụ: "1. ", "2) ", "- ")
            cleaned = re.sub(r'^\d+[.)]\s*', '', line)  # Bỏ "1. " hoặc "1) "
            cleaned = re.sub(r'^[-*]\s*', '', cleaned)     # Bỏ "- " hoặc "* "
            cleaned = cleaned.strip()

            if cleaned:
                self._parsed_prompts.append(ParsedPrompt(index=index, content=cleaned, original_text=line))
                index += 1

        if not self._parsed_prompts:
            QMessageBox.warning(
                self,
                "Lỗi",
                "Không tìm thấy prompt hợp lệ nào!"
            )
            return

        # Clear previous results
        self._clear_results()
        self.log_console.clear()
        self._log("=== TẠO ẢNH TRỰC TIẾP (Bỏ qua ChatGPT) ===")
        self._log(f"Kích thước ảnh: {width}x{height}")
        self._log(f"Số lượng prompts: {len(self._parsed_prompts)}")

        for p in self._parsed_prompts:
            self._log(f"  [{p.index}] {p.content[:80]}...")

        # Disable controls
        self._disable_controls()

        # Create image items
        self._create_image_items()

        # Start image generation
        provider = self._get_selected_provider()
        provider_name = "ImageFX" if provider == "imagefx" else "Gemini"
        self._log(f"Bắt đầu tạo ảnh với {provider_name}...")
        self._start_image_generation()

    def _disable_controls(self):
        """Disable tất cả controls khi đang xử lý"""
        self.start_btn.setEnabled(False)
        self.direct_start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.prompt_input.setEnabled(False)
        self.direct_prompt_input.setEnabled(False)
        self.download_btn.setEnabled(False)

    def _call_chatgpt(self, prompt: str):
        """Gọi ChatGPT API"""
        num_prompts = self.num_prompts_spin.value()

        # Set callback cho log
        chatgpt_service.set_status_callback(self._log)

        result = chatgpt_service.generate_image_prompts(
            user_prompt=prompt,
            num_prompts=num_prompts
        )

        if not result.success:
            self._log(f"Lỗi ChatGPT: {result.error_message}")
            QMessageBox.critical(
                self,
                "Lỗi ChatGPT",
                f"Không thể tạo image prompts:\n{result.error_message}"
            )
            self._reset_controls()
            return

        # Step 2: Parse prompts
        self._log("Bước 2: Parse image prompts từ response...")
        self._log(f"Response từ ChatGPT:\n{result.content[:500]}...")

        self._parsed_prompts = parse_prompts(result.content)

        if not self._parsed_prompts:
            self._log("Không tìm thấy image prompt nào trong response!")
            QMessageBox.warning(
                self,
                "Lỗi",
                "Không thể parse image prompts từ ChatGPT response."
            )
            self._reset_controls()
            return

        self._log(f"Đã tìm thấy {len(self._parsed_prompts)} image prompts")

        # Create image items
        self._create_image_items()

        # Step 3: Generate images
        self._log("Bước 3: Tạo ảnh với Gemini...")
        self._start_image_generation()

    def _call_chatgpt_web(self, prompt: str):
        """Gọi ChatGPT qua Web browser"""
        num_prompts = self.num_prompts_spin.value()

        chatgpt_web_service.set_status_callback(self._log)

        self._log("Đang gửi prompt đến ChatGPT Web...")

        import threading
        def call_web():
            result = chatgpt_web_service.generate_image_prompts(
                user_prompt=prompt,
                num_prompts=num_prompts
            )

            # Xử lý kết quả trong main thread
            if result.success:
                self._handle_chatgpt_web_success(result.content)
            else:
                self._handle_chatgpt_web_error(result.error_message)

        thread = threading.Thread(target=call_web, daemon=True)
        thread.start()

    def _handle_chatgpt_web_success(self, content: str):
        """Xử lý khi ChatGPT Web trả về thành công"""
        # Step 2: Parse prompts
        self._log("Bước 2: Parse image prompts từ response...")
        self._log(f"Response từ ChatGPT:\n{content[:500]}...")

        self._parsed_prompts = parse_prompts(content)

        if not self._parsed_prompts:
            self._log("Không tìm thấy image prompt nào trong response!")
            QMessageBox.warning(
                self,
                "Lỗi",
                "Không thể parse image prompts từ ChatGPT response."
            )
            self._reset_controls()
            return

        self._log(f"Đã tìm thấy {len(self._parsed_prompts)} image prompts")

        # Create image items
        self._create_image_items()

        # Step 3: Generate images
        self._log("Bước 3: Tạo ảnh...")
        self._start_image_generation()

    def _handle_chatgpt_web_error(self, error_message: str):
        """Xử lý khi ChatGPT Web gặp lỗi"""
        self._log(f"Lỗi ChatGPT Web: {error_message}")
        QMessageBox.critical(
            self,
            "Lỗi ChatGPT Web",
            f"Không thể tạo image prompts:\n{error_message}"
        )
        self._reset_controls()

    def _create_image_items(self):
        """Tạo các image item widgets"""
        self.placeholder.setVisible(False)

        for prompt_obj in self._parsed_prompts:
            item = ImageItemWidget(
                index=prompt_obj.index,
                prompt=prompt_obj.content
            )
            item.view_clicked.connect(self._on_view_image)
            item.regenerate_clicked.connect(self._on_regenerate_image)
            item.edit_prompt_clicked.connect(self._on_edit_prompt)

            self._image_items.append(item)
            self.results_layout.addWidget(item)

    def _get_selected_provider(self) -> str:
        """Lấy provider đã chọn từ dropdown"""
        return self.image_provider_combo.currentData() or "imagefx"

    def _start_image_generation(self):
        """Bắt đầu tạo ảnh trong background thread"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self._parsed_prompts))
        self.progress_bar.setValue(0)

        # Lấy kích thước ảnh đã chọn
        image_size = self._get_image_size()

        # Lấy provider đã chọn
        provider = self._get_selected_provider()

        # Lấy config
        config = config_service.config
        bearer_token = config.google_bearer_token
        gemini_api_key = config.gemini_api_key

        # Create worker với provider
        self._worker = ImageGeneratorWorker(
            prompts=self._parsed_prompts,
            image_size=image_size,
            bearer_token=bearer_token,
            provider=provider,
            gemini_api_key=gemini_api_key
        )
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)

        # Connect signals
        self._worker_thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.image_started.connect(self._on_image_started)
        self._worker.image_completed.connect(self._on_image_completed)
        self._worker.image_failed.connect(self._on_image_failed)
        self._worker.log_message.connect(self._log)
        self._worker.finished.connect(self._on_generation_finished)

        # Start
        self._worker_thread.start()

    def _on_progress(self, current: int, total: int):
        """Handler cập nhật progress"""
        self.progress_bar.setValue(current)

    def _on_image_started(self, index: int):
        """Handler khi bắt đầu tạo một ảnh"""
        for item in self._image_items:
            if item.index == index:
                item.set_status(ImageStatus.PROCESSING)
                break

    def _on_image_completed(self, index: int, data: bytes, mime_type: str):
        """Handler khi tạo ảnh thành công"""
        for item in self._image_items:
            if item.index == index:
                item.set_status(ImageStatus.SUCCESS)
                item.set_image(data, mime_type)
                break

    def _on_image_failed(self, index: int, error: str):
        """Handler khi tạo ảnh thất bại"""
        for item in self._image_items:
            if item.index == index:
                item.set_error(error)
                break

    def _on_generation_finished(self):
        """Handler khi hoàn thành tạo tất cả ảnh"""
        self._log("Hoàn thành tạo ảnh!")

        # Cleanup thread
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None
            self._worker = None

        self._reset_controls()

        # Enable download if any successful
        successful = sum(1 for item in self._image_items if item.status == ImageStatus.SUCCESS)
        if successful > 0:
            self.download_btn.setEnabled(True)
            self._log(f"Có {successful}/{len(self._image_items)} ảnh tạo thành công.")

    def _on_stop_clicked(self):
        """Handler khi bấm nút Dừng"""
        if self._worker:
            self._worker.stop()
            self._log("Đang dừng...")

    def _reset_controls(self):
        """Reset controls về trạng thái ban đầu"""
        self.start_btn.setEnabled(True)
        self.direct_start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.prompt_input.setEnabled(True)
        self.direct_prompt_input.setEnabled(True)
        self.progress_bar.setVisible(False)

    def _on_view_image(self, index: int):
        """Handler xem ảnh"""
        for item in self._image_items:
            if item.index == index:
                pixmap = item.get_full_image()
                if pixmap:
                    dialog = ImagePreviewDialog(pixmap, item.prompt, self)
                    dialog.exec()
                break

    def _on_regenerate_image(self, index: int):
        """Handler tạo lại ảnh"""
        # Tìm prompt tương ứng
        prompt_obj = None
        for p in self._parsed_prompts:
            if p.index == index:
                prompt_obj = p
                break

        if not prompt_obj:
            return

        # Tìm item widget
        item_widget = None
        for item in self._image_items:
            if item.index == index:
                item_widget = item
                break

        if not item_widget:
            return

        # Lấy provider đã chọn
        provider = self._get_selected_provider()
        provider_name = "ImageFX" if provider == "imagefx" else "Gemini"

        self._log(f"Tạo lại ảnh #{index} với {provider_name}...")
        item_widget.set_status(ImageStatus.PROCESSING)

        config = config_service.config
        image_size = self._get_image_size()

        try:
            if provider == "imagefx":
                # Tạo ảnh với ImageFX
                bearer_token = config.google_bearer_token
                size_str = map_size_to_api_format(image_size)

                request = ImageRequest(
                    model="IMAGEN_4",
                    prompt=prompt_obj.content,
                    n=1,
                    size=size_str,
                    response_format="b64_json"
                )

                result = asyncio.run(generate_google_flow_images(request, bearer_token))

                if result.data and len(result.data) > 0:
                    image_data_obj = result.data[0]
                    image_bytes = base64.b64decode(image_data_obj.b64_json)

                    item_widget.set_status(ImageStatus.SUCCESS)
                    item_widget.set_image(image_bytes, "image/png")
                    self._log(f"Tạo lại ảnh #{index} thành công!")
                else:
                    item_widget.set_error("Không có dữ liệu ảnh trong response")
                    self._log(f"Tạo lại ảnh #{index} thất bại: Không có dữ liệu ảnh")
            else:
                # Tạo ảnh với Gemini
                result = gemini_service.generate_image(
                    prompt=prompt_obj.content,
                    api_key=config.gemini_api_key,
                    max_retries=3,
                    retry_delay=2.0,
                    image_size=image_size
                )

                if result.success and result.image_data:
                    item_widget.set_status(ImageStatus.SUCCESS)
                    item_widget.set_image(result.image_data, result.mime_type)
                    self._log(f"Tạo lại ảnh #{index} thành công!")
                else:
                    error_msg = result.error_message or "Không thể tạo ảnh"
                    item_widget.set_error(error_msg)
                    self._log(f"Tạo lại ảnh #{index} thất bại: {error_msg}")

        except Exception as e:
            error_msg = str(e)
            item_widget.set_error(error_msg)
            self._log(f"Tạo lại ảnh #{index} thất bại: {error_msg}")

    def _on_edit_prompt(self, index: int, new_prompt: str):
        """Handler khi chỉnh sửa prompt (chỉ lưu, không tạo lại ảnh)"""
        # Cập nhật prompt trong parsed_prompts
        for i, p in enumerate(self._parsed_prompts):
            if p.index == index:
                self._parsed_prompts[i] = ParsedPrompt(
                    index=index,
                    content=new_prompt,
                    original_text=new_prompt
                )
                break

        self._log(f"Đã lưu prompt #{index}")
        self._log(f"Prompt mới: {new_prompt[:100]}...")

    def _select_all(self):
        """Chọn tất cả ảnh"""
        for item in self._image_items:
            item.checkbox.setChecked(True)

    def _deselect_all(self):
        """Bỏ chọn tất cả"""
        for item in self._image_items:
            item.checkbox.setChecked(False)

    def _download_selected(self):
        """Tải các ảnh đã chọn"""
        config = config_service.config
        output_dir = config.output_directory

        if not output_dir:
            QMessageBox.warning(
                self,
                "Lỗi",
                "Chưa cấu hình thư mục lưu ảnh!"
            )
            return

        selected = [
            item for item in self._image_items
            if item.is_selected and item.image_data
        ]

        if not selected:
            QMessageBox.information(
                self,
                "Thông báo",
                "Không có ảnh nào được chọn để tải."
            )
            return

        self._log(f"Đang lưu {len(selected)} ảnh vào {output_dir}...")

        success_count = 0
        for item in selected:
            result = ImageDownloader.save_image_from_prompt(
                image_data=item.image_data,
                prompt=item.prompt,
                output_dir=output_dir,
                index=item.index,
                mime_type=item.mime_type
            )

            if result.success:
                success_count += 1
                self._log(f"Đã lưu: {result.file_path}")
            else:
                self._log(f"Lỗi lưu ảnh #{item.index}: {result.error_message}")

        self._log(f"Hoàn thành! Đã lưu {success_count}/{len(selected)} ảnh.")

        QMessageBox.information(
            self,
            "Hoàn thành",
            f"Đã lưu {success_count}/{len(selected)} ảnh vào:\n{output_dir}"
        )

    def test_google_flow_generation(self, test_prompt: str = "A beautiful sunset over mountains"):
        """
        Test hàm tạo ảnh với Google Flow API

        Args:
            test_prompt: Prompt để test (mặc định: "A beautiful sunset over mountains")

        Returns:
            dict: Kết quả test với các trường:
                - success: bool
                - message: str
                - image_data: bytes (nếu thành công)
                - error: str (nếu thất bại)
        """
        self._log("=== BẮT ĐẦU TEST GOOGLE FLOW API ===")

        # Lấy config
        config = config_service.config
        bearer_token = config.google_bearer_token

        # Kiểm tra bearer token
        if not bearer_token:
            error_msg = "Google Bearer Token chưa được cấu hình!"
            self._log(f"Lỗi: {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "image_data": None,
                "error": error_msg
            }

        self._log(f"Bearer Token: {bearer_token[:20]}...{bearer_token[-10:]}")
        self._log(f"Test Prompt: {test_prompt}")

        try:
            # Tạo ImageRequest
            request = ImageRequest(
                model="IMAGEN_4",
                prompt=test_prompt,
                n=1,
                size="1024x1024",
                response_format="b64_json"
            )
            self._log("Đã tạo ImageRequest")
            self._log(f"  - Model: {request.model}")
            self._log(f"  - Size: {request.size}")
            self._log(f"  - N: {request.n}")

            # Gọi API
            self._log("Đang gọi Google Flow API...")
            result = asyncio.run(generate_google_flow_images(request, bearer_token))

            self._log(f"Response created: {result.created}")
            self._log(f"Số lượng ảnh trả về: {len(result.data)}")

            if result.data and len(result.data) > 0:
                image_data_obj = result.data[0]
                image_bytes = base64.b64decode(image_data_obj.b64_json)

                self._log(f"Ảnh đầu tiên:")
                self._log(f"  - Base64 length: {len(image_data_obj.b64_json)}")
                self._log(f"  - Image bytes: {len(image_bytes)} bytes")
                self._log(f"  - Revised prompt: {image_data_obj.revised_prompt}")

                self._log("=== TEST THÀNH CÔNG ===")

                return {
                    "success": True,
                    "message": "Tạo ảnh thành công!",
                    "image_data": image_bytes,
                    "error": None
                }
            else:
                error_msg = "Không có dữ liệu ảnh trong response"
                self._log(f"Lỗi: {error_msg}")
                self._log("=== TEST THẤT BẠI ===")

                return {
                    "success": False,
                    "message": error_msg,
                    "image_data": None,
                    "error": error_msg
                }

        except Exception as e:
            error_msg = str(e)
            self._log(f"Exception: {error_msg}")
            self._log("=== TEST THẤT BẠI ===")

            return {
                "success": False,
                "message": f"Lỗi khi gọi API: {error_msg}",
                "image_data": None,
                "error": error_msg
            }
