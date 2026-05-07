from __future__ import annotations

"""路由实现。

当前阶段重点提供最小可用接口：
1. 健康检查接口，用于本地联调和部署存活检查。
2. 单次文本比对接口，支持 JSON 文本输入和 multipart 文件上传。
"""

import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, status

from backend.api.schemas import (
    DiffResponse,
    DiffStatsResponse,
    ErrorResponse,
    PreprocessOptionsPayload,
    TextDiffRequest,
)
from backend.config import Settings
from backend.core.diff_service import process_text_diff, save_report, strip_markdown_text
from backend.core.models import PreprocessOptions, ReportMetadata


router = APIRouter()


def _get_settings(request: Request) -> Settings:
    """从请求上下文读取应用配置。"""

    return request.scope["settings"]


def _build_preprocess_options(payload: PreprocessOptionsPayload) -> PreprocessOptions:
    """把 API 层请求模型转换成核心层 dataclass。"""

    return PreprocessOptions(
        normalize_width=payload.normalize_width,
        normalize_punctuation=payload.normalize_punctuation,
        case_sensitive=payload.case_sensitive,
        diff_mode=payload.diff_mode,
    )


async def _read_upload_text(file: UploadFile, settings: Settings) -> str:
    """读取上传文件并按 UTF-8 解码。

    当前限制为一次性读入内存，这样实现最简单，也足够支持首期的中小文本比对。
    如果后续文件体积增大，再把这里替换成流式处理或更严格的配额控制。
    """

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"上传文件为空: {file.filename or 'unknown'}",
        )
    if len(content) > settings.max_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"上传文件超过大小限制: {file.filename or 'unknown'}",
        )
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"文件不是有效的 UTF-8 文本: {file.filename or 'unknown'}",
        ) from exc


def _build_report_filename(reference_name: str, ocr_name: str) -> str:
    """生成唯一且可读的报告文件名。"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 取词干，替换空格，移除 URL 不安全字符（保留中文、字母、数字、连字符、下划线），去开头下划线，限长20字
    def _safe(name: str) -> str:
        stem = Path(name).stem.replace(" ", "_")
        stem = re.sub(r"[^\w\u4e00-\u9fff\-]", "", stem)
        stem = stem.lstrip("_")[:20]
        return stem or "unknown"

    safe_reference = _safe(reference_name)
    safe_ocr = _safe(ocr_name)
    return f"diff_{timestamp}_{safe_reference}_vs_{safe_ocr}.html"


def _build_response(result, report_url: str) -> DiffResponse:
    """把核心层结果转换成 API 响应。"""

    return DiffResponse(
        reference_text=result.reference_text,
        ocr_text=result.ocr_text,
        report_url=report_url,
        stats=DiffStatsResponse(
            reference_length=result.stats.reference_length,
            delete_count=result.stats.delete_count,
            insert_count=result.stats.insert_count,
            replace_count=result.stats.replace_count,
            error_count=result.stats.error_count,
            accuracy=round(result.stats.accuracy, 2),
        ),
    )


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    """返回后端服务健康状态。"""

    settings = _get_settings(request)
    return {"status": "ok", "version": settings.app_version}


@router.post(
    "/diff",
    response_model=DiffResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def diff(request: Request) -> DiffResponse:
    """统一处理文本输入和文件上传。

    这里显式检查 Content-Type，而不是拆成两个不同路径，是为了让前端始终只面对
    一个对比接口。后续如果接口变复杂，再考虑按输入模式拆分。
    """

    settings = _get_settings(request)
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        payload = TextDiffRequest.model_validate(await request.json())
        if not payload.reference.strip() or not payload.ocr.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文本输入不能为空")
        result = process_text_diff(
            reference_raw=strip_markdown_text(payload.reference),
            ocr_raw=strip_markdown_text(payload.ocr),
            options=_build_preprocess_options(payload.preprocess_options),
            reference_meta=ReportMetadata(
                source_label=payload.reference_label,
                report_name=payload.reference_label,
            ),
            ocr_meta=ReportMetadata(
                source_label=payload.ocr_label,
                report_name=payload.ocr_label,
            ),
        )
        ref_name = payload.reference_report_name or payload.reference_label
        ocr_name = payload.ocr_report_name or payload.ocr_label
        report_filename = _build_report_filename(ref_name, ocr_name)
    elif content_type.startswith("multipart/form-data"):
        form = await request.form()
        reference_file = form.get("reference_file")
        ocr_file = form.get("ocr_file")
        if reference_file is None or ocr_file is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传 reference_file 和 ocr_file")
        if not hasattr(reference_file, "read") or not hasattr(ocr_file, "read"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传字段格式不正确")

        options_value = form.get("preprocess_options")
        if options_value:
            if not isinstance(options_value, str):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="preprocess_options 必须是 JSON 字符串")
            options_payload = PreprocessOptionsPayload.model_validate(json.loads(options_value))
        else:
            options_payload = PreprocessOptionsPayload()

        reference_text = await _read_upload_text(reference_file, settings)
        ocr_text = await _read_upload_text(ocr_file, settings)
        result = process_text_diff(
            reference_raw=strip_markdown_text(reference_text),
            ocr_raw=strip_markdown_text(ocr_text),
            options=_build_preprocess_options(options_payload),
            reference_meta=ReportMetadata(
                source_label=reference_file.filename or "reference_upload",
                report_name=reference_file.filename or "reference_upload",
            ),
            ocr_meta=ReportMetadata(
                source_label=ocr_file.filename or "ocr_upload",
                report_name=ocr_file.filename or "ocr_upload",
            ),
        )
        report_filename = _build_report_filename(
            reference_file.filename or "reference_upload",
            ocr_file.filename or "ocr_upload",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="仅支持 application/json 或 multipart/form-data",
        )

    report_path = settings.report_dir / report_filename
    save_report(result.report_html, report_path)
    report_url = f"{settings.report_mount_path}/{report_filename}"
    return _build_response(result, report_url)


@router.get("/reports")
async def list_reports(request: Request) -> dict:
    """列出所有已生成的报告文件，按创建时间倒序排列。"""

    settings = _get_settings(request)
    report_dir = settings.report_dir
    reports = []
    if report_dir.exists():
        files = sorted(report_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files:
            reports.append(
                {
                    "filename": f.name,
                    "url": f"{settings.report_mount_path}/{f.name}",
                    "created_at": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
    return {"reports": reports}