"""
Image Item Widget - Widget hiển thị mỗi ảnh trong danh sách
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QFrame, QSizePolicy,
    QDialog, QTextEdit, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage

import io
from typing import Optional
from enum import Enum

from services.gemini_service import ImageStatus


class EditPromptDialog(QDialog):
    """Dialog để chỉnh sửa prompt"""

    def __init__(self, current_prompt: str, index: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Chỉnh sửa Prompt #{index}")
        self.setMinimumSize(500, 300)
        self.resize(600, 350)

        layout = QVBoxLayout(self)

        # Label hướng dẫn
        label = QLabel("Chỉnh sửa prompt bên dưới:")
        label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(label)

        # Text edit cho prompt
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlainText(current_prompt)
        self.prompt_edit.setStyleSheet("""
            QTextEdit {
                font-size: 13px;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.prompt_edit)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        button_box.button(QDialogButtonBox.Save).setText("Lưu")
        button_box.button(QDialogButtonBox.Cancel).setText("Hủy")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_prompt(self) -> str:
        """Lấy prompt đã chỉnh sửa"""
        return self.prompt_edit.toPlainText().strip()


class ImageItemWidget(QWidget):
    """
    Widget hiển thị một ảnh trong danh sách kết quả
    - Thumbnail ảnh
    - Prompt text
    - Checkbox chọn
    - Nút xem ảnh
    - Nút tạo lại
    - Trạng thái
    """

    # Signals
    view_clicked = Signal(int)       # index
    regenerate_clicked = Signal(int)  # index
    edit_prompt_clicked = Signal(int, str)  # index, new_prompt
    selection_changed = Signal(int, bool)  # index, selected

    # Kích thước thumbnail
    THUMBNAIL_SIZE = 100

    def __init__(
        self,
        index: int,
        prompt: str,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self._index = index
        self._prompt = prompt
        self._status = ImageStatus.PENDING
        self._image_data: Optional[bytes] = None
        self._mime_type = "image/png"

        self._init_ui()
        self._update_status_display()

    def _init_ui(self):
        """Khởi tạo UI"""
        self.setObjectName("imageItem")
        self.setStyleSheet("""
            #imageItem {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
            }
            #imageItem:hover {
                background-color: #e8e8e8;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.checkbox)

        # Thumbnail container
        self.thumbnail_frame = QFrame()
        self.thumbnail_frame.setFixedSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE)
        self.thumbnail_frame.setStyleSheet("""
            QFrame {
                background-color: #e0e0e0;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)

        thumb_layout = QVBoxLayout(self.thumbnail_frame)
        thumb_layout.setContentsMargins(0, 0, 0, 0)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setFixedSize(self.THUMBNAIL_SIZE - 2, self.THUMBNAIL_SIZE - 2)
        self.thumbnail_label.setStyleSheet("border: none; background: transparent;")
        self.thumbnail_label.setText("...")
        thumb_layout.addWidget(self.thumbnail_label)

        layout.addWidget(self.thumbnail_frame)

        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)

        # Index label
        self.index_label = QLabel(f"Ảnh #{self._index}")
        self.index_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_layout.addWidget(self.index_label)

        # Prompt label (truncated)
        prompt_display = self._prompt[:80] + "..." if len(self._prompt) > 80 else self._prompt
        self.prompt_label = QLabel(prompt_display)
        self.prompt_label.setWordWrap(True)
        self.prompt_label.setStyleSheet("color: #666; font-size: 12px;")
        self.prompt_label.setMaximumWidth(300)
        info_layout.addWidget(self.prompt_label)

        # Status label
        self.status_label = QLabel("Đang chờ...")
        self.status_label.setStyleSheet("font-style: italic; color: #999;")
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()
        layout.addLayout(info_layout, 1)

        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(5)

        self.view_btn = QPushButton("Xem")
        self.view_btn.setFixedWidth(80)
        self.view_btn.setEnabled(False)
        self.view_btn.clicked.connect(lambda: self.view_clicked.emit(self._index))
        button_layout.addWidget(self.view_btn)

        self.regenerate_btn = QPushButton("Tạo lại")
        self.regenerate_btn.setFixedWidth(80)
        self.regenerate_btn.clicked.connect(lambda: self.regenerate_clicked.emit(self._index))
        button_layout.addWidget(self.regenerate_btn)

        self.edit_btn = QPushButton("Sửa prompt")
        self.edit_btn.setFixedWidth(80)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        button_layout.addWidget(self.edit_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _on_checkbox_changed(self, state):
        """Handler khi checkbox thay đổi"""
        self.selection_changed.emit(self._index, state == Qt.Checked)

    def _on_edit_clicked(self):
        """Handler khi bấm nút Sửa prompt"""
        dialog = EditPromptDialog(self._prompt, self._index, self)
        if dialog.exec() == QDialog.Accepted:
            new_prompt = dialog.get_prompt()
            if new_prompt and new_prompt != self._prompt:
                # Cập nhật prompt
                self.set_prompt(new_prompt)
                # Emit signal để tạo lại ảnh với prompt mới
                self.edit_prompt_clicked.emit(self._index, new_prompt)

    def set_prompt(self, new_prompt: str):
        """Cập nhật prompt mới"""
        self._prompt = new_prompt
        # Cập nhật hiển thị
        prompt_display = self._prompt[:80] + "..." if len(self._prompt) > 80 else self._prompt
        self.prompt_label.setText(prompt_display)

    def _update_status_display(self):
        """Cập nhật hiển thị trạng thái"""
        status_config = {
            ImageStatus.PENDING: ("Đang chờ...", "#999", "#f5f5f5"),
            ImageStatus.PROCESSING: ("Đang tạo ảnh...", "#ff9800", "#fff3e0"),
            ImageStatus.SUCCESS: ("Hoàn thành", "#4caf50", "#e8f5e9"),
            ImageStatus.ERROR: ("Lỗi", "#f44336", "#ffebee"),
        }

        text, color, bg_color = status_config.get(
            self._status,
            ("Unknown", "#999", "#f5f5f5")
        )

        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"font-style: italic; color: {color};")

        # Update background
        self.setStyleSheet(f"""
            #imageItem {{
                background-color: {bg_color};
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
            }}
        """)

    def set_status(self, status: ImageStatus, message: str = ""):
        """
        Cập nhật trạng thái

        Args:
            status: ImageStatus
            message: Message tùy chỉnh (optional)
        """
        self._status = status
        self._update_status_display()

        if message:
            self.status_label.setText(message)

    def set_image(self, image_data: bytes, mime_type: str = "image/png"):
        """
        Set ảnh đã tạo

        Args:
            image_data: Dữ liệu ảnh
            mime_type: MIME type
        """
        self._image_data = image_data
        self._mime_type = mime_type

        # Tạo thumbnail
        try:
            image = QImage()
            image.loadFromData(image_data)

            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                scaled = pixmap.scaled(
                    self.THUMBNAIL_SIZE - 4,
                    self.THUMBNAIL_SIZE - 4,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled)
                self.view_btn.setEnabled(True)
            else:
                self.thumbnail_label.setText("Lỗi")

        except Exception as e:
            self.thumbnail_label.setText("Lỗi")
            print(f"[ImageItem] Lỗi load thumbnail: {e}")

    def set_error(self, error_message: str):
        """
        Set trạng thái lỗi

        Args:
            error_message: Thông báo lỗi
        """
        self._status = ImageStatus.ERROR
        self._update_status_display()
        self.status_label.setText(f"Lỗi: {error_message[:50]}...")
        self.thumbnail_label.setText("X")
        self.thumbnail_label.setStyleSheet("color: red; font-size: 24px; font-weight: bold;")

    @property
    def index(self) -> int:
        """Lấy index"""
        return self._index

    @property
    def prompt(self) -> str:
        """Lấy prompt"""
        return self._prompt

    @property
    def status(self) -> ImageStatus:
        """Lấy status"""
        return self._status

    @property
    def image_data(self) -> Optional[bytes]:
        """Lấy image data"""
        return self._image_data

    @property
    def mime_type(self) -> str:
        """Lấy mime type"""
        return self._mime_type

    @property
    def is_selected(self) -> bool:
        """Kiểm tra có được chọn không"""
        return self.checkbox.isChecked()

    def get_full_image(self) -> Optional[QPixmap]:
        """Lấy ảnh full size"""
        if self._image_data:
            image = QImage()
            image.loadFromData(self._image_data)
            if not image.isNull():
                return QPixmap.fromImage(image)
        return None
