from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, Float,
    ForeignKey, Boolean, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


# ==================== 原有表 ====================
class User(Base):
    """管理员账户表"""
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_superadmin = Column(Boolean, default=False)


class KnowledgeDoc(Base):
    """知识库文档元数据表"""
    __tablename__ = "knowledge_doc"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Tourist(Base):
    """
    游客账户表
    - id: 内部自增主键
    - display_id: 业务展示编号（原 tourist_id），如 U00001
    """
    __tablename__ = "tourist"

    id = Column(Integer, primary_key=True, index=True)
    display_id = Column(String(50), unique=True, index=True, nullable=True,
                        comment="业务展示编号，如U00001")
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    gender = Column(String(4), nullable=True, comment="性别: 男/女/其他")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interactions = relationship("InteractionLog", back_populates="tourist")


class TouristVisit(Base):
    """游客游览记录表（保持原样）"""
    __tablename__ = "tourist_visit"

    id = Column(Integer, primary_key=True, index=True)
    tourist_id = Column(String(50))          # 原始ID，如U00001
    user_nickname = Column(String(100))
    age = Column(Integer)
    gender = Column(String(4))
    attraction_name = Column(String(200))
    attraction_content = Column(Text)
    attraction_type = Column(String(50))
    visit_date = Column(Date, index=True)
    stay_duration = Column(Float)
    ticket_cost = Column(Float)
    food_cost = Column(Float)
    shopping_cost = Column(Float)
    transport_cost = Column(Float)
    entertainment_cost = Column(Float)
    total_cost = Column(Float)
    group_size = Column(Integer)
    satisfaction = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InteractionLog(Base):
    """
    游客对话记录表
    - tourist_pk: 外键指向 Tourist.id，避免与 TouristVisit.tourist_id 混淆
    """
    __tablename__ = "interaction_log"

    id = Column(Integer, primary_key=True, index=True)
    tourist_pk = Column(Integer, ForeignKey("tourist.id"),
                        nullable=False, index=True,
                        comment="关联 Tourist.id")
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sources = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tourist = relationship("Tourist", back_populates="interactions")


class ProjectNode(Base):
    """项目文件树节点"""
    __tablename__ = "project_structure"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("project_structure.id"),
                       nullable=True)
    name = Column(String(255), nullable=False)
    node_type = Column(String(10), nullable=False)
    path = Column(String(1000), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)

    children = relationship(
        "ProjectNode",
        backref="parent",
        remote_side=[id],
        order_by="ProjectNode.sort_order"
    )


class TaskPlan(Base):
    """任务计划表"""
    __tablename__ = "task_plan"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="in_progress")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    owner = Column(String)


class TaskStep(Base):
    """任务步骤表"""
    __tablename__ = "task_step"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("task_plan.id"), nullable=False)
    step_order = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String, default="pending")
    result = Column(Text, nullable=True)

    plan = relationship("TaskPlan", backref="steps")


# ==================== 新增：景点信息表（含经纬度范围）====================
class Attraction(Base):
    """
    景点结构化数据表
    适用于灵山胜境、拈花湾禅意小镇等景区的景点数据
    经纬度范围字段初始可为空，后续可补充
    """
    __tablename__ = "attraction"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenic_area = Column(String(100), nullable=False, index=True,
                         comment="景区名称")
    attraction_id = Column(String(20), unique=True, nullable=False,
                           comment="景点ID，如 LS-001")
    name = Column(String(200), nullable=False, comment="景点名称")
    location = Column(Text, comment="具体位置")
    specs = Column(Text, comment="建筑/景观参数")
    function_desc = Column(Text, comment="核心功能")
    cultural_connotation = Column(Text, comment="文化内涵")
    detail = Column(Text, comment="详细介绍")
    highlights = Column(Text, comment="游玩亮点")
    opening_info = Column(Text, comment="演艺/开放信息")
    remarks = Column(Text, comment="备注")

    # 经纬度范围（初始为空，可按需填写）
    min_longitude = Column(Float, nullable=True, comment="最小经度")
    max_longitude = Column(Float, nullable=True, comment="最大经度")
    min_latitude = Column(Float, nullable=True, comment="最小纬度")
    max_latitude = Column(Float, nullable=True, comment="最大纬度")
    # 新增景点类型
    attraction_type = Column(String(50), nullable=True, comment="景点类型，如：历史文化/自然公园等")
    # 视频资源
    video_url = Column(String(500), nullable=True, comment="景点介绍视频文件名")
    video_duration = Column(String(20), nullable=True, comment="视频时长，如 3:20")

    __table_args__ = (
        Index("ix_attraction_scenic_name", "scenic_area", "name"),
    )


# ==================== 新增：数字人系统配置表 ====================
class SystemConfig(Base):
    """
    系统全局配置表
    用于存储跨应用共享的配置项，如 Live2D 当前模型
    """
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True,
                        comment="配置键名，如 live2d_current_model")
    config_value = Column(Text, nullable=False, comment="配置值")
    description = Column(Text, nullable=True, comment="配置描述")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(50), nullable=True, comment="更新人")

    __table_args__ = (
        Index("ix_system_config_key", "config_key"),
    )

