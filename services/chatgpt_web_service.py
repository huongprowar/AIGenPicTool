"""
ChatGPT Web Service - Tương tác với ChatGPT qua trình duyệt web
Thay thế cho API khi không có API key hợp lệ
"""

import time
import threading
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

try:
    import undetected_chromedriver as uc
    HAS_UNDETECTED = True
except ImportError:
    HAS_UNDETECTED = False

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class ChatGPTWebError(Exception):
    """Custom exception cho ChatGPT Web errors"""
    pass


class WebErrorType(Enum):
    """Loại lỗi"""
    BROWSER_NOT_FOUND = "browser_not_found"
    LOGIN_REQUIRED = "login_required"
    TIMEOUT = "timeout"
    ELEMENT_NOT_FOUND = "element_not_found"
    UNKNOWN = "unknown"


@dataclass
class ChatGPTWebResponse:
    """Response từ ChatGPT Web"""
    success: bool
    content: str
    error_message: str = ""
    error_type: Optional[WebErrorType] = None


class ChatGPTWebService:
    """
    Service tương tác với ChatGPT qua trình duyệt web
    - Mở trình duyệt Chrome
    - Điều hướng đến ChatGPT
    - Gửi prompt và lấy response
    """

    CHATGPT_URL = "https://chat.openai.com/"

    # Selectors cho ChatGPT web interface (có thể cần cập nhật nếu UI thay đổi)
    SELECTORS = {
        # Textarea để nhập prompt
        "prompt_textarea": "textarea[data-id='root']",
        "prompt_textarea_alt": "#prompt-textarea",
        "prompt_textarea_alt2": "textarea",

        # Nút gửi
        "send_button": "button[data-testid='send-button']",
        "send_button_alt": "button[data-testid='fruitjuice-send-button']",

        # Response container
        "response_container": "div[data-message-author-role='assistant']",
        "response_text": "div.markdown",

        # Login check
        "login_button": "button[data-testid='login-button']",
        "chat_input_form": "form",
    }

    def __init__(self):
        """Khởi tạo service"""
        self._driver: Optional[webdriver.Chrome] = None
        self._status_callback: Optional[Callable[[str], None]] = None
        self._is_logged_in: bool = False
        self._lock = threading.Lock()

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback để cập nhật trạng thái"""
        self._status_callback = callback

    def _log_status(self, message: str) -> None:
        """Log trạng thái"""
        print(f"[ChatGPT Web] {message}")
        if self._status_callback:
            self._status_callback(message)

    def _create_driver(self) -> webdriver.Chrome:
        """Tạo Chrome driver"""
        self._log_status("Đang khởi tạo trình duyệt Chrome...")

        if HAS_UNDETECTED:
            # Sử dụng undetected-chromedriver để tránh bị phát hiện
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")

            driver = uc.Chrome(options=options)
        else:
            # Fallback to regular selenium
            options = Options()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=options)

            # Thêm script để ẩn automation
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })

        return driver

    def _get_driver(self) -> webdriver.Chrome:
        """Lấy hoặc tạo driver"""
        if self._driver is None:
            self._driver = self._create_driver()
        return self._driver

    def _find_element_with_fallback(self, driver, selectors: list, timeout: int = 10):
        """Tìm element với nhiều selector fallback"""
        for selector in selectors:
            try:
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return element
            except TimeoutException:
                continue
        return None

    def _wait_for_response_complete(self, driver, timeout: int = 120) -> str:
        """
        Đợi ChatGPT trả lời xong và lấy nội dung

        Args:
            driver: WebDriver instance
            timeout: Thời gian tối đa chờ (giây)

        Returns:
            Nội dung response
        """
        self._log_status("Đang chờ ChatGPT trả lời...")

        start_time = time.time()
        last_response = ""
        stable_count = 0

        while time.time() - start_time < timeout:
            try:
                # Tìm tất cả response từ assistant
                responses = driver.find_elements(By.CSS_SELECTOR, self.SELECTORS["response_container"])

                if responses:
                    # Lấy response cuối cùng
                    last_response_element = responses[-1]

                    # Tìm nội dung markdown trong response
                    try:
                        markdown_elements = last_response_element.find_elements(By.CSS_SELECTOR, self.SELECTORS["response_text"])
                        if markdown_elements:
                            current_response = markdown_elements[-1].text
                        else:
                            current_response = last_response_element.text
                    except:
                        current_response = last_response_element.text

                    # Kiểm tra xem response đã ổn định chưa (không thay đổi trong 2 giây)
                    if current_response == last_response and current_response.strip():
                        stable_count += 1
                        if stable_count >= 4:  # 4 lần check * 0.5s = 2 giây ổn định
                            self._log_status("ChatGPT đã trả lời xong!")
                            return current_response
                    else:
                        stable_count = 0
                        last_response = current_response

                # Kiểm tra xem có đang loading không
                loading_indicators = driver.find_elements(By.CSS_SELECTOR, "[class*='result-streaming']")
                if not loading_indicators and last_response.strip():
                    time.sleep(1)  # Chờ thêm một chút
                    # Double check
                    loading_indicators = driver.find_elements(By.CSS_SELECTOR, "[class*='result-streaming']")
                    if not loading_indicators:
                        return last_response

            except Exception as e:
                self._log_status(f"Lỗi khi đọc response: {e}")

            time.sleep(0.5)

        # Timeout - trả về response hiện tại nếu có
        if last_response.strip():
            self._log_status("Timeout nhưng đã có response, sử dụng response hiện tại")
            return last_response

        raise TimeoutException("Không nhận được response từ ChatGPT")

    def _send_prompt(self, driver, prompt: str) -> bool:
        """
        Gửi prompt vào ChatGPT

        Args:
            driver: WebDriver instance
            prompt: Nội dung prompt

        Returns:
            True nếu gửi thành công
        """
        self._log_status("Đang tìm ô nhập prompt...")

        # Tìm textarea
        textarea = self._find_element_with_fallback(
            driver,
            [
                self.SELECTORS["prompt_textarea"],
                self.SELECTORS["prompt_textarea_alt"],
                self.SELECTORS["prompt_textarea_alt2"]
            ],
            timeout=30
        )

        if not textarea:
            raise ChatGPTWebError("Không tìm thấy ô nhập prompt")

        self._log_status("Đang nhập prompt...")

        # Clear và nhập prompt
        textarea.clear()

        # Nhập từng dòng để tránh lỗi với prompt dài
        lines = prompt.split('\n')
        for i, line in enumerate(lines):
            textarea.send_keys(line)
            if i < len(lines) - 1:
                textarea.send_keys(Keys.SHIFT + Keys.ENTER)

        time.sleep(0.5)

        # Tìm và click nút gửi
        self._log_status("Đang gửi prompt...")

        send_button = self._find_element_with_fallback(
            driver,
            [
                self.SELECTORS["send_button"],
                self.SELECTORS["send_button_alt"]
            ],
            timeout=10
        )

        if send_button:
            try:
                send_button.click()
            except:
                # Fallback: dùng Enter
                textarea.send_keys(Keys.ENTER)
        else:
            # Dùng Enter để gửi
            textarea.send_keys(Keys.ENTER)

        return True

    def open_browser_and_wait_login(self) -> ChatGPTWebResponse:
        """
        Mở trình duyệt và chờ user đăng nhập

        Returns:
            ChatGPTWebResponse
        """
        try:
            with self._lock:
                driver = self._get_driver()

                self._log_status("Đang mở ChatGPT...")
                driver.get(self.CHATGPT_URL)

                self._log_status("Vui lòng đăng nhập vào ChatGPT nếu cần...")
                self._log_status("Sau khi đăng nhập xong, hãy quay lại ứng dụng")

                # Chờ đến khi có thể nhập prompt (nghĩa là đã đăng nhập)
                max_wait = 300  # 5 phút
                start_time = time.time()

                while time.time() - start_time < max_wait:
                    try:
                        # Kiểm tra xem đã có thể nhập prompt chưa
                        textarea = self._find_element_with_fallback(
                            driver,
                            [
                                self.SELECTORS["prompt_textarea"],
                                self.SELECTORS["prompt_textarea_alt"],
                                self.SELECTORS["prompt_textarea_alt2"]
                            ],
                            timeout=5
                        )

                        if textarea and textarea.is_enabled():
                            self._is_logged_in = True
                            self._log_status("Đã sẵn sàng! Có thể bắt đầu gửi prompt.")
                            return ChatGPTWebResponse(
                                success=True,
                                content="Đã đăng nhập và sẵn sàng"
                            )
                    except:
                        pass

                    time.sleep(2)

                return ChatGPTWebResponse(
                    success=False,
                    content="",
                    error_message="Timeout chờ đăng nhập",
                    error_type=WebErrorType.LOGIN_REQUIRED
                )

        except Exception as e:
            return ChatGPTWebResponse(
                success=False,
                content="",
                error_message=str(e),
                error_type=WebErrorType.UNKNOWN
            )

    def generate_image_prompts(
        self,
        user_prompt: str,
        num_prompts: int = 3,
        custom_system_prompt: Optional[str] = None
    ) -> ChatGPTWebResponse:
        """
        Gửi prompt đến ChatGPT web và lấy response

        Args:
            user_prompt: Prompt từ user
            num_prompts: Số lượng image prompts cần tạo
            custom_system_prompt: System prompt tùy chỉnh (sẽ được thêm vào prompt)

        Returns:
            ChatGPTWebResponse chứa kết quả
        """
        if not user_prompt or not user_prompt.strip():
            return ChatGPTWebResponse(
                success=False,
                content="",
                error_message="Prompt không được để trống",
                error_type=WebErrorType.UNKNOWN
            )

        try:
            with self._lock:
                driver = self._get_driver()

                # Nếu chưa mở ChatGPT, mở nó
                if "chat.openai.com" not in driver.current_url:
                    self._log_status("Đang mở ChatGPT...")
                    driver.get(self.CHATGPT_URL)
                    time.sleep(3)

                # Tạo prompt hoàn chỉnh
                full_prompt = self._build_full_prompt(user_prompt, num_prompts, custom_system_prompt)

                # Gửi prompt
                self._send_prompt(driver, full_prompt)

                # Đợi và lấy response
                response_text = self._wait_for_response_complete(driver)

                return ChatGPTWebResponse(
                    success=True,
                    content=response_text
                )

        except TimeoutException as e:
            return ChatGPTWebResponse(
                success=False,
                content="",
                error_message="Timeout chờ response từ ChatGPT",
                error_type=WebErrorType.TIMEOUT
            )
        except ChatGPTWebError as e:
            return ChatGPTWebResponse(
                success=False,
                content="",
                error_message=str(e),
                error_type=WebErrorType.ELEMENT_NOT_FOUND
            )
        except Exception as e:
            return ChatGPTWebResponse(
                success=False,
                content="",
                error_message=f"Lỗi: {str(e)}",
                error_type=WebErrorType.UNKNOWN
            )

    def _build_full_prompt(
        self,
        user_prompt: str,
        num_prompts: int,
        custom_system_prompt: Optional[str] = None
    ) -> str:
        """Tạo prompt hoàn chỉnh để gửi cho ChatGPT"""

        system_instruction = custom_system_prompt or """You are an expert image prompt engineer. Create detailed, creative image prompts for AI image generation.

Rules:
1. Create clear, descriptive prompts that work well with image generation AI
2. Include details about: subject, style, lighting, mood, colors, composition
3. Keep each prompt under 200 words
4. Format your response EXACTLY as:

Image Prompt 1: [Your detailed prompt]
Image Prompt 2: [Your detailed prompt]
...

Only output the prompts, no other text."""

        full_prompt = f"""{system_instruction}

User request: {user_prompt}"""



        return full_prompt

    def start_new_chat(self) -> bool:
        """Bắt đầu chat mới"""
        try:
            with self._lock:
                if self._driver:
                    self._log_status("Đang tạo chat mới...")
                    self._driver.get(self.CHATGPT_URL)
                    time.sleep(2)
                    return True
        except Exception as e:
            self._log_status(f"Lỗi khi tạo chat mới: {e}")
        return False

    def close_browser(self) -> None:
        """Đóng trình duyệt"""
        with self._lock:
            if self._driver:
                try:
                    self._driver.quit()
                except:
                    pass
                self._driver = None
                self._is_logged_in = False
                self._log_status("Đã đóng trình duyệt")

    def is_browser_open(self) -> bool:
        """Kiểm tra trình duyệt có đang mở không"""
        if self._driver is None:
            return False
        try:
            # Thử lấy title để kiểm tra driver còn hoạt động
            _ = self._driver.title
            return True
        except:
            self._driver = None
            return False

    def is_logged_in(self) -> bool:
        """Kiểm tra đã đăng nhập chưa"""
        return self._is_logged_in and self.is_browser_open()


# Singleton instance
chatgpt_web_service = ChatGPTWebService()
