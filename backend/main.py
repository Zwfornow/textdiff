from __future__ import annotations

"""本地开发启动入口。"""

import uvicorn


if __name__ == "__main__":
    # 本地开发阶段优先开启 reload，便于频繁修改后快速验证接口行为。
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)