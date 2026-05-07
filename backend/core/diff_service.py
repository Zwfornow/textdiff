from __future__ import annotations

"""文本比对核心服务。

这个模块负责封装与传输层无关的业务逻辑，供命令行工具和接口层共享。
当前阶段重点保证：
1. 复用现有 Markdown 清洗、预处理、差异统计和 HTML 报告逻辑。
2. 在服务层统一“文本输入”和“文件输入”的处理入口。
3. 保持对外行为与原始脚本一致，便于做无损重构。
"""

import html
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Sequence

from jinja2 import Environment, FileSystemLoader

from .models import DiffResult, DiffStats, PreprocessOptions, ReportMetadata

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=False,
)

# 下面这组正则表达式负责把 Markdown 中常见的结构性语法剥离掉，
# 让后续 diff 尽量只关注真正的文本内容，而不是标题符号、链接语法或代码块围栏。
CODE_FENCE_LINE_RE = re.compile(r"^```[^\n]*$", re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`([^`]*)`")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
AUTOLINK_RE = re.compile(r"<((?:https?|mailto):[^>]+)>")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
LIST_MARKER_RE = re.compile(r"^\s*([-+*]|\d+[.)])\s+", re.MULTILINE)
EMPHASIS_RE = re.compile(r"(\*\*|__|\*|_)(.*?)\1", re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
INLINE_WHITESPACE_RE = re.compile(r"[ \t\r\u3000]+")

# OCR 结果里经常会混入全角/半角不统一、中文括号和英文括号混用等问题。
# 这张映射表用于在 diff 前统一常见标点，减少“视觉等价但编码不同”带来的误报。
PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "（": "(",
        "）": ")",
        "［": "[",
        "］": "]",
        "｛": "{",
        "｝": "}",
        "【": "[",
        "】": "]",
        "〈": "<",
        "〉": ">",
        "《": "<",
        "》": ">",
        "「": '"',
        "」": '"',
        "『": '"',
        "』": '"',
        "〔": "[",
        "〕": "]",
        "，": ",",
        "．": ".",
        "：": ":",
        "；": ";",
        "！": "!",
        "？": "?",
        "―": "-",
        "ー": "-",
        "—": "-",
        "～": "~",
    }
)


def strip_markdown_text(text: str) -> str:
  """对一段 Markdown 字符串做轻量清洗。

  这个函数把“读取文件”和“Markdown 语法剥离”拆开，便于后续同时支持：
  - CLI 从文件系统读取文本
  - API 直接接收文本内容
  - API 读取上传文件后二次复用同一清洗逻辑
  """

  stripped = CODE_FENCE_LINE_RE.sub("", text)
  stripped = IMAGE_RE.sub(r"\1", stripped)
  stripped = LINK_RE.sub(r"\1", stripped)
  stripped = AUTOLINK_RE.sub(r"\1", stripped)
  stripped = INLINE_CODE_RE.sub(r"\1", stripped)
  stripped = HEADING_RE.sub("", stripped)
  stripped = BLOCKQUOTE_RE.sub("", stripped)
  stripped = LIST_MARKER_RE.sub("", stripped)
  stripped = EMPHASIS_RE.sub(r"\2", stripped)
  return stripped.replace("\\", " ")


def read_and_strip_markdown(file_path: Path) -> str:
    """读取 Markdown 文件，并移除常见 Markdown 语法痕迹。

    这里不会尝试做完整 Markdown 解析，只做对 OCR 对比足够实用的轻量清洗：
    - 去掉代码块、标题、列表标记、引用标记
    - 保留图片/链接中的可见文本，去掉其外层语法
    - 去掉 HTML 标签和反斜杠转义符
    """

    text = file_path.read_text(encoding="utf-8")
    return strip_markdown_text(text)


def preprocess_text(text: str, options: PreprocessOptions) -> str:
    """对清洗后的文本做归一化，降低"仅格式不同"导致的误差。

    text_only 模式：去除所有空白，得到纯字符序列用于整体 diff。
    text_and_format 模式：保留换行，只去除行内空格/制表符，保持行结构。
    """

    normalized = text
    if options.normalize_width:
        normalized = unicodedata.normalize("NFKC", normalized)
    if options.normalize_punctuation:
        normalized = normalized.translate(PUNCTUATION_TRANSLATION)
    if not options.case_sensitive:
        normalized = normalized.casefold()
    if options.diff_mode == "text_and_format":
        lines = normalized.split("\n")
        return "\n".join(INLINE_WHITESPACE_RE.sub("", line) for line in lines)
    return WHITESPACE_RE.sub("", normalized)


def compute_diff(reference_text: str, ocr_text: str) -> tuple[list[tuple[str, int, int, int, int]], DiffStats]:
    """执行字符级 diff，并汇总统计指标。"""

    matcher = SequenceMatcher(a=reference_text, b=ocr_text, autojunk=False)
    opcodes = list(matcher.get_opcodes())

    delete_count = 0
    insert_count = 0
    replace_count = 0

    for tag, ref_start, ref_end, ocr_start, ocr_end in opcodes:
        if tag == "delete":
            delete_count += ref_end - ref_start
        elif tag == "insert":
            insert_count += ocr_end - ocr_start
        elif tag == "replace":
            replace_count += max(ref_end - ref_start, ocr_end - ocr_start)

    stats = DiffStats(
        reference_length=len(reference_text),
        delete_count=delete_count,
        insert_count=insert_count,
        replace_count=replace_count,
    )
    return opcodes, stats


def _wrap_span(text: str, css_class: str) -> str:
    """给片段包裹带样式的 span，并做 HTML 转义。"""
    return f'<span class="{css_class}">{html.escape(text)}</span>'


def _render_side(
    opcodes: Sequence[tuple[str, int, int, int, int]],
    reference_text: str,
    ocr_text: str,
) -> tuple[str, str]:
    """根据 opcode 渲染左右两栏文本。"""

    reference_parts: list[str] = []
    ocr_parts: list[str] = []

    for tag, ref_start, ref_end, ocr_start, ocr_end in opcodes:
        ref_segment = reference_text[ref_start:ref_end]
        ocr_segment = ocr_text[ocr_start:ocr_end]

        if tag == "equal":
            reference_parts.append(html.escape(ref_segment))
            ocr_parts.append(html.escape(ocr_segment))
        elif tag == "delete":
            reference_parts.append(_wrap_span(ref_segment, "delete"))
        elif tag == "insert":
            ocr_parts.append(_wrap_span(ocr_segment, "insert"))
        elif tag == "replace":
            reference_parts.append(_wrap_span(ref_segment, "replace"))
            ocr_parts.append(_wrap_span(ocr_segment, "replace"))

    return "".join(reference_parts), "".join(ocr_parts)


def _iter_change_rows(
    opcodes: Iterable[tuple[str, int, int, int, int]],
    reference_text: str,
    ocr_text: str,
) -> Iterable[str]:
    """把每个非 equal 片段转换成 HTML 表格行。"""

    for tag, ref_start, ref_end, ocr_start, ocr_end in opcodes:
        if tag == "equal":
            continue

        ref_segment = reference_text[ref_start:ref_end]
        ocr_segment = ocr_text[ocr_start:ocr_end]
        if tag == "delete":
            detail = f"缺字: {html.escape(ref_segment)}"
            row_class = "delete"
        elif tag == "insert":
            detail = f"多字: {html.escape(ocr_segment)}"
            row_class = "insert"
        else:
            detail = (
                "错字: "
                f'<span class="replace">[原:{html.escape(ref_segment)} -&gt; 错:{html.escape(ocr_segment)}]</span>'
            )
            row_class = "replace"

        yield (
            "<tr>"
            f"<td>{tag}</td>"
            f"<td>{ref_start}:{ref_end}</td>"
            f"<td>{ocr_start}:{ocr_end}</td>"
            f'<td class="{row_class}">{detail}</td>'
            "</tr>"
        )



def generate_html_report(
    reference_meta: ReportMetadata,
    ocr_meta: ReportMetadata,
    reference_text: str,
    ocr_text: str,
    opcodes: Sequence[tuple[str, int, int, int, int]],
    stats: DiffStats,
) -> str:
    """生成单文件 HTML 报告（仅对比文本模式）。"""

    reference_html, ocr_html = _render_side(opcodes, reference_text, ocr_text)
    change_rows = "".join(_iter_change_rows(opcodes, reference_text, ocr_text))
    template = _jinja_env.get_template("report_text_only.html")
    return template.render(
        ref_label=html.escape(reference_meta.source_label),
        ocr_label=html.escape(ocr_meta.source_label),
        accuracy=f"{stats.accuracy:.2f}%",
        reference_length=stats.reference_length,
        error_count=stats.error_count,
        delete_count=stats.delete_count,
        insert_count=stats.insert_count,
        replace_count=stats.replace_count,
        reference_html=reference_html,
        ocr_html=ocr_html,
        change_rows=change_rows,
    )


def _render_line_format_rows(ref_lines: list[str], ocr_lines: list[str]) -> str:
    """生成逐行对比的 HTML 表格行（text_and_format 模式）。"""

    matcher = SequenceMatcher(a=ref_lines, b=ocr_lines, autojunk=False)
    rows: list[str] = []
    ref_idx = 0
    ocr_idx = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                ref_idx += 1
                ocr_idx += 1
                ref_line = ref_lines[i1 + k]
                ocr_line = ocr_lines[j1 + k]
                if not ref_line and not ocr_line:
                    rows.append(
                        '<tr class="line-blank">'
                        f'<td class="ln">{ref_idx}</td><td class="lc"></td>'
                        f'<td class="ln">{ocr_idx}</td><td class="lc"></td>'
                        '</tr>'
                    )
                else:
                    rows.append(
                        '<tr>'
                        f'<td class="ln">{ref_idx}</td>'
                        f'<td class="lc">{html.escape(ref_line)}</td>'
                        f'<td class="ln">{ocr_idx}</td>'
                        f'<td class="lc">{html.escape(ocr_line)}</td>'
                        '</tr>'
                    )
        elif tag == "replace":
            ref_chunk = ref_lines[i1:i2]
            ocr_chunk = ocr_lines[j1:j2]
            for k in range(max(len(ref_chunk), len(ocr_chunk))):
                if k < len(ref_chunk):
                    ref_idx += 1
                    ref_line = ref_chunk[k]
                    ref_ln = str(ref_idx)
                else:
                    ref_line = ""
                    ref_ln = ""
                if k < len(ocr_chunk):
                    ocr_idx += 1
                    ocr_line = ocr_chunk[k]
                    ocr_ln = str(ocr_idx)
                else:
                    ocr_line = ""
                    ocr_ln = ""
                char_m = SequenceMatcher(a=ref_line, b=ocr_line, autojunk=False)
                ref_parts: list[str] = []
                ocr_parts: list[str] = []
                for ctag, ci1, ci2, cj1, cj2 in char_m.get_opcodes():
                    if ctag == "equal":
                        ref_parts.append(html.escape(ref_line[ci1:ci2]))
                        ocr_parts.append(html.escape(ocr_line[cj1:cj2]))
                    elif ctag == "delete":
                        ref_parts.append(
                            f'<span class="delete">{html.escape(ref_line[ci1:ci2])}</span>'
                        )
                    elif ctag == "insert":
                        ocr_parts.append(
                            f'<span class="insert">{html.escape(ocr_line[cj1:cj2])}</span>'
                        )
                    else:
                        ref_parts.append(
                            f'<span class="replace">{html.escape(ref_line[ci1:ci2])}</span>'
                        )
                        ocr_parts.append(
                            f'<span class="replace">{html.escape(ocr_line[cj1:cj2])}</span>'
                        )
                rows.append(
                    '<tr class="line-changed">'
                    f'<td class="ln">{ref_ln}</td>'
                    f'<td class="lc">{"".join(ref_parts)}</td>'
                    f'<td class="ln">{ocr_ln}</td>'
                    f'<td class="lc">{"".join(ocr_parts)}</td>'
                    '</tr>'
                )
        elif tag == "delete":
            for k in range(i2 - i1):
                ref_idx += 1
                rows.append(
                    '<tr class="line-changed">'
                    f'<td class="ln">{ref_idx}</td>'
                    f'<td class="lc"><span class="delete">{html.escape(ref_lines[i1 + k])}</span></td>'
                    '<td class="ln"></td><td class="lc"></td>'
                    '</tr>'
                )
        elif tag == "insert":
            for k in range(j2 - j1):
                ocr_idx += 1
                rows.append(
                    '<tr class="line-changed">'
                    '<td class="ln"></td><td class="lc"></td>'
                    f'<td class="ln">{ocr_idx}</td>'
                    f'<td class="lc"><span class="insert">{html.escape(ocr_lines[j1 + k])}</span></td>'
                    '</tr>'
                )

    return "\n".join(rows)


def generate_html_report_line_format(
    reference_meta: ReportMetadata,
    ocr_meta: ReportMetadata,
    reference_text: str,
    ocr_text: str,
    stats: DiffStats,
) -> str:
    """生成逐行对比的单文件 HTML 报告（text_and_format 模式）。"""

    ref_lines = reference_text.split("\n")
    ocr_lines = ocr_text.split("\n")
    line_rows = _render_line_format_rows(ref_lines, ocr_lines)
    template = _jinja_env.get_template("report_line_format.html")
    return template.render(
        ref_label=html.escape(reference_meta.source_label),
        ocr_label=html.escape(ocr_meta.source_label),
        accuracy=f"{stats.accuracy:.2f}%",
        reference_length=stats.reference_length,
        error_count=stats.error_count,
        delete_count=stats.delete_count,
        insert_count=stats.insert_count,
        replace_count=stats.replace_count,
        line_rows=line_rows,
    )


def process_text_diff(
    reference_raw: str,
    ocr_raw: str,
    options: PreprocessOptions,
    reference_meta: ReportMetadata,
    ocr_meta: ReportMetadata,
) -> DiffResult:
    """统一处理一对文本输入并返回完整比对结果。"""

    reference_text = preprocess_text(reference_raw, options)
    ocr_text = preprocess_text(ocr_raw, options)

    if options.diff_mode == "text_and_format":
        # 统计用去掉换行的纯字符序列，HTML 用保留行结构的文本
        ref_flat = reference_text.replace("\n", "")
        ocr_flat = ocr_text.replace("\n", "")
        opcodes, stats = compute_diff(ref_flat, ocr_flat)
        report_html = generate_html_report_line_format(
            reference_meta, ocr_meta, reference_text, ocr_text, stats
        )
    else:
        opcodes, stats = compute_diff(reference_text, ocr_text)
        report_html = generate_html_report(
            reference_meta, ocr_meta, reference_text, ocr_text, opcodes, stats
        )

    return DiffResult(
        reference_text=reference_text,
        ocr_text=ocr_text,
        opcodes=opcodes,
        stats=stats,
        report_html=report_html,
    )

def process_file_diff(
    reference_path: Path,
    ocr_path: Path,
    options: PreprocessOptions,
) -> DiffResult:
    """处理文件输入。

    这里保留对 UTF-8 文本文件的直接读取逻辑，方便原始 CLI 和后续上传文件
    的 API 入口共用同一个服务函数。
    """

    reference_raw = read_and_strip_markdown(reference_path)
    ocr_raw = read_and_strip_markdown(ocr_path)
    return process_text_diff(
        reference_raw=reference_raw,
        ocr_raw=ocr_raw,
        options=options,
        reference_meta=ReportMetadata(
            source_label=str(reference_path),
            report_name=reference_path.stem,
        ),
        ocr_meta=ReportMetadata(
            source_label=str(ocr_path),
            report_name=ocr_path.stem,
        ),
    )


def save_report(report_html: str, output_path: Path) -> Path:
    """把 HTML 报告写入目标路径，并确保父目录存在。"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_html, encoding="utf-8")
    return output_path