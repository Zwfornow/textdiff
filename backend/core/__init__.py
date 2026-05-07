"""核心能力包。

这里放与传输协议无关的纯业务逻辑，供命令行工具和接口层共同复用。
"""

from .diff_service import (
    compute_diff,
    generate_html_report,
    preprocess_text,
    process_text_diff,
    read_and_strip_markdown,
    save_report,
    strip_markdown_text,
)
from .models import DiffResult, DiffStats, PreprocessOptions, ReportMetadata

__all__ = [
    "compute_diff",
    "generate_html_report",
    "preprocess_text",
    "process_text_diff",
    "read_and_strip_markdown",
    "save_report",
    "strip_markdown_text",
    "DiffResult",
    "DiffStats",
    "PreprocessOptions",
    "ReportMetadata",
]