from __future__ import annotations

"""接口层测试。"""

import json
from pathlib import Path


def test_health_endpoint(client) -> None:
    """健康检查接口应返回稳定的服务状态。"""

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_text_diff_endpoint_returns_report_url(client) -> None:
    """文本输入模式应返回统计结果和可访问报告地址。"""

    response = client.post(
        "/api/diff",
        json={
            "reference": "# 标题\n你好，世界",
            "ocr": "# 标题\n你好，世间",
            "reference_label": "left.md",
            "ocr_label": "right.md",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["stats"]["replace_count"] == 1
    assert payload["report_url"].startswith("/reports/")

    report_response = client.get(payload["report_url"])
    assert report_response.status_code == 200
    assert "OCR 文本比对报告" in report_response.text


def test_file_diff_endpoint_supports_uploads(client, sample_dir: Path) -> None:
    """文件上传模式应复用同一套核心逻辑并返回样例统计结果。"""

    with open(sample_dir / "right_mac.md", "rb") as reference_file, open(sample_dir / "right_my4.md", "rb") as ocr_file:
        response = client.post(
            "/api/diff",
            files={
                "reference_file": ("right_mac.md", reference_file, "text/markdown"),
                "ocr_file": ("right_my4.md", ocr_file, "text/markdown"),
                "preprocess_options": (None, json.dumps({"normalize_width": True, "normalize_punctuation": True, "case_sensitive": False})),
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["stats"]["reference_length"] == 1244
    assert payload["stats"]["error_count"] == 50


def test_text_diff_rejects_empty_input(client) -> None:
    """空文本应被提前拒绝，避免无意义计算。"""

    response = client.post(
        "/api/diff",
        json={
            "reference": "   ",
            "ocr": "abc",
        },
    )

    assert response.status_code == 400