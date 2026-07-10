import json
import os
import requests
import logging
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from shapely.geometry import shape
from shapely.ops import linemerge
from sqlalchemy.orm import Session
from app import models
from app.config import settings
from app.services.rag import retrieve_context
from app.core.admin_tools import create_plan, get_current_plan, update_step_status
import time
# 在原有 import 后增加
from app.routers.map import _get_multi_route_sync

logger = logging.getLogger(__name__)


# ==================== POI 数据加载 ====================

def _load_pois_from_yaml() -> Optional[List[Dict]]:
    """尝试从 YAML 配置文件加载 POI 数据"""
    try:
        import yaml
        yaml_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config", "poi_data.yaml"
        )
        if os.path.exists(yaml_path):
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            pois = data.get("pois", [])
            if pois:
                logger.info(f"从 YAML 加载了 {len(pois)} 个 POI")
                return pois
    except Exception as e:
        logger.warning(f"YAML POI 加载失败，回退到硬编码: {e}")
    return None


# 优先从 YAML 加载，失败则使用硬编码（向后兼容）
_YAML_POIS = _load_pois_from_yaml()

LOCAL_POIS = _YAML_POIS if _YAML_POIS else [
    {"id": "LS-001", "name": "灵山大照壁", "lng": 120.1025, "lat": 31.4214},
    {"id": "LS-002", "name": "五明桥", "lng": 120.1022, "lat": 31.4217},
    {"id": "LS-003", "name": "佛足坛", "lng": 120.1015, "lat": 31.4227},
    {"id": "LS-004", "name": "五智门", "lng": 120.1013, "lat": 31.4231},
    {"id": "LS-005", "name": "菩提大道", "lng": 120.1011, "lat": 31.4232},
    {"id": "LS-006", "name": "九龙灌浴", "lng": 120.1000, "lat": 31.4246},
    {"id": "LS-007", "name": "降魔浮雕", "lng": 120.0996, "lat": 31.4256},
    {"id": "LS-008", "name": "阿育王柱", "lng": 120.0993, "lat": 31.4262},
    {"id": "LS-009", "name": "百子戏弥勒", "lng": 120.0988, "lat": 31.4272},
    {"id": "LS-010", "name": "祥符禅寺", "lng": 120.0980, "lat": 31.4279},
    {"id": "LS-011", "name": "灵山大佛", "lng": 120.0963, "lat": 31.4302},
    {"id": "LS-012", "name": "佛教文化博览馆", "lng": 120.0965, "lat": 31.4295},
    {"id": "LS-013", "name": "灵山梵宫", "lng": 120.1000, "lat": 31.4272},
    {"id": "LS-014", "name": "五印坛城", "lng": 120.1039, "lat": 31.4256},
    {"id": "LS-015", "name": "曼飞龙塔", "lng": 120.1046, "lat": 31.4261},
    {"id": "LS-016", "name": "无尽意斋", "lng": 120.1022, "lat": 31.4278},
    {"id": "NH-001", "name": "拈花广场", "lng": 120.0763, "lat": 31.4196},
    {"id": "NH-002", "name": "梵天花海", "lng": 120.0750, "lat": 31.4160},
    {"id": "NH-003", "name": "香月花街", "lng": 120.0736, "lat": 31.4170},
    {"id": "NH-004", "name": "拈花堂", "lng": 120.0765, "lat": 31.4195},
    {"id": "NH-005", "name": "五灯湖", "lng": 120.0735, "lat": 31.4155},
    {"id": "NH-006", "name": "鹿鸣谷", "lng": 120.0725, "lat": 31.4185},
]

logger.info(f"POI 数据就绪，共 {len(LOCAL_POIS)} 个景点")

# ---------- 数据库坐标查询辅助函数 ----------
def get_attraction_center(attraction_name: str, db: Session):
    """从 Attraction 表中获取景点的中心坐标 (lng, lat)，失败时返回 None"""
    if not db:
        return None
    try:
        attr = db.query(models.Attraction).filter(
            models.Attraction.name == attraction_name
        ).first()
        if attr and attr.min_longitude is not None:
            lng = (attr.min_longitude + attr.max_longitude) / 2
            lat = (attr.min_latitude + attr.max_latitude) / 2
            return lng, lat
    except Exception as e:
        logger.warning(f"从数据库获取景点坐标失败: {e}")
    return None

def get_attraction_coords_with_fallback(attraction_name: str, db: Session):
    """获取坐标，优先数据库，其次本地硬编码 LOCAL_POIS"""
    # 1. 从数据库获取
    coords = get_attraction_center(attraction_name, db)
    if coords:
        return coords
    # 2. 从本地硬编码列表获取
    for p in LOCAL_POIS:
        if p["name"] == attraction_name:
            return p["lng"], p["lat"]
    return None

# ---------- 基础工具函数 ----------
MAP_BASE_URL = "http://127.0.0.1:8000/map"

def send_map_command(action: str, **kwargs):
    payload = {"action": action, **kwargs}
    try:
        r = requests.post(f"{MAP_BASE_URL}/command", json=payload, timeout=2)
        return json.dumps({"status": "ok", "detail": r.json()})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

def get_scenic_boundary() -> str:
    return (
        f"灵山胜境范围：经度 {settings.SCENIC_LON_MIN} ~ {settings.SCENIC_LON_MAX}，"
        f"纬度 {settings.SCENIC_LAT_MIN} ~ {settings.SCENIC_LAT_MAX}"
    )

def search_knowledge_base(query: str) -> str:
    # 使用增强检索：混合检索 + 来源标注
    chunks = retrieve_context(query, top_k=10, return_rich=True, use_cache=True)
    if not chunks:
        return "知识库中未找到相关信息。"
    # chunks 已经带有 [来源: xxx] 标注，直接拼接
    return "\n\n---\n\n".join(chunks)

def get_weather(lat: float, lon: float) -> str:
    try:
        url = f"https://wttr.in/{lat},{lon}?format=j1"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        current = data["current_condition"][0]
        desc = current["weatherDesc"][0]["value"]
        temp_c = current["temp_C"]
        feels_like = current["FeelsLikeC"]
        humidity = current["humidity"]
        wind_speed = current["windspeedKmph"]
        return (
            f"当前天气：{desc}，气温 {temp_c}°C（体感 {feels_like}°C），"
            f"湿度 {humidity}%，风速 {wind_speed} km/h"
        )
    except Exception as e:
        return f"获取天气失败: {str(e)}"

def get_my_visits(db: Session, tourist_id: int) -> str:
    tourist = db.query(models.Tourist).get(tourist_id)
    if not tourist:
        return "用户信息不存在。"
    display_id = tourist.display_id
    if not display_id:
        return "您尚未绑定游览记录。"
    visits = db.query(models.TouristVisit).filter(
        models.TouristVisit.tourist_id == display_id
    ).order_by(models.TouristVisit.visit_date.desc(), models.TouristVisit.id.desc()).limit(10).all()
    if not visits:
        return "未找到游览记录。"
    lines = []
    for v in visits:
        stay = f"{v.stay_duration:.1f}小时" if v.stay_duration is not None else "进行中"
        lines.append(f"{v.visit_date} 景点：{v.attraction_name}，停留：{stay}")
    return "最近的游览记录：\n" + "\n".join(lines)

def get_attraction_boundary(attraction_name: str, db: Session) -> str:
    attr = db.query(models.Attraction).filter(models.Attraction.name == attraction_name).first()
    if not attr:
        return f"未找到景点“{attraction_name}”。"
    return (f"{attr.name} GPS范围：经度 {attr.min_longitude}～{attr.max_longitude}，"
            f"纬度 {attr.min_latitude}～{attr.max_latitude}")

# ---------- 地图控制工具（使用数据库坐标） ----------
def zoom_to_attraction(attraction_name: str, db: Session):
    coords = get_attraction_coords_with_fallback(attraction_name, db)
    if coords:
        return send_map_command("setView", lat=coords[1], lng=coords[0], zoom=16)
    return f"未找到景点“{attraction_name}”。"

def plan_route_on_map(from_attraction: str, to_attraction: str, db: Session = None):
    logger.info(f"[规划路线] 起点: {from_attraction}, 终点: {to_attraction}")

    from_coords = get_attraction_coords_with_fallback(from_attraction, db)
    to_coords = get_attraction_coords_with_fallback(to_attraction, db)
    if not from_coords or not to_coords:
        logger.warning(f"[规划路线] 未找到坐标: {from_attraction}({from_coords}), {to_attraction}({to_coords})")
        return f"找不到景点坐标，请使用准确全名。"

    lng1, lat1 = from_coords
    lng2, lat2 = to_coords
    logger.info(f"[规划路线] 坐标获取成功: ({lng1},{lat1}) -> ({lng2},{lat2})")

    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 吸附到最近路网节点
        logger.info("[规划路线] 查找最近路网节点...")
        cur.execute("""
            SELECT id FROM ways_vertices_pgr
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            LIMIT 1
        """, (lng1, lat1))
        start = cur.fetchone()
        cur.execute("""
            SELECT id FROM ways_vertices_pgr
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            LIMIT 1
        """, (lng2, lat2))
        end = cur.fetchone()
        if not start or not end:
            logger.warning("[规划路线] 景点附近没有可通行道路")
            return "景点附近没有可通行道路"

        logger.info(f"[规划路线] 路网节点: start={start['id']}, end={end['id']}")

        # Dijkstra 最短路径
        logger.info("[规划路线] 开始 Dijkstra 路径计算...")
        cur.execute("""
            SELECT di.seq, di.edge, di.cost, di.agg_cost,
                   ST_AsGeoJSON(ways.geom_gcj02) AS geom
            FROM pgr_dijkstra(
                'SELECT id, source, target,
                        ST_Length(geom_gcj02::geography) AS cost,
                        ST_Length(geom_gcj02::geography) AS reverse_cost
                 FROM ways',
                %s, %s,
                directed := false
            ) AS di
            JOIN ways ON (di.edge = ways.id)
            ORDER BY di.seq
        """, (start["id"], end["id"]))
        rows = cur.fetchall()
        logger.info(f"[规划路线] 路径计算完成，共 {len(rows)} 条边")

        if not rows:
            return "两点之间没有路径"

        # 合并几何
        geoms = [shape(json.loads(row['geom'])) for row in rows]
        merged = linemerge(geoms)
        coords = [[c[0], c[1]] for c in merged.coords]
        total_dist = round(rows[-1]["agg_cost"])
        logger.info(f"[规划路线] 路径距离: {total_dist} 米，坐标点数: {len(coords)}")

        # 广播绘制指令
        send_map_command("drawRoute", route=coords, distance=total_dist)
        return json.dumps({
            "status": "ok",
            "message": f"已在地图上绘制从{from_attraction}到{to_attraction}的路线，距离约{total_dist}米"
        })
    except Exception as e:
        logger.error(f"[规划路线] 异常: {str(e)}", exc_info=True)
        return f"路线规划异常: {str(e)}"
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

# ---------- 新增辅助函数：名称 → ID ----------
def get_attraction_id_by_name(name: str, db: Session):
    logger.debug(f"[名称转ID] 查询景点: {name}")
    # 1. 数据库
    try:
        attr = db.query(models.Attraction).filter(models.Attraction.name == name).first()
        if attr:
            logger.debug(f"[名称转ID] 数据库找到: {name} -> {attr.attraction_id}")
            return attr.attraction_id
    except Exception as e:
        logger.warning(f"[名称转ID] 数据库查询异常: {e}")

    # 2. 本地 POIS
    for p in LOCAL_POIS:
        if p["name"] == name:
            logger.debug(f"[名称转ID] 本地硬编码找到: {name} -> {p['id']}")
            return p["id"]
    
    logger.warning(f"[名称转ID] 未找到景点: {name}")
    return None

def list_attraction_videos(db: Session = None) -> str:
    """列出所有有视频的景点"""
    if not db:
        return "数据库不可用"
    try:
        from app import models
        attrs = db.query(models.Attraction).filter(
            models.Attraction.video_url.isnot(None),
            models.Attraction.video_url != ''
        ).all()
        if not attrs:
            return "暂无景点视频"
        lines = [f"{a.attraction_id} {a.name} → {a.video_url} ({a.video_duration or '未知时长'})" for a in attrs]
        return "有视频的景点：\n" + "\n".join(lines)
    except Exception as e:
        return f"查询失败: {e}"

def get_attraction_id_by_name_or_keyword(keyword: str, db: Session = None) -> str:
    """根据景点名称或关键词查找景点ID"""
    if not db:
        return "数据库不可用"
    try:
        from app import models
        attrs = db.query(models.Attraction).filter(
            models.Attraction.name.ilike(f"%{keyword}%")
        ).all()
        if not attrs:
            attrs = db.query(models.Attraction).filter(
                models.Attraction.scenic_area.ilike(f"%{keyword}%")
            ).all()
        if not attrs:
            return f"未找到与「{keyword}」相关的景点"
        lines = [f"{a.attraction_id}: {a.name}（{a.scenic_area}）{' 有视频' if a.video_url else ''}" for a in attrs[:10]]
        return "\n".join(lines)
    except Exception as e:
        return f"查询失败: {e}"

def plan_multi_route_on_map(names_str: str, optimize: bool = False, db: Session = None):
    logger.info(f"[多段路径规划] 开始处理: 景点={names_str}, 优化={optimize}")

    name_list = [n.strip() for n in names_str.split(",") if n.strip()]
    if len(name_list) < 2:
        logger.warning("[多段路径规划] 景点数量不足2个")
        return "至少需要两个景点才能规划路线"

    # 名称转 ID（复用现有函数）
    ids = []
    for name in name_list:
        aid = get_attraction_id_by_name(name, db)
        if not aid:
            logger.error(f"[多段路径规划] 未找到景点 ID: {name}")
            return f"未找到景点“{name}”，请使用准确全名。"
        ids.append(aid)

    ids_param = ",".join(ids)
    logger.info(f"[多段路径规划] 直接调用后端同步逻辑，ids={ids_param}")

    start_time = time.time()
    try:
        #  直接调用同步函数，不再走 HTTP
        data = _get_multi_route_sync(ids_param, optimize)
        elapsed = time.time() - start_time
        logger.info(f"[多段路径规划] 完成，耗时 {elapsed:.3f}s，距离={data.get('distance')}")

        # 广播路线到地图（根据需要取消注释）
        send_map_command("drawRoute", route=data["coordinates"], distance=data["distance"])

        order_str = " → ".join(data["order"])
        return json.dumps({
            "status": "ok",
            "message": f"已规划游览顺序: {order_str}，总距离约 {data['distance']} 米"
        })
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[多段路径规划] 异常 (耗时 {elapsed:.3f}s): {e}", exc_info=True)
        return f"多段路径规划失败: {str(e)}"

# ---------- 工具列表 ----------
AVAILABLE_TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": "查询景区内部知识库，获取景点介绍、政策规定、设施服务、注意事项等信息。输入应为自然语言问题或关键词。",
        "func": search_knowledge_base,
    },
    {
        "name": "get_weather",
        "description": "通过经纬度查询当前天气情况。参数：lat (纬度，数字)，lon (经度，数字)。返回天气描述、温度、湿度、风速等。",
        "func": get_weather,
        "params": {"lat": "float", "lon": "float"}
    },
    {
        "name": "get_scenic_boundary",
        "description": "获取灵山胜境景区的GPS经纬度边界范围",
        "func": get_scenic_boundary,
        "params": {}
    }
]

def make_plan_tools(db, tourist_id):
    owner = f"tourist_{tourist_id}"
    return [
        {
            "name": "create_plan",
            "description": "创建一个游览计划。参数：title (字符串)，steps (字符串列表)",
            "func": lambda **kw: create_plan(db, kw['title'], kw['steps'], owner=owner),
            "params": {"title": "string", "steps": "list of strings"}
        },
        {
            "name": "get_current_plan",
            "description": "查看当前进行中的游览计划进度",
            "func": lambda **kw: get_current_plan(db, owner=owner),
            "params": {}
        },
        {
            "name": "update_step_status",
            "description": "更新游览计划步骤状态。参数：plan_id, step_order, status, result(可选)",
            "func": lambda **kw: update_step_status(db, kw['plan_id'], kw['step_order'], kw['status'], kw.get('result', '')),
            "params": {"plan_id": "int", "step_order": "int", "status": "string", "result": "string (optional)"}
        },
        {
            "name": "get_my_visits",
            "description": "查询我最近的游览记录，包括景点名称、日期和停留时长。无参数。",
            "func": lambda **kw: get_my_visits(db, tourist_id),
            "params": {}
        },
        {
            "name": "get_attraction_boundary",
            "description": "查询某个具体景点的经纬度范围。参数：attraction_name (景点名称)",
            "func": lambda **kw: get_attraction_boundary(kw['attraction_name'], db),
            "params": {"attraction_name": "string"}
        },
        {
            "name": "zoom_to_attraction",
            "description": "将地图视角移动到指定景点并放大。参数：attraction_name（景点全名）",
            "func": lambda **kw: zoom_to_attraction(kw['attraction_name'], db),
            "params": {"attraction_name": "string"}
        },
        {
            "name": "plan_route_on_map",
            "description": "规划两个景点之间的步行路线并在地图上显示。参数：from_attraction（起点景点全名），to_attraction（终点景点全名）",
            "func": lambda **kw: plan_route_on_map(kw['from_attraction'], kw['to_attraction'], db),
            "params": {"from_attraction": "string", "to_attraction": "string"}
        },
        {
            "name": "plan_multi_route_on_map",
            "description": "规划多个景点的游览路线，可以自动优化访问顺序。参数：names（逗号分隔的景点名称，如“灵山大照壁,九龙灌浴,灵山大佛”），optimize（布尔值，是否自动优化顺序，默认false）",
            "func": lambda **kw: plan_multi_route_on_map(kw['names'], kw.get('optimize', False), db),
            "params": {"names": "string (comma separated)", "optimize": "boolean (optional)"}
        },
        {
            "name": "list_attraction_videos",
            "description": "列出所有已上传介绍视频的景点。无参数。返回景点ID、名称、视频文件名和时长。",
            "func": lambda **kw: list_attraction_videos(db),
            "params": {}
        },
        {
            "name": "find_attraction_id",
            "description": "根据景点名称或关键词查找景点ID。参数：keyword（景点名称关键词）。返回匹配的景点ID和名称。",
            "func": lambda **kw: get_attraction_id_by_name_or_keyword(kw['keyword'], db),
            "params": {"keyword": "string"}
        }
    ]