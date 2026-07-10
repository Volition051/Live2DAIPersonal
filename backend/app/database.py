from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# 1. 创建引擎 (Engine)，建立与 PostgreSQL 的连接池
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,           # 连接池保持的连接数（默认5，太小）
    max_overflow=30,        # 额外可溢出的连接数
    pool_recycle=3600,      # 连接回收时间（秒），防止数据库主动断开
    pool_pre_ping=True,     # 健康检查，防止连接失效
)

# 2. 创建会话工厂 (Session Local)，每次请求从这里拿连接
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. 基类，所有 ORM 模型都要继承它
Base = declarative_base()

# 4. 依赖注入工具：在 API 接口中用它获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db  # 把 db 对象交给路由函数
    finally:
        db.close()  # 请求结束后关闭连接