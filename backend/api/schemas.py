from __future__ import annotations

"""对外请求与响应模型。

核心层继续使用 dataclass 保持纯业务逻辑；接口层使用 Pydantic，负责：
1. 对外暴露稳定的请求/响应结构。
2. 为接口文档自动生成字段说明。
3. 在进入业务层前做基础格式校验。
"""

from pydantic import BaseModel, Field


class PreprocessOptionsPayload(BaseModel):
    """前端可配置的预处理选项。"""

    normalize_width: bool = Field(default=True, description="是否统一全角和半角字符")
    normalize_punctuation: bool = Field(default=True, description="是否统一常见中英文括号和标点")
    case_sensitive: bool = Field(default=False, description="是否区分英文字母大小写")
    diff_mode: str = Field(default="text_only", description="对比模式：text_only 仅对比文本，text_and_format 对比文本与格式（逐行）")


class TextDiffRequest(BaseModel):
    """文本输入模式下的请求体。"""

    reference: str = Field(..., description="参考文本内容")
    ocr: str = Field(..., description="对比文本内容")
    reference_label: str = Field(default="参考文本", description="报告中展示的参考来源名称")
    ocr_label: str = Field(default="对比文本", description="报告中展示的对比来源名称")
    reference_report_name: str = Field(default="", description="报告文件名中的参考端标识（空则回退到 reference_label）")
    ocr_report_name: str = Field(default="", description="报告文件名中的对比端标识（空则回退到 ocr_label）")
    preprocess_options: PreprocessOptionsPayload = Field(
        default_factory=PreprocessOptionsPayload,
        description="文本清洗与归一化选项",
    )


class DiffStatsResponse(BaseModel):
    """响应中的统计信息。"""

    reference_length: int
    delete_count: int
    insert_count: int
    replace_count: int
    error_count: int
    accuracy: float


class DiffResponse(BaseModel):
    """单次 OCR diff 响应。"""

    reference_text: str = Field(..., description="清洗并归一化后的参考文本")
    ocr_text: str = Field(..., description="清洗并归一化后的 OCR 文本")
    stats: DiffStatsResponse
    report_url: str = Field(..., description="生成的 HTML 报告访问地址")


class ErrorResponse(BaseModel):
    """统一错误响应结构。"""

    error: str
    detail: str