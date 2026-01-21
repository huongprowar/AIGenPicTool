/**
 * Background Service Worker
 * Intercept requests và lấy Bearer Token từ Google Labs
 */

// Lưu token mới nhất
let currentToken = null;
let tokenTimestamp = null;

// Lắng nghe requests đến Google APIs
chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    // Tìm Authorization header
    const authHeader = details.requestHeaders.find(
      (h) => h.name.toLowerCase() === "authorization"
    );

    if (authHeader && authHeader.value.startsWith("Bearer ")) {
      const token = authHeader.value.replace("Bearer ", "");

      // Chỉ lưu token dài (token thật, không phải API key ngắn)
      if (token.length > 100) {
        currentToken = token;
        tokenTimestamp = Date.now();

        // Lưu vào storage
        chrome.storage.local.set({
          token: token,
          timestamp: tokenTimestamp,
          url: details.url,
        });

        // Cập nhật badge
        chrome.action.setBadgeText({ text: "OK" });
        chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });

        console.log("[TokenGrabber] Đã bắt được token mới!");

        // Tự động lưu vào file (thông qua download)
        saveTokenToFile(token);
      }
    }
  },
  {
    urls: [
      "https://aisandbox-pa.googleapis.com/*",
      "https://labs.google/*",
      "https://*.googleapis.com/*",
    ],
  },
  ["requestHeaders"]
);

// Lưu token vào file để Python có thể đọc
function saveTokenToFile(token) {
  const data = JSON.stringify({
    token: token,
    timestamp: Date.now(),
    expires_in: 3600, // Token thường hết hạn sau 1 giờ
  }, null, 2);

  // Lưu vào storage
  chrome.storage.local.set({ tokenData: data });

  // Tạo blob và download vào file cố định
  const blob = new Blob([data], { type: "application/json" });
  const url = URL.createObjectURL(blob);

  // Download với tên file cố định - Python sẽ đọc file này
  chrome.downloads.download({
    url: url,
    filename: "google_token.json",
    saveAs: false, // Tự động save, không hỏi
    conflictAction: "overwrite" // Ghi đè file cũ
  }, (downloadId) => {
    // Cleanup URL sau khi download
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}

// Xử lý messages từ popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getToken") {
    chrome.storage.local.get(["token", "timestamp"], (result) => {
      sendResponse({
        token: result.token || null,
        timestamp: result.timestamp || null,
      });
    });
    return true; // Async response
  }

  if (request.action === "clearToken") {
    currentToken = null;
    tokenTimestamp = null;
    chrome.storage.local.remove(["token", "timestamp", "tokenData"]);
    chrome.action.setBadgeText({ text: "" });
    sendResponse({ success: true });
    return true;
  }
});

// Khởi tạo - kiểm tra token cũ
chrome.storage.local.get(["token", "timestamp"], (result) => {
  if (result.token) {
    currentToken = result.token;
    tokenTimestamp = result.timestamp;

    // Kiểm tra token còn hạn không (50 phút)
    const age = Date.now() - result.timestamp;
    if (age < 50 * 60 * 1000) {
      chrome.action.setBadgeText({ text: "OK" });
      chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });
    } else {
      chrome.action.setBadgeText({ text: "OLD" });
      chrome.action.setBadgeBackgroundColor({ color: "#FF9800" });
    }
  }
});
