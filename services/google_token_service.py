"""
Google Token Service - Tự động lấy Bearer Token từ Google Labs
"""

import time
import json
import threading
from typing import Optional, Callable
from dataclasses import dataclass

try:
    import undetected_chromedriver as uc
    HAS_UNDETECTED = True
except ImportError:
    HAS_UNDETECTED = False

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException


@dataclass
class TokenResult:
    """Kết quả lấy token"""
    success: bool
    token: str = ""
    error_message: str = ""


class GoogleTokenService:
    """
    Service tự động lấy Bearer Token từ Google Labs (ImageFX)
    - Mở trình duyệt đến labs.google
    - Chờ user đăng nhập (nếu cần)
    - Bắt token từ network requests
    """

    GOOGLE_LABS_URL = "https://labs.google/fx/tools/image-fx"

    def __init__(self):
        self._driver: Optional[webdriver.Chrome] = None
        self._status_callback: Optional[Callable[[str], None]] = None
        self._current_token: str = ""
        self._token_timestamp: float = 0
        self._lock = threading.Lock()

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback để cập nhật trạng thái"""
        self._status_callback = callback

    def _log_status(self, message: str) -> None:
        """Log trạng thái"""
        print(f"[GoogleToken] {message}")
        if self._status_callback:
            self._status_callback(message)

    def _create_driver(self) -> webdriver.Chrome:
        """Tạo Chrome driver với khả năng bắt network requests"""
        self._log_status("Đang khởi tạo trình duyệt Chrome...")

        if HAS_UNDETECTED:
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            # Enable performance logging để bắt network requests
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            driver = uc.Chrome(options=options)
        else:
            options = Options()
            options.add_argument("--start-maximized")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            # Enable performance logging
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            driver = webdriver.Chrome(options=options)

        return driver

    def _get_driver(self) -> webdriver.Chrome:
        """Lấy hoặc tạo driver"""
        if self._driver is None:
            self._driver = self._create_driver()
        return self._driver

    def _extract_token_from_logs(self, driver) -> Optional[str]:
        """Trích xuất Bearer Token từ network logs"""
        try:
            logs = driver.get_log('performance')
            for log in logs:
                try:
                    message = json.loads(log['message'])['message']
                    if message['method'] == 'Network.requestWillBeSent':
                        headers = message.get('params', {}).get('request', {}).get('headers', {})
                        auth = headers.get('authorization') or headers.get('Authorization')
                        if auth and auth.startswith('Bearer '):
                            token = auth.replace('Bearer ', '')
                            if len(token) > 100:  # Token hợp lệ thường dài
                                return token
                except:
                    continue
        except Exception as e:
            self._log_status(f"Lỗi khi đọc logs: {e}")
        return None

    def open_and_get_token(self) -> TokenResult:
        """
        Mở Google Labs và lấy Bearer Token

        Returns:
            TokenResult với token nếu thành công
        """
        try:
            with self._lock:
                driver = self._get_driver()

                self._log_status("Đang mở Google Labs ImageFX...")
                driver.get(self.GOOGLE_LABS_URL)

                self._log_status("Vui lòng đăng nhập Google nếu cần...")
                self._log_status("Sau khi đăng nhập, hãy tạo 1 ảnh bất kỳ để lấy token")

                # Chờ trang load và user đăng nhập
                max_wait = 300  # 5 phút
                start_time = time.time()
                token = None

                while time.time() - start_time < max_wait:
                    # Thử lấy token từ logs
                    token = self._extract_token_from_logs(driver)
                    if token:
                        self._current_token = token
                        self._token_timestamp = time.time()
                        self._log_status("Đã lấy được Bearer Token!")
                        return TokenResult(success=True, token=token)

                    time.sleep(2)

                return TokenResult(
                    success=False,
                    error_message="Timeout - Không lấy được token. Hãy thử tạo 1 ảnh trên trang web."
                )

        except Exception as e:
            return TokenResult(
                success=False,
                error_message=f"Lỗi: {str(e)}"
            )

    def refresh_token(self) -> TokenResult:
        """
        Refresh token bằng cách reload trang và bắt request mới
        """
        try:
            with self._lock:
                if self._driver is None:
                    return TokenResult(success=False, error_message="Trình duyệt chưa mở")

                self._log_status("Đang refresh token...")

                # Reload trang
                self._driver.refresh()
                time.sleep(3)

                # Chờ và bắt token mới
                max_wait = 60
                start_time = time.time()

                while time.time() - start_time < max_wait:
                    token = self._extract_token_from_logs(self._driver)
                    if token and token != self._current_token:
                        self._current_token = token
                        self._token_timestamp = time.time()
                        self._log_status("Đã refresh token thành công!")
                        return TokenResult(success=True, token=token)
                    time.sleep(2)

                # Nếu không có token mới, trả về token cũ nếu còn
                if self._current_token:
                    return TokenResult(success=True, token=self._current_token)

                return TokenResult(
                    success=False,
                    error_message="Không thể refresh token"
                )

        except Exception as e:
            return TokenResult(
                success=False,
                error_message=f"Lỗi refresh: {str(e)}"
            )

    def get_current_token(self) -> str:
        """Lấy token hiện tại"""
        return self._current_token

    def is_token_valid(self) -> bool:
        """
        Kiểm tra token còn hợp lệ không (dựa trên thời gian)
        Token thường hết hạn sau ~1 giờ
        """
        if not self._current_token:
            return False
        # Coi token hết hạn sau 50 phút (để có buffer)
        return (time.time() - self._token_timestamp) < 3000

    def close_browser(self) -> None:
        """Đóng trình duyệt"""
        with self._lock:
            if self._driver:
                try:
                    self._driver.quit()
                except:
                    pass
                self._driver = None
                self._log_status("Đã đóng trình duyệt")

    def is_browser_open(self) -> bool:
        """Kiểm tra trình duyệt có đang mở không"""
        if self._driver is None:
            return False
        try:
            _ = self._driver.title
            return True
        except:
            self._driver = None
            return False


# Singleton instance
google_token_service = GoogleTokenService()
