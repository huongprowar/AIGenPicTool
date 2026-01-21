"""
Google Token Service - Tự động lấy Bearer Token từ Google Labs

Cách sử dụng (tránh lỗi "unsupported browser"):
1. Gọi launch_browser_for_login() - mở browser bình thường (không qua Selenium)
2. Đăng nhập Google trong browser đó
3. Gọi get_token_from_browser() - kết nối vào browser và lấy token
"""

import os
import time
import json
import threading
import subprocess
import socket
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
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.common.exceptions import TimeoutException

from utils.browser_utils import (
    BrowserType, get_default_browser, find_coccoc_path, get_browser_display_name
)

# Port mặc định cho Remote Debugging
DEFAULT_DEBUG_PORT = 9222


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
        self._driver = None
        self._status_callback: Optional[Callable[[str], None]] = None
        self._current_token: str = ""
        self._token_timestamp: float = 0
        self._lock = threading.Lock()
        self._current_browser: BrowserType = BrowserType.CHROME
        self._browser_name: str = "Chrome"
        self._debug_port: int = DEFAULT_DEBUG_PORT
        self._is_attached: bool = False  # True nếu đang kết nối vào browser có sẵn

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback để cập nhật trạng thái"""
        self._status_callback = callback

    def _log_status(self, message: str) -> None:
        """Log trạng thái"""
        print(f"[GoogleToken] {message}")
        if self._status_callback:
            self._status_callback(message)

    # ==================== ĐỌC TOKEN TỪ EXTENSION ====================

    def _get_token_file_path(self) -> str:
        """Lấy đường dẫn file token từ extension"""
        username = os.getenv('USERNAME') or os.getenv('USER') or 'User'
        # File được extension download vào thư mục Downloads
        return rf"C:\Users\{username}\Downloads\google_token.json"

    def get_token_from_extension(self) -> TokenResult:
        """
        Đọc token từ file mà extension đã lưu.
        Đây là cách đơn giản nhất - chỉ cần cài extension và dùng Google Labs bình thường.

        Returns:
            TokenResult với token nếu thành công
        """
        token_file = self._get_token_file_path()

        if not os.path.exists(token_file):
            return TokenResult(
                success=False,
                error_message=(
                    f"Không tìm thấy file token!\n"
                    f"Hãy cài Extension và truy cập Google Labs ImageFX để lấy token.\n"
                    f"File cần có: {token_file}"
                )
            )

        try:
            with open(token_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            token = data.get('token', '')
            timestamp = data.get('timestamp', 0)

            if not token:
                return TokenResult(
                    success=False,
                    error_message="File token rỗng. Hãy tạo 1 ảnh trên Google Labs ImageFX."
                )

            # Kiểm tra token còn hạn không (50 phút)
            age_minutes = (time.time() * 1000 - timestamp) / 60000
            if age_minutes > 50:
                self._log_status(f"Token có thể đã hết hạn ({int(age_minutes)} phút trước)")

            self._current_token = token
            self._token_timestamp = timestamp / 1000  # Convert ms to seconds

            self._log_status("Đã đọc token từ extension thành công!")
            return TokenResult(success=True, token=token)

        except json.JSONDecodeError:
            return TokenResult(
                success=False,
                error_message="File token bị lỗi format. Hãy tạo lại."
            )
        except Exception as e:
            return TokenResult(
                success=False,
                error_message=f"Lỗi đọc file token: {e}"
            )

    def is_extension_token_available(self) -> bool:
        """Kiểm tra có token từ extension không"""
        token_file = self._get_token_file_path()
        if not os.path.exists(token_file):
            return False

        try:
            with open(token_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return bool(data.get('token'))
        except:
            return False

    # ==================== PHƯƠNG THỨC CŨ - DÙNG SELENIUM ====================

    def _is_debug_port_open(self) -> bool:
        """Kiểm tra port debugging có đang mở không"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', self._debug_port))
                return result == 0
        except:
            return False

    def _is_browser_running(self) -> bool:
        """Kiểm tra xem có browser nào đang chạy không"""
        try:
            import psutil
            browser_names = ['chrome.exe', 'msedge.exe', 'browser.exe', 'firefox.exe']
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() in browser_names:
                    return True
        except:
            pass
        return False

    def _kill_browser_processes(self) -> bool:
        """Đóng tất cả browser processes"""
        try:
            import psutil
            browser_names = ['chrome.exe', 'msedge.exe', 'browser.exe']  # Không kill Firefox
            killed = False
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'] and proc.info['name'].lower() in browser_names:
                    try:
                        proc.terminate()
                        killed = True
                    except:
                        pass
            if killed:
                time.sleep(2)  # Chờ processes đóng
            return killed
        except Exception as e:
            self._log_status(f"Lỗi khi đóng browser: {e}")
            return False

    def _get_browser_path(self) -> Optional[str]:
        """Lấy đường dẫn trình duyệt mặc định"""
        browser_paths = {
            BrowserType.CHROME: [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ],
            BrowserType.EDGE: [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ],
            BrowserType.COCCOC: [
                r"C:\Program Files\CocCoc\Browser\Application\browser.exe",
                r"C:\Program Files (x86)\CocCoc\Browser\Application\browser.exe",
            ],
            BrowserType.FIREFOX: [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
                r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            ],
        }

        paths = browser_paths.get(self._current_browser, browser_paths[BrowserType.CHROME])
        for path in paths:
            if os.path.exists(path):
                return path
        return None

    def _get_user_data_dir(self) -> Optional[str]:
        """Lấy đường dẫn user data của trình duyệt mặc định"""
        username = os.getenv('USERNAME') or os.getenv('USER') or 'User'

        user_data_dirs = {
            BrowserType.CHROME: rf"C:\Users\{username}\AppData\Local\Google\Chrome\User Data",
            BrowserType.EDGE: rf"C:\Users\{username}\AppData\Local\Microsoft\Edge\User Data",
            BrowserType.COCCOC: rf"C:\Users\{username}\AppData\Local\CocCoc\Browser\User Data",
        }

        path = user_data_dirs.get(self._current_browser)
        if path and os.path.exists(path):
            return path
        return None

    def launch_browser_for_login(self, url: str = None, auto_close_existing: bool = False) -> bool:
        """
        Mở trình duyệt với Remote Debugging, sử dụng PROFILE GỐC (đã đăng nhập sẵn).

        QUAN TRỌNG: Cần đóng browser hiện tại trước vì không thể dùng chung profile.

        Args:
            url: URL để mở (mặc định là Google Labs ImageFX)
            auto_close_existing: Tự động đóng browser đang chạy

        Returns:
            True nếu mở thành công
        """
        # Phát hiện trình duyệt mặc định
        self._detect_default_browser()

        url = url or self.GOOGLE_LABS_URL
        browser_path = self._get_browser_path()
        user_data_dir = self._get_user_data_dir()

        if not browser_path:
            self._log_status(f"Không tìm thấy trình duyệt {self._browser_name}!")
            return False

        # Kiểm tra nếu đã có browser đang chạy với debug port
        if self._is_debug_port_open():
            self._log_status(f"✓ Trình duyệt đã sẵn sàng (port {self._debug_port})")
            self._log_status("Bạn có thể nhấn 'Lấy Token' ngay")
            return True

        # Kiểm tra browser đang chạy (chiếm profile)
        if self._is_browser_running():
            if auto_close_existing:
                self._log_status("Đang đóng trình duyệt hiện tại...")
                self._kill_browser_processes()
            else:
                self._log_status("⚠ Phát hiện trình duyệt đang chạy!")
                self._log_status("Cần đóng trình duyệt để sử dụng profile đã đăng nhập.")
                self._log_status("→ Hãy đóng browser thủ công hoặc bật 'Tự động đóng browser'")
                return False

        self._log_status(f"Đang mở {self._browser_name} với profile gốc...")

        # Build command - KHÔNG dùng Selenium
        cmd = [browser_path]

        # Thêm remote debugging port
        if self._current_browser == BrowserType.FIREFOX:
            cmd.extend(["--start-debugger-server", str(self._debug_port)])
        else:
            cmd.append(f"--remote-debugging-port={self._debug_port}")

        # SỬ DỤNG PROFILE GỐC - đã có cookies đăng nhập Google
        if user_data_dir and self._current_browser != BrowserType.FIREFOX:
            cmd.append(f"--user-data-dir={user_data_dir}")
            self._log_status(f"Sử dụng profile: {user_data_dir}")

        cmd.append(url)

        try:
            subprocess.Popen(cmd, shell=False)

            self._log_status(f"✓ Đã mở {self._browser_name}!")

            if user_data_dir:
                self._log_status("→ Nếu đã đăng nhập Google trước đó, sẽ tự động đăng nhập")
            else:
                self._log_status("→ Vui lòng đăng nhập tài khoản Google")

            self._log_status("→ Sau đó nhấn 'Lấy Token'")

            time.sleep(2)
            return True

        except Exception as e:
            self._log_status(f"Lỗi mở trình duyệt: {e}")
            return False

    def launch_browser_auto(self, url: str = None) -> bool:
        """
        Mở browser với profile gốc, TỰ ĐỘNG đóng browser đang chạy.
        Tiện lợi hơn nhưng sẽ đóng tất cả cửa sổ browser hiện tại.

        Returns:
            True nếu mở thành công
        """
        return self.launch_browser_for_login(url=url, auto_close_existing=True)

    def get_token_from_browser(self) -> TokenResult:
        """
        Kết nối vào trình duyệt đang mở và lấy token.
        Trình duyệt phải được mở bằng launch_browser_for_login() trước.

        Returns:
            TokenResult với token nếu thành công
        """
        try:
            with self._lock:
                # Kiểm tra browser có đang chạy với debug port không
                if not self._is_debug_port_open():
                    return TokenResult(
                        success=False,
                        error_message=(
                            f"Không tìm thấy trình duyệt!\n"
                            f"Hãy nhấn 'Mở Trình Duyệt' trước để mở browser."
                        )
                    )

                self._log_status(f"Đang kết nối vào trình duyệt (port {self._debug_port})...")

                # Kết nối vào browser đang chạy
                options = ChromeOptions()
                options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self._debug_port}")
                options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

                try:
                    driver = webdriver.Chrome(options=options)
                    self._driver = driver
                    self._is_attached = True
                    self._current_browser = BrowserType.CHROME  # Chromium-based
                    self._log_status("Đã kết nối vào trình duyệt!")
                except Exception as e:
                    return TokenResult(
                        success=False,
                        error_message=f"Không thể kết nối vào trình duyệt: {e}"
                    )

                # Kiểm tra xem đang ở đúng trang không
                current_url = driver.current_url
                if "labs.google" not in current_url:
                    self._log_status("Đang chuyển đến Google Labs ImageFX...")
                    driver.get(self.GOOGLE_LABS_URL)
                    time.sleep(3)

                self._log_status("Đang chờ lấy token...")
                self._log_status("(Hãy tạo 1 ảnh bất kỳ trên trang web nếu chưa có)")

                # Chờ và bắt token
                max_wait = 120  # 2 phút
                start_time = time.time()

                while time.time() - start_time < max_wait:
                    token = self._extract_token_from_chromium_logs(driver)
                    if token:
                        self._current_token = token
                        self._token_timestamp = time.time()
                        self._log_status("✓ Đã lấy được Bearer Token!")
                        return TokenResult(success=True, token=token)

                    time.sleep(2)

                return TokenResult(
                    success=False,
                    error_message="Timeout - Không lấy được token.\nHãy thử tạo 1 ảnh trên trang web rồi thử lại."
                )

        except Exception as e:
            return TokenResult(
                success=False,
                error_message=f"Lỗi: {str(e)}"
            )

    # ==================== KẾT THÚC PHƯƠNG THỨC MỚI ====================

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

    def _create_coccoc_driver(self):
        """Tạo Cốc Cốc driver (dựa trên Chromium)"""
        self._log_status("Đang khởi tạo trình duyệt Cốc Cốc...")

        coccoc_path = find_coccoc_path()

        if not coccoc_path:
            raise Exception(
                "Không tìm thấy Cốc Cốc!\n"
                "Sẽ sử dụng Chrome thay thế."
            )

        self._log_status(f"Tìm thấy Cốc Cốc tại: {coccoc_path}")

        options = ChromeOptions()
        options.binary_location = coccoc_path
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

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

    def open_and_get_token(self) -> TokenResult:
        """
        Mở Google Labs bằng trình duyệt mặc định và lấy Bearer Token

        Returns:
            TokenResult với token nếu thành công
        """
        try:
            with self._lock:
                driver = self._get_driver()

                self._log_status(f"Đang mở Google Labs ImageFX bằng {self._browser_name}...")
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

    def close_browser(self, force: bool = False) -> None:
        """
        Đóng/ngắt kết nối trình duyệt

        Args:
            force: Nếu True, sẽ đóng cả browser đang attached
        """
        with self._lock:
            if self._driver:
                try:
                    if self._is_attached and not force:
                        # Chỉ ngắt kết nối Selenium, browser vẫn mở
                        self._log_status("Đã ngắt kết nối (browser vẫn mở)")
                    else:
                        self._driver.quit()
                        self._log_status("Đã đóng trình duyệt")
                except:
                    pass
                self._driver = None
                self._is_attached = False

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
