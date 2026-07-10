from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import timedelta
from app.database import get_db
from app import models, schemas
from app.services.indexer import index_document, delete_document_index, get_collection  # ← 修改：导入 get_collection
from app.utils.security import verify_password, create_access_token, get_password_hash
from app.config import settings
from app.core.client import client
from pydantic import BaseModel
from typing import List, Optional
import re
from sqlalchemy import func, extract, desc
from app.core.admin_agent import run_admin_agent
from app.schemas import AdminChatQuery, AdminChatResponse
from sqlalchemy import inspect, text
from app.database import engine, Base
import json
from datetime import date, datetime
import traceback
from sqlalchemy import or_
from typing import Optional
import os
import zipfile
import shutil
import glob
from pathlib import Path
from sqlalchemy import inspect, text, and_, or_, cast, String
from typing import Optional, List
from app.services.tts_service import AVAILABLE_VOICES, DEFAULT_VOICE, DEFAULT_RATE, DEFAULT_VOLUME, DEFAULT_PITCH
from app.services.tts_service import generate_audio_with_visemes
from fastapi.responses import Response

# ===================== 问题清洗工具 =====================
import re as _re

def clean_question(text: str) -> str:
    """去掉存储在数据库中的系统指令前缀，如【...】标记"""
    if not text:
        return text
    # 去掉开头的【...】标记（可能多个）
    cleaned = _re.sub(r'【[^】]*】', '', text).strip()
    return cleaned if cleaned else text  # 如果全被清掉了，返回原文

# ===================== 动态获取数据库表列表 =====================
EXCLUDE_TABLES = {'alembic_version', 'spatial_ref_sys'}

def get_display_tables():
    """直接从 PostgreSQL 的 information_schema 查询所有用户表"""
    sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            all_tables = [row[0] for row in result]
        return [t for t in all_tables if t not in EXCLUDE_TABLES]
    except Exception as e:
        print(f"⚠️ 无法从数据库获取表列表: {e}")
        return [t for t in Base.metadata.tables.keys() if t not in EXCLUDE_TABLES]

display_tables = get_display_tables()
# ===========================================================================
def get_table_meta(table_name: str, db: Session):
    """获取表的主键列名、所有列信息"""
    insp = inspect(db.bind)
    pk_constraint = insp.get_pk_constraint(table_name)
    pk_cols = pk_constraint['constrained_columns'] if pk_constraint else []
    cols_info = insp.get_columns(table_name)
    columns_detail = []
    for col in cols_info:
        columns_detail.append({
            "name": col["name"],
            "type": str(col["type"]),
            "primary_key": col["name"] in pk_cols,
            "autoincrement": col.get("autoincrement", False),
            "nullable": col.get("nullable", True),
        })
    return pk_cols, columns_detail
router = APIRouter(prefix="/admin", tags=["管理员功能"])

# ========== 鉴权核心配置 ==========
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="admin/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的登录凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_superadmin(
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限"
        )
    return current_user

# ========== 登录接口 ==========
@router.post("/login", summary="管理员登录")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "is_superadmin": user.is_superadmin
    }

# ========== 知识库接口 ==========
@router.post("/knowledge/upload", summary="上传景区资料")
async def upload_knowledge(
    file: UploadFile = File(..., description="仅支持 PDF、Word、Excel、TXT 文件"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    ALLOWED_EXTENSIONS = (".pdf", ".docx", ".xlsx", ".txt")
    if not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只允许上传 PDF、Word(.docx)、Excel(.xlsx)、TXT 文件"
        )
    
    contents = await file.read()
    
    db_doc = models.KnowledgeDoc(
        filename=file.filename,
        file_type=file.content_type
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    
    try:
        index_document(db_doc.id, file.filename, contents)
    except Exception as e:
        traceback.print_exc()
        db.delete(db_doc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"索引构建失败: {str(e)}"
        )
    
    return {"filename": file.filename, "doc_id": db_doc.id, "status": "success"}


@router.get("/knowledge/list", summary="获取已上传的知识库列表", response_model=list[schemas.Doc])
async def get_knowledge_list(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    docs = db.query(models.KnowledgeDoc).order_by(models.KnowledgeDoc.created_at.desc()).all()
    return docs

@router.delete("/knowledge/{doc_id}", summary="删除知识库文档")
async def delete_knowledge(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    doc = db.query(models.KnowledgeDoc).filter(models.KnowledgeDoc.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    try:
        delete_document_index(doc_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"索引删除失败: {str(e)}")
    db.delete(doc)
    db.commit()
    return {"message": f"文档 {doc.filename} 已删除", "doc_id": doc_id}

@router.get("/knowledge/stats", summary="获取知识库分片统计")
async def get_knowledge_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    docs = db.query(models.KnowledgeDoc).order_by(models.KnowledgeDoc.created_at.desc()).all()
    stats = []
    total_chunks = 0
    col = get_collection()          # ← 惰性获取 collection
    for doc in docs:
        res = col.get(where={"doc_id": doc.id})
        chunk_count = len(res['ids'])
        stats.append({
            "doc_id": doc.id,
            "filename": doc.filename,
            "chunk_count": chunk_count
        })
        total_chunks += chunk_count
    return {"docs": stats, "total_chunks": total_chunks}

# ========== 游客统计接口 ==========
@router.get("/visitor/stats/gender", summary="性别分布")
def visitor_gender_stats(db: Session = Depends(get_db)):
    res = db.query(
        models.TouristVisit.gender,
        func.count(models.TouristVisit.id)
    ).group_by(models.TouristVisit.gender).all()
    return [{"name": g, "value": c} for g, c in res]

@router.get("/visitor/stats/age", summary="年龄分布")
def visitor_age_stats(db: Session = Depends(get_db)):
    age_groups = {
        "18岁以下": (0,17),
        "18-30岁": (18,30),
        "31-45岁": (31,45),
        "46-60岁": (46,60),
        "60岁以上": (61,200)
    }
    data = []
    for name, (lo, hi) in age_groups.items():
        count = db.query(func.count(models.TouristVisit.id)).filter(
            models.TouristVisit.age >= lo,
            models.TouristVisit.age <= hi
        ).scalar()
        data.append({"name": name, "value": count})
    return data

@router.get("/visitor/stats/attraction-top", summary="热门景点TOP10")
def top_attractions(db: Session = Depends(get_db)):
    res = db.query(
        models.TouristVisit.attraction_name,
        func.count(models.TouristVisit.id).label('count')
    ).group_by(models.TouristVisit.attraction_name).order_by(
        desc('count')
    ).limit(10).all()
    return [{"name": name, "count": c} for name, c in res]

@router.get("/visitor/stats/monthly", summary="月度客流量趋势")
def monthly_visitors(db: Session = Depends(get_db)):
    res = db.query(
        func.to_char(models.TouristVisit.visit_date, 'YYYY-MM').label('month'),
        func.count(models.TouristVisit.id)
    ).group_by('month').order_by('month').all()
    return [{"month": m, "count": c} for m, c in res]

@router.get("/visitor/stats/spending", summary="消费组成（平均值）")
def spending_avg(db: Session = Depends(get_db)):
    avg = db.query(
        func.avg(models.TouristVisit.ticket_cost).label('ticket'),
        func.avg(models.TouristVisit.food_cost).label('food'),
        func.avg(models.TouristVisit.shopping_cost).label('shopping'),
        func.avg(models.TouristVisit.transport_cost).label('transport'),
        func.avg(models.TouristVisit.entertainment_cost).label('entertainment')
    ).one()
    return {
        "门票": round(avg.ticket or 0, 2),
        "餐饮": round(avg.food or 0, 2),
        "购物": round(avg.shopping or 0, 2),
        "交通": round(avg.transport or 0, 2),
        "娱乐": round(avg.entertainment or 0, 2)
    }

@router.get("/visitor/stats/satisfaction", summary="满意度分布")
def satisfaction_stats(db: Session = Depends(get_db)):
    res = db.query(
        models.TouristVisit.satisfaction,
        func.count(models.TouristVisit.id)
    ).group_by(models.TouristVisit.satisfaction).order_by(
        models.TouristVisit.satisfaction
    ).all()
    return [{"score": s, "count": c} for s, c in res]

# =================== 管理员 AI 助手 ===================
@router.post("/text-chat", response_model=AdminChatResponse, summary="管理员智能问答")
async def admin_chat(
    query: AdminChatQuery,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    history = []
    answer, thoughts = run_admin_agent(query.question, history, db)
    thought_items = [schemas.ThoughtItem(**t) for t in thoughts]
    return AdminChatResponse(answer=answer, thoughts=thought_items)

# =================== 管理员管理（超管专用） ===================
@router.get("/manage/list", response_model=List[schemas.AdminUserOut], summary="管理员列表")
def list_admins(
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    admins = db.query(models.User).order_by(models.User.id).all()
    return admins

@router.post("/manage/create", response_model=schemas.AdminUserOut, summary="创建管理员")
def create_admin(
    admin_data: schemas.AdminUserCreate,
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    exists = db.query(models.User).filter(models.User.username == admin_data.username).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    hashed_pw = get_password_hash(admin_data.password)
    new_admin = models.User(
        username=admin_data.username,
        hashed_password=hashed_pw,
        is_superadmin=False
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return new_admin

@router.delete("/manage/{user_id}", summary="删除管理员")
def delete_admin(
    user_id: int,
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    if user_id == superadmin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="管理员不存在")
    super_count = db.query(models.User).filter(models.User.is_superadmin == True).count()
    if target.is_superadmin and super_count <= 1:
        raise HTTPException(status_code=400, detail="不能删除唯一的超级管理员")
    db.delete(target)
    db.commit()
    return {"message": f"管理员 {target.username} 已删除"}

# =================== 数据库浏览接口（超管专用） ===================
@router.get("/db/tables", summary="获取所有数据库表名")
async def get_db_tables(
    superadmin: models.User = Depends(get_current_superadmin),
):
    current_tables = get_display_tables()
    return {"tables": current_tables}

@router.get("/db/table/{table_name}/distinct/{column_name}", summary="获取某列的所有不同值")
async def get_distinct_values(
    table_name: str,
    column_name: str,
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    # 表名白名单校验
    allowed_tables = get_display_tables()
    if table_name not in allowed_tables:
        raise HTTPException(status_code=404, detail="表不存在或不可操作")

    # 列名校验（防止注入，确保列存在）
    pk_cols, columns_detail = get_table_meta(table_name, db)
    valid_columns = [col["name"] for col in columns_detail]
    if column_name not in valid_columns:
        raise HTTPException(status_code=400, detail=f"无效的列名: {column_name}")

    query = f'SELECT DISTINCT "{column_name}" FROM "{table_name}" WHERE "{column_name}" IS NOT NULL ORDER BY "{column_name}"'
    result = db.execute(text(query))
    values = [row[0] for row in result.fetchall()]

    def serialize(val):
        if isinstance(val, (datetime, date)):
            return val.isoformat()
        return val

    return {
        "table": table_name,
        "column": column_name,
        "values": [serialize(v) for v in values],
        "count": len(values)
    }

@router.get("/db/table/{table_name}/data", summary="查看表数据")
async def get_table_data(
    table_name: str,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,           # 搜索关键词
    search_column: Optional[str] = None,    # 指定搜索的列名，为空则搜索所有文本列
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    allowed_tables = get_display_tables()
    if table_name not in allowed_tables:
        raise HTTPException(status_code=404, detail="表不存在或不可查看")

    # 获取表元数据
    pk_cols, columns_detail = get_table_meta(table_name, db)

    # 构建 WHERE 子句（搜索条件）
    where_clauses = []
    params = {}

    if search:
        # 如果指定了列名，校验合法性
        if search_column:
            valid_columns = [c["name"] for c in columns_detail]
            if search_column not in valid_columns:
                raise HTTPException(status_code=400, detail=f"无效的列名: {search_column}")
            # 对该列进行模糊搜索（需要转换为字符串类型）
            where_clauses.append(f'CAST("{search_column}" AS TEXT) ILIKE :search')
            params["search"] = f"%{search}%"
        else:
            # 搜索所有文本类型的列（排除主键、外键、数字等）
            text_columns = [
                c["name"] for c in columns_detail
                if any(t in c["type"].lower() for t in ["char", "text", "varchar"])
            ]
            if text_columns:
                or_parts = []
                for col in text_columns:
                    or_parts.append(f'CAST("{col}" AS TEXT) ILIKE :search')
                    params["search"] = f"%{search}%"
                where_clauses.append("(" + " OR ".join(or_parts) + ")")
            else:
                # 如果没有文本列，回退到所有列（可能会影响性能）
                all_cols = [c["name"] for c in columns_detail]
                or_parts = [f'CAST("{col}" AS TEXT) ILIKE :search' for col in all_cols]
                where_clauses.append("(" + " OR ".join(or_parts) + ")")
                params["search"] = f"%{search}%"

    # 构建 WHERE 字符串
    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    # 计数查询
    count_sql = f'SELECT COUNT(*) FROM "{table_name}"{where_sql}'
    total = db.execute(text(count_sql), params).scalar()

    # 获取列名
    meta_sql = f'SELECT * FROM "{table_name}" LIMIT 0'
    result_proxy = db.execute(text(meta_sql))
    columns = list(result_proxy.keys())

    # 分页查询
    offset = (page - 1) * page_size
    data_sql = f'SELECT * FROM "{table_name}"{where_sql} LIMIT :limit OFFSET :offset'
    params["limit"] = page_size
    params["offset"] = offset
    rows_proxy = db.execute(text(data_sql), params)
    rows = [dict(row) for row in rows_proxy.mappings().all()]

    def serialize(val):
        if isinstance(val, (datetime, date)):
            return val.isoformat()
        return val

    clean_rows = [{k: serialize(v) for k, v in row.items()} for row in rows]

    return {
        "table": table_name,
        "columns": columns,
        "primary_keys": pk_cols,
        "columns_detail": columns_detail,
        "rows": clean_rows,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.post("/db/table/{table_name}/data", summary="新增记录")
async def create_table_data(
    table_name: str,
    data: dict,  # 前端传来的字段键值对
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    allowed_tables = get_display_tables()
    if table_name not in allowed_tables:
        raise HTTPException(status_code=404, detail="表不存在或不可操作")

    pk_cols, columns_detail = get_table_meta(table_name, db)
    all_col_names = [c["name"] for c in columns_detail]

    # 校验请求字段是否都是合法列名
    for key in data.keys():
        if key not in all_col_names:
            raise HTTPException(status_code=400, detail=f"无效字段: {key}")

    columns_part = ", ".join(f'"{col}"' for col in data.keys())
    values_part = ", ".join(f":{col}" for col in data.keys())
    insert_sql = f'INSERT INTO "{table_name}" ({columns_part}) VALUES ({values_part})'

    try:
        db.execute(text(insert_sql), data)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"插入失败: {str(e)}")

    # 尝试返回刚插入的记录（通过主键查询）
    if pk_cols and all(col in data for col in pk_cols):
        where_clause = " AND ".join(f'"{col}" = :{col}' for col in pk_cols)
        select_sql = f'SELECT * FROM "{table_name}" WHERE {where_clause}'
        row = db.execute(text(select_sql), {col: data[col] for col in pk_cols}).mappings().first()
        if row:
            return {"success": True, "row": dict(row)}
    return {"success": True}


@router.put("/db/table/{table_name}/data", summary="更新记录")
async def update_table_data(
    table_name: str,
    data: dict,
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    allowed_tables = get_display_tables()
    if table_name not in allowed_tables:
        raise HTTPException(status_code=404, detail="表不存在或不可操作")

    pk_cols, columns_detail = get_table_meta(table_name, db)
    if not pk_cols:
        raise HTTPException(status_code=400, detail="该表没有主键，无法更新")

    missing_pk = [col for col in pk_cols if col not in data]
    if missing_pk:
        raise HTTPException(status_code=400, detail=f"缺少主键字段: {missing_pk}")

    all_col_names = [c["name"] for c in columns_detail]
    pk_values = {col: data[col] for col in pk_cols}
    update_fields = {col: val for col, val in data.items() if col not in pk_cols}

    if not update_fields:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    for col in update_fields.keys():
        if col not in all_col_names:
            raise HTTPException(status_code=400, detail=f"无效字段: {col}")

    set_clause = ", ".join(f'"{col}" = :set_{col}' for col in update_fields)
    where_clause = " AND ".join(f'"{col}" = :pk_{col}' for col in pk_cols)
    update_sql = f'UPDATE "{table_name}" SET {set_clause} WHERE {where_clause}'

    params = {}
    for col, val in update_fields.items():
        params[f"set_{col}"] = val
    for col, val in pk_values.items():
        params[f"pk_{col}"] = val

    try:
        result = db.execute(text(update_sql), params)
        db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="未找到要更新的记录")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"更新失败: {str(e)}")

    return {"success": True, "updated": result.rowcount}


@router.delete("/db/table/{table_name}/data", summary="删除记录")
async def delete_table_data(
    table_name: str,
    data: dict,  # 包含所有主键字段的值
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    allowed_tables = get_display_tables()
    if table_name not in allowed_tables:
        raise HTTPException(status_code=404, detail="表不存在或不可操作")

    pk_cols, _ = get_table_meta(table_name, db)
    if not pk_cols:
        raise HTTPException(status_code=400, detail="该表没有主键，无法删除")

    missing_pk = [col for col in pk_cols if col not in data]
    if missing_pk:
        raise HTTPException(status_code=400, detail=f"缺少主键字段: {missing_pk}")

    where_clause = " AND ".join(f'"{col}" = :{col}' for col in pk_cols)
    delete_sql = f'DELETE FROM "{table_name}" WHERE {where_clause}'

    try:
        result = db.execute(text(delete_sql), {col: data[col] for col in pk_cols})
        db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="未找到要删除的记录")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"删除失败: {str(e)}")

    return {"success": True, "deleted": result.rowcount}

# =================== 文档分片浏览接口 ===================
@router.get("/knowledge/{doc_id}/chunks", summary="分页获取文档向量分片")
async def get_doc_chunks(
    doc_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    doc = db.query(models.KnowledgeDoc).filter(models.KnowledgeDoc.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    col = get_collection()          # ← 惰性获取 collection
    results = col.get(
        where={"doc_id": doc_id},
        include=["documents", "metadatas"]
    )
    all_ids = results.get("ids", [])
    all_documents = results.get("documents", [])
    all_metadatas = results.get("metadatas", [])

    total = len(all_ids)
    start = (page - 1) * page_size
    end = start + page_size
    page_ids = all_ids[start:end]
    page_docs = all_documents[start:end]
    if not all_metadatas:
        all_metadatas = [{}] * total
    page_metas = all_metadatas[start:end]

    items = []
    for i in range(len(page_ids)):
        items.append({
            "chunk_id": page_ids[i],
            "content": page_docs[i] if i < len(page_docs) else "",
            "metadata": page_metas[i] if i < len(page_metas) else {}
        })

    return {
        "doc_id": doc_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }

# =================== 景点管理接口（经纬度编辑） ===================

from sqlalchemy import func

@router.get("/attractions", summary="获取景点列表（管理用）")
async def list_attractions(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    scenic_area: Optional[str] = None,
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    query = db.query(models.Attraction)
    if search:
        query = query.filter(
            or_(
                models.Attraction.name.ilike(f"%{search}%"),
                models.Attraction.scenic_area.ilike(f"%{search}%")
            )
        )
    if scenic_area:
        query = query.filter(models.Attraction.scenic_area == scenic_area)

    # === 修改点：用 func.count() 替代 query.count() ===
    total = query.with_entities(func.count(models.Attraction.id)).scalar()
    # =================================================

    items = query.order_by(models.Attraction.scenic_area, models.Attraction.id)\
                 .offset((page - 1) * page_size)\
                 .limit(page_size)\
                 .all()

    data = []
    for att in items:
        data.append({
            "id": att.id,
            "scenic_area": att.scenic_area,
            "attraction_id": att.attraction_id,
            "name": att.name,
            "location": att.location,
            "attraction_type": att.attraction_type,
            "min_longitude": att.min_longitude,
            "max_longitude": att.max_longitude,
            "min_latitude": att.min_latitude,
            "max_latitude": att.max_latitude,
            "video_url": att.video_url,
            "video_duration": att.video_duration,
        })
    return {"total": total, "page": page, "page_size": page_size, "data": data}


class AttractionUpdate(BaseModel):
    min_longitude: Optional[float] = None
    max_longitude: Optional[float] = None
    min_latitude: Optional[float] = None
    max_latitude: Optional[float] = None
    attraction_type: Optional[str] = None
    video_url: Optional[str] = None
    video_duration: Optional[str] = None

@router.put("/attractions/{attraction_id}", summary="更新景点经纬度及类型")
async def update_attraction_coords(
    attraction_id: str,
    payload: AttractionUpdate,
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    att = db.query(models.Attraction).filter(
        models.Attraction.attraction_id == attraction_id
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="景点不存在")

    if payload.attraction_type is not None:
        att.attraction_type = payload.attraction_type
    if payload.min_longitude is not None:
        att.min_longitude = payload.min_longitude
    if payload.max_longitude is not None:
        att.max_longitude = payload.max_longitude
    if payload.min_latitude is not None:
        att.min_latitude = payload.min_latitude
    if payload.max_latitude is not None:
        att.max_latitude = payload.max_latitude
    if payload.video_url is not None:
        att.video_url = payload.video_url
    if payload.video_duration is not None:
        att.video_duration = payload.video_duration

    db.commit()
    db.refresh(att)
    return {"message": "更新成功", "attraction_id": att.attraction_id}

# ==================== 视频上传接口 ====================

VIDEO_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "videos"

@router.post("/attractions/video/upload", summary="上传景点介绍视频")
async def upload_attraction_video(
    attraction_id: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    """上传景点视频，保存到 static/videos/ 目录"""
    # 验证景点存在
    att = db.query(models.Attraction).filter(
        models.Attraction.attraction_id == attraction_id
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="景点不存在")

    # 只允许视频格式
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.mp4', '.webm', '.mov', '.avi'):
        raise HTTPException(status_code=400, detail="仅支持 mp4/webm/mov/avi 格式")

    # 保存文件
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{attraction_id}{ext}"
    file_path = VIDEO_DIR / safe_name
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 更新数据库
    att.video_url = safe_name
    db.commit()

    print(f"📹 视频已上传: {safe_name} ({len(content)} bytes)")
    return {"message": "上传成功", "video_url": safe_name, "size": len(content)}

# =================== Live2D 模型上传接口 ===================

@router.post("/Live2D/upload", summary="上传 Live2D 模型压缩包")
async def upload_live2d_model(
    file: UploadFile = File(...),
    superadmin: models.User = Depends(get_current_superadmin),
):
    """
    上传 Live2D 模型压缩包，自动解压并查找 .model3.json 文件
    """
    # 定义目标目录（相对于项目根目录）
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TARGET_DIR = os.path.join(PROJECT_ROOT, "..", "frontend-tourist", "public", "Resources")
    
    # 确保目标目录存在
    os.makedirs(TARGET_DIR, exist_ok=True)
    
    # 创建临时目录用于解压
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 保存上传的文件到临时目录
        temp_file_path = os.path.join(temp_dir, file.filename)
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 解压文件
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        if file.filename.endswith('.zip'):
            with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="仅支持 .zip 格式的压缩包"
            )
        
        # 递归查找所有 .model3.json 文件
        model_files = glob.glob(os.path.join(extract_dir, "**", "*.model3.json"), recursive=True)
        
        if not model_files:
            # 未找到模型文件，删除上传内容
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未在压缩包中找到 .model3.json 模型文件"
            )
        
        # 提取模型名称（使用文件名作为模型标识）
        extracted_models = []
        for model_file in model_files:
            # 获取相对路径
            rel_path = os.path.relpath(model_file, extract_dir)
            # 转换为 Web 路径格式（使用正斜杠）
            web_path = "/Resources/" + rel_path.replace("\\", "/")
            
            # 提取模型名称（从路径中提取第一级目录名或文件名）
            path_parts = Path(rel_path).parts
            if len(path_parts) > 1:
                model_name = path_parts[0]  # 使用第一级目录名
            else:
                model_name = Path(model_file).stem  # 使用文件名（不含扩展名）
            
            # 将解压后的文件移动到目标目录
            target_model_path = os.path.join(TARGET_DIR, rel_path)
            os.makedirs(os.path.dirname(target_model_path), exist_ok=True)
            shutil.move(model_file, target_model_path)
            
            # 移动相关的资源文件（同一目录下的其他文件）
            model_dir = os.path.dirname(model_file)
            for item in os.listdir(model_dir):
                if item != os.path.basename(model_file):
                    src = os.path.join(model_dir, item)
                    dst = os.path.join(TARGET_DIR, os.path.dirname(rel_path), item)
                    if os.path.isfile(src):
                        shutil.move(src, dst)
                    elif os.path.isdir(src):
                        if os.path.exists(dst):
                            shutil.rmtree(dst)
                        shutil.move(src, dst)
            
            extracted_models.append({
                "name": model_name,
                "path": web_path,
                "filename": os.path.basename(model_file)
            })
        
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return {
            "message": f"成功上传 {len(extracted_models)} 个模型",
            "models": extracted_models
        }
    
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        # 发生错误时清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理文件失败: {str(e)}"
        )


@router.get("/Live2D/models", summary="获取已上传的 Live2D 模型列表")
async def get_live2d_models(
    superadmin: models.User = Depends(get_current_superadmin),
):
    """
    扫描 Resources 目录，返回所有可用的 Live2D 模型
    """
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    RESOURCES_DIR = os.path.join(PROJECT_ROOT, "..", "frontend-tourist", "public", "Resources")
    
    if not os.path.exists(RESOURCES_DIR):
        return {"models": []}
    
    # 递归查找所有 .model3.json 文件
    model_files = glob.glob(os.path.join(RESOURCES_DIR, "**", "*.model3.json"), recursive=True)
    
    models_list = []
    for model_file in model_files:
        # 获取相对路径
        rel_path = os.path.relpath(model_file, RESOURCES_DIR)
        # 转换为 Web 路径格式
        web_path = "/Resources/" + rel_path.replace("\\", "/")
        
        # 提取模型名称
        path_parts = Path(rel_path).parts
        if len(path_parts) > 1:
            model_name = path_parts[0]
        else:
            model_name = Path(model_file).stem
        
        # 获取文件大小和修改时间
        file_stat = os.stat(model_file)
        
        models_list.append({
            "name": model_name,
            "path": web_path,
            "filename": os.path.basename(model_file),
            "size": file_stat.st_size,
            "modified_time": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
        })
    
    # 按修改时间排序（最新的在前）
    models_list.sort(key=lambda x: x["modified_time"], reverse=True)
    
    return {"models": models_list, "total": len(models_list)}


@router.post("/Live2D/switch", summary="切换当前使用的 Live2D 模型")
async def switch_live2d_model(
    model_path: str = Query(..., description="模型路径，例如：/Resources/haru/model.model3.json"),
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    """
    切换当前使用的 Live2D 模型（保存到数据库，实现跨应用同步）
    1. 验证模型路径是否存在
    2. 将配置保存到 system_config 表
    3. 返回成功响应
    """
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    RESOURCES_DIR = os.path.join(PROJECT_ROOT, "..", "frontend-tourist", "public", "Resources")
    
    # 验证模型路径是否存在
    # 修复：使用 removeprefix 或切片来正确去除前缀，而不是 lstrip
    if model_path.startswith("/Resources/"):
        relative_path = model_path[len("/Resources/"):]
    else:
        relative_path = model_path
    
    full_path = os.path.join(RESOURCES_DIR, relative_path.replace("/", os.sep))
    
    if not os.path.exists(full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模型文件不存在: {model_path} (完整路径: {full_path})"
        )
    
    if not full_path.endswith(".model3.json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效模型路径，必须以 .model3.json 结尾"
        )
    
    # 保存到数据库 system_config 表
    try:
        # 查询是否已存在该配置项
        config = db.query(models.SystemConfig).filter(
            models.SystemConfig.config_key == "live2d_current_model"
        ).first()
        
        if config:
            # 更新现有配置
            config.config_value = model_path
            config.updated_by = superadmin.username
        else:
            # 创建新配置
            config = models.SystemConfig(
                config_key="live2d_current_model",
                config_value=model_path,
                description="当前使用的 Live2D 模型路径",
                updated_by=superadmin.username
            )
            db.add(config)
        
        db.commit()
        db.refresh(config)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存配置失败: {str(e)}"
        )
    
    return {
        "message": "模型切换成功",
        "model_path": model_path,
        "note": "请刷新游客端页面以应用更改"
    }

@router.get("/dashboard", summary="数据大屏统计")
async def dashboard(
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin)
):
    today = date.today()
    # 本周一
    week_start = today - timedelta(days=today.weekday())

    # 从 attraction 表中获取所有灵山胜境和拈花湾禅意小镇的景点名称
    allowed_attractions = db.query(models.Attraction.name).filter(
        models.Attraction.scenic_area.in_(["灵山胜境", "拈花湾禅意小镇"])
    ).all()
    allowed_names = [a[0] for a in allowed_attractions]

    # 基础查询，只统计这些景点的游览记录
    if allowed_names:
        base_query = db.query(models.TouristVisit).filter(
            models.TouristVisit.attraction_name.in_(allowed_names)
        )

        # 1. 累计游客数（不同 tourist_id）
        total_visitors = base_query.with_entities(
            func.count(func.distinct(models.TouristVisit.tourist_id))
        ).scalar()

        # 2. 今日游客数
        today_visitors = base_query.filter(
            func.date(models.TouristVisit.visit_date) == today
        ).with_entities(
            func.count(func.distinct(models.TouristVisit.tourist_id))
        ).scalar()

        # 3. 人均消费
        avg_spending = base_query.filter(
            models.TouristVisit.total_cost.isnot(None)
        ).with_entities(
            func.avg(models.TouristVisit.total_cost)
        ).scalar()
        avg_spending = round(avg_spending or 0, 2)

        # 4. 平均满意度
        avg_satisfaction = base_query.filter(
            models.TouristVisit.satisfaction.isnot(None)
        ).with_entities(
            func.avg(models.TouristVisit.satisfaction)
        ).scalar()
        avg_satisfaction = round(avg_satisfaction or 0, 1)

        # 5. 景点热度 TOP10
        top_attractions = base_query.with_entities(
            models.TouristVisit.attraction_name,
            func.count(models.TouristVisit.id).label('count')
        ).group_by(models.TouristVisit.attraction_name)\
         .order_by(desc('count'))\
         .limit(10).all()

        # 6. 性别分布
        gender_stats = base_query.with_entities(
            models.TouristVisit.gender,
            func.count(models.TouristVisit.id)
        ).group_by(models.TouristVisit.gender).all()

        # 7. 月度趋势（最近12个月）
        monthly_result = db.execute(
            text("""
                SELECT to_char(visit_date, 'YYYY-MM') as month, COUNT(*) as count
                FROM tourist_visit
                WHERE attraction_name IN :names
                  AND visit_date >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY month
                ORDER BY month
            """),
            {"names": tuple(allowed_names)}
        ).fetchall()

        # 8. 今日平均满意度
        today_satisfaction = base_query.filter(
            models.TouristVisit.satisfaction.isnot(None),
            func.date(models.TouristVisit.visit_date) == today
        ).with_entities(
            func.avg(models.TouristVisit.satisfaction)
        ).scalar()
        today_satisfaction = round(today_satisfaction or 0, 1)
    else:
        total_visitors = 0
        today_visitors = 0
        avg_spending = 0
        avg_satisfaction = 0
        top_attractions = []
        gender_stats = []
        monthly_result = []
        today_satisfaction = 0

    # ========== 交互数据统计（来自 interaction_log）==========
    # 9. 今日服务人次（今日对话数）
    today_interactions = db.query(func.count(models.InteractionLog.id)).filter(
        func.date(models.InteractionLog.created_at) == today
    ).scalar() or 0

    # 10. 本周服务人次
    weekly_interactions = db.query(func.count(models.InteractionLog.id)).filter(
        func.date(models.InteractionLog.created_at) >= week_start,
        func.date(models.InteractionLog.created_at) <= today
    ).scalar() or 0

    # 11. 累计服务人次
    total_interactions = db.query(func.count(models.InteractionLog.id)).scalar() or 0

    # 12. 热门问答 TOP10（按问题出现频率）
    popular_questions = db.query(
        models.InteractionLog.question,
        func.count(models.InteractionLog.id).label('count')
    ).group_by(models.InteractionLog.question)\
     .order_by(desc('count'))\
     .limit(10).all()

    # 13. 游客满意度趋势（按周统计最近8周）
    weekly_satisfaction = db.execute(
        text("""
            SELECT
                to_char(date_trunc('week', visit_date), 'MM-DD') as week_label,
                ROUND(AVG(satisfaction)::numeric, 1) as avg_sat
            FROM tourist_visit
            WHERE satisfaction IS NOT NULL
              AND visit_date >= CURRENT_DATE - INTERVAL '8 weeks'
            GROUP BY date_trunc('week', visit_date)
            ORDER BY date_trunc('week', visit_date)
        """)
    ).fetchall()

    # 14. 今日互动时段分布（按小时统计今天的对话量）
    hourly_distribution = db.execute(
        text("""
            SELECT
                EXTRACT(HOUR FROM created_at)::int as hour,
                COUNT(*) as count
            FROM interaction_log
            WHERE DATE(created_at) = CURRENT_DATE
            GROUP BY EXTRACT(HOUR FROM created_at)
            ORDER BY hour
        """)
    ).fetchall()

    return {
        "totalVisitors": total_visitors,
        "todayVisitors": today_visitors,
        "avgSpending": avg_spending,
        "avgSatisfaction": avg_satisfaction,
        "todaySatisfaction": today_satisfaction,
        "todayInteractions": today_interactions,
        "weeklyInteractions": weekly_interactions,
        "totalInteractions": total_interactions,
        "topAttractions": [{"name": name, "count": count} for name, count in top_attractions],
        "genderDistribution": [{"name": g or "未知", "value": c} for g, c in gender_stats],
        "monthlyTrend": [{"month": m, "count": c} for m, c in monthly_result],
        "popularQuestions": [
            {"question": (cq[:50] + ("..." if len(cq) > 50 else "")) if cq else "", "count": c}
            for q, c in popular_questions
            for cq in [clean_question(q)]
        ],
        "weeklySatisfaction": [{"week": w, "avg": float(s)} for w, s in weekly_satisfaction],
        "hourlyDistribution": [{"hour": f"{h:02d}:00", "count": c} for h, c in hourly_distribution]
    }


# =================== 游客感受度报告 ===================
@router.get("/reports/sentiment", summary="游客感受度报告")
async def sentiment_report(
    period: str = "30d",  # 支持 "7d", "30d", "90d"
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin)
):
    """分析交互记录，生成游客关注点分析、情感趋势报告及服务建议"""
    # 解析时间范围
    days = 30
    if period == "7d":
        days = 7
    elif period == "90d":
        days = 90

    start_date = date.today() - timedelta(days=days)
    today = date.today()

    # 1. 时间范围内交互总数
    total_interactions = db.query(func.count(models.InteractionLog.id)).filter(
        func.date(models.InteractionLog.created_at) >= start_date,
        func.date(models.InteractionLog.created_at) <= today
    ).scalar() or 0

    # 2. 每日交互趋势
    daily_trend = db.execute(
        text("""
            SELECT
                DATE(created_at) as day,
                COUNT(*) as count
            FROM interaction_log
            WHERE DATE(created_at) >= :start_date
              AND DATE(created_at) <= :end_date
            GROUP BY DATE(created_at)
            ORDER BY day
        """),
        {"start_date": start_date, "end_date": today}
    ).fetchall()

    # 3. 游客关注话题分析（从问题中提取关键词）
    # 定义景区相关关键词类别
    topic_keywords = {
        "景点介绍": ["景点", "在哪里", "介绍", "有什么", "怎么走", "路线", "地图", "位置", "开放时间", "门票"],
        "历史文化": ["历史", "文化", "佛教", "禅", "灵山", "拈花湾", "典故", "传说", "由来", "修建"],
        "服务设施": ["停车场", "厕所", "餐厅", "吃饭", "住宿", "酒店", "wifi", "充电", "轮椅", "婴儿车"],
        "演出活动": ["表演", "演出", "活动", "时间表", "灯光", "音乐", "喷泉", "秀", "节目", "几点"],
        "购票咨询": ["票价", "优惠", "团购", "退票", "学生票", "老人票", "预约", "购票", "多少钱", "免费"],
        "交通出行": ["公交", "地铁", "打车", "自驾", "导航", "停车", "怎么去", "交通", "大巴", "打车"],
        "投诉建议": ["投诉", "不满意", "差", "态度", "卫生", "脏", "乱", "吵", "排队", "等太久"],
        "游玩体验": ["好玩", "推荐", "攻略", "打卡", "拍照", "风景", "美", "值得", "时间", "路线"],
    }

    # 获取所有问题文本
    questions_result = db.query(models.InteractionLog.question).filter(
        func.date(models.InteractionLog.created_at) >= start_date,
        func.date(models.InteractionLog.created_at) <= today
    ).all()

    all_questions = [clean_question(q[0]) for q in questions_result if q[0]]

    # 统计各话题命中次数
    topic_counts = {}
    for topic, keywords in topic_keywords.items():
        count = 0
        for question in all_questions:
            if any(kw in question for kw in keywords):
                count += 1
        topic_counts[topic] = count

    attention_topics = [
        {"topic": t, "count": c, "percentage": round(c / max(total_interactions, 1) * 100, 1)}
        for t, c in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # 4. 情感分布分析（基于关键词匹配）
    positive_keywords = ["谢谢", "很好", "不错", "棒", "赞", "满意", "方便", "漂亮", "美", "喜欢", "推荐", "好玩", "值得", "👍", "😊"]
    negative_keywords = ["不好", "差", "失望", "投诉", "垃圾", "坑", "贵", "不值", "难", "乱", "脏", "吵", "太慢", "排队久", "😡", "👎"]
    complaint_keywords = ["投诉", "退款", "赔偿", "道歉", "态度差", "骗", "假", "糟糕"]

    sentiment_stats = {"positive": 0, "neutral": 0, "negative": 0, "complaint": 0}
    for question in all_questions:
        q_lower = question.lower()
        if any(kw in question for kw in complaint_keywords):
            sentiment_stats["complaint"] += 1
        elif any(kw in question for kw in negative_keywords):
            sentiment_stats["negative"] += 1
        elif any(kw in question for kw in positive_keywords):
            sentiment_stats["positive"] += 1
        else:
            sentiment_stats["neutral"] += 1

    # 5. 热门问题 TOP15
    hot_questions = db.query(
        models.InteractionLog.question,
        func.count(models.InteractionLog.id).label('count')
    ).filter(
        func.date(models.InteractionLog.created_at) >= start_date,
        func.date(models.InteractionLog.created_at) <= today
    ).group_by(models.InteractionLog.question)\
     .order_by(desc('count'))\
     .limit(15).all()

    # 6. 每日情感趋势（简化版：按日统计正面/负面比例）
    sentiment_trend = db.execute(
        text("""
            SELECT
                DATE(created_at) as day,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE question ~ '谢谢|很好|不错|棒|赞|满意|方便|漂亮|喜欢|推荐|好玩|值得') as positive_cnt,
                COUNT(*) FILTER (WHERE question ~ '不好|差|失望|投诉|垃圾|坑|贵|不值|乱|脏|吵|太慢') as negative_cnt
            FROM interaction_log
            WHERE DATE(created_at) >= :start_date
              AND DATE(created_at) <= :end_date
            GROUP BY DATE(created_at)
            ORDER BY day
        """),
        {"start_date": start_date, "end_date": today}
    ).fetchall()

    # 7. 自动服务建议
    suggestions = []
    # 基于投诉比例给出建议
    complaint_ratio = sentiment_stats["complaint"] / max(total_interactions, 1) * 100
    negative_ratio = (sentiment_stats["complaint"] + sentiment_stats["negative"]) / max(total_interactions, 1) * 100

    if complaint_ratio > 5:
        suggestions.append({
            "level": "warning",
            "category": "投诉预警",
            "content": f"近{days}天投诉类对话占比{complaint_ratio:.1f}%，建议重点关注投诉内容并及时回复处理，排查高频投诉场景。"
        })
    if negative_ratio > 15:
        suggestions.append({
            "level": "warning",
            "category": "负面情绪预警",
            "content": f"近{days}天负面情绪对话占比{negative_ratio:.1f}%，建议加强景区服务质量巡查，优化游客体验。"
        })

    # 基于话题分布给出建议
    top_topic = attention_topics[0] if attention_topics else None
    if top_topic and top_topic["topic"] == "购票咨询":
        suggestions.append({
            "level": "info",
            "category": "信息优化",
            "content": "游客对票务信息关注度最高，建议在显眼位置完善票务说明，包括票价、优惠政策、购票渠道等。"
        })
    if top_topic and top_topic["topic"] == "投诉建议":
        suggestions.append({
            "level": "error",
            "category": "紧急关注",
            "content": "游客投诉类问题占比异常高，建议立即启动服务改进流程，重点排查游客反馈的突出问题。"
        })
    if top_topic and top_topic["topic"] == "交通出行":
        suggestions.append({
            "level": "info",
            "category": "配套设施",
            "content": "游客对交通信息需求量大，建议完善交通指引标识、增加接驳车班次或优化导航信息。"
        })

    # 基于交互量趋势给出建议
    if len(daily_trend) >= 7:
        recent_avg = sum(r[1] for r in daily_trend[-7:]) / 7
        earlier_avg = sum(r[1] for r in daily_trend[-14:-7]) / max(len(daily_trend[-14:-7]), 1)
        if earlier_avg > 0 and recent_avg > earlier_avg * 1.5:
            suggestions.append({
                "level": "info",
                "category": "运营提示",
                "content": f"最近一周日均咨询量({recent_avg:.0f})较前期({earlier_avg:.0f})增长显著，建议适当增配客服/数字人资源以应对高峰。"
            })

    # 默认建议
    if len(suggestions) == 0:
        suggestions.append({
            "level": "info",
            "category": "整体良好",
            "content": "近期的游客互动数据整体表现良好，未发现明显的异常指标。建议持续关注游客反馈，定期优化知识库内容。"
        })
        suggestions.append({
            "level": "info",
            "category": "持续改进",
            "content": "建议定期分析热门问答，将高频问题补充到知识库中，提升数字人的回答准确率和游客满意度。"
        })

    return {
        "period": {"start": start_date.isoformat(), "end": today.isoformat(), "days": days},
        "totalInteractions": total_interactions,
        "dailyTrend": [{"date": str(d), "count": c} for d, c in daily_trend],
        "attentionTopics": attention_topics,
        "sentimentDistribution": [
            {"name": "正面反馈", "value": sentiment_stats["positive"], "itemStyle": {"color": "#67C23A"}},
            {"name": "中性咨询", "value": sentiment_stats["neutral"], "itemStyle": {"color": "#909399"}},
            {"name": "负面反馈", "value": sentiment_stats["negative"], "itemStyle": {"color": "#E6A23C"}},
            {"name": "投诉建议", "value": sentiment_stats["complaint"], "itemStyle": {"color": "#F56C6C"}},
        ],
        "sentimentTrend": [
            {
                "date": str(d),
                "total": t,
                "positive": p,
                "negative": n,
                "neutral": t - p - n
            }
            for d, t, p, n in sentiment_trend
        ],
        "hotQuestions": [
            {"question": (cq[:60] + ("..." if len(cq) > 60 else "")) if cq else "", "count": c}
            for q, c in hot_questions
            for cq in [clean_question(q)]
        ],
        "serviceSuggestions": suggestions,
    }

# =================== TTS 音频设置接口（超管专用） ===================

def get_tts_config(db: Session) -> dict:
    """从 SystemConfig 表中读取 TTS 配置，若无则返回默认值"""
    config = {}
    for key in ["voice", "rate", "volume", "pitch"]:
        row = db.query(models.SystemConfig).filter(
            models.SystemConfig.config_key == f"tts_{key}"
        ).first()
        config[key] = row.config_value if row else None

    # 填充默认值
    if not config["voice"]:
        config["voice"] = DEFAULT_VOICE
    if not config["rate"]:
        config["rate"] = DEFAULT_RATE
    if not config["volume"]:
        config["volume"] = DEFAULT_VOLUME
    if not config["pitch"]:
        config["pitch"] = DEFAULT_PITCH
    return config

def save_tts_config(db: Session, config: dict):
    """将 TTS 配置保存到 SystemConfig 表"""
    for key, value in config.items():
        row = db.query(models.SystemConfig).filter(
            models.SystemConfig.config_key == f"tts_{key}"
        ).first()
        if row:
            row.config_value = value
        else:
            db.add(models.SystemConfig(
                config_key=f"tts_{key}",
                config_value=value,
                description=f"TTS 语音配置 - {key}"
            ))
    db.commit()
# =================== TTS 文本转语音接口（保留这个，删除下面重复的） ===================
@router.post("/tts/text-to-speech", summary="文本转语音（生成音频）")
async def text_to_speech(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    生成语音音频流，支持自定义发音人、语速、音量、音调
    """
    import traceback
    
    required_fields = ["text"]
    if not all(field in payload for field in required_fields):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少必要参数: text"
        )
    
    text = payload["text"]
    voice = payload.get("voice", DEFAULT_VOICE)
    rate = payload.get("rate", DEFAULT_RATE)
    volume = payload.get("volume", DEFAULT_VOLUME)
    pitch = payload.get("pitch", DEFAULT_PITCH)
    
    # 打印请求参数，便于调试
    print(f"📝 TTS请求参数: text={text[:50]}, voice={voice}, rate={rate}, volume={volume}, pitch={pitch}")
    
    try:
        audio_bytes, _ = await generate_audio_with_visemes(
            text=text,
            voice=voice,
            rate=rate,
            volume=volume,
            pitch=pitch
        )
        
        print(f" TTS生成成功，音频大小: {len(audio_bytes)} bytes")
        
        # 返回音频流
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=tts.mp3"
            }
        )
    except Exception as e:
        # 打印完整异常堆栈到控制台
        print(f"❌ TTS生成失败: {str(e)}")
        print("详细堆栈信息:")
        traceback.print_exc()
        
        # 返回更详细的错误信息
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"语音生成失败: {str(e)}"
        )

# ❌ 删除下面这个重复的接口！
# @router.post("/tts/text-to-speech", summary="文本转语音（生成音频）")
# async def text_to_speech(...):
#     ...

@router.get("/tts/voices", summary="获取所有可用发音人（管理后台用）")
async def admin_get_voices(
    superadmin: models.User = Depends(get_current_superadmin),
):
    """返回发音人列表，供音频设置页面下拉框使用"""
    return {
        "success": True,
        "voices": AVAILABLE_VOICES,
        "default_voice": DEFAULT_VOICE
    }

@router.get("/tts/config", summary="获取当前 TTS 配置")
async def admin_get_tts_config(
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    config = get_tts_config(db)
    return {"success": True, "config": config}

@router.post("/tts/config", summary="更新 TTS 配置")
async def admin_update_tts_config(
    payload: dict,
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    required = ["voice", "rate", "volume", "pitch"]
    if not all(k in payload for k in required):
        raise HTTPException(status_code=400, detail="缺少必要参数 (voice, rate, volume, pitch)")
    save_tts_config(db, payload)
    return {"success": True, "message": "语音配置已更新"}

# ── 背景图片管理 ──
BACKGROUND_DIR = Path(__file__).resolve().parent.parent.parent / "static"
os.makedirs(BACKGROUND_DIR, exist_ok=True)

@router.get("/background", summary="获取当前背景图片 URL")
async def get_background():
    """返回自定义背景，无则返回默认"""
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        path = BACKGROUND_DIR / f"custom_background{ext}"
        if path.exists():
            return {"url": f"/static/custom_background{ext}"}
    # 无自定义背景 → 返回默认图
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        path = BACKGROUND_DIR / f"background{ext}"
        if path.exists():
            return {"url": f"/static/background{ext}"}
    return {"url": None}

@router.post("/background/upload", summary="上传背景图片")
async def upload_background(
    file: UploadFile = File(...),
    superadmin: models.User = Depends(get_current_superadmin),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / WebP")
    # 删除旧自定义背景
    for old_ext in (".jpg", ".jpeg", ".png", ".webp"):
        old = BACKGROUND_DIR / f"custom_background{old_ext}"
        if old.exists():
            old.unlink()
    # 保存新背景
    safe_name = f"custom_background{ext}"
    file_path = BACKGROUND_DIR / safe_name
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    return {"message": "上传成功", "url": f"/static/{safe_name}", "size": len(content)}

@router.post("/background/reset", summary="重置为默认背景")
async def reset_background(
    superadmin: models.User = Depends(get_current_superadmin),
):
    """只删除自定义背景，不动默认 background.jpg"""
    deleted = []
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        path = BACKGROUND_DIR / f"custom_background{ext}"
        if path.exists():
            path.unlink()
            deleted.append(f"custom_background{ext}")
    return {"message": "已重置为默认背景", "deleted": deleted}

# ── 前端外观设置 ──
APPEARANCE_DEFAULTS = {
    "header_bg": "rgba(255,255,255,0.85)",
    "header_bg_image": "",
    "header_text_color": "#2c3e50",
    "btn_map": "true", "btn_recommend": "true",
    "btn_video": "true", "btn_action": "true",
    "welcome_title": "您好，我是您的智能导游",
    "welcome_text": "嗨，欢迎来到灵山胜境！有什么想了解的，尽管问我哦～",
    "welcome_tips": "🕐 表演时间,📏 景点参数,🗺️ 游览路线,⭐ 猜你喜欢",
    "brand_title": "灵山胜境 · 智能导游",
    "chat_bg": "transparent", "chat_bg_image": "", "chat_text_color": "#2c3e50", "chat_font_size": "15",
    "bubble_ai_bg": "#ffffff", "bubble_user_bg": "#4a7c59", "bubble_user_text": "#ffffff",
    "input_bg": "#ffffff", "input_bg_image": "", "input_border": "#e5e0d8", "input_send_btn": "#4a7c59",
    "input_placeholder": "输入您的问题，按 Enter 发送...",
    "show_live2d": "true", "map_default_open": "false",
}

def _get_appearance(db: Session) -> dict:
    config = {}
    for key, default in APPEARANCE_DEFAULTS.items():
        row = db.query(models.SystemConfig).filter(
            models.SystemConfig.config_key == f"appearance_{key}"
        ).first()
        config[key] = row.config_value if row else default
    return config

@router.get("/appearance", summary="获取前端外观设置")
async def get_appearance(db: Session = Depends(get_db)):
    return _get_appearance(db)

@router.post("/appearance", summary="保存前端外观设置")
async def save_appearance(
    payload: dict,
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    for key, default in APPEARANCE_DEFAULTS.items():
        if key in payload:
            val = str(payload[key])
            row = db.query(models.SystemConfig).filter(
                models.SystemConfig.config_key == f"appearance_{key}"
            ).first()
            if row:
                row.config_value = val
            else:
                db.add(models.SystemConfig(
                    config_key=f"appearance_{key}",
                    config_value=val,
                    description=f"前端外观: {key}"
                ))
    db.commit()
    return {"message": "保存成功"}

@router.post("/appearance/upload", summary="上传外观图片")
async def upload_appearance_image(
    file: UploadFile = File(...),
    superadmin: models.User = Depends(get_current_superadmin),
):
    import time
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / WebP")
    safe_name = f"appearance_{int(time.time())}{ext}"
    file_path = BACKGROUND_DIR / safe_name
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    return {"message": "上传成功", "url": f"/static/{safe_name}"}

@router.post("/appearance/reset", summary="恢复默认外观")
async def reset_appearance(
    db: Session = Depends(get_db),
    superadmin: models.User = Depends(get_current_superadmin),
):
    for key in APPEARANCE_DEFAULTS:
        db.query(models.SystemConfig).filter(
            models.SystemConfig.config_key == f"appearance_{key}"
        ).delete()
    db.commit()
    return {"message": "已恢复默认外观"}
