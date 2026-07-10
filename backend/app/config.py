"""
全局配置模块
基于 pydantic_settings 管理应用配置，自动从 .env 文件加载环境变量。
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os
from typing import Optional, Literal

# 设置 HuggingFace 镜像端点，加速模型下载（可在部署时覆盖）
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

#  项目根目录，所有文件操作以此为基础
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """应用配置类，所有字段均可通过 .env 文件或环境变量覆盖"""

    # ---------- 数据库 ----------
    DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/my_db?client_encoding=utf8"

    # ---------- ChromaDB 向量库 ----------
    CHROMA_PATH: str = "./chroma_db"                     
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"          

    # ---------- JWT 鉴权 ----------
    SECRET_KEY: str = ""                                       # ⚠️ 必须从环境变量注入，此处为空
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # ---------- Agent 控制 ----------
    AGENT_MAX_ITERATIONS: int = 500

    # ---------- LLM 提供商选择 ----------
    # 可选值: dashscope（阿里百炼）, deepseek（DeepSeek）
    LLM_PROVIDER: Literal["dashscope", "deepseek"] = "dashscope"

    # ---------- 百炼（DashScope）API ----------
    DASHSCOPE_API_KEY: str = ""                                # ⚠️ 必须从环境变量注入，原硬编码已移除
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_MODEL: str = "qwen3.5-flash"

    # ---------- DeepSeek API ----------
    DEEPSEEK_API_KEY: str = ""                                 # ⚠️ 填入你的 DeepSeek API 密钥
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"                      # 可改为 v4-pro 等具体模型名

    # ---------- 用户专属漫游默认配置 ----------
    GPS_SIMULATION_DEFAULT_USER_ID: Optional[int] = 3

    # ---------- 坐标测试 ----------
    TEST_LATITUDE: Optional[float] = None
    TEST_LONGITUDE: Optional[float] = None

    # ---------- GPS 模拟漫游 ----------
    GPS_SIMULATION_ENABLED: bool = False
    GPS_SIMULATION_INTERVAL_SEC: float = 3.0
    GPS_SIMULATION_START_LAT: float = 31.4200
    GPS_SIMULATION_START_LNG: float = 120.0950
    GPS_SIMULATION_STEP_LAT: float = 0.0001
    GPS_SIMULATION_STEP_LNG: float = 0.0001

    # ---------- 景区地理围栏 ----------
    SCENIC_LON_MIN: float = 120.0950
    SCENIC_LON_MAX: float = 120.1060
    SCENIC_LAT_MIN: float = 31.4200
    SCENIC_LAT_MAX: float = 31.4317

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

# 全局配置实例
settings = Settings()

#  启动时校验：根据所选提供商确保对应密钥已被正确设置
if settings.LLM_PROVIDER == "deepseek":
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError(
            "LLM_PROVIDER 设置为 deepseek，但 DEEPSEEK_API_KEY 未设置！\n"
            "请在项目根目录的 .env 文件中添加：\n"
            "DEEPSEEK_API_KEY=sk-你的DeepSeek密钥\n"
            "或直接设置系统环境变量。"
        )
else:
    if not settings.DASHSCOPE_API_KEY:
        raise ValueError(
            "DASHSCOPE_API_KEY 未设置！\n"
            "请在项目根目录的 .env 文件中添加：\n"
            "DASHSCOPE_API_KEY=sk-你的真实密钥\n"
            "或直接设置系统环境变量。"
        )
if not settings.SECRET_KEY:
    raise ValueError(
        "SECRET_KEY 未设置！\n"
        "请在 .env 文件中添加：\n"
        "SECRET_KEY=随机字符串（可使用 openssl rand -hex 32 生成）"
    )
