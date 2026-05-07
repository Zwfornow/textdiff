from __future__ import annotations

"""后端运行配置。

当前阶段先使用标准库读取环境变量，避免过早引入额外配置依赖。
等后续配置项继续增多，再考虑切换到更完整的设置管理方案。
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """集中管理后端运行时配置。

    这些字段优先覆盖当前第一阶段真正会用到的运行边界：
    - API 标题与版本，用于接口文档与健康检查
    - 报告目录，用于保存 HTML 差异报告
    - CORS 白名单，用于本地前后端分端口开发
    - 最大文件大小，用于避免超大文本拖垮服务
    """

    app_name: str = "OCR Diff API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    report_mount_path: str = "/reports"
    report_dir: Path = Path("backend/reports")
    max_file_size: int = 5 * 1024 * 1024
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")


def get_settings() -> Settings:
    """从环境变量构造配置对象。

    这里保持逻辑尽量直白，方便后续部署到服务器时通过环境变量覆盖。
    report_dir 如果传入相对路径，则默认相对于项目根目录解析。
    """

    report_dir_value = os.getenv("REPORT_DIR", "backend/reports")
    settings = Settings(
        app_name=os.getenv("APP_NAME", "OCR Diff API"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        api_prefix=os.getenv("API_PREFIX", "/api"),
        report_mount_path=os.getenv("REPORT_MOUNT_PATH", "/reports"),
        report_dir=Path(report_dir_value),
        max_file_size=int(os.getenv("MAX_FILE_SIZE", str(5 * 1024 * 1024))),
        cors_origins=tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if origin.strip()
        ),
    )
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    return settings