"""启动 Godot 后端服务。"""

from __future__ import annotations

import uvicorn


def main() -> int:
    """用 uvicorn 启动 FastAPI。"""

    uvicorn.run("aitown.api.server:app", host="127.0.0.1", port=8000, reload=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
