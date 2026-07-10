from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app import models
from app.models import TaskPlan, TaskStep
from app.services.indexer import get_collection    # ← 修改：导入惰性函数
from app.config import PROJECT_ROOT
import os
from pathlib import Path

# ---------- 文件系统工具 ----------
def list_project_structure(root_path: str = None, max_depth: int = None) -> str:
    if root_path is None:
        root_path = "."
    clean = root_path.lstrip("/").replace("/", os.sep)
    root = (PROJECT_ROOT / clean).resolve()
    if not str(root).startswith(str(PROJECT_ROOT.resolve())):
        return "无权限访问该目录"
    lines = []
    def walk(path, prefix="", depth=0):
        if max_depth is not None and depth > max_depth:
            return
        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return
        for item in items:
            if item.name.startswith('.') and item.name != '.env':
                continue
            if item.is_dir():
                lines.append(f"{prefix}📁 {item.name}/")
                walk(item, prefix + "  ", depth + 1)
            else:
                size = item.stat().st_size
                lines.append(f"{prefix}📄 {item.name} ({size} B)")
    walk(root)
    return "\n".join(lines) if lines else "目录为空或无法访问"

def read_file_content(file_path: str, max_lines: int = 100) -> str:
    root = PROJECT_ROOT.resolve()
    target = Path(file_path)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    if not str(target).startswith(str(root)):
        return "拒绝访问：只能查看项目内的文件"
    if not target.is_file():
        return f"文件不存在：{file_path}"
    try:
        with open(target, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            lines = all_lines[:max_lines]
            if not lines:
                return f"=== {target.name} ===\n(空文件)"
        return f"=== {target.name} (前{len(lines)}行) ===\n" + "".join(lines)
    except Exception as e:
        return f"读取失败：{str(e)}"

# ---------- 游客统计工具 ----------
def query_visitor_gender_stats(db: Session) -> str:
    res = db.query(
        models.TouristVisit.gender,
        func.count(models.TouristVisit.id)
    ).group_by(models.TouristVisit.gender).all()
    data = [{"name": g, "count": c} for g, c in res]
    return f"性别分布: {data}"

def query_visitor_age_stats(db: Session) -> str:
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
        data.append({"name": name, "count": count})
    return f"年龄分布: {data}"

def query_top_attractions(db: Session, limit: int = 10) -> str:
    res = db.query(
        models.TouristVisit.attraction_name,
        func.count(models.TouristVisit.id).label('count')
    ).group_by(models.TouristVisit.attraction_name).order_by(
        desc('count')
    ).limit(limit).all()
    data = [{"name": name, "count": c} for name, c in res]
    return f"热门景点: {data}"

def query_monthly_visitors(db: Session) -> str:
    res = db.query(
        func.to_char(models.TouristVisit.visit_date, 'YYYY-MM').label('month'),
        func.count(models.TouristVisit.id)
    ).group_by('month').order_by('month').all()
    data = [{"month": m, "count": c} for m, c in res]
    return f"月度客流: {data}"

def query_spending_avg(db: Session) -> str:
    avg = db.query(
        func.avg(models.TouristVisit.ticket_cost).label('ticket'),
        func.avg(models.TouristVisit.food_cost).label('food'),
        func.avg(models.TouristVisit.shopping_cost).label('shopping'),
        func.avg(models.TouristVisit.transport_cost).label('transport'),
        func.avg(models.TouristVisit.entertainment_cost).label('entertainment')
    ).one()
    return f"平均消费: 门票{avg.ticket or 0:.2f}, 餐饮{avg.food or 0:.2f}, 购物{avg.shopping or 0:.2f}, 交通{avg.transport or 0:.2f}, 娱乐{avg.entertainment or 0:.2f}"

def query_satisfaction_stats(db: Session) -> str:
    res = db.query(
        models.TouristVisit.satisfaction,
        func.count(models.TouristVisit.id)
    ).group_by(models.TouristVisit.satisfaction).order_by(
        models.TouristVisit.satisfaction
    ).all()
    data = [{"score": s, "count": c} for s, c in res]
    return f"满意度分布: {data}"

# ---------- 知识库工具 ----------
def query_knowledge_doc_list(db: Session) -> str:
    docs = db.query(models.KnowledgeDoc).order_by(models.KnowledgeDoc.created_at.desc()).all()
    if not docs:
        return "知识库为空"
    col = get_collection()       # ← 惰性获取 collection
    info = []
    for doc in docs:
        res = col.get(where={"doc_id": doc.id})
        chunk_count = len(res['ids']) if res and res['ids'] else 0
        info.append(f"{doc.filename} (ID:{doc.id}, 分块:{chunk_count})")
    return "知识库文档:\n" + "\n".join(info)

def query_knowledge_stats(db: Session) -> str:
    docs = db.query(models.KnowledgeDoc).all()
    total_chunks = 0
    details = []
    col = get_collection()       # ← 惰性获取
    for doc in docs:
        res = col.get(where={"doc_id": doc.id})
        cnt = len(res['ids']) if res and res['ids'] else 0
        total_chunks += cnt
        details.append(f"  {doc.filename}: {cnt} chunks")
    return f"知识库总文档数: {len(docs)}, 总块数: {total_chunks}\n" + "\n".join(details)

def get_system_health(db: Session) -> str:
    try:
        db.query(models.User).first()
        db_status = "正常"
    except:
        db_status = "异常"
    try:
        col = get_collection()   # ← 惰性获取
        col_count = col.count()
        chroma_status = f"正常 ({col_count} 条向量)"
    except Exception as e:
        chroma_status = f"异常 ({e})"
    return f"数据库: {db_status}\n向量库: {chroma_status}"

# ---------- 项目结构描述管理 ----------
def get_annotated_project_structure(db: Session, root_path: str = "/backend", max_depth: int = None) -> str:
    nodes = db.query(models.ProjectNode).order_by(models.ProjectNode.path).all()
    if not nodes:
        return "数据库中暂无项目结构描述，请先运行导入脚本。"
    lines = []
    for n in nodes:
        if not n.path.startswith(root_path):
            continue
        if max_depth is not None:
            relative = n.path[len(root_path):].lstrip("/")
            depth = relative.count("/") + 1 if relative else 0
            if depth > max_depth:
                continue
        else:
            depth = n.path.count("/") - root_path.count("/")
        indent = "  " * depth
        icon = "📁" if n.node_type == "directory" else "📄"
        desc = f"  # {n.description}" if n.description else ""
        lines.append(f"{indent}{icon} {n.name}{desc}")
    return "\n".join(lines)

def update_file_description(db: Session, file_path: str, description: str) -> str:
    node = db.query(models.ProjectNode).filter_by(path=file_path).first()
    if not node:
        return f"路径不存在：{file_path}"
    node.description = description
    db.commit()
    return f"已更新描述：{file_path} -> {description}"

def search_project_nodes(db: Session, keyword: str) -> str:
    nodes = db.query(models.ProjectNode).filter(
        (models.ProjectNode.name.ilike(f"%{keyword}%")) |
        (models.ProjectNode.description.ilike(f"%{keyword}%"))
    ).all()
    if not nodes:
        return f"未找到与“{keyword}”相关的文件或文件夹"
    lines = []
    for n in nodes:
        lines.append(f"{n.path} ({n.node_type}) - {n.description}")
    return "\n".join(lines)

# ---------- 任务计划工具（create_plan 等已定义，未改动，仍使用原导入） ----------
def create_plan(db: Session, title: str, steps: list[str], owner: str = "admin") -> str:
    plan = TaskPlan(title=title, owner=owner)
    db.add(plan)
    db.commit()
    for i, step_text in enumerate(steps):
        step = TaskStep(plan_id=plan.id, step_order=i+1, content=step_text)
        db.add(step)
    db.commit()
    return f"计划已创建（ID:{plan.id}），共 {len(steps)} 步。"

def get_current_plan(db: Session, owner: str = "admin") -> str:
    plan = db.query(TaskPlan).filter_by(status="in_progress", owner=owner)\
              .order_by(TaskPlan.created_at.desc()).first()
    if not plan:
        return "当前没有进行中的任务计划。"
    steps = db.query(TaskStep).filter_by(plan_id=plan.id).order_by(TaskStep.step_order).all()
    lines = [f"📋 {plan.title} (ID:{plan.id})"]
    for s in steps:
        status_icon = {"pending": "⏳", "in_progress": "▶️", "completed": "", "failed": "❌"}.get(s.status, "❓")
        lines.append(f"  {status_icon} 步骤{s.step_order}: {s.content}")
    return "\n".join(lines)

def update_step_status(db: Session, plan_id: int, step_order: int, status: str, result: str = "") -> str:
    step = db.query(TaskStep).filter_by(plan_id=plan_id, step_order=step_order).first()
    if not step:
        return "步骤不存在。"
    step.status = status
    if result:
        step.result = result
    db.commit()
    all_steps = db.query(TaskStep).filter_by(plan_id=plan_id).all()
    if all(s.status == "completed" for s in all_steps):
        plan = db.query(TaskPlan).get(plan_id)
        plan.status = "completed"
        db.commit()
        return f"步骤 {step_order} 更新完成，🎉 所有步骤已完成，计划已标记为完成。"
    return f"步骤 {step_order} 状态更新为 {status}。"

def create_plan_for_tourist(db: Session, tourist_id: int, title: str, steps: list[str]) -> str:
    return create_plan(db, title, steps, owner=f"tourist_{tourist_id}")