# 架构说明

当前仓库已经从“单脚本工具”进入“服务化第一阶段”。

## 当前结构

### 1. 核心层

位置：`backend/core`

职责：

- 读取并清洗 Markdown 文本。
- 做预处理和归一化。
- 执行字符级 diff。
- 生成 HTML 报告。
- 统一返回服务层结果对象。

这一层不依赖 FastAPI，因此可以同时被 CLI 和 Web API 复用。

### 2. API 层

位置：`backend/api`

职责：

- 定义请求和响应模型。
- 解析 JSON 文本输入和 multipart 文件上传。
- 调用核心层服务。
- 写入报告文件并返回 `report_url`。

### 3. 应用装配层

位置：`backend/app.py`

职责：

- 创建 FastAPI 应用。
- 配置 CORS。
- 挂载路由和报告静态目录。
- 提供统一异常兜底。

### 4. 前端层

位置：`frontend/src`

职责：

- 提供最小可用的 Next.js 页面。
- 支持文本输入和文件上传两种模式。
- 调用后端 `/api/diff` 接口。
- 展示统计结果，并通过 iframe 预览后端 HTML 报告。

### 5. CLI 兼容层

位置：`textdiff_ocr.py`

职责：

- 保留原有命令行入口。
- 改为调用 `backend/core/diff_service.py`，与 Web 共享同一套算法。

## 当前实现状态

已完成：

- 核心逻辑下沉。
- FastAPI 最小接口。
- 文本输入和文件上传两种模式。
- HTML 报告落盘与静态访问。
- 最小可用的 Next.js 前端。
- pytest 回归测试。

未完成：

- Nginx 配置落地。
- 更完整的部署文档。
- 更细的错误模型与日志。
