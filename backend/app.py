from __future__ import annotations

"""应用装配入口。

这一层只负责组装应用，不直接承载业务逻辑。这样做的好处是：
1. 便于测试时创建应用实例。
2. 便于后续接入更多路由、中间件和生命周期管理。
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from backend.config import get_settings


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""

    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 把运行配置挂到应用状态上，便于路由函数统一读取，避免在多处重复构造配置。
    app.state.settings = settings

    @app.middleware("http")
    async def inject_settings(request: Request, call_next):
        request.scope["settings"] = settings
        return await call_next(request)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """兜底返回统一错误结构。

        首期先返回简单 JSON，方便前端明确识别错误；后续再接日志和监控。
        """

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_server_error", "detail": str(exc)},
        )

    app.include_router(router, prefix=settings.api_prefix, dependencies=[])
    app.mount(settings.report_mount_path, StaticFiles(directory=settings.report_dir), name="reports")
    return app


app = create_app()