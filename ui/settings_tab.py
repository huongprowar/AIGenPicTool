"""
Settings Tab - Tab cài đặt của ứng dụng
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QFileDialog,
    QGroupBox, QMessageBox, QSpacerItem, QSizePolicy,
    QComboBox
)
from PySide6.QtCore import Qt, Signal

from services.config_service import config_service
from services.chatgpt_service import chatgpt_service
from services.gemini_service import gemini_service


class SettingsTab(QWidget):
    """
    Tab cài đặt
    - Input API keys (ChatGPT, Gemini)
    - Chọn thư mục lưu ảnh
    - Nút Save/Test connection
    """

    # Signal khi settings được lưu
    settings_saved = Signal()

    def __init__(self):
        super().__init__()
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        """Khởi tạo UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Cài Đặt Ứng Dụng")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # API Keys Group
        api_group = QGroupBox("API Keys")
        api_layout = QFormLayout()
        api_layout.setSpacing(15)

        # ChatGPT API Key
        self.chatgpt_key_input = QLineEdit()
        self.chatgpt_key_input.setPlaceholderText("Nhập ChatGPT API Key (sk-...)")
        self.chatgpt_key_input.setEchoMode(QLineEdit.Password)
        self.chatgpt_key_input.setMinimumWidth(400)

        chatgpt_row = QHBoxLayout()
        chatgpt_row.addWidget(self.chatgpt_key_input)

        self.test_chatgpt_btn = QPushButton("Test")
        self.test_chatgpt_btn.setFixedWidth(80)
        self.test_chatgpt_btn.clicked.connect(self._test_chatgpt)
        chatgpt_row.addWidget(self.test_chatgpt_btn)

        self.toggle_chatgpt_btn = QPushButton("Hiện")
        self.toggle_chatgpt_btn.setFixedWidth(60)
        self.toggle_chatgpt_btn.clicked.connect(lambda: self._toggle_password(self.chatgpt_key_input, self.toggle_chatgpt_btn))
        chatgpt_row.addWidget(self.toggle_chatgpt_btn)

        api_layout.addRow("ChatGPT API Key:", chatgpt_row)

        # Gemini API Key
        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setPlaceholderText("Nhập Gemini API Key")
        self.gemini_key_input.setEchoMode(QLineEdit.Password)
        self.gemini_key_input.setMinimumWidth(400)

        gemini_row = QHBoxLayout()
        gemini_row.addWidget(self.gemini_key_input)

        self.test_gemini_btn = QPushButton("Test")
        self.test_gemini_btn.setFixedWidth(80)
        self.test_gemini_btn.clicked.connect(self._test_gemini)
        gemini_row.addWidget(self.test_gemini_btn)

        self.toggle_gemini_btn = QPushButton("Hiện")
        self.toggle_gemini_btn.setFixedWidth(60)
        self.toggle_gemini_btn.clicked.connect(lambda: self._toggle_password(self.gemini_key_input, self.toggle_gemini_btn))
        gemini_row.addWidget(self.toggle_gemini_btn)

        api_layout.addRow("Gemini API Key:", gemini_row)

        # Google Bearer Token
        self.google_token_input = QLineEdit()
        self.google_token_input.setPlaceholderText("Nhập Google Bearer Token cho Google Flow API")
        self.google_token_input.setEchoMode(QLineEdit.Password)
        self.google_token_input.setMinimumWidth(400)

        google_row = QHBoxLayout()
        google_row.addWidget(self.google_token_input)

        self.toggle_google_btn = QPushButton("Hiện")
        self.toggle_google_btn.setFixedWidth(60)
        self.toggle_google_btn.clicked.connect(lambda: self._toggle_password(self.google_token_input, self.toggle_google_btn))
        google_row.addWidget(self.toggle_google_btn)

        api_layout.addRow("Google Bearer Token:", google_row)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # Output Directory Group
        output_group = QGroupBox("Thư mục lưu ảnh")
        output_layout = QFormLayout()
        output_layout.setSpacing(15)

        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("Chọn thư mục lưu ảnh...")
        self.output_dir_input.setMinimumWidth(400)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_input)

        self.browse_btn = QPushButton("Chọn...")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self._browse_directory)
        output_row.addWidget(self.browse_btn)

        output_layout.addRow("Đường dẫn:", output_row)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # Advanced Settings Group
        advanced_group = QGroupBox("Cài đặt nâng cao")
        advanced_layout = QFormLayout()
        advanced_layout.setSpacing(15)

        # ChatGPT Model - Dropdown với các model có sẵn
        self.chatgpt_model_combo = QComboBox()
        self.chatgpt_model_combo.setMinimumWidth(300)

        # Danh sách các model ChatGPT (model_id, display_name)
        self.CHATGPT_MODELS = [
            # GPT-4o series (Mới nhất, khuyến nghị)
            ("gpt-4o", "GPT-4o - Flagship multimodal"),
            ("gpt-4o-mini", "GPT-4o Mini - Nhanh, rẻ (Khuyến nghị)"),
            ("gpt-4o-2024-11-20", "GPT-4o (2024-11-20)"),
            ("gpt-4o-2024-08-06", "GPT-4o (2024-08-06)"),
            ("gpt-4o-2024-05-13", "GPT-4o (2024-05-13)"),

            # GPT-4 Turbo
            ("gpt-4-turbo", "GPT-4 Turbo - Vision capable"),
            ("gpt-4-turbo-2024-04-09", "GPT-4 Turbo (2024-04-09)"),
            ("gpt-4-turbo-preview", "GPT-4 Turbo Preview"),

            # GPT-4 Classic
            ("gpt-4", "GPT-4 Classic"),
            ("gpt-4-0613", "GPT-4 (0613)"),

            # GPT-3.5 Turbo (Rẻ nhất)
            ("gpt-3.5-turbo", "GPT-3.5 Turbo - Rẻ nhất"),
            ("gpt-3.5-turbo-0125", "GPT-3.5 Turbo (0125)"),

            # O1 series (Reasoning models)
            ("o1", "O1 - Reasoning model"),
            ("o1-mini", "O1 Mini - Reasoning nhẹ"),
            ("o1-preview", "O1 Preview"),
        ]

        for model_id, display_name in self.CHATGPT_MODELS:
            self.chatgpt_model_combo.addItem(display_name, model_id)

        # Set default là gpt-4o-mini (index 1)
        self.chatgpt_model_combo.setCurrentIndex(1)

        advanced_layout.addRow("ChatGPT Model:", self.chatgpt_model_combo)

        # Gemini Model - Dropdown với các model có sẵn
        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.setMinimumWidth(300)

        # Danh sách các model Gemini (model_id, display_name)
        self.GEMINI_MODELS = [
            # Gemini 2.0 (Mới nhất)
            ("gemini-2.0-flash-exp", "Gemini 2.0 Flash Exp - Tạo ảnh (Khuyến nghị)"),
            ("gemini-2.0-flash", "Gemini 2.0 Flash - Nhanh nhất"),

            # Gemini 1.5 Flash (Rate limit cao)
            ("gemini-1.5-flash", "Gemini 1.5 Flash - Rate limit cao"),
            ("gemini-1.5-flash-8b", "Gemini 1.5 Flash 8B - Rất nhanh"),
            ("gemini-1.5-flash-latest", "Gemini 1.5 Flash Latest"),

            # Gemini 1.5 Pro (Chất lượng cao)
            ("gemini-1.5-pro", "Gemini 1.5 Pro - Chất lượng cao"),
            ("gemini-1.5-pro-latest", "Gemini 1.5 Pro Latest"),
            ("gemini-1.5-pro-latest", "Gemini 1.5 Pro Latest"),

            # Experimental
            ("gemma-3-1b-it", "gemma-3-1b-it"),
            ("gemma-3-4b-it", "gemma-3-4b-it"),
            ("gemma-3-12b-it", "gemma-3-12b-it"),
            ("gemma-3-27b-it", "gemma-3-27b-it"),
            ("gemma-3n-e2b-it", "gemma-3n-e2b-it"),
            ("gemma-3n-e4b-it", "gemma-3n-e4b-it"),

        ]
        # Lưu ý: Chỉ gemini-2.0-flash-exp hỗ trợ image generation

        for model_id, display_name in self.GEMINI_MODELS:
            self.gemini_model_combo.addItem(display_name, model_id)

        # Set default là gemini-2.0-flash-exp (index 0)
        self.gemini_model_combo.setCurrentIndex(0)

        advanced_layout.addRow("Gemini Model:", self.gemini_model_combo)

        # Max Retries
        self.max_retries_input = QLineEdit()
        self.max_retries_input.setPlaceholderText("3")
        self.max_retries_input.setFixedWidth(100)
        advanced_layout.addRow("Số lần retry:", self.max_retries_input)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.reset_btn = QPushButton("Reset mặc định")
        self.reset_btn.clicked.connect(self._reset_settings)
        button_layout.addWidget(self.reset_btn)

        self.save_btn = QPushButton("Lưu cài đặt")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 30px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

        # Spacer
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.status_label)

    def _load_settings(self):
        """Load settings từ config"""
        config = config_service.config

        self.chatgpt_key_input.setText(config.chatgpt_api_key)
        self.gemini_key_input.setText(config.gemini_api_key)
        self.google_token_input.setText(config.google_bearer_token)
        self.output_dir_input.setText(config.output_directory)

        # Load ChatGPT model vào combo box
        model_index = self.chatgpt_model_combo.findData(config.chatgpt_model)
        if model_index >= 0:
            self.chatgpt_model_combo.setCurrentIndex(model_index)
        else:
            # Nếu model không có trong list, set về default (gpt-4o-mini)
            self.chatgpt_model_combo.setCurrentIndex(1)

        # Load Gemini model vào combo box
        gemini_model_index = self.gemini_model_combo.findData(config.gemini_model)
        if gemini_model_index >= 0:
            self.gemini_model_combo.setCurrentIndex(gemini_model_index)
        else:
            # Nếu model không có trong list, set về default (gemini-2.0-flash-exp)
            self.gemini_model_combo.setCurrentIndex(0)

        self.max_retries_input.setText(str(config.max_retries))

        self.status_label.setText("Đã load cài đặt từ file config")

    def _save_settings(self):
        """Lưu settings"""
        # Validate
        chatgpt_key = self.chatgpt_key_input.text().strip()
        gemini_key = self.gemini_key_input.text().strip()
        google_token = self.google_token_input.text().strip()
        output_dir = self.output_dir_input.text().strip()
        # Lấy model từ combo box (userData chứa model_id)
        chatgpt_model = self.chatgpt_model_combo.currentData() or "gpt-4o-mini"
        gemini_model = self.gemini_model_combo.currentData() or "gemini-2.0-flash-exp"

        try:
            max_retries = int(self.max_retries_input.text().strip() or "3")
        except ValueError:
            max_retries = 3

        # Validation
        errors = []
        if not chatgpt_key:
            errors.append("- ChatGPT API Key không được để trống")
        if not gemini_key:
            errors.append("- Gemini API Key không được để trống")
        if not output_dir:
            errors.append("- Thư mục lưu ảnh không được để trống")

        if errors:
            QMessageBox.warning(
                self,
                "Lỗi",
                "Vui lòng sửa các lỗi sau:\n\n" + "\n".join(errors)
            )
            return

        # Update config
        config_service.update(
            chatgpt_api_key=chatgpt_key,
            gemini_api_key=gemini_key,
            google_bearer_token=google_token,
            output_directory=output_dir,
            chatgpt_model=chatgpt_model,
            gemini_model=gemini_model,
            max_retries=max_retries
        )

        # Save to file
        if config_service.save():
            # Reset clients để sử dụng key mới
            chatgpt_service.reset_client()
            gemini_service.reset()

            self.status_label.setText("Đã lưu cài đặt thành công!")
            self.status_label.setStyleSheet("color: green; font-style: italic;")

            self.settings_saved.emit()

            QMessageBox.information(
                self,
                "Thành công",
                "Cài đặt đã được lưu!"
            )
        else:
            self.status_label.setText("Lỗi khi lưu cài đặt!")
            self.status_label.setStyleSheet("color: red; font-style: italic;")

            QMessageBox.critical(
                self,
                "Lỗi",
                "Không thể lưu cài đặt. Vui lòng kiểm tra quyền ghi file."
            )

    def _reset_settings(self):
        """Reset về mặc định"""
        reply = QMessageBox.question(
            self,
            "Xác nhận",
            "Bạn có chắc muốn reset về cài đặt mặc định?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            config_service.reset()
            self._load_settings()
            self.status_label.setText("Đã reset về mặc định")

    def _browse_directory(self):
        """Mở dialog chọn thư mục"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục lưu ảnh",
            self.output_dir_input.text() or ""
        )

        if directory:
            self.output_dir_input.setText(directory)

    def _toggle_password(self, input_field: QLineEdit, button: QPushButton):
        """Toggle hiện/ẩn password"""
        if input_field.echoMode() == QLineEdit.Password:
            input_field.setEchoMode(QLineEdit.Normal)
            button.setText("Ẩn")
        else:
            input_field.setEchoMode(QLineEdit.Password)
            button.setText("Hiện")

    def _test_chatgpt(self):
        """Test kết nối ChatGPT"""
        api_key = self.chatgpt_key_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập ChatGPT API Key")
            return

        self.test_chatgpt_btn.setEnabled(False)
        self.test_chatgpt_btn.setText("...")

        try:
            # Tạm thời set key để test
            config_service.update(chatgpt_api_key=api_key)
            chatgpt_service.reset_client()

            result = chatgpt_service.test_connection()

            if result.success:
                QMessageBox.information(
                    self,
                    "Thành công",
                    "Kết nối ChatGPT API thành công!"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Lỗi",
                    f"Không thể kết nối:\n{result.error_message}"
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Lỗi khi test kết nối:\n{str(e)}"
            )

        finally:
            self.test_chatgpt_btn.setEnabled(True)
            self.test_chatgpt_btn.setText("Test")

    def _test_gemini(self):
        """Test kết nối Gemini"""
        api_key = self.gemini_key_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập Gemini API Key")
            return

        self.test_gemini_btn.setEnabled(False)
        self.test_gemini_btn.setText("...")

        try:
            gemini_service.reset()
            result = gemini_service.test_connection(api_key)

            if result.success:
                QMessageBox.information(
                    self,
                    "Thành công",
                    "Kết nối Gemini API thành công!"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Lỗi",
                    f"Không thể kết nối:\n{result.error_message}"
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Lỗi khi test kết nối:\n{str(e)}"
            )

        finally:
            self.test_gemini_btn.setEnabled(True)
            self.test_gemini_btn.setText("Test")
