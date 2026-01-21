"""
Browser Utils - Phát hiện và sử dụng trình duyệt mặc định của hệ thống
"""

import os
import sys
import winreg
from pathlib import Path
from enum import Enum
from typing import Optional, Tuple


class BrowserType(Enum):
    """Các loại trình duyệt được hỗ trợ"""
    CHROME = "chrome"
    CHROME_UNDETECTED = "chrome_undetected"
    FIREFOX = "firefox"
    EDGE = "edge"
    COCCOC = "coccoc"
    UNKNOWN = "unknown"


# Mapping từ ProgId trong Registry sang BrowserType
PROGID_TO_BROWSER = {
    "ChromeHTML": BrowserType.CHROME,
    "FirefoxURL": BrowserType.FIREFOX,
    "FirefoxURL-308046B0AF4A39CB": BrowserType.FIREFOX,
    "MSEdgeHTM": BrowserType.EDGE,
    "MSEdgeDHTML": BrowserType.EDGE,
    "CocCocHTML": BrowserType.COCCOC,
    "CocCocHTM": BrowserType.COCCOC,
}

# Đường dẫn Cốc Cốc
COCCOC_PATHS = [
    r"C:\Program Files\CocCoc\Browser\Application\browser.exe",
    r"C:\Program Files (x86)\CocCoc\Browser\Application\browser.exe",
]


def get_default_browser() -> Tuple[BrowserType, str]:
    """
    Phát hiện trình duyệt mặc định của Windows

    Returns:
        Tuple[BrowserType, str]: (Loại trình duyệt, Tên hiển thị)
    """
    if sys.platform != "win32":
        return BrowserType.CHROME, "Chrome (Default for non-Windows)"

    try:
        # Đọc từ Registry
        key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")

            # Tìm trong mapping
            for pattern, browser_type in PROGID_TO_BROWSER.items():
                if pattern in prog_id:
                    browser_names = {
                        BrowserType.CHROME: "Google Chrome",
                        BrowserType.FIREFOX: "Mozilla Firefox",
                        BrowserType.EDGE: "Microsoft Edge",
                        BrowserType.COCCOC: "Cốc Cốc",
                    }
                    return browser_type, browser_names.get(browser_type, prog_id)

            # Không tìm thấy trong mapping
            return BrowserType.UNKNOWN, prog_id

    except WindowsError:
        pass
    except Exception as e:
        print(f"[BrowserUtils] Lỗi phát hiện browser: {e}")

    # Fallback: thử tìm browser nào có sẵn
    return _detect_available_browser()


def _detect_available_browser() -> Tuple[BrowserType, str]:
    """Tìm browser có sẵn trên máy"""

    # Kiểm tra Edge (có sẵn trên Windows 10/11)
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if Path(edge_path).exists():
        return BrowserType.EDGE, "Microsoft Edge"

    # Kiểm tra Chrome
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in chrome_paths:
        if Path(path).exists():
            return BrowserType.CHROME, "Google Chrome"

    # Kiểm tra Cốc Cốc
    for path in COCCOC_PATHS:
        if Path(path).exists():
            return BrowserType.COCCOC, "Cốc Cốc"

    # Kiểm tra Firefox
    firefox_path = r"C:\Program Files\Mozilla Firefox\firefox.exe"
    if Path(firefox_path).exists():
        return BrowserType.FIREFOX, "Mozilla Firefox"

    # Mặc định về Chrome (Selenium sẽ tự tìm)
    return BrowserType.CHROME, "Chrome (Default)"


def find_coccoc_path() -> Optional[str]:
    """Tìm đường dẫn cài đặt Cốc Cốc"""
    username = os.getenv('USERNAME') or os.getenv('USER') or 'User'

    paths = COCCOC_PATHS + [
        rf"C:\Users\{username}\AppData\Local\CocCoc\Browser\Application\browser.exe",
    ]

    for path in paths:
        if Path(path).exists():
            return path

    return None


def get_browser_display_name(browser_type: BrowserType) -> str:
    """Lấy tên hiển thị của browser"""
    names = {
        BrowserType.CHROME: "Google Chrome",
        BrowserType.CHROME_UNDETECTED: "Chrome (Undetected)",
        BrowserType.FIREFOX: "Mozilla Firefox",
        BrowserType.EDGE: "Microsoft Edge",
        BrowserType.COCCOC: "Cốc Cốc",
        BrowserType.UNKNOWN: "Unknown Browser",
    }
    return names.get(browser_type, "Unknown")
