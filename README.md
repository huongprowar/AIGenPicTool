# AI Image Generator

Ứng dụng desktop tạo ảnh AI sử dụng ChatGPT để sinh image prompts và Gemini để generate ảnh.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![PySide6](https://img.shields.io/badge/PySide6-6.5+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## Mục Lục

- [Tính Năng](#tính-năng)
- [Yêu Cầu Hệ Thống](#yêu-cầu-hệ-thống)
- [Cài Đặt](#cài-đặt)
- [Cấu Hình](#cấu-hình)
- [Hướng Dẫn Sử Dụng](#hướng-dẫn-sử-dụng)
- [Cấu Trúc Project](#cấu-trúc-project)
- [Luồng Hoạt Động](#luồng-hoạt-động)
- [API Reference](#api-reference)
- [Xử Lý Lỗi](#xử-lý-lỗi)
- [FAQ](#faq)

---

## Tính Năng

### Tab Tạo Ảnh
- Nhập prompt gốc bằng tiếng Việt hoặc tiếng Anh
- Tự động gọi ChatGPT để sinh ra nhiều image prompts chi tiết
- Tạo ảnh song song với Gemini API
- Hiển thị thumbnail và trạng thái realtime
- Xem ảnh full size
- Tạo lại từng ảnh riêng lẻ
- Chọn và tải về nhiều ảnh cùng lúc

### Tab Cài Đặt
- Lưu trữ API Keys an toàn
- Test kết nối API trước khi sử dụng
- Chọn thư mục lưu ảnh
- Cấu hình model và số lần retry

### Tính Năng Kỹ Thuật
- Background thread - không block UI khi tạo ảnh
- Auto retry khi gặp lỗi network hoặc rate limit
- Parse nhiều format prompt từ ChatGPT
- Log console theo dõi tiến trình
- Lưu cấu hình tự động

---

## Yêu Cầu Hệ Thống

| Yêu cầu | Phiên bản |
|---------|-----------|
| Python | 3.9 trở lên |
| OS | Windows 10/11, macOS, Linux |
| RAM | Tối thiểu 4GB |
| Internet | Bắt buộc (gọi API) |

### API Keys cần thiết
1. **OpenAI API Key** - Lấy tại: https://platform.openai.com/api-keys
2. **Google Gemini API Key** - Lấy tại: https://aistudio.google.com/app/apikey

---

## Cài Đặt

### Cách 1: Sử dụng script (Windows)

```batch
# Double-click file run.bat
# Script sẽ tự động:
# - Tạo virtual environment
# - Cài đặt dependencies
# - Chạy ứng dụng
```

### Cách 2: Cài đặt thủ công

```bash
# Clone hoặc download project
cd D:/Code/AITool

# Tạo virtual environment
python -m venv venv

# Kích hoạt virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt

# Chạy ứng dụng
python main.py
```

### Dependencies

```
PySide6>=6.5.0          # Qt GUI Framework
requests>=2.31.0        # HTTP Client
openai>=1.0.0           # OpenAI API
google-generativeai>=0.3.0  # Gemini API
Pillow>=10.0.0          # Image processing
aiohttp>=3.9.0          # Async support
```

---

## Cấu Hình

### Lần đầu khởi động

1. Ứng dụng sẽ tự động mở tab **Cài Đặt**
2. Nhập **ChatGPT API Key** (bắt đầu bằng `sk-`)
3. Nhập **Gemini API Key**
4. Chọn **Thư mục lưu ảnh**
5. Bấm **Test** để kiểm tra kết nối
6. Bấm **Lưu cài đặt**

### File cấu hình

Cấu hình được lưu tại `config.json`:

```json
{
  "chatgpt_api_key": "sk-...",
  "gemini_api_key": "...",
  "output_directory": "D:/Pictures/AI",
  "chatgpt_model": "gpt-4o-mini",
  "gemini_model": "gemini-2.0-flash-exp",
  "max_retries": 3,
  "retry_delay": 2.0
}
```

> **Lưu ý**: File `config.json` chứa API keys nhạy cảm. Không commit lên git.

---

## Hướng Dẫn Sử Dụng

### Bước 1: Nhập Prompt Gốc

Nhập mô tả ý tưởng của bạn vào ô text. Ví dụ:

```
Tạo 3 ảnh về phong cảnh Việt Nam vào buổi hoàng hôn,
phong cách tranh sơn dầu
```

```
Design 5 logo variations for a tech startup called "AIFlow",
minimal style, blue color palette
```

### Bước 2: Chọn Số Lượng Ảnh

Điều chỉnh số lượng ảnh muốn tạo (1-10 ảnh).

### Bước 3: Bắt Đầu Tạo Ảnh

Bấm nút **"Bắt đầu tạo ảnh"**. Ứng dụng sẽ:

1. Gọi ChatGPT để sinh image prompts
2. Parse và tách các prompts
3. Gọi Gemini để tạo từng ảnh
4. Hiển thị kết quả realtime

### Bước 4: Xem và Quản Lý Kết Quả

- **Checkbox**: Chọn/bỏ chọn ảnh
- **Xem**: Mở ảnh full size
- **Tạo lại**: Generate lại ảnh đó

### Bước 5: Tải Ảnh

Bấm **"Tải tất cả ảnh đã chọn"** để lưu về thư mục đã cấu hình.

---

## Cấu Trúc Project

```
AITool/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── run.bat                 # Windows launcher
├── config.json            # Config (auto-generated)
├── .gitignore
│
├── services/              # Business Logic Layer
│   ├── __init__.py
│   ├── config_service.py   # Quản lý cấu hình
│   ├── chatgpt_service.py  # Gọi ChatGPT API
│   └── gemini_service.py   # Gọi Gemini API
│
├── ui/                    # Presentation Layer
│   ├── __init__.py
│   ├── main_window.py      # Cửa sổ chính
│   ├── create_tab.py       # Tab tạo ảnh
│   ├── settings_tab.py     # Tab cài đặt
│   └── image_item.py       # Widget hiển thị ảnh
│
└── utils/                 # Utility Layer
    ├── __init__.py
    ├── prompt_parser.py    # Parse prompts từ ChatGPT
    └── image_downloader.py # Lưu ảnh xuống disk
```

### Kiến Trúc

```
┌─────────────────────────────────────────────────────────┐
│                    UI Layer (PySide6)                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐   │
│  │ MainWindow  │ │ CreateTab   │ │ SettingsTab     │   │
│  └─────────────┘ └─────────────┘ └─────────────────┘   │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                   Service Layer                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐   │
│  │ ConfigSvc   │ │ ChatGPTSvc  │ │ GeminiSvc       │   │
│  └─────────────┘ └─────────────┘ └─────────────────┘   │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                   Utility Layer                          │
│  ┌─────────────────────┐ ┌─────────────────────────┐   │
│  │ PromptParser        │ │ ImageDownloader         │   │
│  └─────────────────────┘ └─────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Luồng Hoạt Động

```
┌──────────────┐
│ User Input   │ "Tạo 3 ảnh phong cảnh Việt Nam"
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ ChatGPT API  │ Sinh ra 3 image prompts chi tiết
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Prompt       │ Parse và tách từng prompt
│ Parser       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Gemini API   │ Tạo ảnh từ mỗi prompt (có retry)
│ (Loop)       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Display      │ Hiển thị thumbnail + status
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Download     │ Lưu ảnh đã chọn vào thư mục
└──────────────┘
```

---

## API Reference

### ChatGPT Service

```python
from services.chatgpt_service import chatgpt_service

# Tạo image prompts
result = chatgpt_service.generate_image_prompts(
    user_prompt="Tạo 3 ảnh về mèo",
    num_prompts=3
)

if result.success:
    print(result.content)  # Raw text từ ChatGPT
else:
    print(result.error_message)
```

### Gemini Service

```python
from services.gemini_service import gemini_service

# Tạo ảnh
result = gemini_service.generate_image(
    prompt="A cute cat sitting on a windowsill",
    api_key="your-api-key",
    max_retries=3
)

if result.success:
    image_bytes = result.image_data
    mime_type = result.mime_type
```

### Prompt Parser

```python
from utils.prompt_parser import parse_prompts

text = """
Image Prompt 1: A beautiful sunset over the ocean
Image Prompt 2: Mountains covered in snow
Image Prompt 3: A cozy cabin in the forest
"""

prompts = parse_prompts(text)
for p in prompts:
    print(f"{p.index}: {p.content}")
```

### Image Downloader

```python
from utils.image_downloader import ImageDownloader

result = ImageDownloader.save_image_from_prompt(
    image_data=bytes_data,
    prompt="sunset over ocean",
    output_dir="D:/Pictures",
    index=1,
    mime_type="image/png"
)

print(result.file_path)  # D:/Pictures/20240115_143022_01_sunset_over_ocean.png
```

---

## Xử Lý Lỗi

### Lỗi thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|-----|-------------|-----------|
| `API Key không hợp lệ` | Key sai hoặc hết hạn | Kiểm tra lại API key |
| `Rate limit exceeded` | Gọi API quá nhiều | Đợi vài phút rồi thử lại |
| `Network error` | Mất kết nối internet | Kiểm tra kết nối mạng |
| `Quota exceeded` | Hết quota API | Nạp thêm credit hoặc đợi reset |
| `Response không chứa ảnh` | Gemini không generate được | Thử lại hoặc sửa prompt |

### Retry Logic

Ứng dụng tự động retry khi gặp lỗi:
- **Network error**: Retry sau 2 giây
- **Rate limit**: Retry với exponential backoff
- **Số lần retry tối đa**: 3 (có thể cấu hình)

---

## FAQ

### Q: Tại sao chọn PySide6 thay vì Tkinter?

**A:** PySide6 (Qt) có:
- UI đẹp và professional hơn
- Nhiều widget có sẵn
- Hỗ trợ threading tốt
- Cross-platform nhất quán

### Q: Gemini có hỗ trợ tạo ảnh không?

**A:** Gemini 2.0 Flash Experimental có khả năng tạo ảnh thông qua `response_modalities=["IMAGE"]`. Tuy nhiên tính năng này đang trong giai đoạn experimental.

### Q: Prompt tiếng Việt có hoạt động không?

**A:** Có, ChatGPT hiểu tiếng Việt và sẽ tạo ra các image prompts phù hợp.

### Q: Làm sao để tăng chất lượng ảnh?

**A:**
- Viết prompt gốc chi tiết hơn
- Thêm các từ khóa về style, lighting, mood
- Tăng số lượng ảnh để có nhiều lựa chọn

### Q: API key có bị lộ không?

**A:** API keys được lưu trong `config.json` local. File này đã được thêm vào `.gitignore`. Không commit file này lên public repository.

---

## Contributing

1. Fork repository
2. Tạo feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Tạo Pull Request

---

## License

MIT License - Xem file [LICENSE](LICENSE) để biết thêm chi tiết.

---

## Liên Hệ

- Issues: Tạo issue trên GitHub
- Email: your-email@example.com

---

**Made with Python & PySide6**
