"""
Google Token Service - Tự động lấy Bearer Token từ Google Labs
"""

import os
import time
import json
import threading
from typing import Optional, Callable, Literal
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

try:
    import undetected_chromedriver as uc
    HAS_UNDETECTED = True
except ImportError:
    HAS_UNDETECTED = False

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.common.exceptions import TimeoutException


class BrowserType(Enum):
    """Các loại trình duyệt được hỗ trợ"""
    CHROME = "chrome"
    CHROME_UNDETECTED = "chrome_undetected"
    FIREFOX = "firefox"
    EDGE = "edge"
    COCCOC = "coccoc"


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

    # Danh sách trình duyệt hỗ trợ để hiển thị trong UI
    SUPPORTED_BROWSERS = [
        (BrowserType.CHROME_UNDETECTED, "Chrome (Undetected) - Khuyến nghị"),
        (BrowserType.CHROME, "Chrome"),
        (BrowserType.COCCOC, "Cốc Cốc"),
        (BrowserType.EDGE, "Microsoft Edge"),
        (BrowserType.FIREFOX, "Firefox"),
    ]

    # Đường dẫn mặc định của Cốc Cốc trên Windows
    COCCOC_PATHS = [
        r"C:\Program Files\CocCoc\Browser\Application\browser.exe",
        r"C:\Program Files (x86)\CocCoc\Browser\Application\browser.exe",
        r"C:\Users\{username}\AppData\Local\CocCoc\Browser\Application\browser.exe",
    ]

    def __init__(self):
        self._driver = None  # Có thể là Chrome, Firefox, hoặc Edge
        self._status_callback: Optional[Callable[[str], None]] = None
        self._current_token: str = ""
        self._token_timestamp: float = 0
        self._lock = threading.Lock()
        self._current_browser: BrowserType = BrowserType.CHROME_UNDETECTED

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback để cập nhật trạng thái"""
        self._status_callback = callback

    def _log_status(self, message: str) -> None:
        """Log trạng thái"""
        print(f"[GoogleToken] {message}")
        if self._status_callback:
            self._status_callback(message)

    def _create_chrome_driver(self, use_undetected: bool = True):
        """Tạo Chrome driver"""
        self._log_status("Đang khởi tạo trình duyệt Chrome...")

        if use_undetected and HAS_UNDETECTED:
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            return uc.Chrome(options=options)
        else:
            options = ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            return webdriver.Chrome(options=options)

    def _create_firefox_driver(self):
        """Tạo Firefox driver"""
        self._log_status("Đang khởi tạo trình duyệt Firefox...")

        options = FirefoxOptions()
        options.add_argument("--start-maximized")
        # Firefox sử dụng devtools để bắt network
        options.set_preference("devtools.netmonitor.enabled", True)
        return webdriver.Firefox(options=options)

    def _create_edge_driver(self):
        """Tạo Edge driver"""
        self._log_status("Đang khởi tạo trình duyệt Edge...")

        options = EdgeOptions()
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.set_capability('ms:loggingPrefs', {'performance': 'ALL'})
        return webdriver.Edge(options=options)

    def _find_coccoc_path(self) -> Optional[str]:
        """Tìm đường dẫn cài đặt Cốc Cốc"""
        username = os.getenv('USERNAME') or os.getenv('USER') or 'User'

        for path_template in self.COCCOC_PATHS:
            path = path_template.replace('{username}', username)
            if Path(path).exists():
                return path

        return None

    def _create_coccoc_driver(self):
        """Tạo Cốc Cốc driver (dựa trên Chromium)"""
        self._log_status("Đang khởi tạo trình duyệt Cốc Cốc...")

        # Tìm đường dẫn Cốc Cốc
        coccoc_path = self._find_coccoc_path()

        if not coccoc_path:
            raise Exception(
                "Không tìm thấy Cốc Cốc!\n"
                "Vui lòng cài đặt Cốc Cốc hoặc chọn trình duyệt khác."
            )

        self._log_status(f"Tìm thấy Cốc Cốc tại: {coccoc_path}")

        # Cốc Cốc dựa trên Chromium nên dùng ChromeOptions
        options = ChromeOptions()
        options.binary_location = coccoc_path
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

        # Sử dụng ChromeDriver (tương thích với Cốc Cốc)
        return webdriver.Chrome(options=options)

    def _create_driver(self, browser_type: BrowserType = None):
        """Tạo driver dựa trên loại trình duyệt được chọn"""
        if browser_type is None:
            browser_type = self._current_browser

        self._current_browser = browser_type

        if browser_type == BrowserType.CHROME_UNDETECTED:
            return self._create_chrome_driver(use_undetected=True)
        elif browser_type == BrowserType.CHROME:
            return self._create_chrome_driver(use_undetected=False)
        elif browser_type == BrowserType.FIREFOX:
            return self._create_firefox_driver()
        elif browser_type == BrowserType.EDGE:
            return self._create_edge_driver()
        elif browser_type == BrowserType.COCCOC:
            return self._create_coccoc_driver()
        else:
            # Default to Chrome
            return self._create_chrome_driver(use_undetected=HAS_UNDETECTED)

    def _get_driver(self, browser_type: BrowserType = None):
        """Lấy hoặc tạo driver"""
        if self._driver is None:
            self._driver = self._create_driver(browser_type)
        return self._driver

    def _extract_token_from_logs(self, driver) -> Optional[str]:
        """Trích xuất Bearer Token từ network logs"""
        try:
            # Chrome, Edge, Cốc Cốc sử dụng performance logs (Chromium-based)
            if self._current_browser in [BrowserType.CHROME, BrowserType.CHROME_UNDETECTED, BrowserType.EDGE, BrowserType.COCCOC]:
                return self._extract_token_from_chromium_logs(driver)
            elif self._current_browser == BrowserType.FIREFOX:
                return self._extract_token_from_firefox(driver)
        except Exception as e:
            self._log_status(f"Lỗi khi đọc logs: {e}")
        return None

    def _extract_token_from_chromium_logs(self, driver) -> Optional[str]:
        """Trích xuất token từ Chrome/Edge performance logs"""
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
            self._log_status(f"Lỗi khi đọc Chromium logs: {e}")
        return None

    def _extract_token_from_firefox(self, driver) -> Optional[str]:
        """
        Trích xuất token từ Firefox
        Firefox không hỗ trợ performance logs như Chrome,
        nên cần dùng cách khác (inject script để intercept requests)
        """
        try:
            # Inject script để lấy token từ localStorage hoặc sessionStorage
            # Google thường lưu token trong một số biến
            script = """
            // Thử lấy từ các nguồn khác nhau
            var token = null;

            // Kiểm tra window.__INITIAL_DATA__ hoặc các biến global
            if (window.__INITIAL_DATA__ && window.__INITIAL_DATA__.authToken) {
                token = window.__INITIAL_DATA__.authToken;
            }

            // Kiểm tra localStorage
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                var value = localStorage.getItem(key);
                if (value && value.length > 100 && value.indexOf('ya29') === 0) {
                    token = value;
                    break;
                }
            }

            // Kiểm tra sessionStorage
            if (!token) {
                for (var i = 0; i < sessionStorage.length; i++) {
                    var key = sessionStorage.key(i);
                    var value = sessionStorage.getItem(key);
                    if (value && value.length > 100 && value.indexOf('ya29') === 0) {
                        token = value;
                        break;
                    }
                }
            }

            return token;
            """
            token = driver.execute_script(script)
            if token and len(token) > 100:
                return token
        except Exception as e:
            self._log_status(f"Lỗi khi đọc Firefox storage: {e}")
        return None

    def open_and_get_token(self, browser_type: BrowserType = None) -> TokenResult:
        """
        Mở Google Labs và lấy Bearer Token

        Args:
            browser_type: Loại trình duyệt sử dụng (mặc định: Chrome Undetected)

        Returns:
            TokenResult với token nếu thành công
        """
        try:
            with self._lock:
                # Đóng driver cũ nếu đang mở với browser khác
                if self._driver is not None and browser_type is not None and browser_type != self._current_browser:
                    self._log_status("Đóng trình duyệt cũ...")
                    try:
                        self._driver.quit()
                    except:
                        pass
                    self._driver = None

                driver = self._get_driver(browser_type)

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
