"""
Config Service - Quản lý cấu hình ứng dụng
Lưu trữ và load settings từ file JSON
"""

import json
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class AppConfig:
    """Data class chứa cấu hình ứng dụng"""
    chatgpt_api_key: str = ""
    gemini_api_key: str = ""
    output_directory: str = ""

    # Cấu hình ChatGPT
    chatgpt_model: str = "gpt-4o-mini"
    chatgpt_max_tokens: int = 2000

    # Cấu hình Gemini
    gemini_model: str = "gemini-2.0-flash-exp"

    # Cấu hình retry
    max_retries: int = 3
    retry_delay: float = 2.0


class ConfigService:
    """
    Service quản lý cấu hình ứng dụng
    - Load/Save config từ file JSON
    - Validate config
    - Singleton pattern
    """

    _instance: Optional['ConfigService'] = None
    _config: Optional[AppConfig] = None

    # Tên file config mặc định
    CONFIG_FILENAME = "config.json"

    def __new__(cls):
        """Singleton pattern - chỉ tạo 1 instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Khởi tạo config service"""
        if self._config is None:
            self._config = AppConfig()
            self._config_path = self._get_config_path()
            self.load()

    def _get_config_path(self) -> Path:
        """
        Lấy đường dẫn file config
        Ưu tiên thư mục hiện tại, fallback về user home
        """
        # Thử thư mục hiện tại trước
        current_dir = Path.cwd() / self.CONFIG_FILENAME
        if current_dir.parent.exists():
            return current_dir

        # Fallback về thư mục user
        user_dir = Path.home() / ".ai_image_generator"
        user_dir.mkdir(exist_ok=True)
        return user_dir / self.CONFIG_FILENAME

    @property
    def config(self) -> AppConfig:
        """Getter cho config"""
        return self._config

    def load(self) -> bool:
        """
        Load config từ file JSON
        Returns: True nếu load thành công, False nếu không
        """
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Cập nhật config với dữ liệu từ file
                for key, value in data.items():
                    if hasattr(self._config, key):
                        setattr(self._config, key, value)

                return True
            return False

        except (json.JSONDecodeError, IOError) as e:
            print(f"[ConfigService] Lỗi load config: {e}")
            return False

    def save(self) -> bool:
        """
        Lưu config ra file JSON
        Returns: True nếu lưu thành công, False nếu không
        """
        try:
            # Đảm bảo thư mục cha tồn tại
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self._config), f, indent=2, ensure_ascii=False)

            return True

        except IOError as e:
            print(f"[ConfigService] Lỗi save config: {e}")
            return False

    def update(self, **kwargs) -> None:
        """
        Cập nhật config với các giá trị mới
        Args:
            **kwargs: Các key-value cần cập nhật
        """
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def validate(self) -> dict:
        """
        Validate config, kiểm tra các trường bắt buộc
        Returns: Dict chứa các lỗi (rỗng nếu hợp lệ)
        """
        errors = {}

        if not self._config.chatgpt_api_key:
            errors['chatgpt_api_key'] = "ChatGPT API Key không được để trống"

        if not self._config.gemini_api_key:
            errors['gemini_api_key'] = "Gemini API Key không được để trống"

        if not self._config.output_directory:
            errors['output_directory'] = "Thư mục lưu ảnh không được để trống"
        elif not Path(self._config.output_directory).exists():
            errors['output_directory'] = "Thư mục lưu ảnh không tồn tại"

        return errors

    def is_valid(self) -> bool:
        """Kiểm tra config có hợp lệ không"""
        return len(self.validate()) == 0

    def get_output_path(self) -> Path:
        """Lấy đường dẫn thư mục output"""
        return Path(self._config.output_directory)

    def reset(self) -> None:
        """Reset config về mặc định"""
        self._config = AppConfig()


# Singleton instance để sử dụng global
config_service = ConfigService()
