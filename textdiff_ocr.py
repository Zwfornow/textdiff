from __future__ import annotations

"""OCR Markdown 文本比对工具。

脚本目标：
1. 读取两份 Markdown 文本。
2. 去掉 Markdown 语法和无关空白，得到更稳定的纯文本。
3. 基于字符级 diff 统计缺字、多字、错字。
4. 输出终端统计结果，并生成可视化 HTML 报告。

这里的“准确率”口径为：
  (1 - 错误字符数 / 参考文本总字数) * 100%

其中错误字符数 = 缺字数 + 多字数 + 错字数。
"""

import argparse
import html
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Sequence


# 下面这组正则表达式负责把 Markdown 中常见的结构性语法剥离掉，
# 让后续 diff 尽量只关注真正的文本内容，而不是标题符号、链接语法或代码块围栏。
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
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

# OCR 结果里经常会混入全角/半角不统一、中文括号和英文括号混用等问题。
# 这张映射表用于在 diff 前统一常见标点，减少“视觉等价但编码不同”带来的误报。
PUNCTUATION_TRANSLATION = str.maketrans(
  {
    "（": "(",
    "）": ")",
    "［": "[",
    "］": "]",
    "【": "[",
    "】": "]",
    "｛": "{",
    "｝": "}",
    "〈": "<",
    "〉": ">",
    "《": "<",
    "》": ">",
    "「": "\"",
    "」": "\"",
    "『": "\"",
    "』": "\"",
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


@dataclass(frozen=True)
class PreprocessOptions:
  """控制文本预处理策略。

  默认策略偏向“比较内容是否一致”，而不是比较排版是否完全一致：
  - 统一全角/半角
  - 统一常见标点
  - 英文字母默认不区分大小写
  """

  normalize_width: bool = True
  normalize_punctuation: bool = True
  case_sensitive: bool = False


@dataclass(frozen=True)
class DiffStats:
    """保存 diff 统计结果。

    reference_length 以参考文本为基准，因为准确率按参考文本总字数计算。
    replace_count 采用两段长度的较大值，表示一次替换操作造成的错误规模。
    """

    reference_length: int
    delete_count: int
    insert_count: int
    replace_count: int

    @property
    def error_count(self) -> int:
        """返回总错误字符数。"""
        return self.delete_count + self.insert_count + self.replace_count

    @property
    def accuracy(self) -> float:
        """按参考文本长度计算准确率。"""
        if self.reference_length == 0:
            return 100.0 if self.error_count == 0 else 0.0
        return max(0.0, (1 - (self.error_count / self.reference_length)) * 100)


def read_and_strip_markdown(file_path: Path) -> str:
    """读取 Markdown 文件，并移除常见 Markdown 语法痕迹。

    这里不会尝试做完整 Markdown 解析，只做对 OCR 对比足够实用的轻量清洗：
    - 去掉代码块、标题、列表标记、引用标记
    - 保留图片/链接中的可见文本，去掉其外层语法
    - 去掉 HTML 标签和反斜杠转义符
    """

    text = file_path.read_text(encoding="utf-8")
    # 代码块通常不是 OCR 正文的一部分，直接整体移除，避免大段符号污染比对结果。
    text = CODE_BLOCK_RE.sub(" ", text)
    # 图片和链接保留中括号里的可见文本，丢弃 URL 等附加信息。
    text = IMAGE_RE.sub(r"\1", text)
    text = LINK_RE.sub(r"\1", text)
    text = AUTOLINK_RE.sub(r"\1", text)
    # 行内代码保留内容本身，只去掉包裹它的反引号。
    text = INLINE_CODE_RE.sub(r"\1", text)
    text = HEADING_RE.sub("", text)
    text = BLOCKQUOTE_RE.sub("", text)
    text = LIST_MARKER_RE.sub("", text)
    text = EMPHASIS_RE.sub(r"\2", text)
    text = HTML_TAG_RE.sub(" ", text)
    # Markdown 转义符本身不参与语义，统一替换为空格，交给后续空白压缩处理。
    text = text.replace("\\", " ")
    return text


def preprocess_text(text: str, options: PreprocessOptions) -> str:
  """对清洗后的文本做归一化，降低“仅格式不同”导致的误差。

  这一层处理解决的是 OCR 常见噪声，而不是内容纠错：
  - Unicode NFKC 归一化：统一全角/半角、兼容字符等表示
  - 标点归一化：统一常见中英文括号、引号和标点
  - 大小写折叠：默认将 A/a 视为一致
  - 压缩并移除所有空白：避免换行、缩进、空格对字符级 diff 造成干扰
  """

  normalized = text
  if options.normalize_width:
    normalized = unicodedata.normalize("NFKC", normalized)
  if options.normalize_punctuation:
    normalized = normalized.translate(PUNCTUATION_TRANSLATION)
  if not options.case_sensitive:
    normalized = normalized.casefold()
  return WHITESPACE_RE.sub("", normalized)


def compute_diff(reference_text: str, ocr_text: str) -> tuple[list[tuple[str, int, int, int, int]], DiffStats]:
  """执行字符级 diff，并汇总统计指标。

  SequenceMatcher 会返回一组 opcode，每个 opcode 描述一段区间的关系：
  - equal: 两侧一致
  - delete: OCR 少字，参考文本中有而 OCR 中没有
  - insert: OCR 多字，OCR 中有而参考文本中没有
  - replace: 两侧都有内容，但字符不同
  """

  matcher = SequenceMatcher(a=reference_text, b=ocr_text, autojunk=False)
  opcodes = list(matcher.get_opcodes())

  delete_count = 0
  insert_count = 0
  replace_count = 0

  for tag, ref_start, ref_end, ocr_start, ocr_end in opcodes:
    # delete/insert 直接按对应片段长度累计。
    # replace 使用较长一侧计数，是为了把一次替换视为一个完整错误片段。
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


def _render_side(opcodes: Sequence[tuple[str, int, int, int, int]], reference_text: str, ocr_text: str) -> tuple[str, str]:
  """根据 opcode 渲染左右两栏文本。

  左栏展示参考文本，右栏展示 OCR 文本。
  不同 opcode 会被映射成不同高亮样式，方便从视觉上快速定位错误位置。
  """

  reference_parts: list[str] = []
  ocr_parts: list[str] = []

  for tag, ref_start, ref_end, ocr_start, ocr_end in opcodes:
    ref_segment = reference_text[ref_start:ref_end]
    ocr_segment = ocr_text[ocr_start:ocr_end]

    if tag == "equal":
      # 相同片段只做转义，不做额外标记。
      reference_parts.append(html.escape(ref_segment))
      ocr_parts.append(html.escape(ocr_segment))
    elif tag == "delete":
      # 缺字只会出现在参考文本侧。
      reference_parts.append(_wrap_span(ref_segment, "delete"))
    elif tag == "insert":
      # 多字只会出现在 OCR 文本侧。
      ocr_parts.append(_wrap_span(ocr_segment, "insert"))
    elif tag == "replace":
      # 错字需要在两侧都高亮，便于对照原字与 OCR 结果。
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
        f"<span class=\"replace\">[原:{html.escape(ref_segment)} -&gt; 错:{html.escape(ocr_segment)}]</span>"
      )
      row_class = "replace"

    yield (
      "<tr>"
      f"<td>{tag}</td>"
      f"<td>{ref_start}:{ref_end}</td>"
      f"<td>{ocr_start}:{ocr_end}</td>"
      f"<td class=\"{row_class}\">{detail}</td>"
      "</tr>"
    )


def generate_html_report(
    reference_path: Path,
    ocr_path: Path,
    reference_text: str,
    ocr_text: str,
    opcodes: Sequence[tuple[str, int, int, int, int]],
    stats: DiffStats,
) -> str:
    """生成单文件 HTML 报告。

    报告包含三部分：
    - 汇总指标：准确率、参考文本总字数、错误字符数、缺字/多字/错字数量
    - 左右对照视图：直接高亮原文与 OCR 文本中的差异位置
    - 差异明细表：列出每个差异片段在两侧文本中的区间和内容
    """

    reference_html, ocr_html = _render_side(opcodes, reference_text, ocr_text)
    change_rows = "".join(_iter_change_rows(opcodes, reference_text, ocr_text))
    return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <title>OCR 文本比对报告</title>
  <style>
    :root {{
      --bg: #f7f4ee;
      --panel: #fffdf8;
      --border: #d8ccb8;
      --text: #2d241b;
      --muted: #6c5e50;
      --delete: #ffcccc;
      --insert: #ccffcc;
      --replace: #ffffcc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 24px;
      font-family: "Iowan Old Style", "Hiragino Mincho ProN", serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(184, 157, 121, 0.18), transparent 30%),
        linear-gradient(180deg, #f5efe4 0%, var(--bg) 100%);
    }}
    .container {{ max-width: 1400px; margin: 0 auto; }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 12px 30px rgba(84, 63, 38, 0.08);
    }}
    h1, h2 {{ margin-top: 0; }}
    .meta {{ color: var(--muted); margin-bottom: 18px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 20px 0 24px;
    }}
    .card {{
      padding: 14px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.7);
    }}
    .label {{ display: block; font-size: 13px; color: var(--muted); margin-bottom: 8px; }}
    .value {{ font-size: 28px; font-weight: 700; }}
    .legend {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }}
    .legend span {{ padding: 6px 10px; border-radius: 999px; border: 1px solid var(--border); }}
    .compare {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
    .text-box {{ border: 1px solid var(--border); border-radius: 14px; padding: 16px; background: #fff; }}
    .text-box h2 {{ font-size: 18px; margin-bottom: 12px; }}
    .text-content {{
      white-space: pre-wrap;
      word-break: break-all;
      line-height: 1.8;
      font-size: 16px;
      min-height: 240px;
    }}
    .delete {{ background-color: var(--delete); text-decoration: line-through; }}
    .insert {{ background-color: var(--insert); }}
    .replace {{ background-color: var(--replace); }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    th, td {{ border: 1px solid var(--border); padding: 10px; vertical-align: top; }}
    th {{ background: #efe5d5; text-align: left; }}
    @media (max-width: 900px) {{
      body {{ padding: 16px; }}
      .compare {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class=\"container\">
    <div class=\"panel\">
      <h1>OCR 文本比对报告</h1>
      <div class=\"meta\">参考文本: {html.escape(str(reference_path))}<br />OCR 文本: {html.escape(str(ocr_path))}</div>
      <div class=\"summary\">
        <div class=\"card\"><span class=\"label\">准确率</span><span class=\"value\">{stats.accuracy:.2f}%</span></div>
        <div class=\"card\"><span class=\"label\">参考文本总字数</span><span class=\"value\">{stats.reference_length}</span></div>
        <div class=\"card\"><span class=\"label\">错误字符数</span><span class=\"value\">{stats.error_count}</span></div>
        <div class=\"card\"><span class=\"label\">缺字 / 多字 / 错字</span><span class=\"value\">{stats.delete_count} / {stats.insert_count} / {stats.replace_count}</span></div>
      </div>
      <div class=\"legend\">
        <span class=\"delete\">缺字</span>
        <span class=\"insert\">多字</span>
        <span class=\"replace\">错字</span>
      </div>
      <div class=\"compare\">
        <section class=\"text-box\">
          <h2>参考文本纯文本</h2>
          <div class=\"text-content\">{reference_html}</div>
        </section>
        <section class=\"text-box\">
          <h2>OCR 文本纯文本</h2>
          <div class=\"text-content\">{ocr_html}</div>
        </section>
      </div>
      <h2 style=\"margin-top: 24px;\">差异明细</h2>
      <table>
        <thead>
          <tr>
            <th>类型</th>
            <th>参考文本位置</th>
            <th>OCR 文本位置</th>
            <th>内容</th>
          </tr>
        </thead>
        <tbody>{change_rows}</tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
  """解析命令行参数。"""

  parser = argparse.ArgumentParser(description="比较两个 Markdown 文件，输出准确率和 HTML 差异报告。")
  parser.add_argument("reference", type=Path, help="参考 Markdown 文件路径")
  parser.add_argument("ocr", type=Path, help="OCR Markdown 文件路径")
  parser.add_argument(
    "-o",
    "--output",
    type=Path,
    default=Path("ocr_diff_report.html"),
    help="输出 HTML 报告路径，默认: ocr_diff_report.html",
  )
  parser.add_argument(
    "--case-sensitive",
    action="store_true",
    help="区分英文字母大小写。默认关闭，即 A 和 a 不计为错字。",
  )
  parser.add_argument(
    "--no-normalize-width",
    action="store_true",
    help="关闭 Unicode 宽度归一化。默认会统一全角/半角字符后再比对。",
  )
  parser.add_argument(
    "--no-normalize-punctuation",
    action="store_true",
    help="关闭常见中英文括号和标点归一化。默认会统一 [] ［］ () （） 等样式后再比对。",
  )
  return parser.parse_args()


def main() -> int:
  """串联整个处理流程，并把结果写到终端和 HTML 文件。"""

  args = parse_args()
  preprocess_options = PreprocessOptions(
    normalize_width=not args.no_normalize_width,
    normalize_punctuation=not args.no_normalize_punctuation,
    case_sensitive=args.case_sensitive,
  )

  # 先做 Markdown 语法清洗，再做归一化，这样可以避免把语法符号带入 diff。
  reference_raw = read_and_strip_markdown(args.reference)
  ocr_raw = read_and_strip_markdown(args.ocr)
  reference_text = preprocess_text(reference_raw, preprocess_options)
  ocr_text = preprocess_text(ocr_raw, preprocess_options)

  # 生成统计结果和可视化报告。
  opcodes, stats = compute_diff(reference_text, ocr_text)
  report_html = generate_html_report(args.reference, args.ocr, reference_text, ocr_text, opcodes, stats)
  args.output.write_text(report_html, encoding="utf-8")

  # 终端输出适合快速查看，HTML 报告适合后续逐段定位问题。
  print(f"参考文本总字数: {stats.reference_length}")
  print(f"错误字符数: {stats.error_count}")
  print(f"缺字: {stats.delete_count}")
  print(f"多字: {stats.insert_count}")
  print(f"错字: {stats.replace_count}")
  print(f"准确率: {stats.accuracy:.2f}%")
  print(f"HTML 报告: {args.output}")
  return 0


if __name__ == "__main__":
    raise SystemExit(main())