# app/services/recommender.py
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models

logger = logging.getLogger(__name__)

def get_personalized_recommendation_data(db: Session, tourist_id: int) -> dict:
    """
    基于用户游览记录生成推荐数据，包含消费细分统计
    """
    tourist = db.query(models.Tourist).get(tourist_id)
    if not tourist or not tourist.display_id:
        return {"success": False, "reason": "您还没有绑定游览记录，请先在景区游玩后使用推荐功能。"}

    display_id = tourist.display_id

    # 1. 用户已游览景点及类型（去重）
    user_visits = db.query(models.TouristVisit.attraction_name,
                           models.TouristVisit.attraction_type)\
                    .filter(models.TouristVisit.tourist_id == display_id,
                            models.TouristVisit.attraction_type.isnot(None))\
                    .distinct().all()
    if not user_visits:
        return {"success": False, "reason": "您尚未游览过任何有类型记录的景点，无法进行个性化推荐。"}

    # 2. 统计偏好类型（前3）
    type_counter = {}
    for _, atype in user_visits:
        type_counter[atype] = type_counter.get(atype, 0) + 1
    top_types = sorted(type_counter.items(), key=lambda x: x[1], reverse=True)[:3]
    favorite_types = [t[0] for t in top_types]

    # 3. 未去过的同类型景点
    visited_names = {name for name, _ in user_visits}
    candidates = db.query(models.Attraction).filter(
        models.Attraction.attraction_type.in_(favorite_types)
    ).all()
    recommended = [att for att in candidates if att.name not in visited_names]

    if not recommended:
        all_att = db.query(models.Attraction).all()
        recommended = [att for att in all_att if att.name not in visited_names]

    def sort_key(att):
        try:
            return favorite_types.index(att.attraction_type)
        except ValueError:
            return 99
    recommended.sort(key=sort_key)
    recommended = recommended[:5]

    # 4. 同类型其他游客消费细分统计（排除当前用户）
    type_insights = {}
    for atype in favorite_types:
        stats = db.query(
            func.avg(models.TouristVisit.ticket_cost).label('avg_ticket'),
            func.avg(models.TouristVisit.food_cost).label('avg_food'),
            func.avg(models.TouristVisit.shopping_cost).label('avg_shopping'),
            func.avg(models.TouristVisit.transport_cost).label('avg_transport'),
            func.avg(models.TouristVisit.entertainment_cost).label('avg_entertainment'),
            func.avg(models.TouristVisit.total_cost).label('avg_total'),
            func.avg(models.TouristVisit.satisfaction).label('avg_satisfaction'),
            func.count(models.TouristVisit.id).label('visit_count')
        ).filter(
            models.TouristVisit.attraction_type == atype,
            models.TouristVisit.tourist_id != display_id,
            func.coalesce(models.TouristVisit.total_cost,
                          models.TouristVisit.ticket_cost,
                          models.TouristVisit.food_cost).isnot(None)
        ).first()

        if stats and stats.visit_count:
            type_insights[atype] = {
                "avg_ticket": round(stats.avg_ticket, 2) if stats.avg_ticket else None,
                "avg_food": round(stats.avg_food, 2) if stats.avg_food else None,
                "avg_shopping": round(stats.avg_shopping, 2) if stats.avg_shopping else None,
                "avg_transport": round(stats.avg_transport, 2) if stats.avg_transport else None,
                "avg_entertainment": round(stats.avg_entertainment, 2) if stats.avg_entertainment else None,
                "avg_total": round(stats.avg_total, 2) if stats.avg_total else None,
                "avg_satisfaction": round(stats.avg_satisfaction, 1) if stats.avg_satisfaction else None,
                "visit_count": stats.visit_count
            }

    return {
        "success": True,
        "favorite_types": favorite_types,
        "recommended_attractions": [
            {
                "name": att.name,
                "type": att.attraction_type,
                "highlights": att.highlights or "暂无简介"
            }
            for att in recommended
        ],
        "type_insights": type_insights
    }