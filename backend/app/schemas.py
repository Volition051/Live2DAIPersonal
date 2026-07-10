from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date


# ========== 知识库相关 ==========
class DocBase(BaseModel):
    filename: str

class DocCreate(DocBase):
    pass

class Doc(DocBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ========== 问答相关 ==========
class ChatQuery(BaseModel):
    question: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    mode: str = "normal"  # "normal" = 仅RAG轻量问答, "agent" = 完整工具+技能

class ThoughtItem(BaseModel):
    step: int
    type: str          # "thought", "action", "action_input", "observation", "final_answer"
    content: str
    duration_ms: Optional[int] = None   # 该步骤耗时（毫秒）
    raw_content: Optional[str] = None   # 原始完整内容（observation 时供前端展开）

class ChatResponse(BaseModel):
    answer: str
    thoughts: Optional[List[ThoughtItem]] = []
    in_scenic_area: Optional[bool] = None

class BindRequest(BaseModel):
    display_id: str    # 改为 display_id，与 Tourist.display_id 一致

class UpdateProfileRequest(BaseModel):
    username: str
    gender: Optional[str] = None

class AdminChatQuery(BaseModel):
    question: str

class AdminChatResponse(BaseModel):
    answer: str
    thoughts: Optional[List[ThoughtItem]] = []


# ========== 管理员管理 ==========
class AdminUserCreate(BaseModel):
    username: str
    password: str

class AdminUserOut(BaseModel):
    id: int
    username: str
    is_superadmin: bool

    model_config = {"from_attributes": True}


# ========== 游客相关 ==========
class TouristCreate(BaseModel):
    username: str
    password: str

class TouristOut(BaseModel):
    id: int
    display_id: Optional[str] = None
    username: str
    gender: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ========== 对话记录 ==========
class InteractionLogOut(BaseModel):
    id: int
    tourist_pk: int               # 对应 InteractionLog.tourist_pk
    question: str
    answer: str
    created_at: datetime

    model_config = {"from_attributes": True}


# 景点相关
class AttractionBase(BaseModel):
    scenic_area: str
    attraction_id: str
    name: str
    location: Optional[str] = None
    specs: Optional[str] = None
    function_desc: Optional[str] = None
    cultural_connotation: Optional[str] = None
    detail: Optional[str] = None
    highlights: Optional[str] = None
    opening_info: Optional[str] = None
    remarks: Optional[str] = None
    attraction_type: Optional[str] = None          # 新增
    min_longitude: Optional[float] = None
    max_longitude: Optional[float] = None
    min_latitude: Optional[float] = None
    max_latitude: Optional[float] = None

class AttractionCreate(AttractionBase):
    pass

class AttractionOut(AttractionBase):
    id: int

    model_config = {"from_attributes": True}

class AttractionUpdate(BaseModel):
    attraction_type: Optional[str] = None
    min_longitude: Optional[float] = None
    max_longitude: Optional[float] = None
    min_latitude: Optional[float] = None
    max_latitude: Optional[float] = None