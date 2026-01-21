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
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from utils.browser_utils import (
    BrowserType, get_default_browser, find_coccoc_path, get_browser_display_name
)


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
    - Mở trình duyệt Chrome/Firefox/Edge/Cốc Cốc
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

        # Indicators khi ChatGPT đang trả lời
        "stop_button": "button[data-testid='stop-button']",
        "stop_button_alt": "button[aria-label='Stop generating']",
        "streaming_indicator": "[class*='result-streaming']",
        "streaming_indicator_alt": "[class*='streaming']",
        "typing_indicator": "[class*='typing']",
        "thinking_indicator": "[class*='thinking']",
    }

    def __init__(self):
        """Khởi tạo service"""
        self._driver = None
        self._status_callback: Optional[Callable[[str], None]] = None
        self._is_logged_in: bool = False
        self._lock = threading.Lock()
        self._current_browser: BrowserType = BrowserType.CHROME
        self._browser_name: str = "Chrome"

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback để cập nhật trạng thái"""
        self._status_callback = callback

    def _log_status(self, message: str) -> None:
        """Log trạng thái"""
        print(f"[ChatGPT Web] {message}")
        if self._status_callback:
            self._status_callback(message)

    def _detect_default_browser(self) -> None:
        """Phát hiện và lưu trình duyệt mặc định"""
        browser_type, browser_name = get_default_browser()
        self._current_browser = browser_type
        self._browser_name = browser_name
        self._log_status(f"Phát hiện trình duyệt mặc định: {browser_name}")

    def get_browser_name(self) -> str:
        """Lấy tên trình duyệt hiện tại"""
        return self._browser_name

    def _create_chrome_driver(self, use_undetected: bool = True):
        """Tạo Chrome driver"""
        self._log_status("Đang khởi tạo trình duyệt Chrome...")

        if use_undetected and HAS_UNDETECTED:
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            return uc.Chrome(options=options)
        else:
            options = ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=options)

            # Thêm script để ẩn automation
            try:
                driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': '''
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        })
                    '''
                })
            except:
                pass

            return driver

    def _create_firefox_driver(self):
        """Tạo Firefox driver"""
        self._log_status("Đang khởi tạo trình duyệt Firefox...")

        options = FirefoxOptions()
        options.add_argument("--start-maximized")
        return webdriver.Firefox(options=options)

    def _create_edge_driver(self):
        """Tạo Edge driver"""
        self._log_status("Đang khởi tạo trình duyệt Edge...")

        options = EdgeOptions()
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        return webdriver.Edge(options=options)

    def _create_coccoc_driver(self):
        """Tạo Cốc Cốc driver"""
        self._log_status("Đang khởi tạo trình duyệt Cốc Cốc...")

        coccoc_path = find_coccoc_path()

        if not coccoc_path:
            raise ChatGPTWebError(
                "Không tìm thấy Cốc Cốc!\n"
                "Sẽ sử dụng Chrome thay thế."
            )

        self._log_status(f"Tìm thấy Cốc Cốc tại: {coccoc_path}")

        options = ChromeOptions()
        options.binary_location = coccoc_path
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        return webdriver.Chrome(options=options)

    def _create_driver(self):
        """Tạo driver dựa trên trình duyệt mặc định của hệ thống"""
        # Phát hiện trình duyệt mặc định
        self._detect_default_browser()

        browser_type = self._current_browser

        try:
            if browser_type == BrowserType.CHROME_UNDETECTED:
                return self._create_chrome_driver(use_undetected=True)
            elif browser_type == BrowserType.CHROME:
                # Thử dùng undetected trước nếu có
                if HAS_UNDETECTED:
                    return self._create_chrome_driver(use_undetected=True)
                return self._create_chrome_driver(use_undetected=False)
            elif browser_type == BrowserType.FIREFOX:
                return self._create_firefox_driver()
            elif browser_type == BrowserType.EDGE:
                return self._create_edge_driver()
            elif browser_type == BrowserType.COCCOC:
                return self._create_coccoc_driver()
            else:
                # Fallback to Chrome
                self._log_status(f"Browser không hỗ trợ ({browser_type}), sử dụng Chrome")
                return self._create_chrome_driver(use_undetected=HAS_UNDETECTED)
        except Exception as e:
            self._log_status(f"Lỗi tạo {self._browser_name}: {e}")
            self._log_status("Thử fallback sang Chrome...")
            return self._create_chrome_driver(use_undetected=HAS_UNDETECTED)

    def _get_driver(self):
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

    def _is_chatgpt_still_generating(self, driver) -> bool:
        """
        Kiểm tra ChatGPT có đang generate response không

        Returns:
            True nếu đang generate, False nếu đã xong
        """
        # Kiểm tra nút Stop có hiển thị không
        stop_selectors = [
            self.SELECTORS["stop_button"],
            self.SELECTORS["stop_button_alt"],
            "button[aria-label*='Stop']",
            "button[aria-label*='stop']",
        ]

        for selector in stop_selectors:
            try:
                stop_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in stop_buttons:
                    if btn.is_displayed():
                        return True
            except:
                pass

        # Kiểm tra các streaming/typing indicators
        streaming_selectors = [
            self.SELECTORS["streaming_indicator"],
            self.SELECTORS["streaming_indicator_alt"],
            self.SELECTORS["typing_indicator"],
            self.SELECTORS["thinking_indicator"],
            "[class*='animate-pulse']",
            "[class*='cursor-blink']",
            "span.cursor",
        ]

        for selector in streaming_selectors:
            try:
                indicators = driver.find_elements(By.CSS_SELECTOR, selector)
                for ind in indicators:
                    if ind.is_displayed():
                        return True
            except:
                pass

        return False

    def _wait_for_response_complete(self, driver, timeout: int = 180) -> str:
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
        required_stable_checks = 6  # 6 lần * 1s = 6 giây ổn định

        # Đợi một chút để ChatGPT bắt đầu generate
        time.sleep(2)

        while time.time() - start_time < timeout:
            try:
                # Kiểm tra ChatGPT có đang generate không
                is_generating = self._is_chatgpt_still_generating(driver)

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

                    # Log tiến trình
                    response_len = len(current_response)
                    elapsed = int(time.time() - start_time)
                    if elapsed % 5 == 0:  # Log mỗi 5 giây
                        status = "đang tạo..." if is_generating else "kiểm tra..."
                        self._log_status(f"ChatGPT {status} ({response_len} ký tự, {elapsed}s)")

                    # Nếu không còn generating VÀ response ổn định
                    if not is_generating:
                        if current_response == last_response and current_response.strip():
                            stable_count += 1
                            if stable_count >= required_stable_checks:
                                self._log_status(f"ChatGPT đã trả lời xong! ({len(current_response)} ký tự)")
                                return current_response
                        else:
                            stable_count = 0
                            last_response = current_response
                    else:
                        # Đang generate, reset stable count
                        stable_count = 0
                        last_response = current_response

            except Exception as e:
                self._log_status(f"Lỗi khi đọc response: {e}")

            time.sleep(1)

        # Timeout - trả về response hiện tại nếu có
        if last_response.strip():
            self._log_status(f"Timeout ({timeout}s) nhưng đã có response, sử dụng response hiện tại ({len(last_response)} ký tự)")
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
        Mở trình duyệt mặc định và chờ user đăng nhập

        Returns:
            ChatGPTWebResponse
        """
        try:
            with self._lock:
                driver = self._get_driver()

                self._log_status(f"Đang mở ChatGPT bằng {self._browser_name}...")
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
