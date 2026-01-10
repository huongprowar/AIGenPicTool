"""
Prompt Parser - Xử lý parse image prompts từ ChatGPT response
Hỗ trợ nhiều format khác nhau
"""

import re
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class ParsedPrompt:
    """Data class chứa thông tin prompt đã parse"""
    index: int           # Số thứ tự (bắt đầu từ 1)
    content: str         # Nội dung prompt
    original_text: str   # Text gốc trước khi parse


class PromptParser:
    """
    Parser để tách các image prompt từ ChatGPT response
    Hỗ trợ nhiều format:
    - Image Prompt 1: content
    - Prompt 1: content
    - 1. content
    - 1) content
    - **Prompt 1:** content
    - [1] content
    """

    # Các pattern regex để match prompt
    PATTERNS = [
        # Pattern 1: "Image Prompt 1: content" hoặc "Image Prompt 1 - content"
        r'(?:Image\s+)?Prompt\s*(\d+)\s*[:\-]\s*(.+?)(?=(?:(?:Image\s+)?Prompt\s*\d+\s*[:\-])|$)',

        # Pattern 2: "1. content" (numbered list với dấu chấm)
        r'^(\d+)\.\s+(.+?)(?=^\d+\.|$)',

        # Pattern 3: "1) content" (numbered list với ngoặc đơn)
        r'^(\d+)\)\s+(.+?)(?=^\d+\)|$)',

        # Pattern 4: "**Prompt 1:** content" (Markdown bold)
        r'\*\*(?:Image\s+)?Prompt\s*(\d+)[:\*]+\s*(.+?)(?=\*\*(?:Image\s+)?Prompt|$)',

        # Pattern 5: "[1] content" (bracket notation)
        r'\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)',

        # Pattern 6: "Prompt: content" (single prompt without number)
        r'(?:Image\s+)?Prompt\s*[:\-]\s*(.+)',
    ]

    @classmethod
    def parse(cls, text: str) -> List[ParsedPrompt]:
        """
        Parse text và trả về danh sách các prompt

        Args:
            text: Response text từ ChatGPT

        Returns:
            List các ParsedPrompt đã extract được
        """
        if not text or not text.strip():
            return []

        # Chuẩn hóa text
        text = text.strip()

        # Thử từng pattern
        for pattern in cls.PATTERNS[:-1]:  # Bỏ qua pattern cuối (single prompt)
            results = cls._try_pattern(text, pattern)
            if results:
                return results

        # Thử pattern single prompt
        single_match = re.search(cls.PATTERNS[-1], text, re.IGNORECASE | re.DOTALL)
        if single_match:
            content = single_match.group(1).strip()
            return [ParsedPrompt(index=1, content=content, original_text=text)]

        # Fallback: Xử lý theo dòng nếu không match pattern nào
        return cls._parse_by_lines(text)

    @classmethod
    def _try_pattern(cls, text: str, pattern: str) -> List[ParsedPrompt]:
        """
        Thử match text với một pattern cụ thể

        Args:
            text: Text cần parse
            pattern: Regex pattern

        Returns:
            List các ParsedPrompt nếu match, rỗng nếu không
        """
        flags = re.IGNORECASE | re.MULTILINE | re.DOTALL
        matches = list(re.finditer(pattern, text, flags))

        if not matches:
            return []

        results = []
        for match in matches:
            groups = match.groups()

            if len(groups) >= 2:
                # Pattern có số thứ tự
                try:
                    index = int(groups[0])
                except (ValueError, TypeError):
                    index = len(results) + 1
                content = groups[1].strip()
            else:
                # Pattern không có số thứ tự
                index = len(results) + 1
                content = groups[0].strip()

            # Làm sạch content
            content = cls._clean_content(content)

            if content:
                results.append(ParsedPrompt(
                    index=index,
                    content=content,
                    original_text=match.group(0)
                ))

        return results

    @classmethod
    def _parse_by_lines(cls, text: str) -> List[ParsedPrompt]:
        """
        Fallback: Parse theo từng dòng
        Mỗi dòng không rỗng là một prompt

        Args:
            text: Text cần parse

        Returns:
            List các ParsedPrompt
        """
        results = []
        lines = text.split('\n')

        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Bỏ qua dòng rỗng hoặc quá ngắn
            if not line or len(line) < 10:
                continue

            # Bỏ qua các dòng là tiêu đề hoặc ghi chú
            if cls._is_header_or_note(line):
                continue

            # Làm sạch dòng
            content = cls._clean_line(line)

            if content and len(content) >= 10:
                results.append(ParsedPrompt(
                    index=len(results) + 1,
                    content=content,
                    original_text=line
                ))

        return results

    @classmethod
    def _clean_content(cls, content: str) -> str:
        """
        Làm sạch nội dung prompt

        Args:
            content: Nội dung cần làm sạch

        Returns:
            Nội dung đã làm sạch
        """
        # Loại bỏ markdown formatting
        content = re.sub(r'\*\*|\*|__|_', '', content)

        # Loại bỏ ký tự xuống dòng thừa
        content = re.sub(r'\n+', ' ', content)

        # Loại bỏ khoảng trắng thừa
        content = re.sub(r'\s+', ' ', content)

        return content.strip()

    @classmethod
    def _clean_line(cls, line: str) -> str:
        """
        Làm sạch một dòng text

        Args:
            line: Dòng cần làm sạch

        Returns:
            Dòng đã làm sạch
        """
        # Loại bỏ số thứ tự đầu dòng
        line = re.sub(r'^[\d]+[.\):\-]\s*', '', line)

        # Loại bỏ prefix "Prompt:", "Image Prompt:", etc.
        line = re.sub(r'^(?:Image\s+)?Prompt\s*[:\-]\s*', '', line, flags=re.IGNORECASE)

        # Loại bỏ markdown
        line = re.sub(r'\*\*|\*|__|_', '', line)

        # Loại bỏ quotes
        line = re.sub(r'^["\']|["\']$', '', line)

        return line.strip()

    @classmethod
    def _is_header_or_note(cls, line: str) -> bool:
        """
        Kiểm tra xem dòng có phải là tiêu đề hoặc ghi chú không

        Args:
            line: Dòng cần kiểm tra

        Returns:
            True nếu là tiêu đề/ghi chú
        """
        # Các pattern cho tiêu đề/ghi chú
        header_patterns = [
            r'^#+\s',                    # Markdown header: # Header
            r'^Here are',                # "Here are the prompts..."
            r'^Below are',               # "Below are..."
            r'^I\'ve created',           # "I've created..."
            r'^These prompts',           # "These prompts..."
            r'^Note:',                   # "Note:..."
            r'^\*\*Note',                # "**Note..."
            r'^---+$',                   # Separator line
            r'^===+$',                   # Separator line
        ]

        for pattern in header_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True

        return False

    @classmethod
    def extract_prompt_count(cls, text: str) -> int:
        """
        Đếm số lượng prompt trong text

        Args:
            text: Text cần đếm

        Returns:
            Số lượng prompt
        """
        prompts = cls.parse(text)
        return len(prompts)


# Convenience functions
def parse_prompts(text: str) -> List[ParsedPrompt]:
    """Hàm tiện ích để parse prompts"""
    return PromptParser.parse(text)


def get_prompt_contents(text: str) -> List[str]:
    """Lấy danh sách nội dung prompt (không có metadata)"""
    prompts = PromptParser.parse(text)
    return [p.content for p in prompts]
