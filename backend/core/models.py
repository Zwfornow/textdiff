from __future__ import annotations

"""核心数据模型。

这里优先使用标准库 dataclass，保持核心层尽量轻量，避免在服务层直接耦合
接口框架或序列化库。后续接口层需要对外暴露时，再做协议模型映射。
"""

from dataclasses import dataclass


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
    diff_mode: str = "text_only"


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


@dataclass(frozen=True)
class ReportMetadata:
    """描述一份 HTML 报告的展示信息。

    source_label 用于页面显示来源名称，report_name 用于生成落盘文件名。
    先拆成单独对象，是为了后续接入 API 时既能支持文本输入，也能支持文件输入。
    """

    source_label: str
    report_name: str


@dataclass(frozen=True)
class DiffResult:
    """描述一次完整比对的服务层结果。

    服务层除了返回统计信息，还会携带清洗后的文本和 opcode，方便后续 API 层
    决定是直接返回 JSON、落盘报告，还是做更多展示加工。
    """

    reference_text: str
    ocr_text: str
    opcodes: list[tuple[str, int, int, int, int]]
    stats: DiffStats
    report_html: str