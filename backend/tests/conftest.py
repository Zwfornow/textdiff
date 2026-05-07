from __future__ import annotations

"""测试公共夹具。

测试阶段需要隔离报告输出目录，避免每次执行测试都污染真实的开发产物目录。
这里通过临时目录覆盖环境变量，再创建全新的应用实例。
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture()
def sample_dir() -> Path:
    """返回项目中的样例数据目录。"""

    return Path(__file__).resolve().parents[2] / "md_summary"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """创建隔离报告目录的测试客户端。

    使用环境变量覆盖报告输出目录，这样测试生成的 HTML 报告会落到 pytest 临时目录，
    不会污染开发时的 backend/reports。
    """

    previous_report_dir = os.environ.get("REPORT_DIR")
    os.environ["REPORT_DIR"] = str(tmp_path / "reports")
    app = create_app()
    test_client = TestClient(app)
    yield test_client
    if previous_report_dir is None:
        os.environ.pop("REPORT_DIR", None)
    else:
        os.environ["REPORT_DIR"] = previous_report_dir