"""
Image Downloader - Lưu ảnh vào thư mục chỉ định
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass

from PIL import Image
import io


@dataclass
class SaveResult:
    """Kết quả lưu ảnh"""
    success: bool
    file_path: str = ""
    error_message: str = ""


class ImageDownloader:
    """
    Class xử lý lưu ảnh vào thư mục
    - Tự động tạo tên file từ prompt
    - Hỗ trợ lưu batch nhiều ảnh
    - Tự động tạo thư mục nếu chưa tồn tại
    """

    # Ký tự không hợp lệ cho tên file
    INVALID_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

    # Độ dài tối đa của tên file
    MAX_FILENAME_LENGTH = 100

    @classmethod
    def sanitize_filename(cls, text: str, max_length: int = MAX_FILENAME_LENGTH) -> str:
        """
        Làm sạch text để dùng làm tên file

        Args:
            text: Text gốc
            max_length: Độ dài tối đa

        Returns:
            Text đã làm sạch
        """
        # Loại bỏ ký tự không hợp lệ
        clean = re.sub(cls.INVALID_CHARS, '', text)

        # Thay khoảng trắng bằng underscore
        clean = re.sub(r'\s+', '_', clean)

        # Loại bỏ underscore liên tiếp
        clean = re.sub(r'_+', '_', clean)

        # Loại bỏ underscore đầu/cuối
        clean = clean.strip('_')

        # Truncate nếu quá dài
        if len(clean) > max_length:
            clean = clean[:max_length]

        # Fallback nếu rỗng
        if not clean:
            clean = "image"

        return clean

    @classmethod
    def generate_filename(
        cls,
        prompt: str,
        index: int = 1,
        extension: str = "png"
    ) -> str:
        """
        Tạo tên file từ prompt

        Args:
            prompt: Prompt gốc
            index: Số thứ tự ảnh
            extension: Định dạng file

        Returns:
            Tên file
        """
        # Timestamp để đảm bảo unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Làm sạch prompt
        clean_prompt = cls.sanitize_filename(prompt, max_length=50)

        # Tạo tên file
        filename = f"{timestamp}_{index:02d}_{clean_prompt}.{extension}"

        return filename

    @classmethod
    def save_image(
        cls,
        image_data: bytes,
        output_dir: str,
        filename: str,
        mime_type: str = "image/png"
    ) -> SaveResult:
        """
        Lưu ảnh vào thư mục

        Args:
            image_data: Dữ liệu ảnh (bytes)
            output_dir: Thư mục đích
            filename: Tên file
            mime_type: MIME type của ảnh

        Returns:
            SaveResult chứa kết quả
        """
        try:
            # Đảm bảo thư mục tồn tại
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Xác định extension từ mime_type
            extension_map = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/webp": ".webp",
                "image/gif": ".gif",
            }

            extension = extension_map.get(mime_type, ".png")

            # Đảm bảo filename có đúng extension
            if not filename.lower().endswith(extension):
                # Thay thế extension cũ nếu có
                base_name = Path(filename).stem
                filename = f"{base_name}{extension}"

            # Full path
            file_path = output_path / filename

            # Lưu ảnh sử dụng PIL để đảm bảo format đúng
            image = Image.open(io.BytesIO(image_data))
            image.save(str(file_path))

            return SaveResult(
                success=True,
                file_path=str(file_path)
            )

        except Exception as e:
            return SaveResult(
                success=False,
                error_message=f"Lỗi lưu ảnh: {str(e)}"
            )

    @classmethod
    def save_image_from_prompt(
        cls,
        image_data: bytes,
        prompt: str,
        output_dir: str,
        index: int = 1,
        mime_type: str = "image/png"
    ) -> SaveResult:
        """
        Lưu ảnh với tên tự động từ prompt

        Args:
            image_data: Dữ liệu ảnh (bytes)
            prompt: Prompt gốc
            output_dir: Thư mục đích
            index: Số thứ tự ảnh
            mime_type: MIME type của ảnh

        Returns:
            SaveResult chứa kết quả
        """
        # Xác định extension từ mime_type
        extension_map = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/webp": "webp",
            "image/gif": "gif",
        }
        extension = extension_map.get(mime_type, "png")

        # Tạo filename
        filename = cls.generate_filename(prompt, index, extension)

        return cls.save_image(image_data, output_dir, filename, mime_type)

    @classmethod
    def save_batch(
        cls,
        images: List[Tuple[bytes, str, str]],  # (data, prompt, mime_type)
        output_dir: str
    ) -> List[SaveResult]:
        """
        Lưu nhiều ảnh cùng lúc

        Args:
            images: List của tuple (image_data, prompt, mime_type)
            output_dir: Thư mục đích

        Returns:
            List của SaveResult
        """
        results = []

        for index, (data, prompt, mime_type) in enumerate(images, 1):
            result = cls.save_image_from_prompt(
                image_data=data,
                prompt=prompt,
                output_dir=output_dir,
                index=index,
                mime_type=mime_type
            )
            results.append(result)

        return results

    @classmethod
    def get_image_info(cls, file_path: str) -> Optional[dict]:
        """
        Lấy thông tin ảnh

        Args:
            file_path: Đường dẫn file

        Returns:
            Dict chứa thông tin hoặc None nếu lỗi
        """
        try:
            with Image.open(file_path) as img:
                return {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                    "size_bytes": os.path.getsize(file_path)
                }
        except Exception:
            return None
