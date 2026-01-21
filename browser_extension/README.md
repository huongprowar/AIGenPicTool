# Google Token Grabber Extension

Extension tự động lấy Bearer Token từ Google Labs ImageFX.

## Cài đặt Extension

### Chrome / Edge / Cốc Cốc

1. Mở trình duyệt và truy cập:
   - **Chrome**: `chrome://extensions/`
   - **Edge**: `edge://extensions/`
   - **Cốc Cốc**: `coccoc://extensions/`

2. Bật **Developer mode** (Chế độ nhà phát triển) ở góc phải trên

3. Click **Load unpacked** (Tải tiện ích đã giải nén)

4. Chọn thư mục `browser_extension` này

5. Extension sẽ xuất hiện trên thanh công cụ với icon chữ "T"

## Cách sử dụng

### Lấy Token

1. Truy cập [Google Labs ImageFX](https://labs.google/fx/tools/image-fx)

2. Đăng nhập tài khoản Google (nếu chưa đăng nhập)

3. Tạo một ảnh bất kỳ (nhập prompt và click Generate)

4. Extension sẽ tự động:
   - Bắt Bearer Token từ request
   - Hiện badge "OK" màu xanh
   - Lưu token vào file `Downloads/google_token.json`

5. Click vào icon extension để xem và copy token

### Trong Python

```python
from services.google_token_service import google_token_service

# Đọc token từ extension (đơn giản nhất)
result = google_token_service.get_token_from_extension()

if result.success:
    print(f"Token: {result.token[:50]}...")
else:
    print(f"Lỗi: {result.error_message}")
```

## File Token

Extension tự động lưu token vào:
```
C:\Users\<username>\Downloads\google_token.json
```

Nội dung file:
```json
{
  "token": "ya29.a0ARW5m...",
  "timestamp": 1703123456789,
  "expires_in": 3600
}
```

## Lưu ý

- Token có hiệu lực khoảng **1 giờ**
- Khi token hết hạn, chỉ cần tạo thêm 1 ảnh mới trên ImageFX
- Extension sẽ tự động cập nhật token mới

## Xử lý lỗi

| Vấn đề | Giải pháp |
|--------|-----------|
| Badge không hiện "OK" | Refresh trang ImageFX và tạo ảnh mới |
| File token không tạo | Kiểm tra quyền download của browser |
| Token hết hạn | Tạo ảnh mới trên ImageFX |

## Cấu trúc thư mục

```
browser_extension/
├── manifest.json      # Cấu hình extension
├── background.js      # Service worker bắt requests
├── popup.html         # Giao diện popup
├── popup.js           # Logic popup
├── icons/             # Icons
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── README.md          # File này
```
