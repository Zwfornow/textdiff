# API 文档

本文档描述当前已经实现的 FastAPI 接口。

## 基础信息

- 服务默认地址：`http://localhost:8000`
- API 前缀：`/api`
- 报告静态目录：`/reports`

## 1. 健康检查

路径：`GET /api/health`

用途：

- 本地开发时确认服务已经启动。
- 部署到服务器后用于负载均衡或监控做存活探测。

示例响应：

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

## 2. 文本对比

路径：`POST /api/diff`

请求头：`Content-Type: application/json`

请求体示例：

```json
{
  "reference": "# 标题\n你好，世界",
  "ocr": "# 标题\n你好，世间",
  "reference_label": "left.md",
  "ocr_label": "right.md",
  "preprocess_options": {
    "normalize_width": true,
    "normalize_punctuation": true,
    "case_sensitive": false
  }
}
```

响应体示例：

```json
{
  "reference_text": "标题你好,世界",
  "ocr_text": "标题你好,世间",
  "stats": {
    "reference_length": 7,
    "delete_count": 0,
    "insert_count": 0,
    "replace_count": 1,
    "error_count": 1,
    "accuracy": 85.71
  },
  "report_url": "/reports/diff_20260427_135558_left_vs_right.html"
}
```

## 3. 文件上传对比

路径：`POST /api/diff`

请求头：`Content-Type: multipart/form-data`

字段说明：

- `reference_file`：参考文件。
- `ocr_file`：OCR 文件。
- `preprocess_options`：可选，JSON 字符串格式的预处理配置。

curl 示例：

```bash
curl -X POST http://localhost:8000/api/diff \
  -F 'reference_file=@md_summary/right_mac.md' \
  -F 'ocr_file=@md_summary/right_my4.md' \
  -F 'preprocess_options={"normalize_width": true, "normalize_punctuation": true, "case_sensitive": false}'
```

## 4. 报告访问

路径：`GET /reports/{report_filename}.html`

说明：

- 成功对比后，接口会返回 `report_url`。
- 当前阶段由 FastAPI 直接暴露静态目录；后续接入 Nginx 后会改为由 Nginx 统一代理。

## 5. 当前错误响应

当前阶段主要返回以下状态码：

- `400`：输入为空、上传字段缺失或格式错误。
- `413`：上传文件超过大小限制。
- `415`：请求类型不是 JSON 或 multipart。
- `422`：上传文件不是有效 UTF-8 文本。
- `500`：后端未处理异常。
