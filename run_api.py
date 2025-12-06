#!/usr/bin/env python3
"""启动 FastAPI 服务"""

import uvicorn
from novel_speedy.api import app

if __name__ == "__main__":
    uvicorn.run(
        "novel_speedy.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式下自动重载
        log_level="info"
    )
