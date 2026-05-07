from __future__ import annotations

"""OCR Markdown 文本比对工具。

当前文件保留命令行入口职责，但核心业务逻辑已经下沉到 backend.core。
这样做的目的有两个：
1. 保持现有 CLI 使用方式不变，避免影响当前脚本用户。
2. 为后续 FastAPI 接口复用同一套 diff 服务提供稳定入口。
"""

import argparse
from pathlib import Path

from backend.core.diff_service import process_file_diff, save_report
from backend.core.models import PreprocessOptions


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

  # CLI 入口现在直接调用服务层，保证命令行和 Web API 后续共用同一套核心实现。
  result = process_file_diff(
    reference_path=args.reference,
    ocr_path=args.ocr,
    options=preprocess_options,
  )
  save_report(result.report_html, args.output)

  # 终端输出适合快速查看，HTML 报告适合后续逐段定位问题。
  print(f"参考文本总字数: {result.stats.reference_length}")
  print(f"错误字符数: {result.stats.error_count}")
  print(f"缺字: {result.stats.delete_count}")
  print(f"多字: {result.stats.insert_count}")
  print(f"错字: {result.stats.replace_count}")
  print(f"准确率: {result.stats.accuracy:.2f}%")
  print(f"HTML 报告: {args.output}")
  return 0


if __name__ == "__main__":
    raise SystemExit(main())