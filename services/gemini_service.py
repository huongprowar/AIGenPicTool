"""
Gemini Image Service - Gọi API Gemini để tạo ảnh từ prompt
"""

import time
import base64
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core import exceptions as google_exceptions

from services.config_service import config_service


class GeminiError(Exception):
    """Custom exception cho Gemini errors"""
    pass


class ImageStatus(Enum):
    """Trạng thái của việc tạo ảnh"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class ImageResult:
    """Kết quả tạo ảnh"""
    success: bool
    prompt: str
    image_data: Optional[bytes] = None  # Raw image bytes
    image_path: Optional[str] = None    # Đường dẫn nếu đã lưu
    error_message: str = ""
    status: ImageStatus = ImageStatus.PENDING
    mime_type: str = "image/png"


class GeminiImageService:
    """
    Service gọi Gemini API để tạo ảnh
    - Sử dụng Gemini 2.0 Flash với image generation capability
    - Hỗ trợ retry khi gặp lỗi
    - Có callback để cập nhật trạng thái
    """

    def __init__(self):
        """Khởi tạo service"""
        self._configured = False
        self._model = None
        self._current_model_name = None
        self._status_callback: Optional[Callable[[str], None]] = None

    def _configure(self, api_key: str) -> None:
        """
        Cấu hình Gemini API

        Args:
            api_key: Gemini API key
        """
        if not api_key:
            raise GeminiError("Gemini API Key chưa được cấu hình")

        genai.configure(api_key=api_key)
        self._configured = True

    def _get_model(self, api_key: str):
        """
        Lấy hoặc tạo Gemini model

        Args:
            api_key: Gemini API key

        Returns:
            Gemini model instance
        """
        if not self._configured:
            self._configure(api_key)

        # Lấy model từ config
        model_name = config_service.config.gemini_model or "gemini-2.0-flash-exp"

        if self._model is None or self._current_model_name != model_name:
            # Sử dụng model từ config
            self._model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=GenerationConfig(
                    temperature=1.0,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                )
            )
            self._current_model_name = model_name

        return self._model

    def reset(self) -> None:
        """Reset service (dùng khi thay đổi API key hoặc model)"""
        self._configured = False
        self._model = None
        self._current_model_name = None

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """
        Set callback để cập nhật trạng thái

        Args:
            callback: Hàm callback nhận message string
        """
        self._status_callback = callback

    def _log_status(self, message: str) -> None:
        """Log trạng thái"""
        print(f"[Gemini] {message}")
        if self._status_callback:
            self._status_callback(message)

    def generate_image(
        self,
        prompt: str,
        api_key: str,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        image_size: tuple = (1024, 1024)
    ) -> ImageResult:
        """
        Tạo ảnh từ prompt sử dụng Gemini API

        Args:
            prompt: Image prompt
            api_key: Gemini API key
            max_retries: Số lần retry tối đa
            retry_delay: Thời gian chờ giữa các lần retry (giây)
            image_size: Tuple (width, height) kích thước ảnh mong muốn

        Returns:
            ImageResult chứa kết quả
        """
        # Validate input
        if not prompt or not prompt.strip():
            return ImageResult(
                success=False,
                prompt=prompt,
                error_message="Prompt không được để trống",
                status=ImageStatus.ERROR
            )

        if not api_key:
            return ImageResult(
                success=False,
                prompt=prompt,
                error_message="Gemini API Key chưa được cấu hình",
                status=ImageStatus.ERROR
            )

        last_error = None

        for attempt in range(max_retries):
            try:
                self._log_status(f"Đang tạo ảnh (lần {attempt + 1}/{max_retries})...")

                model = self._get_model(api_key)

                # Xác định aspect ratio từ kích thước
                width, height = image_size
                if width == height:
                    aspect_desc = "square"
                elif width > height:
                    aspect_desc = "landscape (horizontal)"
                else:
                    aspect_desc = "portrait (vertical)"

                # Tạo prompt yêu cầu generate image với thông tin kích thước
                generation_prompt = f"""Generate an image based on this description:

{prompt}

Image specifications:
- Target dimensions: {width}x{height} pixels
- Aspect ratio: {aspect_desc}
- Quality: high-resolution, detailed

Please create a high-quality, detailed image that matches this description and specifications."""

                # Gọi API với response_modalities để yêu cầu image
                response = model.generate_content(
                    generation_prompt,
                    generation_config=GenerationConfig(
                        temperature=1.0,
                        response_modalities=["TEXT", "IMAGE"],
                    )
                )

                # Xử lý response
                if response.candidates:
                    for candidate in response.candidates:
                        if candidate.content and candidate.content.parts:
                            for part in candidate.content.parts:
                                # Kiểm tra nếu part có inline_data (image)
                                if hasattr(part, 'inline_data') and part.inline_data:
                                    image_data = part.inline_data.data
                                    mime_type = part.inline_data.mime_type or "image/png"

                                    self._log_status("Tạo ảnh thành công!")

                                    return ImageResult(
                                        success=True,
                                        prompt=prompt,
                                        image_data=image_data,
                                        mime_type=mime_type,
                                        status=ImageStatus.SUCCESS
                                    )

                # Không tìm thấy image trong response
                self._log_status("Response không chứa ảnh, thử lại...")
                time.sleep(retry_delay)

            except google_exceptions.ResourceExhausted as e:
                last_error = e
                self._log_status(f"Quota exceeded, chờ {retry_delay * (attempt + 1)}s...")
                time.sleep(retry_delay * (attempt + 1))

            except google_exceptions.InvalidArgument as e:
                last_error = e
                error_msg = str(e)
                if "API key" in error_msg or "authentication" in error_msg.lower():
                    return ImageResult(
                        success=False,
                        prompt=prompt,
                        error_message="API Key không hợp lệ",
                        status=ImageStatus.ERROR
                    )
                self._log_status(f"Invalid argument: {e}")
                time.sleep(retry_delay)

            except google_exceptions.GoogleAPIError as e:
                last_error = e
                self._log_status(f"API Error: {e}")
                time.sleep(retry_delay)

            except Exception as e:
                last_error = e
                self._log_status(f"Lỗi không xác định: {e}")
                time.sleep(retry_delay)

        # Hết retry
        error_msg = str(last_error) if last_error else "Không thể tạo ảnh"
        return ImageResult(
            success=False,
            prompt=prompt,
            error_message=f"Không thể tạo ảnh sau {max_retries} lần thử: {error_msg}",
            status=ImageStatus.ERROR
        )

    def test_connection(self, api_key: str) -> ImageResult:
        """
        Test kết nối với Gemini API

        Args:
            api_key: Gemini API key

        Returns:
            ImageResult cho biết kết quả test
        """
        try:
            self._configure(api_key)
            # Sử dụng model từ config
            model_name = config_service.config.gemini_model or "gemini-2.0-flash-exp"
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Hello")

            return ImageResult(
                success=True,
                prompt="test",
                status=ImageStatus.SUCCESS
            )
        except Exception as e:
            return ImageResult(
                success=False,
                prompt="test",
                error_message=str(e),
                status=ImageStatus.ERROR
            )


# Singleton instance
gemini_service = GeminiImageService()
