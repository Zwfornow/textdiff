from __future__ import annotations

"""核心服务回归测试。"""

from pathlib import Path

from backend.core.diff_service import process_file_diff, save_report, strip_markdown_text
from backend.core.models import PreprocessOptions


def test_process_file_diff_matches_current_sample(sample_dir: Path) -> None:
    """使用现有样例验证重构后的服务层统计结果。

    这个测试直接覆盖当前仓库中最有代表性的样例组合，确保服务化后仍与原始脚本
    输出的关键统计值一致。
    """

    result = process_file_diff(
        reference_path=sample_dir / "right_mac.md",
        ocr_path=sample_dir / "right_my4.md",
        options=PreprocessOptions(),
    )

    assert result.stats.reference_length == 1244
    assert result.stats.delete_count == 6
    assert result.stats.insert_count == 4
    assert result.stats.replace_count == 40
    assert result.stats.error_count == 50
    assert round(result.stats.accuracy, 2) == 95.98
    assert "OCR 文本比对报告" in result.report_html


def test_strip_markdown_text_preserves_visible_content() -> None:
    """验证 Markdown 清洗会保留可见文本而不是把整段内容抹掉。"""

    stripped = strip_markdown_text("# 标题\n[链接文字](https://example.com) 和 `代码`")

    assert "标题" in stripped
    assert "链接文字" in stripped
    assert "代码" in stripped


def test_save_report_writes_html_file(tmp_path: Path) -> None:
    """验证报告写盘逻辑会自动创建父目录并写入内容。"""

    output_path = tmp_path / "nested" / "report.html"
    saved_path = save_report("<html>ok</html>", output_path)

    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8") == "<html>ok</html>"