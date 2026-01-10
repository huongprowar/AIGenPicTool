#!/usr/bin/env python3
"""
AI Image Generator - Main Entry Point
=====================================

Ứng dụng desktop tạo ảnh AI sử dụng:
- ChatGPT để tạo image prompts
- Gemini để generate ảnh

Author: AI Image Generator Team
Version: 1.0.0
"""

import sys
import os

# Thêm thư mục hiện tại vào PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


def setup_high_dpi():
    """Cấu hình high DPI cho màn hình độ phân giải cao"""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


def create_app() -> QApplication:
    """Tạo và cấu hình QApplication"""
    app = QApplication(sys.argv)

    # App metadata
    app.setApplicationName("AI Image Generator")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("AITools")

    # Style
    app.setStyle("Fusion")

    # Font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Global stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #fafafa;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #ddd;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QLineEdit, QTextEdit {
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 8px;
            background: white;
        }
        QLineEdit:focus, QTextEdit:focus {
            border-color: #2196F3;
        }
        QPushButton {
            padding: 8px 16px;
            border-radius: 4px;
            border: 1px solid #ccc;
            background: #f5f5f5;
        }
        QPushButton:hover {
            background: #e0e0e0;
        }
        QPushButton:pressed {
            background: #d0d0d0;
        }
        QScrollArea {
            border: none;
        }
        QProgressBar {
            border: 1px solid #ccc;
            border-radius: 4px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #2196F3;
            border-radius: 3px;
        }
    """)

    return app


def main():
    """Main function"""
    print("=" * 50)
    print("  AI Image Generator v1.0.0")
    print("=" * 50)
    print()

    # Setup high DPI before creating QApplication
    setup_high_dpi()

    # Create app
    app = create_app()

    # Import here to avoid circular imports
    from ui.main_window import MainWindow

    # Create and show main window
    window = MainWindow()
    window.show()

    print("Application started successfully!")
    print("Close the window to exit.")
    print()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
