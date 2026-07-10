import logging
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"

import sys, re, time
from app.routers.tourist import start_user_simulation
from app.config import settings

# 过滤遥测 stderr
class FilteredStderr:
    def __init__(self, stream):
        self.stream = stream
    def write(self, msg):
        if "Failed to send telemetry event" not in msg:
            self.stream.write(msg)
    def flush(self):
        self.stream.flush()
sys.stderr = FilteredStderr(sys.stderr)

_last_time = time.perf_counter()
def lap(msg):
    global _last_time
    now = time.perf_counter()
    delta = now - _last_time
    _last_time = now
    print(f"[TIMER] {msg}: {delta:.3f}s")

lap("开始 main.py")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
lap("导入 FastAPI")

from app.routers import admin, tourist, map
lap("导入路由")

from app.database import engine, Base, SessionLocal
lap("导入数据库")

from app import models
lap("导入 models")

from app.utils.security import get_password_hash
from sqlalchemy import inspect, text
lap("导入 security / sqlalchemy")

# 日志配置
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
for name in ["app.main","app.routers.tourist","app.core.memory","app.core.agent","app.services.tts_service"]:
    logging.getLogger(name).setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)
os.environ["TQDM_DISABLE"] = "1"

logger = logging.getLogger("app.main")

# ========== FastAPI 应用 ==========
app = FastAPI(
    title="景区 RAG 智能问答系统",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin.router)
app.include_router(tourist.router)
app.include_router(map.router)
app.mount("/tiles", StaticFiles(directory="static/tiles"), name="tiles")
app.mount("/videos", StaticFiles(directory="static/videos"), name="videos")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ========== /api 前缀兼容 ==========
from fastapi import FastAPI as _FastAPI
_api_sub = _FastAPI()
from app.routers import map as _mr
_api_sub.include_router(_mr.router)
from app.routers import tourist as _tr
_api_sub.include_router(_tr.router)
from app.routers import admin as _ar
_api_sub.include_router(_ar.router)
app.mount("/api", _api_sub)

# ========== 前端 SPA（根据 SPA_MODE 选择游客端/管理端）==========
from starlette.responses import FileResponse
import os as _os

_mode = os.environ.get("SPA_MODE", "tourist")
_spa_dir = "web-admin" if _mode == "admin" else "web"

app.mount("/assets", StaticFiles(directory=f"{_spa_dir}/assets"), name="spa-assets")

@app.get("/favicon.svg")
async def favicon():
    return FileResponse(f"{_spa_dir}/favicon.svg")

@app.get("/")
async def serve_root():
    return FileResponse(f"{_spa_dir}/index.html")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith(("docs","openapi","tiles","videos","static","tourist","map","api","favicon","assets")):
        raise HTTPException(404)
    f = f"{_spa_dir}/{full_path}"
    if _os.path.isfile(f) and not full_path.endswith(".html"):
        return FileResponse(f)
    return FileResponse(f"{_spa_dir}/index.html")
lap("FastAPI 初始化完成")

# ========== 扩大线程池（必须在这里注册） ==========
import asyncio
from concurrent.futures import ThreadPoolExecutor

@app.on_event("startup")
async def set_executor():
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=200))
    logger.info(" 已扩大默认线程池至 200 个工作线程")

# ========== 数据库初始化 ==========
@app.on_event("startup")
def startup_db():
    lap("开始 startup_db")
    Base.metadata.create_all(bind=engine)
    lap("建表完成")
    logger.info(" 数据库表检查/创建完成")

    db = SessionLocal()
    try:
        conn = db.connection()
        inspector = inspect(conn)
        columns = [c["name"] for c in inspector.get_columns("user")]
        if "is_superadmin" not in columns:
            conn.execute(text("ALTER TABLE \"user\" ADD COLUMN is_superadmin BOOLEAN DEFAULT FALSE"))
            db.commit()
            logger.info(" 已添加 is_superadmin 列")
        lap("检查/添加列完成")

        att_columns = [c["name"] for c in inspector.get_columns("attraction")]
        if "attraction_type" not in att_columns:
            conn.execute(text("ALTER TABLE attraction ADD COLUMN attraction_type VARCHAR(50)"))
            db.commit()
            logger.info(" 已添加 attraction_type 列")
        if "video_url" not in att_columns:
            conn.execute(text("ALTER TABLE attraction ADD COLUMN video_url VARCHAR(500)"))
            conn.execute(text("ALTER TABLE attraction ADD COLUMN video_duration VARCHAR(20)"))
            db.commit()
            logger.info(" 已添加 video_url / video_duration 列")

        tourist_columns = [c["name"] for c in inspector.get_columns("tourist")]
        if "gender" not in tourist_columns:
            conn.execute(text("ALTER TABLE tourist ADD COLUMN gender VARCHAR(4)"))
            db.commit()
            logger.info(" 已添加 tourist.gender 列")
        admin_user = db.query(models.User).filter(models.User.username == "admin").first()
        if admin_user:
            if not admin_user.is_superadmin:
                admin_user.is_superadmin = True
                db.commit()
                logger.info(" 已将 admin 升级为超级管理员")
        else:
            hashed_pw = get_password_hash("admin123")
            new_admin = models.User(
                username="admin",
                hashed_password=hashed_pw,
                is_superadmin=True
            )
            db.add(new_admin)
            db.commit()
            logger.info(" 超级管理员已创建")
        lap("管理员初始化完成")
    finally:
        db.close()
    lap("startup_db 结束")

@app.get("/", tags=["根路径"])
def read_root():
    return {"message": "欢迎使用景区 RAG 系统", "docs": "/docs"}

# ========== 自动启动用户漫游 ==========
@app.on_event("startup")
async def auto_start_user_simulation():
    if not settings.GPS_SIMULATION_ENABLED:
        return

    user_id = getattr(settings, "GPS_SIMULATION_DEFAULT_USER_ID", None)
    if user_id is None:
        logger.info("📌 未配置 GPS_SIMULATION_DEFAULT_USER_ID，跳过自动启动用户漫游")
        return

    start_lat = getattr(settings, "GPS_SIMULATION_START_LAT", 31.4200)
    start_lng = getattr(settings, "GPS_SIMULATION_START_LNG", 120.0950)
    step_lat = getattr(settings, "GPS_SIMULATION_STEP_LAT", 0.0001)
    step_lng = getattr(settings, "GPS_SIMULATION_STEP_LNG", 0.0001)

    start_user_simulation(
        user_id=user_id,
        start_lat=start_lat,
        start_lng=start_lng,
        step_lat=step_lat,
        step_lng=step_lng
    )
    logger.info(f"🎮 已自动为用户 {user_id} 启动 GPS 漫游，起点 ({start_lat}, {start_lng})")

# ========== 向量库热启动 ==========
@app.on_event("startup")
async def warmup_vectorstore():
    warmup_enabled = getattr(settings, "WARMUP_VECTORDB", True)
    if not warmup_enabled:
        logger.info("📌 WARMUP_VECTORDB 已关闭，跳过向量库预热")
        return

    logger.info("🔥 开始向量库热启动（加载 embedding 模型 + Chroma 初始化）...")
    try:
        from app.services.rag import retrieve_context
        _ = retrieve_context("预热查询", top_k=1)
        logger.info(" 向量库热启动完成")
    except Exception as e:
        logger.warning(f"⚠️ 向量库预热失败（首次查询将自动初始化）: {e}")