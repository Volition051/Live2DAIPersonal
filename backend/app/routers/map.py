# backend/app/routers/map.py
from fastapi import APIRouter, Query, HTTPException, WebSocket, WebSocketDisconnect
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from shapely.geometry import shape
from shapely.ops import linemerge
from app.config import settings
from pydantic import BaseModel
import asyncio
from app.database import SessionLocal
from app.models import Attraction
import itertools
from typing import List, Optional
import time
import asyncio
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/map", tags=["地图服务"])

# 硬编码列表（保留备用，当前接口已不再使用）
POIS = [
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
]

def get_db_conn():
    return psycopg2.connect(settings.DATABASE_URL)

@router.get("/pois")
def get_pois():
    db = SessionLocal()
    try:
        attractions = db.query(Attraction).all()
        features = []
        for attr in attractions:
            if attr.min_longitude is not None and attr.min_latitude is not None:
                lng = (attr.min_longitude + attr.max_longitude) / 2
                lat = (attr.min_latitude + attr.max_latitude) / 2
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lng, lat]},
                    "properties": {
                        "id": attr.attraction_id,
                        "name": attr.name
                    }
                })
        return {"type": "FeatureCollection", "features": features}
    finally:
        db.close()

@router.get("/route")
def get_route(from_id: str = Query(...), to_id: str = Query(...)):
    db = SessionLocal()
    try:
        from_attr = db.query(Attraction).filter(Attraction.attraction_id == from_id).first()
        to_attr = db.query(Attraction).filter(Attraction.attraction_id == to_id).first()
        if not from_attr or not to_attr or not from_attr.min_longitude or not to_attr.min_longitude:
            raise HTTPException(status_code=400, detail="景点不存在或坐标缺失")
        lng1 = (from_attr.min_longitude + from_attr.max_longitude) / 2
        lat1 = (from_attr.min_latitude + from_attr.max_latitude) / 2
        lng2 = (to_attr.min_longitude + to_attr.max_longitude) / 2
        lat2 = (to_attr.min_latitude + to_attr.max_latitude) / 2
    finally:
        db.close()

    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT id FROM ways_vertices_pgr
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        LIMIT 1
    """, (lng1, lat1))
    start = cur.fetchone()
    if not start:
        raise HTTPException(status_code=404, detail="起点附近无路网节点")
    start_vid = start["id"]

    cur.execute("""
        SELECT id FROM ways_vertices_pgr
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        LIMIT 1
    """, (lng2, lat2))
    end = cur.fetchone()
    if not end:
        raise HTTPException(status_code=404, detail="终点附近无路网节点")
    end_vid = end["id"]

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
    """, (start_vid, end_vid))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="两点不可达")

    geoms = [shape(json.loads(row["geom"])) for row in rows]
    merged = linemerge(geoms)
    coords = [[c[0], c[1]] for c in merged.coords]
    total_dist = round(rows[-1]["agg_cost"])

    return {"distance": total_dist, "coordinates": coords}

@router.get("/road_network")
def road_network():
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT ST_AsGeoJSON(geom_gcj02) AS geometry FROM ways")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    features = []
    for row in rows:
        geom = json.loads(row["geometry"])
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {}
        })
    return {"type": "FeatureCollection", "features": features}

# ---------- WebSocket 与 命令广播 ----------
connected_clients: list[WebSocket] = []

async def safe_broadcast(message: dict):
    """向所有客户端广播消息，自动移除断开的连接，设置2秒超时"""
    dead = []
    for client in connected_clients:
        try:
            await asyncio.wait_for(client.send_json(message), timeout=2.0)
        except Exception:
            dead.append(client)
    for d in dead:
        if d in connected_clients:
            connected_clients.remove(d)

@router.websocket("/ws/control")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # 收到任意消息后广播给所有客户端（包括发送者，因为前端也需要更新）
            await safe_broadcast(data)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

class MapCommand(BaseModel):
    action: str
    lat: float = None
    lng: float = None
    zoom: int = None
    southWest: list = None
    northEast: list = None
    route: list = None
    distance: float = None

@router.post("/command")
async def post_command(cmd: MapCommand):
    payload = cmd.dict(exclude_none=True)
    await safe_broadcast(payload)
    return {"status": "broadcast_sent", "command": payload}

@router.get("/route/from_coords", summary="根据起止坐标规划路径")
def get_route_from_coords(
    from_lat: float = Query(..., description="起点纬度"),
    from_lng: float = Query(..., description="起点经度"),
    to_lat: float = Query(..., description="终点纬度"),
    to_lng: float = Query(..., description="终点经度"),
):
    """
    通过起止经纬度坐标（GCJ-02）计算最短路径。
    返回距离（米）及路径坐标串。
    """
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 查找起点最近的路网节点
    cur.execute("""
        SELECT id FROM ways_vertices_pgr
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        LIMIT 1
    """, (from_lng, from_lat))
    start = cur.fetchone()
    if not start:
        raise HTTPException(status_code=404, detail="起点附近无路网节点")
    start_vid = start["id"]

    # 查找终点最近的路网节点
    cur.execute("""
        SELECT id FROM ways_vertices_pgr
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        LIMIT 1
    """, (to_lng, to_lat))
    end = cur.fetchone()
    if not end:
        raise HTTPException(status_code=404, detail="终点附近无路网节点")
    end_vid = end["id"]

    # Dijkstra 最短路径
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
    """, (start_vid, end_vid))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="两点不可达")

    geoms = [shape(json.loads(row["geom"])) for row in rows]
    merged = linemerge(geoms)
    coords = [[c[0], c[1]] for c in merged.coords]  # [lng, lat]
    total_dist = round(rows[-1]["agg_cost"])

    return {"distance": total_dist, "coordinates": coords}

# ---------- 内部辅助函数 ----------
def _get_attraction_coords(attraction_id: str, db):
    """查询景点中心坐标，返回 (lng, lat) 或 None"""
    attr = db.query(Attraction).filter(Attraction.attraction_id == attraction_id).first()
    if not attr or attr.min_longitude is None:
        return None
    lng = (attr.min_longitude + attr.max_longitude) / 2
    lat = (attr.min_latitude + attr.max_latitude) / 2
    return lng, lat

def _find_nearest_vertex(cur, lng, lat):
    """找到离(lng,lat)最近的路网节点ID"""
    cur.execute("""
        SELECT id FROM ways_vertices_pgr
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        LIMIT 1
    """, (lng, lat))
    row = cur.fetchone()
    return row["id"] if row else None

def _dijkstra_path(cur, start_vid, end_vid):
    """返回最短路径的坐标列表 ([[lng,lat], ...]) 和距离(米)，若不可达返回(None,None)"""
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
    """, (start_vid, end_vid))
    rows = cur.fetchall()
    if not rows:
        return None, None

    geoms = [shape(json.loads(row["geom"])) for row in rows]
    merged = linemerge(geoms)
    coords = [[c[0], c[1]] for c in merged.coords]
    total_dist = round(rows[-1]["agg_cost"])
    return coords, total_dist

def _tsp_order(vertex_ids: List[int], cur) -> Optional[List[int]]:
    """
    暴力求解 TSP 最优顺序（适用于顶点数 ≤ 8），返回顶点ID列表（最优顺序）
    原理：计算所有顶点对之间的最短距离，然后枚举全排列找总距离最小的顺序。
    """
    n = len(vertex_ids)
    if n <= 2:
        return vertex_ids  # 无需优化

    # 预计算距离矩阵
    dist = [[0]*n for _ in range(n)]
    for i in range(n):
        for j in range(i+1, n):
            cur.execute("""
                SELECT agg_cost FROM pgr_dijkstraCost(
                    'SELECT id, source, target,
                            ST_Length(geom_gcj02::geography) AS cost,
                            ST_Length(geom_gcj02::geography) AS reverse_cost
                     FROM ways',
                    %s, %s, directed := false
                )
            """, (vertex_ids[i], vertex_ids[j]))
            row = cur.fetchone()
            d = row["agg_cost"] if row else float('inf')
            dist[i][j] = d
            dist[j][i] = d

    best_order = None
    best_cost = float('inf')
    # 固定起点为第一个顶点（因为 TSP 环路通常需要回到起点，但这里我们只求开放路径顺序）
    # 对开放路径，我们可以不加固定起点，直接全排列
    for perm in itertools.permutations(range(n)):
        cost = 0.0
        for k in range(n-1):
            cost += dist[perm[k]][perm[k+1]]
        if cost < best_cost:
            best_cost = cost
            best_order = list(perm)

    return [vertex_ids[i] for i in best_order] if best_order else vertex_ids

def _get_multi_route_sync(ids: str, optimize: bool):
    start_time = time.time()
    logger.info(f"[多段规划] 请求开始, ids={ids}, optimize={optimize}")

    db = SessionLocal()
    try:
        id_list = [x.strip() for x in ids.split(",") if x.strip()]
        if len(id_list) < 2:
            raise HTTPException(status_code=400, detail="至少需要2个景点")

        points = []
        names = []
        for pid in id_list:
            coord = _get_attraction_coords(pid, db)
            if coord is None:
                raise HTTPException(status_code=400, detail=f"景点 {pid} 不存在或无坐标")
            points.append(coord)
            attr = db.query(Attraction).filter(Attraction.attraction_id == pid).first()
            names.append(attr.name if attr else pid)
    finally:
        db.close()

    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        vertex_ids = []
        for (lng, lat) in points:
            vid = _find_nearest_vertex(cur, lng, lat)
            if vid is None:
                raise HTTPException(status_code=404, detail=f"景点附近无路网节点")
            vertex_ids.append(vid)

        if optimize and len(vertex_ids) > 2:
            ordered_vids = _tsp_order(vertex_ids, cur)
            if ordered_vids != vertex_ids:
                vid_to_idx = {v: i for i, v in enumerate(vertex_ids)}
                new_indices = [vid_to_idx[v] for v in ordered_vids]
                points = [points[i] for i in new_indices]
                names = [names[i] for i in new_indices]
                vertex_ids = ordered_vids
    finally:
        pass

    total_dist = 0
    all_coords = []
    for i in range(len(vertex_ids) - 1):
        start_vid = vertex_ids[i]
        end_vid = vertex_ids[i + 1]
        coords, seg_dist = _dijkstra_path(cur, start_vid, end_vid)
        if coords is None:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail=f"景点间不可达: {names[i]} -> {names[i+1]}")
        total_dist += seg_dist
        if i == 0:
            all_coords.extend(coords)
        else:
            all_coords.extend(coords[1:])

    cur.close()
    conn.close()

    total_elapsed = time.time() - start_time
    logger.info(f"[多段规划] 完成，耗时 {total_elapsed:.3f}s, 总距离 {total_dist}m, 顺序 {names}")
    return {
        "distance": total_dist,
        "coordinates": all_coords,
        "order": names,
    }

@router.get("/route/multi", summary="多景点路径规划（支持自动优化顺序）")
async def get_multi_route(
    ids: str = Query(..., description="逗号分隔的景点ID，如 LS-001,LS-003,LS-005"),
    optimize: bool = Query(False, description="是否自动优化访问顺序（TSP）")
):
    # 异步包装，避免阻塞事件循环
    return await asyncio.to_thread(_get_multi_route_sync, ids, optimize)
