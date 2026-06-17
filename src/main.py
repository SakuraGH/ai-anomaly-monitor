"""AI 异常监控与归因系统 — FastAPI 入口。"""

from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.datasource_api import router as datasource_router
from src.api.metrics_api import router as metrics_router
from src.api.monitor_api import router as monitor_router
from src.api.report_api import router as report_router
from src.api.knowledge_api import router as knowledge_router
from src.api.deps import get_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    state = get_state()
    state.init_all()
    state.scheduler.start()
    yield
    # 关闭时清理
    state.scheduler.shutdown(wait=False)


app = FastAPI(
    title="AI 异常监控与归因系统",
    description="接入数据即可自动监控异常并归因的 AI 助手",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasource_router)
app.include_router(metrics_router)
app.include_router(monitor_router)
app.include_router(report_router)
app.include_router(knowledge_router)


@app.get("/")
def root():
    return {"message": "AI 异常监控与归因系统运行中", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
