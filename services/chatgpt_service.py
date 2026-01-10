"""
ChatGPT Service - Gọi API ChatGPT để tạo image prompts
"""

import time
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

from openai import OpenAI, APIError, RateLimitError, APIConnectionError

from services.config_service import config_service


class ChatGPTError(Exception):
    """Custom exception cho ChatGPT errors"""
    pass


class ErrorType(Enum):
    """Loại lỗi"""
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    AUTH = "authentication"
    INVALID_REQUEST = "invalid_request"
    UNKNOWN = "unknown"


@dataclass
class ChatGPTResponse:
    """Response từ ChatGPT API"""
    success: bool
    content: str
    error_message: str = ""
    error_type: Optional[ErrorType] = None
    tokens_used: int = 0


class ChatGPTService:
    """
    Service gọi ChatGPT API để generate image prompts
    - Hỗ trợ retry khi gặp lỗi
    - Có callback để cập nhật trạng thái
    """

    # System prompt mặc định để ChatGPT tạo image prompts
    DEFAULT_SYSTEM_PROMPT = """You are an expert image prompt engineer. Your task is to create detailed, creative image prompts for AI image generation based on the user's input.

Rules:
1. Create clear, descriptive prompts that work well with image generation AI
2. Include details about: subject, style, lighting, mood, colors, composition
3. Keep each prompt under 200 words
4. Format your response EXACTLY as follows:

Image Prompt 1: [Your detailed prompt here]
Image Prompt 2: [Your detailed prompt here]
Image Prompt 3: [Your detailed prompt here]

If the user asks for a specific number of prompts, create that many.
If not specified, create 3 diverse variations.
Do NOT include any other text, explanations, or formatting - only the prompts in the exact format shown above."""

    def __init__(self):
        """Khởi tạo service"""
        self._client: Optional[OpenAI] = None
        self._status_callback: Optional[Callable[[str], None]] = None

    def _get_client(self) -> OpenAI:
        """
        Lấy hoặc tạo OpenAI client

        Returns:
            OpenAI client instance
        """
        if self._client is None:
            api_key = config_service.config.chatgpt_api_key
            if not api_key:
                raise ChatGPTError("ChatGPT API Key chưa được cấu hình")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def reset_client(self) -> None:
        """Reset client (dùng khi thay đổi API key)"""
        self._client = None

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """
        Set callback để cập nhật trạng thái

        Args:
            callback: Hàm callback nhận message string
        """
        self._status_callback = callback

    def _log_status(self, message: str) -> None:
        """Log trạng thái"""
        print(f"[ChatGPT] {message}")
        if self._status_callback:
            self._status_callback(message)

    def generate_image_prompts(
        self,
        user_prompt: str,
        num_prompts: int = 3,
        custom_system_prompt: Optional[str] = None
    ) -> ChatGPTResponse:
        """
        Gọi ChatGPT để tạo image prompts

        Args:
            user_prompt: Prompt gốc từ user
            num_prompts: Số lượng image prompts cần tạo
            custom_system_prompt: System prompt tùy chỉnh (optional)

        Returns:
            ChatGPTResponse chứa kết quả
        """
        # Validate input
        if not user_prompt or not user_prompt.strip():
            return ChatGPTResponse(
                success=False,
                content="",
                error_message="Prompt không được để trống",
                error_type=ErrorType.INVALID_REQUEST
            )

        # Lấy config
        config = config_service.config
        max_retries = config.max_retries
        retry_delay = config.retry_delay

        # Chuẩn bị system prompt
        system_prompt = custom_system_prompt or self.DEFAULT_SYSTEM_PROMPT

        # Thêm yêu cầu số lượng vào user prompt
        enhanced_prompt = f"{user_prompt}\n\nPlease create exactly {num_prompts} different image prompts."

        # Retry loop
        last_error = None
        for attempt in range(max_retries):
            try:
                self._log_status(f"Đang gọi ChatGPT API (lần {attempt + 1}/{max_retries})...")

                client = self._get_client()
                response = client.chat.completions.create(
                    model=config.chatgpt_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": enhanced_prompt}
                    ],
                    max_tokens=config.chatgpt_max_tokens,
                    temperature=0.8,  # Tăng creativity
                )

                # Extract content
                content = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0

                self._log_status(f"ChatGPT trả về thành công ({tokens_used} tokens)")

                return ChatGPTResponse(
                    success=True,
                    content=content,
                    tokens_used=tokens_used
                )

            except RateLimitError as e:
                last_error = e
                self._log_status(f"Rate limit exceeded, chờ {retry_delay}s...")
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff

            except APIConnectionError as e:
                last_error = e
                self._log_status(f"Lỗi kết nối, thử lại sau {retry_delay}s...")
                time.sleep(retry_delay)

            except APIError as e:
                last_error = e
                if "authentication" in str(e).lower() or "api key" in str(e).lower():
                    return ChatGPTResponse(
                        success=False,
                        content="",
                        error_message=f"Lỗi xác thực: API Key không hợp lệ",
                        error_type=ErrorType.AUTH
                    )
                self._log_status(f"API Error: {e}")
                time.sleep(retry_delay)

            except Exception as e:
                last_error = e
                self._log_status(f"Lỗi không xác định: {e}")
                break

        # Hết retry
        error_msg = str(last_error) if last_error else "Lỗi không xác định"
        return ChatGPTResponse(
            success=False,
            content="",
            error_message=f"Không thể kết nối ChatGPT sau {max_retries} lần thử: {error_msg}",
            error_type=ErrorType.NETWORK
        )

    def test_connection(self) -> ChatGPTResponse:
        """
        Test kết nối với ChatGPT API

        Returns:
            ChatGPTResponse cho biết kết quả test
        """
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return ChatGPTResponse(
                success=True,
                content="Kết nối thành công!"
            )
        except Exception as e:
            return ChatGPTResponse(
                success=False,
                content="",
                error_message=str(e)
            )


# Singleton instance
chatgpt_service = ChatGPTService()
