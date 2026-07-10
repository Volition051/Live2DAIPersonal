import time, io, base64, asyncio, os
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.database import get_db, SessionLocal
from app import models, schemas
from app.core.agent import run_agent_with_thoughts, _clean_punctuation
from app.core.memory import MemoryManager
from app.services.tts_service import generate_audio_stream, generate_audio_with_visemes
from app.core.tools import make_plan_tools, AVAILABLE_TOOLS
from app.config import settings
from app.utils.security import verify_password, get_password_hash, create_access_token
import logging
from sqlalchemy import func, and_
from app.services.recommender import get_personalized_recommendation_data
import asyncio

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tourist", tags=["游客功能"])

# ==================== GPS 状态存储 ====================
tourist_positions: dict = {}            # 前端实时上传
simulated_positions: dict = {}          # 用户专属模拟坐标
user_simulation_tasks: dict = {}        # 用户漫游后台任务
user_visit_state: dict = {}             # 游览状态跟踪 { user_id: {"in_scenic": bool, "record_id": int, "enter_time": datetime, "last_date": date} }
user_last_attraction: dict = {}        # GPS自动介绍跟踪 { user_id: attraction_id }
user_last_intro_time: dict = {}        # 上次自动介绍时间 { user_id: datetime }，防止边界抖动频繁触发

oauth2_scheme_tourist = OAuth2PasswordBearer(tokenUrl="tourist/login")

# ==================== 景区围栏判断 ====================
def is_within_scenic_area(lat: float, lng: float) -> bool:
    if lat is None or lng is None:
        return False
    return (
        settings.SCENIC_LON_MIN <= lng <= settings.SCENIC_LON_MAX and
        settings.SCENIC_LAT_MIN <= lat <= settings.SCENIC_LAT_MAX
    )

# ==================== 根据经纬度匹配景点 ====================
def find_attraction_by_gps(lat: float, lng: float, db: Session):
    """返回匹配的第一个 Attraction 对象，若无则返回 None"""
    return db.query(models.Attraction).filter(
        models.Attraction.min_longitude.isnot(None),
        models.Attraction.max_longitude.isnot(None),
        models.Attraction.min_latitude.isnot(None),
        models.Attraction.max_latitude.isnot(None),
        models.Attraction.min_longitude <= lng,
        models.Attraction.max_longitude >= lng,
        models.Attraction.min_latitude <= lat,
        models.Attraction.max_latitude >= lat,
    ).first()

# ==================== 游览记录跟踪 ====================
def get_next_tourist_id(db: Session) -> str:
    """生成下一个 tourist_id（格式 Uxxxxx）"""
    max_id = db.query(func.max(models.TouristVisit.tourist_id)).filter(
        models.TouristVisit.tourist_id.like('U%')
    ).scalar()
    if max_id:
        num = int(max_id[1:]) + 1
    else:
        num = 1
    return f"U{num:05d}"

def track_visit(user_id: int, lat: float, lng: float, db: Session):
    """根据用户最新坐标维护游览记录，支持多景点切换"""
    state = user_visit_state.setdefault(user_id, {
        "in_scenic": False,
        "record_id": None,
        "enter_time": None,
        "last_date": None,
        "current_attraction_id": None
    })
    now = datetime.now()
    today = now.date()
    in_scenic = is_within_scenic_area(lat, lng)

    # 获取游客信息
    tourist = db.query(models.Tourist).get(user_id)
    if not tourist:
        return

    # 自动分配 display_id（如果为空）
    if not tourist.display_id:
        new_id = get_next_tourist_id(db)
        tourist.display_id = new_id
        db.commit()
        logger.info(f"👤 为用户 {user_id} 分配 display_id: {new_id}")

    # ---------- 内部工具函数 ----------
    def end_current_record():
        """结束当前活跃记录，计算停留时长"""
        if state["record_id"] and state["enter_time"]:
            record = db.query(models.TouristVisit).get(state["record_id"])
            if record and record.stay_duration is None:
                duration = (now - state["enter_time"]).total_seconds() / 3600.0
                record.stay_duration = round(duration, 2)
                db.commit()
                logger.info(f"🏁 结束记录 {record.id}，景点 {record.attraction_name}，停留 {duration:.2f} 小时")
        state["record_id"] = None
        state["enter_time"] = None
        state["current_attraction_id"] = None

    def create_new_record(attraction):
        """创建一条新的游览记录"""
        nonlocal tourist
        record = models.TouristVisit(
            tourist_id=tourist.display_id,
            user_nickname=tourist.username,
            attraction_name=attraction.name if attraction else "灵山胜境",
            attraction_content=attraction.detail if attraction else "",
            attraction_type=attraction.attraction_type if attraction else None,
            visit_date=today,
            age=None, gender=tourist.gender, ticket_cost=None, food_cost=None,
            shopping_cost=None, transport_cost=None, entertainment_cost=None,
            total_cost=None, group_size=None, satisfaction=None
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        state["in_scenic"] = True
        state["record_id"] = record.id
        state["enter_time"] = now
        state["current_attraction_id"] = attraction.attraction_id if attraction else None
        state["last_date"] = today
        logger.info(f"📝 创建新记录 {record.id}：{record.attraction_name}")

    # ---------- 跨天处理 ----------
    if state["in_scenic"] and state["last_date"] and state["last_date"] < today:
        end_current_record()
        state["last_date"] = today

    # ---------- 景区外 ----------
    if not in_scenic:
        if state["in_scenic"]:
            logger.info(f"👤 用户{user_id} 离开景区")
            end_current_record()
            state["in_scenic"] = False
        return

    # ---------- 景区内：匹配当前景点 ----------
    attraction = find_attraction_by_gps(lat, lng, db)
    new_attraction_id = attraction.attraction_id if attraction else None

    # 情况1：刚进入景区
    if not state["in_scenic"]:
        create_new_record(attraction)
        return

    # 情况2：已有一份记录，检查景点是否变化
    if state["current_attraction_id"] != new_attraction_id:
        # 结束上一个景点的记录
        end_current_record()
        # 开始新景点的记录
        create_new_record(attraction)
    else:
        # 景点未变，无需任何操作（停留时长将在离开时计算）
        pass

# ==================== 用户专属漫游任务（含游览记录） ====================
async def user_roaming_loop(user_id: int, start_lat: float, start_lng: float, step_lat: float, step_lng: float):
    lat, lng = start_lat, start_lng
    while True:
        simulated_positions[user_id] = {"lat": lat, "lng": lng}
        in_scenic = is_within_scenic_area(lat, lng)
        logger.info(f"👤 用户{user_id}漫游更新: ({lat:.6f}, {lng:.6f}) {' 景区内' if in_scenic else '❌ 不在景区'}")

        # 独立数据库会话处理游览记录
        db = SessionLocal()
        try:
            track_visit(user_id, lat, lng, db)
        except Exception as e:
            logger.error(f"游览记录更新失败: {e}")
            db.rollback()
        finally:
            db.close()

        await asyncio.sleep(settings.GPS_SIMULATION_INTERVAL_SEC)
        lat += step_lat
        lng += step_lng

# ==================== 认证 ====================
async def get_current_tourist(
    token: str = Depends(oauth2_scheme_tourist),
    db: Session = Depends(get_db)
) -> models.Tourist:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的登录凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        tourist_id: int = int(payload.get("sub"))
        if tourist_id is None:
            raise credentials_exception
    except (JWTError, ValueError):
        raise credentials_exception

    tourist = db.query(models.Tourist).get(tourist_id)
    if tourist is None:
        raise credentials_exception
    return tourist

# ==================== 位置工具函数 ====================
def get_effective_location(tourist_id: int, request_lat: float = None, request_lng: float = None):
    user_sim = simulated_positions.get(tourist_id)
    if user_sim:
        return user_sim["lat"], user_sim["lng"]
    if settings.TEST_LATITUDE is not None and settings.TEST_LONGITUDE is not None:
        return settings.TEST_LATITUDE, settings.TEST_LONGITUDE
    cached = tourist_positions.get(tourist_id)
    if cached:
        return cached["lat"], cached["lng"]
    if request_lat is not None and request_lng is not None:
        return request_lat, request_lng
    return None, None

def start_user_simulation(user_id: int, start_lat: float, start_lng: float, step_lat: float = None, step_lng: float = None):
    global user_simulation_tasks
    if user_id in user_simulation_tasks:
        user_simulation_tasks[user_id].cancel()
    step_lat = step_lat if step_lat is not None else settings.GPS_SIMULATION_STEP_LAT
    step_lng = step_lng if step_lng is not None else settings.GPS_SIMULATION_STEP_LNG
    loop = asyncio.get_running_loop()
    task = loop.create_task(user_roaming_loop(user_id, start_lat, start_lng, step_lat, step_lng))
    user_simulation_tasks[user_id] = task
    logger.info(f"🚀 已启动用户{user_id}漫游，起点({start_lat},{start_lng})，步长({step_lat},{step_lng})")

def stop_user_simulation(user_id: int):
    if user_id in user_simulation_tasks:
        user_simulation_tasks[user_id].cancel()
        del user_simulation_tasks[user_id]
        logger.info(f"🛑 已停止用户{user_id}漫游")
    if user_id in simulated_positions:
        del simulated_positions[user_id]

# ==================== 模拟控制 API ====================
@router.post("/simulation/start_user", summary="为用户启动GPS模拟漫游")
async def api_start_user_simulation(
    tourist_id: int = Query(..., description="游客内部ID"),
    start_lat: float = Query(settings.GPS_SIMULATION_START_LAT),
    start_lng: float = Query(settings.GPS_SIMULATION_START_LNG),
    step_lat: float = Query(settings.GPS_SIMULATION_STEP_LAT),
    step_lng: float = Query(settings.GPS_SIMULATION_STEP_LNG),
):
    start_user_simulation(tourist_id, start_lat, start_lng, step_lat, step_lng)
    return {"message": f"已为用户{tourist_id}启动漫游"}

@router.post("/simulation/set", summary="设置用户静态模拟坐标")
async def set_user_fixed_position(tourist_id: int = Query(...), lat: float = Query(...), lng: float = Query(...)):
    stop_user_simulation(tourist_id)
    simulated_positions[tourist_id] = {"lat": lat, "lng": lng}
    return {"message": f"已设置用户{tourist_id}固定坐标"}

@router.delete("/simulation/clear", summary="清除用户模拟数据")
async def clear_user_simulation(tourist_id: int = Query(...)):
    stop_user_simulation(tourist_id)
    if tourist_id in simulated_positions:
        del simulated_positions[tourist_id]
    return {"message": f"已清除用户{tourist_id}模拟数据"}

# =================== 注册/登录/绑定 ===================
@router.post("/register", summary="游客注册")
async def register(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # ... 原有代码
    existing = db.query(models.Tourist).filter_by(username=form_data.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    tourist = models.Tourist(
        username=form_data.username,
        hashed_password=get_password_hash(form_data.password)
    )
    db.add(tourist)
    db.commit()
    db.refresh(tourist)
    return {"msg": "注册成功", "tourist_id": tourist.id}

@router.post("/login", summary="游客登录")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    tourist = db.query(models.Tourist).filter_by(username=form_data.username).first()
    if not tourist or not verify_password(form_data.password, tourist.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(tourist.id)}, expires_delta=access_token_expires)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "tourist_id": tourist.id,
        "user_info": {
            "username": tourist.username,
            "gender": tourist.gender,
        }
    }

@router.put("/bind", summary="绑定游览记录ID")
async def bind_tourist_id(bind_req: schemas.BindRequest, db: Session = Depends(get_db), current_user: models.Tourist = Depends(get_current_tourist)):
    display_id = bind_req.display_id.strip()
    if not display_id:
        raise HTTPException(status_code=400, detail="游览ID不能为空")
    existing = db.query(models.Tourist).filter(models.Tourist.display_id == display_id).first()
    if existing and existing.id != current_user.id:
        raise HTTPException(status_code=400, detail="该游览ID已被其他账户绑定")
    visit_exists = db.query(models.TouristVisit).filter(models.TouristVisit.tourist_id == display_id).first()
    if not visit_exists:
        raise HTTPException(status_code=404, detail="未找到该游览ID对应的记录")
    current_user.display_id = display_id
    db.commit()
    return {"message": "绑定成功"}

@router.put("/profile", summary="更新游客个人资料")
async def update_profile(
    profile: schemas.UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: models.Tourist = Depends(get_current_tourist)
):
    """更新用户名"""
    if not profile.username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    # 检查用户名是否已存在
    existing = db.query(models.Tourist).filter(
        models.Tourist.username == profile.username,
        models.Tourist.id != current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该用户名已被使用")

    current_user.username = profile.username
    # 如果传了 gender 则更新
    if profile.gender is not None:
        if profile.gender not in ("男", "女", "其他", ""):
            raise HTTPException(status_code=400, detail="性别仅支持: 男/女/其他")
        current_user.gender = profile.gender if profile.gender else None
        # 同步更新已有的游览记录
        db.query(models.TouristVisit).filter(
            models.TouristVisit.tourist_id == current_user.display_id
        ).update({"gender": current_user.gender})
    db.commit()
    db.refresh(current_user)

    return {
        "message": "用户名修改成功",
        "user_info": {
            "username": current_user.username,
            "gender": current_user.gender,
        }
    }

@router.get("/visits", summary="获取我的游览记录")
async def get_my_visits(db: Session = Depends(get_db), current_user: models.Tourist = Depends(get_current_tourist)):
    if not current_user.display_id:
        raise HTTPException(status_code=404, detail="请先绑定游览ID")
    visits = db.query(models.TouristVisit).filter(models.TouristVisit.tourist_id == current_user.display_id).order_by(models.TouristVisit.visit_date.desc()).all()
    return visits

@router.get("/conversations", summary="获取我的对话记录")
async def get_my_conversations(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(50, ge=1, le=200, description="返回的最大记录数"),
    db: Session = Depends(get_db),
    current_user: models.Tourist = Depends(get_current_tourist)
):
    """获取当前游客的对话记录，按时间倒序"""
    total = db.query(func.count(models.InteractionLog.id)).filter(
        models.InteractionLog.tourist_pk == current_user.id
    ).scalar()

    logs = db.query(models.InteractionLog).filter(
        models.InteractionLog.tourist_pk == current_user.id
    ).order_by(models.InteractionLog.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": log.id,
                "question": log.question,
                "answer": log.answer,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    }

# =================== 前端上传 GPS ===================

@router.post("/gps", summary="接收前端定时上传的GPS坐标")
async def upload_gps(
    payload: dict,
    current_user: models.Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db)
):
    lat = payload.get("latitude")
    lng = payload.get("longitude")

    # 若前端传了有效坐标则缓存，否则使用后端有效位置
    if lat is not None and lng is not None:
        await asyncio.to_thread(tourist_positions.__setitem__, current_user.id, {"lat": lat, "lng": lng})
        logger.info(f"📥 收到前端GPS: tourist={current_user.id}, lat={lat}, lng={lng}")
    else:
        logger.info(f"📥 前端GPS为空，使用后端有效位置: tourist={current_user.id}")

    # ==================== GPS → 景点匹配 & 自动介绍触发 ====================
    lat_effective, lng_effective = get_effective_location(current_user.id, lat, lng)
    response = {"message": "GPS坐标已更新"}

    if lat_effective is not None and lng_effective is not None:
        attraction = await asyncio.to_thread(find_attraction_by_gps, lat_effective, lng_effective, db)
        if attraction:
            last_attr_id = user_last_attraction.get(current_user.id)
            is_new = (last_attr_id != attraction.attraction_id)

            # 边界防抖：30秒内同一用户不重复触发"新景点"介绍
            if is_new:
                now = datetime.now()
                last_time = user_last_intro_time.get(current_user.id)
                if last_time and (now - last_time).total_seconds() < 30:
                    is_new = False  # 抑制重复触发
                else:
                    user_last_intro_time[current_user.id] = now

            user_last_attraction[current_user.id] = attraction.attraction_id

            response["matched_attraction"] = {
                "attraction_id": attraction.attraction_id,
                "name": attraction.name,
                "scenic_area": attraction.scenic_area,
                "is_new": is_new,
                "detail": attraction.detail,
                "highlights": attraction.highlights,
                "cultural_connotation": attraction.cultural_connotation,
                "function_desc": attraction.function_desc,
                "location": attraction.location,
                "opening_info": attraction.opening_info,
                "specs": attraction.specs,
            }
            if is_new:
                logger.info(f"🎯 用户{current_user.id} 进入新景点: {attraction.name} ({attraction.attraction_id})")
        else:
            # 用户离开了所有景点范围
            if current_user.id in user_last_attraction:
                old_attr = user_last_attraction.pop(current_user.id)
                logger.info(f"🚶 用户{current_user.id} 离开景点: {old_attr}")

    return response

@router.get("/streaming-thoughts/{user_id}", summary="获取实时思考流")
def get_streaming_thoughts(user_id: str):
    """前端轮询此接口获取 AI 实时思考内容（类似 DeepSeek 思考显示）"""
    from app.core.base_agent import get_live_thoughts
    thoughts = get_live_thoughts(user_id)
    return {"thoughts": thoughts}


@router.post("/text-chat", response_model=schemas.ChatResponse, summary="文字问答接口")
async def text_chat(
    query: schemas.ChatQuery,
    db: Session = Depends(get_db),
    tourist: models.Tourist = Depends(get_current_tourist)
):
    # ==================== 个性化推荐（简化版：数据驱动，一次生成）====================
    if "个性化推荐" in query.question.strip():
        t0 = time.perf_counter()
        memory = MemoryManager(db, tourist.id)

        # 1. 获取推荐数据（异步执行，避免阻塞事件循环）
        rec_data = await asyncio.to_thread(get_personalized_recommendation_data, db, tourist.id)
        if not rec_data["success"]:
            reason = rec_data.get("reason", "暂时无法生成推荐")
            return schemas.ChatResponse(answer=reason, thoughts=[], in_scenic_area=None)

        # 2. 提取位置信息（仅用于提示，不强制使用）
        lat, lng = get_effective_location(tourist.id, query.latitude, query.longitude)

        # 3. 构建上下文消息（把数据自然嵌入问题中）
        context = "以下是根据我的游览记录生成的个性化推荐数据，请据此向我推荐：\n"
        if lat is not None and lng is not None:
            context += f"您当前所在位置：纬度{lat}，经度{lng}\n"
        context += f"您最喜欢的景点类型：{'、'.join(rec_data['favorite_types'])}\n"
        context += "为您推荐以下尚未游览的景点：\n"
        for att in rec_data["recommended_attractions"]:
            context += f"- {att['name']}（{att['type']}），亮点：{att['highlights']}\n"

        if rec_data.get("type_insights"):
            context += "同类景点其他游客的消费参考：\n"
            for atype, info in rec_data["type_insights"].items():
                parts = []
                if info.get('avg_total'):
                    parts.append(f"总花费约{info['avg_total']}元")
                if info.get('avg_ticket'):
                    parts.append(f"门票{info['avg_ticket']}元")
                if info.get('avg_food'):
                    parts.append(f"餐饮{info['avg_food']}元")
                if info.get('avg_shopping'):
                    parts.append(f"购物{info['avg_shopping']}元")
                if info.get('avg_transport'):
                    parts.append(f"交通{info['avg_transport']}元")
                if info.get('avg_entertainment'):
                    parts.append(f"娱乐{info['avg_entertainment']}元")
                sat = f"，满意度{info['avg_satisfaction']}分" if info.get('avg_satisfaction') else ""
                cnt = f"，已有{info['visit_count']}人次游览"
                context += f"- {atype}：{'、'.join(parts)}{sat}{cnt}\n"

        context += "\n为我推荐我没去过但可能感兴趣的景点，结合消费数据给出预算建议，并使用地图工具规划游览顺序。本次提问为个性化推荐。"

        # 4. 使用正常问答流程（但仅迭代1次，不强制工具）
        logger.info(">>> 个性化推荐开始推理（简化数据驱动）")
        t3 = time.perf_counter()
        all_rec_tools = AVAILABLE_TOOLS.copy()
        all_rec_tools.extend(make_plan_tools(db, tourist.id))
        answer, thoughts, step_logs = await asyncio.to_thread(
            run_agent_with_thoughts,
            question=context,
            optional_tools=all_rec_tools,
            max_iterations=20,
            verbose=True,
            tourist_id=tourist.id,
            mode="agent",  # 个性化推荐始终用 Agent 模式
        )
        t_agent = time.perf_counter() - t3

        # 5. 记录交互
        await asyncio.to_thread(memory.add_interaction, query.question, answer)
        logger.info(f"个性化推荐总耗时: {t_agent*1000:.1f} ms")

        thought_items = [schemas.ThoughtItem(**t) for t in thoughts]
        in_scenic = is_within_scenic_area(lat, lng)
        return schemas.ChatResponse(answer=answer, thoughts=thought_items, in_scenic_area=in_scenic)

    # ==================== 正常问答流程（完全不变）====================
    is_normal = query.mode == "normal"
    working_memory = []
    semantic_context = ""

    t0 = time.perf_counter()
    memory = MemoryManager(db, tourist.id)
    t_mem_init = time.perf_counter() - t0

    # normal 模式：跳过记忆压缩和工具构建，大幅提速
    if is_normal:
        agent_history = []
        plan_tools = []
        all_tools = [t for t in AVAILABLE_TOOLS if t["name"] == "search_knowledge_base"]
        t_context = 0
        t_tools = 0
    else:
        t1 = time.perf_counter()
        working_memory, semantic_context = await asyncio.to_thread(memory.build_context, query.question)
        t_context = time.perf_counter() - t1

        agent_history = working_memory.copy()

        t2 = time.perf_counter()
        plan_tools = make_plan_tools(db, tourist.id)
        all_tools = AVAILABLE_TOOLS.copy()
        all_tools.extend(plan_tools)
        t_tools = time.perf_counter() - t2

    tool_names = [t["name"] for t in all_tools]

    logger.info("=" * 60)
    logger.info(f"📢 用户提问: {query.question}")

    # 显示各种位置来源
    logger.info(f"🧭 实时GPS缓存: {tourist_positions.get(tourist.id)}")
    logger.info(f"🧪 测试GPS配置: ({settings.TEST_LATITUDE}, {settings.TEST_LONGITUDE})")
    user_sim = simulated_positions.get(tourist.id)
    if user_sim:
        logger.info(f"👤 用户专属模拟坐标: ({user_sim['lat']}, {user_sim['lng']})")

    lat, lng = get_effective_location(tourist.id, query.latitude, query.longitude)

    if lat is not None and lng is not None:
        if user_sim:
            logger.info(f"👤 使用用户专属模拟位置: ({lat}, {lng})")
        elif settings.TEST_LATITUDE is not None:
            logger.info(f"🧪 使用测试位置: ({lat}, {lng})")
        elif tourist_positions.get(tourist.id):
            logger.info(f"📡 使用前端上传位置: ({lat}, {lng})")
        else:
            logger.info(f"📍 使用请求携带位置: ({lat}, {lng})")
    else:
        logger.info("⚠️ 无可用位置信息")

    wm_count = len(working_memory) if working_memory else 0
    sc_count = 1 if semantic_context else 0
    logger.info(f"🧠 工作记忆: {wm_count} 条  语义记忆: {sc_count} 个历史片段")
    logger.info(f"🔧 可用工具: {', '.join(tool_names)}" if tool_names else "🔧 可用工具: 无")
    logger.info("=" * 60)

    logger.info(">>> 智能体开始推理")
    t3 = time.perf_counter()

    # 构建增强问题：GPS + 语义记忆（作为后台参考，不冒充用户发言）
    augmented_question = query.question
    if lat is not None and lng is not None:
        augmented_question += f"\n(当前用户经纬度: 纬度 {lat}, 经度 {lng})"
    if semantic_context:
        augmented_question += (
            "\n\n【后台提供的与当前问题可能相关的历史对话片段，请仅作内部参考，不要复述本提示内容】\n"
            + semantic_context
        )

    answer, thoughts, step_logs = await asyncio.to_thread(
        lambda: run_agent_with_thoughts(augmented_question, agent_history, optional_tools=plan_tools, verbose=True, tourist_id=tourist.id, mode=query.mode)
    )
    t_agent = time.perf_counter() - t3

    if step_logs:
        for step in step_logs:
            round_num = step["round"]
            thought = step["thought"]
            action = step["action"]
            obs = step.get("obs", "")
            final = step.get("final_answer", "")
            is_repeat = step.get("is_repeat", False)
            logger.info(f"  [{round_num}] Thought: {thought}")
            if action:
                repeat_flag = " ⚠️ 重复调用" if is_repeat else ""
                logger.info(f"      🔧 Action: {action}{repeat_flag}")
            if obs:
                obs_short = obs[:80] + ("..." if len(obs) > 80 else "")
                logger.info(f"      📋 Obs: {obs_short}")
            if final:
                final_short = final[:100] + ("..." if len(final) > 100 else "")
                logger.info(f"      💬 Final Answer 预览: {final_short}")

    logger.info("-" * 40)
    logger.info(f"📝 最终回答:\n{answer}")

    in_scenic = is_within_scenic_area(lat, lng)
    logger.info(f"📍 景区边界检查: {' 在景区内' if in_scenic else '❌ 不在景区内'}")

    t4 = time.perf_counter()
    await asyncio.to_thread(memory.add_interaction, query.question, answer)
    t_mem_add = time.perf_counter() - t4

    logger.info("-" * 40)
    logger.info("⏱️ 各阶段耗时：")
    logger.info(f"  记忆初始化:    {t_mem_init*1000:.1f} ms")
    logger.info(f"  上下文构建:    {t_context*1000:.1f} ms")
    logger.info(f"  工具准备:      {t_tools*1000:.1f} ms")
    logger.info(f"  Agent推理:     {t_agent*1000:.1f} ms")
    logger.info(f"  记忆存储:      {t_mem_add*1000:.1f} ms")
    logger.info(f"  总耗时:        {(time.perf_counter()-t0)*1000:.1f} ms")
    logger.info("=" * 60 + "\n")

    thought_items = [schemas.ThoughtItem(**t) for t in thoughts]
    return schemas.ChatResponse(answer=answer, thoughts=thought_items, in_scenic_area=in_scenic)

# ==================== AI 自动景点介绍 ====================
from app.core.client import client as llm_client, model_name

AUTO_INTRO_PROMPT = """你是一个专业的景区导游。请根据以下景点信息，生成一段热情、自然、口语化的景点介绍。

要求：
1. 像一位真正的导游一样，用亲切的语气向游客介绍
2. 突出景点的特色和亮点
3. 融入文化内涵和历史背景
4. 字数控制在150-300字
5. 语言生动有趣，让人产生游览兴趣
6. 直接输出介绍内容，不需要前缀或后缀标记
7. 标点符号只能使用常用口语标点：逗号（，）、句号（。）、问号（？）、感叹号（！）、分号（；）、冒号（：）、顿号（、）、引号（""、''）。禁止使用：括号、书名号、破折号、省略号、波浪线、星号、井号及其他特殊符号。

景点名称：{name}
所属景区：{scenic_area}
位置：{location}
建筑/景观参数：{specs}
核心功能：{function_desc}
文化内涵：{cultural_connotation}
详细介绍：{detail}
游玩亮点：{highlights}
演艺/开放信息：{opening_info}

请在介绍开头必须用 [动作:xxx] 标记选择合适的肢体动作，然后写介绍正文。不允许省略。
可选动作：invite(邀请)/explain(解释)/wave(挥手)/celebrate(庆祝)。
例：[动作:invite] 大家好！欢迎来到...

请开始介绍："""

# ==================== 景点视频映射（占位数据，后续改为数据库字段） ====================
ATTRACTION_VIDEOS = {
    "LS-001": {"name": "灵山大照壁介绍.mp4", "duration": "2:30"},
    "LS-002": {"name": "五明桥全景.mp4", "duration": "1:45"},
    "LS-003": {"name": "佛足坛文化解读.mp4", "duration": "3:10"},
    "LS-004": {"name": "五智门.mp4", "duration": "2:00"},
    "LS-006": {"name": "九龙灌浴表演.mp4", "duration": "5:20"},
    "LS-009": {"name": "百子戏弥勒.mp4", "duration": "2:15"},
    "LS-010": {"name": "祥符禅寺.mp4", "duration": "3:00"},
    "LS-011": {"name": "灵山大佛全景.mp4", "duration": "4:00"},
    "LS-013": {"name": "灵山梵宫内部.mp4", "duration": "4:30"},
    "LS-014": {"name": "五印坛城.mp4", "duration": "2:50"},
    "NH-001": {"name": "拈花广场.mp4", "duration": "2:10"},
    "NH-002": {"name": "梵天花海.mp4", "duration": "3:30"},
}

@router.post("/attraction-auto-intro", summary="AI自动生成景点介绍")
async def auto_attraction_intro(
    payload: dict,
    tourist: models.Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db)
):
    """
    根据景点ID或景点数据，使用AI生成一段自然的景点介绍。
    前端在GPS匹配到新景点时自动调用此接口。
    """
    attraction_id = payload.get("attraction_id")

    # 从数据库获取景点信息
    attraction = None
    if attraction_id:
        attraction = db.query(models.Attraction).filter(
            models.Attraction.attraction_id == attraction_id
        ).first()

    if not attraction:
        raise HTTPException(status_code=404, detail="景点不存在")

    # 构建提示词
    prompt = AUTO_INTRO_PROMPT.format(
        name=attraction.name or "未知",
        scenic_area=attraction.scenic_area or "景区",
        location=attraction.location or "暂无信息",
        specs=attraction.specs or "暂无信息",
        function_desc=attraction.function_desc or "暂无信息",
        cultural_connotation=attraction.cultural_connotation or "暂无信息",
        detail=attraction.detail or "暂无信息",
        highlights=attraction.highlights or "暂无信息",
        opening_info=attraction.opening_info or "暂无信息",
    )

    logger.info(f"🤖 为用户{tourist.id} 自动生成景点介绍: {attraction.name}")

    try:
        # 异步调用LLM
        response = await asyncio.to_thread(
            lambda: llm_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是一个热情专业的景区导游。标点符号只能使用常用口语标点：逗号（，）、句号（。）、问号（？）、感叹号（！）、分号（；）、冒号（：）、顿号（、）、引号（""、''）。禁止使用括号、书名号、破折号、省略号、波浪线、星号、井号及其他特殊符号。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600,
            )
        )
        intro_text = response.choices[0].message.content.strip()
        intro_text = _clean_punctuation(intro_text)
        logger.info(f"✅ AI介绍生成成功: {intro_text[:80]}...")
    except Exception as e:
        logger.error(f"❌ AI介绍生成失败: {e}")
        # 降级：返回景点基本信息
        parts = [f"欢迎来到{attraction.name}！"]
        if attraction.highlights:
            parts.append(f"这里是{attraction.highlights}。")
        if attraction.detail:
            parts.append(attraction.detail[:200])
        intro_text = "".join(parts)

    # 从数据库读取视频信息（优先数据库，回退硬编码字典）
    if attraction.video_url:
        video = {
            "name": attraction.video_url,
            "duration": attraction.video_duration or "未知",
        }
    else:
        video = ATTRACTION_VIDEOS.get(attraction.attraction_id)

    return {
        "success": True,
        "attraction_name": attraction.name,
        "attraction_id": attraction.attraction_id,
        "introduction": intro_text,
        "video": video,  # None 表示该景点暂无视频
    }


# =================== TTS 配置读取（与管理员端同步） ===================
def get_tts_config(db: Session) -> dict:
    """从 SystemConfig 表中读取全局 TTS 配置，若无则返回默认值"""
    from app.services.tts_service import DEFAULT_VOICE, DEFAULT_RATE, DEFAULT_VOLUME, DEFAULT_PITCH
    
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
# =================== TTS 接口（已修复：同步管理员全局配置） ===================
@router.post("/text-to-speech", summary="文本转语音接口")
async def text_to_speech(
    payload: dict,
    tourist: models.Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db)  #  注入数据库依赖
):
    import traceback
    
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    #  读取管理员设置的全局TTS配置
    tts_config = get_tts_config(db)
    
    # 打印请求日志（与管理员端一致）
    print(f"\n📢 [游客端TTS请求] 用户ID={tourist.id}, 完整文本: {text}")
    print(f"📢 [游客端TTS参数] 发音人={tts_config['voice']}, 语速={tts_config['rate']}, 音量={tts_config['volume']}, 音调={tts_config['pitch']}\n")
    
    try:
        audio_bytes = await generate_audio_stream(
            text=text,
            voice=tts_config["voice"],
            rate=tts_config["rate"],
            volume=tts_config["volume"],
            pitch=tts_config["pitch"]
        )
        
        print(f" [游客端TTS成功] 生成音频大小: {len(audio_bytes)} 字节\n")
        
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"}
        )
    except Exception as e:
        # 打印完整异常堆栈
        print(f"❌ [游客端TTS失败] 错误: {str(e)}")
        print("详细堆栈信息:")
        traceback.print_exc()
        
        raise HTTPException(status_code=500, detail=f"TTS Error: {str(e)}")

@router.post("/text-to-speech-with-visemes", summary="文本转语音接口（带口型数据）")
async def text_to_speech_with_visemes(
    payload: dict,
    tourist: models.Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db)  #  注入数据库依赖
):
    import traceback
    
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    #  读取管理员设置的全局TTS配置
    tts_config = get_tts_config(db)
    
    # 打印请求日志
    print(f"\n📢 [游客端TTS+口型请求] 用户ID={tourist.id}, 完整文本: {text}")
    print(f"📢 [游客端TTS参数] 发音人={tts_config['voice']}, 语速={tts_config['rate']}, 音量={tts_config['volume']}, 音调={tts_config['pitch']}\n")
    
    try:
        audio_bytes, visemes = await generate_audio_with_visemes(
            text=text,
            voice=tts_config["voice"],
            rate=tts_config["rate"],
            volume=tts_config["volume"],
            pitch=tts_config["pitch"]
        )
        
        #  新增：生成字幕数据
        from app.services.tts_service import text_to_subtitle_data
        subtitles = text_to_subtitle_data(text)
        
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        return {
            "audio": audio_base64,
            "visemes": visemes,
            "subtitles": subtitles,   # 新增字段
            "text": text
        }
    except Exception as e:
        # 打印完整异常堆栈
        print(f"❌ [游客端TTS+口型失败] 错误: {str(e)}")
        print("详细堆栈信息:")
        traceback.print_exc()
        
        raise HTTPException(status_code=500, detail=f"TTS with Visemes Error: {str(e)}")


@router.get("/live2d/current-model", summary="获取当前 Live2D 模型配置")
async def get_current_live2d_model(db: Session = Depends(get_db)):
    """
    从数据库读取当前 Live2D 模型配置
    用于游客端启动时动态加载模型
    """
    try:
        config = db.query(models.SystemConfig).filter(
            models.SystemConfig.config_key == "live2d_current_model"
        ).first()
        
        if config:
            return {
                "success": True,
                "model_path": config.config_value,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None
            }
        else:
            # 没有配置时返回默认值
            return {
                "success": False,
                "model_path": "/Resources/haru_greeter_pro_jp/runtime/haru_greeter_t05.model3.json",
                "message": "未找到配置，使用默认模型"
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取配置失败: {str(e)}"
        )
    
@router.get("/simulation/position", summary="获取用户当前模拟位置")
async def get_simulated_position(
    tourist_id: int = Query(...),
    current_user: models.Tourist = Depends(get_current_tourist)
):
    pos = await asyncio.to_thread(simulated_positions.get, tourist_id)
    if pos is None:
        return {"position": None, "message": "该用户无模拟位置"}
    return {"position": pos}

# ── 背景图片 ──
from pathlib import Path

BACKGROUND_DIR = Path(__file__).resolve().parent.parent.parent / "static"

@router.get("/background", summary="获取当前背景图片 URL")
async def get_background():
    # 优先自定义，其次默认
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        path = BACKGROUND_DIR / f"custom_background{ext}"
        if path.exists():
            return {"url": f"/static/custom_background{ext}"}
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        path = BACKGROUND_DIR / f"background{ext}"
        if path.exists():
            return {"url": f"/static/background{ext}"}
    return {"url": None}

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

@router.get("/appearance", summary="获取前端外观设置")
async def get_appearance(db: Session = Depends(get_db)):
    from app.models import SystemConfig
    config = {}
    for key, default in APPEARANCE_DEFAULTS.items():
        row = db.query(SystemConfig).filter(
            SystemConfig.config_key == f"appearance_{key}"
        ).first()
        config[key] = row.config_value if row else default
    return config